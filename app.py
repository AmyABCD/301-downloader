"""
301 Downloader (YouTube, Facebook, Instagram, TikTok & more)
Backend powered by FastAPI, yt-dlp, and FFmpeg.
"""

import os
import sys
import time
import uuid
import re
import json
import asyncio
import threading
import shutil
import urllib.parse
import socket
from typing import Optional, Dict, Any, List

# Ensure utf-8 stdout on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import yt_dlp

# Resolve ffmpeg executable location
try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="301 Downloader", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store download jobs in memory
# job_id -> dict
JOBS: Dict[str, Dict[str, Any]] = {}

# Public tunnel tracking
GLOBAL_PUBLIC_URL: List[Optional[str]] = [None]
TUNNEL_PROCESS: List[Optional[Any]] = [None]

class AnalyzeRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_type: str  # "video" or "audio"
    quality: str      # e.g. "1080", "720", "480", "360", "best", or for audio "320", "256", "192", "128"


def launch_cloudflared_tunnel(port: int = 8000) -> Optional[str]:
    """Launches Cloudflare Quick Tunnel to expose the webapp publicly on the internet."""
    import subprocess
    if GLOBAL_PUBLIC_URL[0]:
        return GLOBAL_PUBLIC_URL[0]

    try:
        cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        TUNNEL_PROCESS[0] = proc

        start_time = time.time()
        # Scan stderr for trycloudflare.com link
        while time.time() - start_time < 20:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            if "trycloudflare.com" in line:
                m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if m:
                    url = m.group(0)
                    GLOBAL_PUBLIC_URL[0] = url
                    # Copy to Windows clipboard
                    try:
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command", f'Set-Clipboard -Value "{url}"'],
                            capture_output=True,
                            timeout=2
                        )
                    except Exception:
                        pass
                    return url
    except Exception as e:
        print("Cloudflare tunnel launch error:", e)
    return None


