import asyncio, json, os, re, secrets, shutil, sys, time
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
DATA = ROOT / 'downloads'
DATA.mkdir(exist_ok=True)
app = FastAPI(docs_url=None, redoc_url=None)
slots = asyncio.Semaphore(2)
jobs = {}
rates = {}
MAX_BYTES = 500 * 1024 * 1024
TTL = 3600
class Input(BaseModel):
    url: str = Field(max_length=2048)
class Download(Input):
    kind: str
    quality: str

def validate(url):
    try:
        u = urlsplit(url)
        host = (u.hostname or '').lower()
        roots = ('youtube.com', 'youtu.be', 'facebook.com', 'fb.watch', 'instagram.com')
        if u.scheme != 'https' or u.username or u.password or u.port not in (None,443) or not any(host == r or host.endswith('.'+r) for r in roots):
            raise ValueError()
        return url
    except ValueError:
        raise HTTPException(400, 'YouTube, Facebook эсвэл Instagram-ийн HTTPS линк оруулна уу.')

def cleanup():
    now = time.time()
    for key, job in list(jobs.items()):
        if now-job['created'] > TTL and job['status'] != 'working':
            shutil.rmtree(DATA/key, ignore_errors=True)
            jobs.pop(key, None)
    for key, values in list(rates.items()):
        rates[key] = [v for v in values if now-v < 60]
        if not rates[key]: rates.pop(key,None)

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response

def limit(request):
    cleanup()
    ip = request.client.host if request.client else 'unknown'
    values = rates.setdefault(ip, [])
    if len(values) >= 12: raise HTTPException(429, 'Нэг минут хүлээгээд дахин оролдоно уу.')
    values.append(time.time())

