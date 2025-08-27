import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import settings

BASE = "https://dmigw.govcloud.dk/v1/forecastedr/collections/harmonie_dini_sf/position"
CANDIDATES = ["total-precipitation"]

def _point_request(api_key, lon, lat, parameter):
    params = {"coords": f"POINT({lon} {lat})", "crs": "crs84", "f": "GeoJSON", "api-key": api_key}
    if parameter:
        params["parameter-name"] = parameter
    r = requests.get(BASE, params=params, timeout=20)
    return r

def _find_precip_key(features):
    if not isinstance(features, list):
        return None
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties", {})
        for k in props.keys():
            kl = k.lower()
            if "precip" in kl or "rain" in kl or "solid" in kl:
                return k
    return None

def _parse_features(features, key, tz_name):
    tz = ZoneInfo(tz_name)
    out = []
    for feat in features:
        props = feat.get("properties", {}) if isinstance(feat, dict) else {}
        step = props.get("step") or props.get("datetime") or props.get("time") or props.get("validTime")
        if not step:
            continue
        try:
            if step.endswith('Z'):
                parsed = datetime.fromisoformat(step[:-1] + '+00:00')
            else:
                parsed = datetime.fromisoformat(step)
        except Exception:
            continue
        ts = parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
        val = props.get(key)
        if val is None:
            continue
        try:
            out.append((ts, float(val)))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out

def _convert_to_hourly(entries):
    if not entries or len(entries) < 2:
        return entries
    hourly_entries = []
    prev_ts, prev_val = entries[0]
    for i in range(1, len(entries)):
        ts, val = entries[i]
        time_diff = (ts - prev_ts).total_seconds() / 3600
        if time_diff > 0:
            hourly_val = (val - prev_val) / time_diff
        else:
            hourly_val = val - prev_val
        hourly_entries.append((ts, max(0, hourly_val)))
        prev_ts, prev_val = ts, val
    return hourly_entries

def probe_and_get_entries(api_key, lon, lat, tz_name):
    if not api_key:
        raise ValueError("Missing value API_KEY in settings. Add it.")
    resp = _point_request(api_key, lon, lat, None)
    if resp.ok:
        j = resp.json()
        features = j.get("features", [])
        pk = _find_precip_key(features)
        if pk:
            return _parse_features(features, pk, tz_name), True
    for param in CANDIDATES:
        try:
            r = _point_request(api_key, lon, lat, param)
        except Exception:
            continue
        if not r.ok:
            continue
        j = r.json()
        features = j.get("features", [])
        pk = _find_precip_key(features)
        if not pk:
            if features and isinstance(features[0], dict):
                props = features[0].get("properties", {})
                if param in props:
                    pk = param
        if pk:
            return _parse_features(features, pk, tz_name), True
    return [], False

def rain_today_warning(api_key=None, lat=settings.LATITUDE, lon=settings.LONGITUDE, tz_name=settings.TIMEZONE):
    if api_key is None:
        api_key = settings.API_KEY
    entries, found_data = probe_and_get_entries(api_key, lon, lat, tz_name)
    if not entries:
        print("No forecast data available for today. (No entries)")
        return
    entries = _convert_to_hourly(entries)
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    start_of_today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)
    today_entries = [(ts, v) for ts, v in entries if start_of_today <= ts < end_of_today]
    if not today_entries:
        print("No forecast data available for today. (No today_entries)")
        return
    future_entries = [(ts, v) for ts, v in today_entries if ts >= now_local]
    if not future_entries:
        print("No future forecast data available for today. (No future_entries)")
        return
    vals = [v for _, v in future_entries]
    max_v = max(vals) if vals else 0
    avg = sum(vals) / len(vals) if vals else 0
    is_prob = all(0 <= v <= 1 for v in vals) if vals else False
    if is_prob:
        threshold = 0.5
        if max_v >= threshold:
            print("Warning: Rain likely today (probability metric).")
        else:
            print("No rain expected today (probability metric).")
        print(f"Peak probability: {max_v*100:.0f}%")
        print(f"Average probability: {avg*100:.0f}%")
    else:
        threshold_mm = 0.2
        if max_v >= threshold_mm:
            print("Warning: Rain expected today.")
        else:
            print("No rain expected today.")
        print(f"Peak predicted precipitation: {max_v:.2f} mm")
    shown = 0
    for ts, v in future_entries:
        if shown >= 12:
            break
        if is_prob:
            print(ts.strftime("%H:%M"), f"{v*100:.0f}%")
        else:
            print(ts.strftime("%H:%M"), f"{v:.2f} mm")
        shown += 1

if __name__ == "__main__":
    rain_today_warning()

