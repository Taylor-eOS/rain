import http.server
import socketserver
import html
from datetime import datetime, time
from zoneinfo import ZoneInfo
import socket
from contextlib import closing
import threading
import time as time_module
import rain_dmi
import settings
PORT = 8000

forecast_data = []
last_updated = datetime.now()
data_lock = threading.Lock()
DAYS_AHEAD = 1

def get_local_ip():
    try:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except:
        return socket.gethostbyname(socket.gethostname())

def update_forecast_data():
    global forecast_data, last_updated
    while True:
        try:
            entries, found_data = rain_dmi.probe_and_get_entries(
                api_key=settings.API_KEY,
                lon=settings.LONGITUDE,
                lat=settings.LATITUDE,
                tz_name=settings.TIMEZONE
            )
            if found_data and entries:
                hourly_entries = rain_dmi._convert_to_hourly(entries)
                tz = ZoneInfo(settings.TIMEZONE)
                now_local = datetime.now(tz)
                midnight_today = datetime.combine(now_local.date(), time(0, 0), tz)
                midnight_tomorrow = midnight_today.replace(day=midnight_today.day + DAYS_AHEAD)
                future_entries = [(ts, v) for ts, v in hourly_entries 
                                 if ts >= now_local and ts < midnight_tomorrow]
                with data_lock:
                    forecast_data = future_entries
                    last_updated = datetime.now()
            else:
                with data_lock:
                    last_updated = datetime.now()
            
        except Exception as e:
            print(f"Error updating forecast: {e}")
            with data_lock:
                last_updated = datetime.now()
        
        time_module.sleep(3600)

def render_html(forecast, last_updated):
    lines = []
    if last_updated:
        header = f"<div style='font-family:monospace'>Last update: {last_updated.astimezone().strftime('%Y-%m-%d %H:%M %Z')}</div>"
    else:
        header = "<div style='font-family:monospace'>Last update: Never</div>"
    lines.append(header)
    is_probability = False
    if forecast and forecast[0][1] <= 1:
        is_probability = True
    for ts, value in forecast:
        time_label = ts.strftime("%Y-%m-%d %H:%M")
        if value is None:
            value_text = "N/A"
            progress_value = 0
        else:
            if is_probability:
                value_text = f"{value*100:.0f}%"
                progress_value = value * 100
            else:
                value_text = f"{value:.2f} mm"
                progress_value = min(value * 10, 100)
        lines.append(
            f"<div style='font-family:monospace'>"
            f"{html.escape(time_label)} "
            f"<span style='display:inline-block;width:4ch'>{html.escape(value_text)}</span> "
            f"<progress value='{progress_value}' max='100'></progress>"
            f"</div>"
        )
    body = "<!doctype html><html><head><meta charset='utf-8'><title>Rain Forecast</title></head><body>" + "".join(lines) + "</body></html>"
    return body.encode("utf-8")

class RainForecastHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            with data_lock:
                forecast = forecast_data
                updated = last_updated
            html_content = render_html(forecast, updated)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-length', str(len(html_content)))
            self.end_headers()
            try:
                self.wfile.write(html_content)
            except BrokenPipeError:
                pass
        else:
            self.send_error(404, "File not found")

def run_server():
    update_thread = threading.Thread(target=update_forecast_data, daemon=True)
    update_thread.start()
    time_module.sleep(2)
    local_ip = get_local_ip()
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("0.0.0.0", PORT), RainForecastHandler)
    print(f"Serving rain forecast at http://{local_ip}:{PORT}")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server")
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    run_server()

