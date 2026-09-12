import ephem
from datetime import datetime, timezone

dt = datetime(2026, 9, 12, 5, 27, 45, tzinfo=timezone.utc)
sun = ephem.Sun(dt)
moon = ephem.Moon(dt)

print(f"Sun RA: {sun.a * 180 / 3.14159265:.2f} Dec: {sun.d * 180 / 3.14159265:.2f}")
print(f"Moon RA: {moon.a * 180 / 3.14159265:.2f} Dec: {moon.d * 180 / 3.14159265:.2f}")
