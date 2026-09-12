import datetime
import math

def calc_js(timestamp_ms):
    D = (timestamp_ms - 946728000000) / 86400000.0
    rad = math.pi / 180
    
    # Sun
    g = (357.529 + 0.98560028 * D) * rad
    q = 280.459 + 0.98564736 * D
    L = (q + 1.915 * math.sin(g) + 0.020 * math.sin(2*g)) * rad
    e = (23.439 - 0.00000036 * D) * rad
    
    sun_phi = ((math.atan2(math.cos(e)*math.sin(L), math.cos(L)) / rad) % 360 + 360) % 360
    sun_theta = math.asin(math.sin(e)*math.sin(L)) / rad
    
    # Moon
    Lm = (218.316 + 13.176396 * D) * rad
    Mm = (134.963 + 13.064993 * D) * rad
    Fm = (93.272 + 13.229350 * D) * rad
    
    lon = Lm + 6.289 * rad * math.sin(Mm)
    lat = 5.128 * rad * math.sin(Fm)
    
    moon_phi = ((math.atan2(math.sin(lon)*math.cos(e) - math.tan(lat)*math.sin(e), math.cos(lon)) / rad) % 360 + 360) % 360
    moon_theta = math.asin(math.sin(lat)*math.cos(e) + math.cos(lat)*math.sin(e)*math.sin(lon)) / rad
    
    print(f"JS Calc -> Sun: RA={sun_phi:.2f}, Dec={sun_theta:.2f} | Moon: RA={moon_phi:.2f}, Dec={moon_theta:.2f}")

# 2026-09-12 14:27:45 KST
dt = datetime.datetime(2026, 9, 12, 14, 27, 45, tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
timestamp_ms = dt.timestamp() * 1000

calc_js(timestamp_ms)
