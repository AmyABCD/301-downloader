"""
301 Downloader - Render Cookie Sync Tool
Энэхүү скрипт нь таны компьютерын Chrome/Edge cookies-г эсвэл бэлэн cookies.txt файлыг 
Render.com дээрх таны 301 Downloader үүлэн серверт автоматаар оруулна.
Ингэснээр та компьютерээ унтраасан ч 24/7 хүн бүр YouTube татаж чадна!
"""
import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

RENDER_API_KEY = "rnd_iOy4LJ8qoeO3HGuiAeDZn39V7quf"
RENDER_SERVICE_ID = "srv-dbmb48vf3r2c7384um0g"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

def print_banner():
    print("=" * 65)
    print("     🚀 301 Downloader - YouTube Cookies Синхрончлогч 🚀")
    print("=" * 65)
    print("Энэхүү тохиргоог нэг удаа хийснээр таны компьютер унтраатай")
    print("байсан ч https://three01-downloader.onrender.com 24/7 найдвартай ажиллана!")
    print("-" * 65)

def upload_cookies_to_render(cookie_content: str):
    print("\n⏳ Render.com сервер рүү Cookies илгээж байна...")
    url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/env-vars"
    
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # First get existing env vars
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            existing = json.loads(resp.read().decode())
    except Exception:
        existing = []

    # Update or append YOUTUBE_COOKIES
    updated = False
    payload_vars = []
    for item in existing:
        ev = item.get("envVar", {})
        k = ev.get("key")
        if k == "YOUTUBE_COOKIES":
            payload_vars.append({"key": "YOUTUBE_COOKIES", "value": cookie_content})
            updated = True
        else:
            payload_vars.append({"key": k, "value": ev.get("value", "")})

    if not updated:
        payload_vars.append({"key": "YOUTUBE_COOKIES", "value": cookie_content})

    # PUT request to Render
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload_vars).encode("utf-8"),
            headers=headers,
            method="PUT"
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            print("✅ АМЖИЛТТАЙ! Cookies Render серверт хадгалагдлаа!")
            print("🚀 Render автоматаар шинэчлэгдэж эхэллээ.")
            print("✨ Одоо та компьютерээ унтраасан ч https://three01-downloader.onrender.com 24/7 ажиллана!")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ Render API алдаа [{e.code}]: {e.read().decode(errors='replace')}")
        return False
    except Exception as e:
        print(f"❌ Холболтын алдаа: {e}")
        return False

def main():
    print_banner()

    # 1. Check if local cookies.txt exists
    if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 50:
        print(f"📁 Бэлэн cookies.txt файл олдлоо ({os.path.getsize(COOKIE_FILE)} байт)")
        with open(COOKIE_FILE, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().strip()
        if content:
            upload_cookies_to_render(content)
            return

    # 2. Offer extraction from Chrome
    print("\nСонголт хийнэ үү:")
    print("1. Chrome хөтчөө түр (3 сек) хаагаад автоматаар татах")
    print("2. 'Get cookies.txt LOCALLY' өргөтгөлийн текстийг шууд paste хийх")
    print("3. cookies.txt файлыг энэ хавтас руу хуулсан тул шууд унших")
    
    choice = input("\nСонголт (1/2/3): ").strip()

    if choice == "1":
        print("\n⚠️ Google Chrome хөтчөө бүрэн хаана уу (Ctrl+Shift+W эсвэл Task Manager-ээс).")
        input("Chrome-оо хаасан бол [Enter] товч дарна уу...")

        print("🔍 Chrome-оос YouTube cookies татаж байна...")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--cookies-from-browser", "chrome",
            "--cookies", COOKIE_FILE,
            "--skip-download",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 50:
            print("✅ Chrome-оос cookies амжилттай татагдлаа!")
            with open(COOKIE_FILE, "r", encoding="utf-8", errors="replace") as f:
                upload_cookies_to_render(f.read().strip())
        else:
            print("❌ Chrome-оос уншиж чадсангүй (Chrome бүрэн хаагдаагүй байна).")
            print("Сонголт 2-оор орж текстийг нь хуулна уу.")

    elif choice == "2":
        print("\n📋 'Get cookies.txt LOCALLY' өргөтгөлийн YouTube cookies текстийг энд Paste хийнэ үү.")
        print("(Дууссан бол шинэ мөрөнд 'END' гэж бичээд Enter дарна уу):")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        content = "\n".join(lines).strip()
        if content:
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            upload_cookies_to_render(content)
        else:
            print("Текст оруулаагүй тул цуцлагдлаа.")

    elif choice == "3":
        if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 50:
            with open(COOKIE_FILE, "r", encoding="utf-8", errors="replace") as f:
                upload_cookies_to_render(f.read().strip())
        else:
            print(f"❌ {COOKIE_FILE} файл олдсонгүй.")

if __name__ == "__main__":
    main()
