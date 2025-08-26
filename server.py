import threading
import time
import socket
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
from rain import rain_probability_next

CACHE = []
CACHE_LOCK = threading.Lock()
LAST_UPDATED = None
PORT = 8000
HOST = "0.0.0.0"

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

def fetch_and_cache():
    global CACHE, LAST_UPDATED
    try:
        data = rain_probability_next()
        with CACHE_LOCK:
            CACHE = data
            LAST_UPDATED = datetime.now(timezone.utc)
    except Exception:
        with CACHE_LOCK:
            LAST_UPDATED = datetime.now(timezone.utc)

def refresher():
    while True:
        start = time.time()
        fetch_and_cache()
        next_run = start + 3600
        sleep_time = max(0, next_run - time.time())
        time.sleep(sleep_time)

def render_html(forecast, last_updated):
    lines = []
    header = f"<div style='font-family:monospace'>Last update: {last_updated.astimezone().strftime('%Y-%m-%d %H:%M %Z')}</div>"
    lines.append(header)
    for ts, prob in forecast:
        time_label = ts.strftime("%Y-%m-%d %H:%M UTC")
        if prob is None:
            prob_text = "N/A"
            value = 0
        else:
            prob_text = f"{prob}%"
            value = prob
        lines.append(
            f"<div style='font-family:monospace'>"
            f"{html.escape(time_label)} "
            f"<span style='display:inline-block;width:4ch'>{html.escape(prob_text)}</span> "
            f"<progress value='{value}' max='100'></progress>"
            f"</div>"
        )
    body = "<!doctype html><html><head><meta charset='utf-8'><title>Precipitation probability</title></head><body>" + "".join(lines) + "</body></html>"
    return body.encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with CACHE_LOCK:
            forecast = list(CACHE)
            last = LAST_UPDATED
        if not forecast:
            try:
                fetch_and_cache()
                with CACHE_LOCK:
                    forecast = list(CACHE)
                    last = LAST_UPDATED
            except Exception as e:
                self.send_response(502)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"Upstream error: {e}".encode("utf-8"))
                return
        html_bytes = render_html(forecast, last or datetime.now(timezone.utc))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

if __name__ == "__main__":
    fetch_and_cache()
    t = threading.Thread(target=refresher, daemon=True)
    t.start()
    local_ip = get_local_ip()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving on {HOST}:{PORT}")
    print(f"Accessible on the local network at http://{local_ip}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

