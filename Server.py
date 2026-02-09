import http.server
import socketserver
import socket
import subprocess
import threading
import time
import re
import os
import platform
import sys

PORT = 8000
CLOUDFLARED_PATH = "./cloudflared"

cloudflared_proc = None
public_url = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def detect_arch():
    arch = platform.machine().lower()
    if arch in ("aarch64", "arm64"):
        return "arm64"
    elif arch.startswith("arm"):
        return "arm"
    elif arch in ("x86_64", "amd64"):
        return "amd64"
    else:
        return None

def get_cloudflared_url(arch):
    if arch == "arm64":
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64"
    elif arch == "arm":
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm"
    elif arch == "amd64":
        return "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
    else:
        return None

def download_cloudflared():
    if os.path.exists(CLOUDFLARED_PATH):
        return

    arch = detect_arch()
    if not arch:
        print("❌ Unsupported architecture:", platform.machine())
        sys.exit(1)

    url = get_cloudflared_url(arch)
    print(f"⬇️ Downloading cloudflared for {arch}...")
    subprocess.run(["wget", "-O", CLOUDFLARED_PATH, url], check=True)
    subprocess.run(["chmod", "+x", CLOUDFLARED_PATH], check=True)
    print("✅ cloudflared downloaded.")

def start_cloudflare():
    global cloudflared_proc, public_url
    print("🌐 Starting Cloudflare Tunnel...")
    cloudflared_proc = subprocess.Popen(
        [CLOUDFLARED_PATH, "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in cloudflared_proc.stdout:
        m = re.search(r"https://[^\s]+\.trycloudflare\.com", line)
        if m:
            public_url = m.group(0)
            print(f"🌍 Public:  {public_url}")
            break

def run_server():
    Handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        ip = get_local_ip()
        time.sleep(2)

        print("\n🚀 Server started!")
        print(f"📡 Local:   http://127.0.0.1:{PORT}")
        print(f"🌐 Network: http://{ip}:{PORT}")
        if public_url:
            print(f"🌍 Public:  {public_url}")
        else:
            print("🌍 Public:  (starting...)")
        print("🛑 Press CTRL + C to stop the server\n")

        httpd.serve_forever()

def cleanup():
    global cloudflared_proc
    print("\n🧹 Cleaning up...")

    if cloudflared_proc and cloudflared_proc.poll() is None:
        cloudflared_proc.terminate()
        try:
            cloudflared_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cloudflared_proc.kill()

    if os.path.exists(CLOUDFLARED_PATH):
        os.remove(CLOUDFLARED_PATH)
        print("🗑️ cloudflared deleted.")

    print("🛑 Server + Cloudflare tunnel stopped. Bye 👋")

try:
    download_cloudflared()
    t = threading.Thread(target=start_cloudflare, daemon=True)
    t.start()
    run_server()
except KeyboardInterrupt:
    cleanup()
except Exception as e:
    print("⚠️ Error:", e)
    cleanup()