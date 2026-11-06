import sys, unittest, json, asyncio
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import app
class AppTests(unittest.TestCase):
    def setUp(self):
        app.rates.clear()
        self.client=TestClient(app.app)
    def test_page_health(self):
        self.assertIn('Татъя', self.client.get('/').text)
        self.assertEqual(self.client.get('/health').json(),{'ok':True})
    def test_url_validation(self):
        for url in ['https://127.0.0.1/video','https://youtube.com.evil.test/x','file:///etc/passwd','https://u:p@youtube.com/x','https://youtube.com:8000/x']:
            self.assertEqual(self.client.post('/api/info',json={'url':url}).status_code,400)
    def test_formats(self):
        async def fake(*args):
            return json.dumps({'title':'Test', 'formats':[{'height':720,'vcodec':'h264','ext':'mp4'},{'height':1080,'vcodec':'h264','ext':'mp4'},{'height':720,'vcodec':'h264','ext':'mp4'}]}).encode()
        with patch.object(app,'run',fake):
            r=self.client.post('/api/info',json={'url':'https://www.youtube.com/watch?v=test'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['heights'],[1080,720])
    def test_errors_and_rate_limit(self):
        self.assertEqual(self.client.get('/api/files/not-real').status_code,404)
        self.assertEqual(self.client.post('/api/download',json={'url':'https://youtu.be/test','kind':'exe','quality':'720'}).status_code,400)
        for i in range(12): self.client.post('/api/info',json={'url':'https://bad.test'})
        self.assertEqual(self.client.post('/api/info',json={'url':'https://bad.test'}).status_code,429)
    def test_fast_mp4_and_mp3_commands(self):
        args=app.media_args('mp4','1080')
        self.assertNotIn('--recode-video',args)
        self.assertIn('bv[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4][height<=1080]',args)
        self.assertIn('--merge-output-format',args)
        mp3=app.media_args('mp3','192')
        self.assertIn('--audio-format',mp3)
        self.assertIn('192K',mp3)
    def test_file_delivery(self):
        key='test-file'
        folder=app.DATA/key
        folder.mkdir(exist_ok=True)
        f=folder/'example.mp3';f.write_bytes(b'example audio')
        app.jobs[key]={'status':'done','progress':100,'message':'done','file':f,'created':app.time.time()}
        try:
            self.assertNotIn('file',self.client.get('/api/jobs/'+key).json())
            r=self.client.get('/api/files/'+key)
            self.assertEqual(r.content,b'example audio')
            self.assertIn('attachment',r.headers['content-disposition'])
        finally:
            app.jobs.pop(key,None);app.shutil.rmtree(folder)
if __name__=='__main__':unittest.main()
