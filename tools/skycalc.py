"""Moon and planet calculations for the import script (needs: pip install astronomy-engine).

Everything here is geocentric (seen from the centre of the Earth), so it does not depend on where you stood.
Only the date and the time, converted to UTC, matter.
"""
import math
import re
from datetime import datetime, timedelta, timezone

SYNODIC_MONTH = 29.530588
SUPERMOON_KM = 361500           # a full moon closer than this counts as a supermoon (approximate, common definition)
MOON_RADIUS_KM = 1737.4
PLANET_RADIUS_KM = {"Mercury": 2439.7, "Venus": 6051.8, "Mars": 3389.5, "Jupiter": 71492.0,
                    "Saturn": 60268.0, "Uranus": 25559.0, "Neptune": 24764.0}   # equatorial, without Saturn's rings
PLANETS = list(PLANET_RADIUS_KM)


def norm_date(s):
    """Reads 2026-11-04, 11-4-2026 or 11/04/2026 (month first, unless the first number is above 12) and returns YYYY-MM-DD, or None."""
    s = str(s or "").strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s)
        if not m:
            return None
        a, b, y = map(int, m.groups())
        mo, d = (b, a) if a > 12 else (a, b)
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def to_utc(date_iso, time_local=None, tz=None):
    """Local date, clock time and time zone -> an aware UTC datetime, plus notes about any guesses made."""
    notes = []
    y, mo, d = map(int, date_iso.split("-"))
    t = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", str(time_local or ""))
    if t:
        hh, mm, ss = int(t[1]), int(t[2]), int(t[3] or 0)
    else:
        hh, mm, ss = 12, 0, 0
        notes.append("no time_local given: calculated for 12:00 on that date, so values can be off by up to half a day")
    tz = str(tz or "").strip()
    if not tz:
        zone = timezone.utc
        notes.append("no timezone given: the time was taken as UTC")
    elif tz.upper() in ("UTC", "Z", "GMT"):
        zone = timezone.utc
    elif re.match(r"^[+-]\d{1,2}(:?\d{2})?$", tz):
        sign = -1 if tz[0] == "-" else 1
        digits = tz[1:].replace(":", "")
        h, mi = (int(digits[:-2]), int(digits[-2:])) if len(digits) > 2 else (int(digits), 0)
        zone = timezone(sign * timedelta(hours=h, minutes=mi))
    else:
        from zoneinfo import ZoneInfo
        try:
            zone = ZoneInfo(tz)
        except Exception:
            raise RuntimeError(f"Unknown time zone '{tz}'. Use a name like America/New_York or an offset like -05:00 "
                               "(on Windows, names need: pip install tzdata).")
    return datetime(y, mo, d, hh, mm, ss, tzinfo=zone).astimezone(timezone.utc), notes


def _time(astronomy, dt):
    return astronomy.Time.Make(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second + dt.microsecond / 1e6)


def _phase_name(angle, frac):
    p = frac * 100
    if p < 2:
        return "New Moon"
    if p > 98:
        return "Full Moon"
    waxing = angle < 180
    if 47 <= p <= 53:
        return "First Quarter" if waxing else "Last Quarter"
    if p < 50:
        return "Waxing crescent" if waxing else "Waning crescent"
    return "Waxing gibbous" if waxing else "Waning gibbous"


def moon_info(dt):
    import astronomy
    t = _time(astronomy, dt)
    angle = astronomy.MoonPhase(t)
    frac = astronomy.Illumination(astronomy.Body.Moon, t).phase_fraction
    vec = astronomy.GeoVector(astronomy.Body.Moon, t, True)
    km = vec.Length() * astronomy.KM_PER_AU
    eq = astronomy.EquatorFromVector(vec)
    # age = days since the most recent new moon
    new = astronomy.SearchMoonPhase(0, t.AddDays(-31), 32)
    while new is not None:
        nxt = astronomy.SearchMoonPhase(0, new.AddDays(1), 32)
        if nxt is not None and nxt.ut <= t.ut:
            new = nxt
        else:
            break
    out = {"phase": _phase_name(angle, frac), "illumination_percent": round(frac * 100, 1),
           "moon_distance_km": int(round(km)),
           "moon_angular_diameter_arcmin": round(math.degrees(2 * math.asin(MOON_RADIUS_KM / km)) * 60, 1),
           "constellation": astronomy.Constellation(eq.ra, eq.dec).name}
    if new is not None:
        age = t.ut - new.ut
        out["moon_age_days"] = round(0.0 if age > SYNODIC_MONTH - 0.5 else age, 1)   # right at a new moon the search finds the previous one
    if frac > 0.98 and km <= SUPERMOON_KM:
        out["supermoon"] = True
    return out


def planet_info(name, dt):
    import astronomy
    if name not in PLANET_RADIUS_KM:
        raise RuntimeError(f"Unknown planet '{name}'. Use one of: {', '.join(PLANETS)}.")
    body = getattr(astronomy.Body, name)
    t = _time(astronomy, dt)
    vec = astronomy.GeoVector(body, t, True)
    au = vec.Length()
    km = au * astronomy.KM_PER_AU
    ill = astronomy.Illumination(body, t)
    eq = astronomy.EquatorFromVector(vec)
    return {"planet_distance_au": round(au, 3), "planet_distance_million_km": round(km / 1e6, 1),
            "apparent_diameter_arcsec": round(math.degrees(2 * math.asin(PLANET_RADIUS_KM[name] / km)) * 3600, 1),
            "illumination_percent": round(ill.phase_fraction * 100, 1), "magnitude": round(ill.mag, 1),
            "constellation": astronomy.Constellation(eq.ra, eq.dec).name}