def get_local_ip() -> str:
    """Detects primary local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.get("/api/network-info")
async def get_network_info():
    """Returns local, LAN, and public URLs."""
    ip = get_local_ip()
    port = int(os.environ.get("PORT", 8000))
    return {
        "local_url": f"http://localhost:{port}",
        "network_url": f"http://{ip}:{port}",
        "public_url": GLOBAL_PUBLIC_URL[0],
        "ip": ip,
        "port": port
    }


@app.post("/api/enable-public-tunnel")
async def enable_public_tunnel():
    """Dynamically activates Cloudflare Tunnel so anyone on the internet can access."""
    if GLOBAL_PUBLIC_URL[0]:
        return {"status": "ok", "public_url": GLOBAL_PUBLIC_URL[0], "message": "Нийтийн линк аль хэдийн идэвхтэй байна"}

    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(None, launch_cloudflared_tunnel, 8000)
    if url:
        return {"status": "ok", "public_url": url, "message": "Нийтийн линк амжилттай үүслээ"}
    raise HTTPException(status_code=500, detail="Cloudflare Tunnel асаахад алдаа гарлаа")


def sanitize_filename(filename: str) -> str:
    """Removes or replaces invalid Windows filename characters."""
    # Replace illegal Windows characters: < > : " / \ | ? *
    clean = re.sub(r'[<>:"/\\|?*]', '_', filename)
    clean = clean.strip('. ')
    return clean if clean else "download"


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "--:--"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_size(bytes_val: Optional[int]) -> str:
    if not bytes_val or bytes_val <= 0:
        return "Хэмжээ тодорхойгүй"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} TB"


def detect_platform(url: str, extractor_key: str = "") -> Dict[str, str]:
    u = url.lower()
    ext = extractor_key.lower()
    if "youtube" in u or "youtu.be" in u or "youtube" in ext:
        return {"name": "YouTube", "icon": "youtube", "color": "text-red-500", "bg": "bg-red-500/10", "border": "border-red-500/30"}
    elif "facebook" in u or "fb.watch" in u or "fb.com" in u or "facebook" in ext:
        return {"name": "Facebook", "icon": "facebook", "color": "text-blue-500", "bg": "bg-blue-500/10", "border": "border-blue-500/30"}
    elif "instagram" in u or "instagr.am" in u or "instagram" in ext:
        return {"name": "Instagram", "icon": "instagram", "color": "text-pink-500", "bg": "bg-pink-500/10", "border": "border-pink-500/30"}
    elif "tiktok" in u or "tiktok" in ext:
        return {"name": "TikTok", "icon": "tiktok", "color": "text-emerald-400", "bg": "bg-emerald-400/10", "border": "border-emerald-400/30"}
    elif "twitter" in u or "x.com" in u or "twitter" in ext:
        return {"name": "X (Twitter)", "icon": "x-twitter", "color": "text-sky-400", "bg": "bg-sky-400/10", "border": "border-sky-400/30"}
    else:
        return {"name": extractor_key or "Web Video", "icon": "globe", "color": "text-indigo-400", "bg": "bg-indigo-400/10", "border": "border-indigo-400/30"}


def clean_media_url(url: str) -> str:
    """Strips playlist parameters (list, index, start_radio) to target single video cleanly."""
    u = url.strip()
    if "youtube.com/watch" in u or "youtu.be/" in u:
        if "watch?v=" in u:
            parsed = urllib.parse.urlparse(u)
            params = urllib.parse.parse_qs(parsed.query)
            v = params.get("v")
            if v:
                return f"https://www.youtube.com/watch?v={v[0]}"
        elif "youtu.be/" in u:
            clean_id = u.split("youtu.be/")[1].split("?")[0].split("&")[0]
            return f"https://www.youtube.com/watch?v={clean_id}"
    return u


def get_ydl_base_opts() -> Dict[str, Any]:
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'no_color': True,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,mn;q=0.8',
        }
    }
    if FFMPEG_EXE:
        opts['ffmpeg_location'] = FFMPEG_EXE
    return opts


@app.post("/api/analyze")
async def analyze_url(req: AnalyzeRequest):
    url = clean_media_url(req.url)
    if not url:
        raise HTTPException(status_code=400, detail="Линк оруулна уу")

    # Run extraction in thread to avoid blocking asyncio event loop
    loop = asyncio.get_event_loop()
    try:
        def extract():
            opts = get_ydl_base_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, extract)
    except Exception as e:
        err_msg = str(e)
        if "Private video" in err_msg or "login" in err_msg.lower():
            detail = "Энэ бичлэг нь хувийн (Private) эсвэл зөвхөн нэвтэрсэн хэрэглэгчдэд нээлттэй байна."
        elif "regex" in err_msg.lower() or "unsupported" in err_msg.lower():
            detail = "Энэ линк хүчингүй эсвэл дэмжигдээгүй сайт байна."
        else:
            detail = f"Мэдээлэл авахад алдаа гарлаа: {err_msg[:120]}"
        raise HTTPException(status_code=400, detail=detail)

    if not info:
        raise HTTPException(status_code=404, detail="Бичлэгийн мэдээлэл олдсонгүй")

    title = info.get("title") or "Нэргүй бичлэг"
    duration = info.get("duration")
    thumbnail = info.get("thumbnail")
    uploader = info.get("uploader") or info.get("channel") or info.get("creator") or "Тодорхойгүй"
    extractor = info.get("extractor_key") or info.get("extractor") or ""
    platform = detect_platform(url, extractor)

    # Process formats
    formats = info.get("formats", [])
    raw_heights = set()
    best_audio_size = 0
    for f in formats:
        if f.get("acodec") != "none" and f.get("vcodec") == "none":
            s = f.get("filesize") or f.get("filesize_approx") or 0
            if s > best_audio_size:
                best_audio_size = s
        h = f.get("height")
        if h and h > 0 and (f.get("vcodec") != "none"):
            raw_heights.add(h)

    sorted_heights = sorted(list(raw_heights), reverse=True)

    # Build video resolution choices
    video_options = []
    
    # Always include Best Available first
    video_options.append({
        "id": "best",
        "label": "Хамгийн өндөр чанар (Best Auto)",
        "resolution": "Шилдэг",
        "badge": "Зөвлөмж",
        "is_recommended": True,
        "filesize_str": "Автомат тохируулга"
    })

    # Standard display mappings
    labels_map = {
        2160: ("4K Ultra HD", "2160p"),
        1440: ("2K Quad HD", "1440p"),
        1080: ("Full HD", "1080p"),
        720: ("HD", "720p"),
        480: ("SD Стандарт", "480p"),
        360: ("Бага чанар", "360p"),
        240: ("Хэмнэлттэй", "240p"),
        144: ("Хамгийн бага", "144p"),
    }

    # Group or select notable heights
    for h in sorted_heights:
        # Find format with this height to estimate size
        matching = [f for f in formats if f.get("height") == h]
        size_est = 0
        if matching:
            best_match = matching[-1]
            size_est = best_match.get("filesize") or best_match.get("filesize_approx") or 0
            if best_match.get("vcodec") != "none" and best_match.get("acodec") == "none":
                # Video-only stream, add audio size approximation
                size_est += best_audio_size

        name, tag = labels_map.get(h, (f"{h}p Видео", f"{h}p"))
        video_options.append({
            "id": str(h),
            "label": f"{name} ({tag})",
            "resolution": f"{h}p",
            "badge": "HD" if h >= 720 else "SD",
            "is_recommended": False,
            "filesize_str": format_size(size_est) if size_est > 0 else "Боломжтой"
        })

    # Audio quality choices (MP3)
    audio_duration_min = (duration or 180) / 60
    audio_options = [
        {
            "id": "320",
            "label": "320 kbps - Студийн дээд чанар",
            "badge": "HQ",
            "filesize_str": f"~{format_size(int(320 * 1024 / 8 * 60 * audio_duration_min))}"
        },
        {
            "id": "256",
            "label": "256 kbps - Маш өндөр чанар",
            "badge": "Сайн",
            "filesize_str": f"~{format_size(int(256 * 1024 / 8 * 60 * audio_duration_min))}"
        },
        {
            "id": "192",
            "label": "192 kbps - Стандарт чанар",
            "badge": "Зөвлөмж",
            "is_recommended": True,
            "filesize_str": f"~{format_size(int(192 * 1024 / 8 * 60 * audio_duration_min))}"
        },
        {
            "id": "128",
            "label": "128 kbps - Хэмнэлттэй чанар",
            "badge": "Жижиг",
            "filesize_str": f"~{format_size(int(128 * 1024 / 8 * 60 * audio_duration_min))}"
        }
    ]

    return {
        "title": title,
        "duration": duration,
        "duration_str": format_duration(duration),
        "thumbnail": thumbnail,
        "uploader": uploader,
        "platform": platform,
        "video_options": video_options,
        "audio_options": audio_options,
    }


def background_downloader(job_id: str, url: str, format_type: str, quality: str):
    job = JOBS.get(job_id)
    if not job:
        return

    job["status"] = "downloading"
    job["stage"] = "Файлыг татаж эхэлж байна..."

    def progress_hook(d):
        if d["status"] == "downloading":
            job["status"] = "downloading"
            job["stage"] = "Файлыг серверт татаж байна..."
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            if total > 0:
                job["percent"] = round((downloaded / total) * 100, 1)
                job["total_bytes"] = total
                job["downloaded_bytes"] = downloaded
            else:
                pct_str = d.get("_percent_str", "").replace("%", "").strip()
                try:
                    job["percent"] = float(pct_str)
                except Exception:
                    pass

            job["speed"] = d.get("_speed_str", "").strip() or "Татаж байна..."
            job["eta"] = d.get("_eta_str", "").strip() or "--"
            job["updated_at"] = time.time()

        elif d["status"] == "finished":
            job["stage"] = "Татаж дууслаа, хөрвүүлж байна..."
            job["percent"] = 99.0

    def postprocessor_hook(d):
        status = d.get("status")
        pp = d.get("postprocessor", "")
        if status == "started":
            job["status"] = "processing"
            if "ExtractAudio" in pp:
                job["stage"] = "MP3 файл руу хөрвүүлж байна (FFmpeg)..."
            elif "Merger" in pp:
                job["stage"] = "Видео болон дууг нэгтгэж байна (FFmpeg)..."
            else:
                job["stage"] = "Боловсруулж байна..."
        elif status == "finished":
            job["stage"] = "Боловсруулж дууслаа..."

    outtmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}_%(title).70B.%(ext)s")

    ydl_opts: Dict[str, Any] = {
        'outtmpl': outtmpl,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [postprocessor_hook],
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'windowsfilenames': True,
        'noplaylist': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    if FFMPEG_EXE:
        ydl_opts['ffmpeg_location'] = FFMPEG_EXE

    if format_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality if quality in ["128", "192", "256", "320"] else "192",
        }]
    else:
        # Video format logic
        if quality == "best" or not quality.isdigit():
            ydl_opts['format'] = 'bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/best'
        else:
            h = int(quality)
            ydl_opts['format'] = f'bv*[height<={h}][ext=mp4]+ba[ext=m4a]/bv*[height<={h}]+ba/b[height<={h}][ext=mp4]/b[height<={h}]/best'
        
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            job["video_title"] = info.get("title") or "Файл"
            job["thumbnail"] = info.get("thumbnail")

        # Find the final generated file
        final_ext = "mp3" if format_type == "audio" else "mp4"
        matched_files = [
            f for f in os.listdir(DOWNLOAD_DIR)
            if f.startswith(job_id) and f.endswith(f".{final_ext}")
        ]

        if not matched_files:
            # Fallback search for any file starting with job_id
            matched_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(job_id)]

        if not matched_files:
            raise Exception("Файл үүсгэгдсэнгүй")

        actual_filename = matched_files[0]
        filepath = os.path.join(DOWNLOAD_DIR, actual_filename)
        filesize = os.path.getsize(filepath)

        # Human friendly public download name
        raw_title = sanitize_filename(job.get("video_title") or "download")
        public_name = f"{raw_title}.{final_ext}"

        job["status"] = "completed"
        job["percent"] = 100.0
        job["stage"] = "Амжилттай татагдлаа!"
        job["filename"] = actual_filename
        job["public_name"] = public_name
        job["filesize"] = filesize
        job["filesize_str"] = format_size(filesize)
        job["download_url"] = f"/api/file/{urllib.parse.quote(actual_filename)}?name={urllib.parse.quote(public_name)}"
        job["updated_at"] = time.time()

    except Exception as e:
        job["status"] = "error"
        job["stage"] = "Алдаа гарлаа"
        job["error_message"] = str(e)
        job["updated_at"] = time.time()


@app.post("/api/download")
async def start_download(req: DownloadRequest):
    url = clean_media_url(req.url)
    if not url:
        raise HTTPException(status_code=400, detail="Линк оруулна уу")

    job_id = str(uuid.uuid4())[:10]
    JOBS[job_id] = {
        "id": job_id,
        "url": url,
        "format_type": req.format_type,
        "quality": req.quality,
        "status": "queued",
        "stage": "Дараалалд орлоо...",
        "percent": 0.0,
        "speed": "--",
        "eta": "--",
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "filename": None,
        "public_name": None,
        "filesize": 0,
        "filesize_str": "",
        "download_url": None,
        "error_message": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }

    thread = threading.Thread(
        target=background_downloader,
        args=(job_id, url, req.format_type, req.quality),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ажил олдсонгүй")
    return job


@app.get("/api/stream/{job_id}")
async def stream_job_progress(job_id: str):
    """Server-Sent Events for real-time progress updates without client polling lag."""
    async def event_generator():
        while True:
            job = JOBS.get(job_id)
            if not job:
                yield "data: {\"status\": \"not_found\"}\n\n"
                break

            data = json.dumps(job)
            yield f"data: {data}\n\n"

            if job["status"] in ("completed", "error"):
                break

            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/file/{filename}")
async def download_file(filename: str, name: Optional[str] = None):
    # Security check: prevent directory traversal
    clean_name = os.path.basename(filename)
    filepath = os.path.join(DOWNLOAD_DIR, clean_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Файл олдсонгүй")

    download_filename = name or clean_name
    ext = os.path.splitext(filepath)[1].lower()
    media_type = "video/mp4" if ext == ".mp4" else "audio/mpeg" if ext == ".mp3" else "application/octet-stream"

    return FileResponse(
        path=filepath,
        filename=download_filename,
        media_type=media_type
    )


@app.get("/api/history")
async def get_history():
    """Returns list of downloaded files in the folder."""
    files = []
    if os.path.exists(DOWNLOAD_DIR):
        for fname in os.listdir(DOWNLOAD_DIR):
            fpath = os.path.join(DOWNLOAD_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                ext = os.path.splitext(fname)[1].lower()
                clean_display = fname
                # Remove job id prefix if present (e.g. "a1b2c3d4e5_Title.mp4")
                if "_" in fname and len(fname.split("_", 1)[0]) == 10:
                    clean_display = fname.split("_", 1)[1]

                files.append({
                    "filename": fname,
                    "display_name": clean_display,
                    "filesize": stat.st_size,
                    "filesize_str": format_size(stat.st_size),
                    "ext": ext.replace(".", "").upper(),
                    "time": stat.st_mtime,
                    "download_url": f"/api/file/{urllib.parse.quote(fname)}?name={urllib.parse.quote(clean_display)}"
                })
    # Sort newest first
    files.sort(key=lambda x: x["time"], reverse=True)
    return files


@app.delete("/api/file/{filename}")
async def delete_file(filename: str):
    clean_name = os.path.basename(filename)
    filepath = os.path.join(DOWNLOAD_DIR, clean_name)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return {"status": "ok", "message": "Файл устгагдлаа"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="Файл олдсонгүй")


@app.post("/api/open-folder")
async def open_download_folder():
    """Convenience feature for Windows desktop: opens the download directory in Windows Explorer."""
    if sys.platform == "win32":
        try:
            os.startfile(DOWNLOAD_DIR)
            return {"status": "ok", "message": "Фолдер нээгдлээ"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Зөвхөн Windows системд ажиллана"}


# Serve static web interface
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    import webbrowser

    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    local_ip = get_local_ip()
    local_url = f"http://localhost:{port}"
    mobile_url = f"http://{local_ip}:{port}"

    print("=" * 65)
    print("  🚀 301 Downloader WebApp амжилттай ажиллаж эхэллээ!")
    print(f"  💻 Энэ компьютер дээр:   {local_url}")
    print(f"  📱 Утсаар орох (Нэг Wi-Fi): {mobile_url}")
    print(f"  ⚙️ FFmpeg байршил:        {FFMPEG_EXE}")
    print(f"  📂 Татаж авах хавтас:     {DOWNLOAD_DIR}")
    print("=" * 65)

    # Automatically launch web browser
    def open_browser():
        time.sleep(1.2)
        webbrowser.open(local_url)

    threading.Thread(target=open_browser, daemon=True).start()

    # Launch public tunnel if requested via --public
    if "--public" in sys.argv:
        def start_tunnel_thread():
            time.sleep(1.0)
            print("\n  [Cloudflare Tunnel] Нийтийн интернэт линк үүсгэж байна...")
            url = launch_cloudflared_tunnel(port)
            if url:
                print("*" * 65)
                print("  🌍 301 Downloader НИЙТИЙН ИНТЕРНЭТ ЛИНК ҮҮСЛЭЭ:")
                print(f"  👉 {url}")
                print("  📋 (Санах ойд хуулагдсан. Энэ линкийг бусдад явуулж татуулна уу!)")
                print("*" * 65)
                # Auto open browser with public link as well
                try:
                    time.sleep(0.5)
                    webbrowser.open(url)
                except Exception:
                    pass
        threading.Thread(target=start_tunnel_thread, daemon=True).start()

    uvicorn.run(app, host=host, port=port)
