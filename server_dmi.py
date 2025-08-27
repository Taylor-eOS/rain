import http.server
import socketserver
import html
from datetime import datetime
from zoneinfo import ZoneInfo
import rain_dmi
import settings
PORT = 8000
HOST = "0.0.0.0"  

def get_rain_forecast():
    try:
        entries, found_data = rain_dmi.probe_and_get_entries(
            api_key=settings.API_KEY,
            lon=settings.LONGITUDE,
            lat=settings.LATITUDE,
            tz_name=settings.TIMEZONE
        )
        if not found_data or not entries:
            return []
        hourly_entries = rain_dmi._convert_to_hourly(entries)
        tz = ZoneInfo(settings.TIMEZONE)
        now_local = datetime.now(tz)
        future_entries = [(ts, v) for ts, v in hourly_entries if ts >= now_local]
        return future_entries
    except Exception as e:
        print(f"Error getting forecast: {e}")
        return []

def render_html(forecast, last_updated):
    lines = []
    header = f"<div style='font-family:monospace'>Last update: {last_updated.astimezone().strftime('%Y-%m-%d %H:%M %Z')}</div>"
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
            forecast = get_rain_forecast()
            last_updated = datetime.now()
            html_content = render_html(forecast, last_updated)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-length', str(len(html_content)))
            self.end_headers()
            self.wfile.write(html_content)
        else:
            self.send_error(404, "File not found")

def run_server():
    with socketserver.TCPServer((HOST, PORT), RainForecastHandler) as httpd:
        print(f"Serving rain forecast at http://{HOST}:{PORT}")
        print("Press Ctrl+C to stop the server")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server")

if __name__ == "__main__":
    run_server()

