import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import settings

def rain_probability_next(lat=settings.LATITUDE, lon=settings.LONGITUDE, num_hours=settings.HOURS_AHEAD):
    tz = ZoneInfo(settings.TIMEZONE)
    now = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    now = now + timedelta(hours=1)
    end = now + timedelta(hours=num_hours)
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=precipitation_probability"
        f"&start_date={now.date()}&end_date={end.date()}"
        f"&timezone={settings.TIMEZONE}"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    times = data.get("hourly", {}).get("time", [])
    probs = data.get("hourly", {}).get("precipitation_probability", [])
    forecast = []
    for t, p in zip(times, probs):
        ts = datetime.fromisoformat(t).replace(tzinfo=tz)
        if now <= ts <= end:
            prob = int(p) if p is not None else None
            forecast.append((ts, prob))
    return forecast

def print_probabilities(lat=settings.LATITUDE, lon=settings.LONGITUDE, num_hours=settings.HOURS_AHEAD):
    forecast = rain_probability_next(lat, lon, num_hours)
    for ts, prob in forecast:
        prob_str = f"{prob}%" if prob is not None else "N/A"
        print(ts.strftime(f"%Y-%m-%d %H:%M"), prob_str)

if __name__ == "__main__":
    print_probabilities()