def command(url):
    return [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist', '--no-colors', '--socket-timeout', '20', '--retries', '2', '--extractor-retries', '2', '--use-extractors', 'youtube.*,facebook.*,instagram.*', url]

def extractor_error(detail):
    lower = detail.lower()
    if 'not a bot' in lower or 'confirm you’re not' in lower or "confirm you're not" in lower:
        return ('platform_verification', 'YouTube энэ серверээс хүн мөн эсэхийг баталгаажуулахыг шаардлаа. Энэ нь бичлэг нууц гэсэн үг биш. Одоогоор энэ серверээр YouTube татах боломжгүй байна.')
    if 'private video' in lower or 'this video is private' in lower:
        return ('private_video', 'Энэ бичлэг нийтэд нээлттэй биш байна.')
    if 'sign in' in lower or 'login' in lower:
        return ('login_required', 'Платформ энэ бичлэгт нэвтрэхийг шаардаж байна.')
    if 'requested format is not available' in lower:
        return ('format_unavailable', 'Сонгосон формат олдсонгүй. Өөр чанар эсвэл MP3 сонгоно уу.')
    if 'unsupported url' in lower:
        return ('unsupported_url', 'Энэ линкийг дэмжихгүй байна. Нэг бичлэгийн линк оруулна уу.')
    if 'video unavailable' in lower or 'not available' in lower:
        return ('unavailable', 'Платформ энэ бичлэгийг серверт өгөх боломжгүй байна.')
    return ('extractor_failed', 'Бичлэгийн мэдээлэл авахад алдаа гарлаа. Серверийн алдааг бүртгэлд хадгаллаа.')

def log_extractor_error(detail):
    code, message = extractor_error(detail)
    # Avoid recording signed URLs or query credentials in operational logs.
    safe_detail = re.sub(r'https?://[^\s]+', '[URL]', detail)
    print(json.dumps({'event':'extractor_error', 'code':code, 'detail':safe_detail[-2400:]}, ensure_ascii=False), flush=True)
    return message

async def run(args, timeout):
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        proc.kill()
        await proc.communicate()
        raise
    if proc.returncode:
        detail = err.decode(errors='replace')[-1800:]
        raise ValueError(log_extractor_error(detail))
    return out

@app.get('/')
async def index(): return FileResponse(ROOT/'static/index.html')
@app.get('/health')
async def health(): return {'ok': True}

@app.post('/api/info')
async def info(body: Input, request: Request):
    limit(request)
    url = validate(body.url)
    if slots.locked(): raise HTTPException(503, 'Сервер завгүй байна. Түр хүлээгээд дахин оролдоно уу.')
    try:
        async with slots:
            raw = await run(command(url)+['--dump-single-json', '--skip-download'], 90)
        data = json.loads(raw)
        if data.get('is_live') or data.get('_type') in ('playlist','multi_video'):
            raise ValueError('Дууссан нэг бичлэгийн линк оруулна уу.')
        formats = data.get('formats') or []
        heights = sorted({int(f['height']) for f in formats if f.get('height') and f.get('vcodec') != 'none' and f.get('ext') == 'mp4'}, reverse=True)
        return {'title':data.get('title','Бичлэг'), 'duration':data.get('duration'), 'heights':heights}
    except asyncio.TimeoutError: raise HTTPException(504,'Шалгах хугацаа дууслаа. Дахин оролдоно уу.')
    except (ValueError, json.JSONDecodeError) as e: raise HTTPException(400,str(e))

def media_args(kind, quality):
    if kind == 'mp3':
        return ['-f', 'bestaudio/best', '-x', '--audio-format', 'mp3', '--audio-quality', quality+'K']
    h = int(quality)
    return ['-f', f'bv[ext=mp4][height<={h}]+ba[ext=m4a]/b[ext=mp4][height<={h}]',
            '-S', 'res,vcodec:h264,acodec:aac', '--merge-output-format', 'mp4']

async def download(key, body):
    job = jobs[key]
    folder = DATA/key
    folder.mkdir()
    try:
        async with slots:
            args = command(body.url)+['--newline','--progress','--progress-template','download:PROGRESS:%(progress._percent_str)s','--max-filesize',str(MAX_BYTES),'--match-filter','!is_live & duration <= 7200','--restrict-filenames','-o',str(folder/'%(title).100s.%(ext)s')]
            args += media_args(body.kind, body.quality)
            proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            async def consume():
                async for line in proc.stdout:
                    text = line.decode(errors='replace').strip()
                    if 'PROGRESS:' in text:
                        match = re.search(r'PROGRESS:\s*([\d.]+)%',text)
                        if match: job['progress'] = min(99,float(match[1]))
                    if '[Merger]' in text or '[ExtractAudio]' in text or '[VideoConvertor]' in text:
                        job['message'] = 'Файл боловсруулж байна…'
                    if text.startswith('ERROR:'): job['failure_message'] = log_extractor_error(text)
                    size = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
                    if size > MAX_BYTES * 3:
                        raise ValueError('Бичлэгийн хэмжээ хэтэрлээ.')
                await proc.wait()
            try: await asyncio.wait_for(consume(),900)
            finally:
                if proc.returncode is None:
                    proc.kill()
                    await proc.wait()
            files = list(folder.glob('*.'+body.kind))
            if proc.returncode or len(files) != 1:
                raise ValueError(job.pop('failure_message', 'Татаж чадсангүй. Бичлэг хэт том эсвэл сонгосон формат байхгүй байж болно.'))
            if files[0].stat().st_size > MAX_BYTES: raise ValueError('Файл 500 MB-аас том байна.')
            job.update(status='done',progress=100,file=files[0], message='Бэлэн боллоо')
    except Exception as e:
        job.update(status='error', message='Хугацаа дууслаа.' if isinstance(e, asyncio.TimeoutError) else str(e))
        shutil.rmtree(folder,ignore_errors=True)
    finally: job['created'] = time.time()

@app.post('/api/download')
async def start(body: Download, request: Request):
    limit(request)
    validate(body.url)
    if body.kind not in ('mp3','mp4'): raise HTTPException(400,'Формат буруу байна.')
    if (body.kind == 'mp3' and body.quality not in ('128','192','320')) or (body.kind == 'mp4' and (not body.quality.isdigit() or not 1 <= int(body.quality) <= 8640)):
        raise HTTPException(400,'Чанарын сонголт буруу байна.')
    if sum(j['status']=='working' for j in jobs.values()) >= 2: raise HTTPException(503,'Хоёр таталт явагдаж байна. Түр хүлээнэ үү.')
    key = secrets.token_urlsafe(24)
    jobs[key] = {'status':'working','progress':0,'message':'Бичлэг татаж байна…','created':time.time()}
    asyncio.create_task(download(key,body))
    return {'id':key}

@app.get('/api/jobs/{key}')
async def status(key: str):
    cleanup()
    job = jobs.get(key)
    if not job: raise HTTPException(404,'Файлын хугацаа дууссан байна.')
    return {k:v for k,v in job.items() if k not in ('file','created','failure_message')}

@app.get('/api/files/{key}')
async def file(key: str):
    cleanup()
    job = jobs.get(key)
    if not job or job['status'] != 'done': raise HTTPException(404,'Файл олдсонгүй.')
    return FileResponse(job['file'],filename=job['file'].name,media_type='audio/mpeg' if job['file'].suffix=='.mp3' else 'video/mp4')
