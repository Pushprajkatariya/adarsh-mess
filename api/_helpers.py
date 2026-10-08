"""
Shared DB helpers + timing logic for all Vercel serverless functions.
Underscore prefix means Vercel won't treat this as a route.
"""
import os
import json
import datetime
import uuid
import socket
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Timing constants (IST)
OPEN_HOUR, OPEN_MINUTE = 9, 0
LUNCH_CLOSE_HOUR, LUNCH_CLOSE_MINUTE = 13, 30
DINNER_CLOSE_HOUR, DINNER_CLOSE_MINUTE = 20, 30
TIFFIN_CLOSE_HOUR, TIFFIN_CLOSE_MINUTE = 23, 0

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def get_ist_now():
    return datetime.datetime.now(IST)


# ---------------------------------------------------------------------------
# DB connection (forces IPv4 to avoid Render/Vercel IPv6 issues)
# ---------------------------------------------------------------------------
def _make_dsn():
    parsed = urlparse(DATABASE_URL)
    hostname = parsed.hostname or ""
    port = parsed.port or 5432
    dbname = (parsed.path or "/postgres").lstrip("/")
    username = parsed.username or "postgres"
    password = parsed.password or ""

    ipv4_addr = None
    try:
        for addrinfo in socket.getaddrinfo(hostname, port, socket.AF_INET, socket.SOCK_STREAM):
            ipv4_addr = addrinfo[4][0]
            break
    except Exception:
        pass

    if ipv4_addr:
        return (
            f"host={hostname} hostaddr={ipv4_addr} port={port} "
            f"dbname={dbname} user={username} password={password} "
            f"sslmode=require connect_timeout=15"
        )
    dsn = DATABASE_URL
    if "sslmode" not in dsn:
        dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
    return dsn


@contextmanager
def get_db():
    conn = psycopg2.connect(_make_dsn(), cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchall(cur):
    return [dict(r) for r in cur.fetchall()]


def fetchone(cur):
    r = cur.fetchone()
    return dict(r) if r else None


def q(sql):
    """Return SQL with %s placeholders (PostgreSQL)."""
    return sql.replace("?", "%s")


# ---------------------------------------------------------------------------
# Status / timing
# ---------------------------------------------------------------------------
def get_current_status(device_id=None):
    now = get_ist_now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    cur_min = now.hour * 60 + now.minute
    open_min = OPEN_HOUR * 60 + OPEN_MINUTE
    is_after_open = cur_min >= open_min

    lunch_open  = is_after_open and cur_min <= LUNCH_CLOSE_HOUR  * 60 + LUNCH_CLOSE_MINUTE
    dinner_open = is_after_open and cur_min <= DINNER_CLOSE_HOUR * 60 + DINNER_CLOSE_MINUTE
    tiffin_open = is_after_open and cur_min <= TIFFIN_CLOSE_HOUR * 60 + TIFFIN_CLOSE_MINUTE

    def reason(is_open, close_label):
        if is_open:       return f"Open (Closes {close_label})"
        if not is_after_open: return "Closed (Opens at 09:00 AM)"
        return "Closed (Cut-off passed)"

    device_bookings = {"tiffin": None, "lunch": None, "dinner": None}
    if device_id:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(q("SELECT student_name, room_number, meal_date FROM bookings WHERE device_id=? AND meal_type='tiffin' AND meal_date=?"), (device_id, tomorrow_str))
                row = fetchone(cur)
                if row:
                    device_bookings["tiffin"] = {"booked": True, **row}

                cur.execute(q("SELECT student_name, room_number, meal_date FROM bookings WHERE device_id=? AND meal_type='lunch' AND meal_date=?"), (device_id, today_str))
                row = fetchone(cur)
                if row:
                    device_bookings["lunch"] = {"booked": True, **row}

                cur.execute(q("SELECT student_name, room_number, meal_date FROM bookings WHERE device_id=? AND meal_type='dinner' AND meal_date=?"), (device_id, today_str))
                row = fetchone(cur)
                if row:
                    device_bookings["dinner"] = {"booked": True, **row}
        except Exception:
            pass

    return {
        "current_time": now.strftime("%I:%M:%S %p"),
        "today": today_str,
        "tomorrow": tomorrow_str,
        "is_after_open": is_after_open,
        "device_bookings": device_bookings,
        "meals": {
            "tiffin": {"open": tiffin_open, "meal_date": tomorrow_str, "target_label": "Next Day",
                       "label": "Morning Tiffin", "status_text": reason(tiffin_open, "11:00 PM"),
                       "timing": "09:00 AM - 11:00 PM (Previous Day)"},
            "lunch":  {"open": lunch_open,  "meal_date": today_str,    "target_label": "Today",
                       "label": "Lunch Late Thali", "status_text": reason(lunch_open, "01:30 PM"),
                       "timing": "09:00 AM - 01:30 PM (Today)"},
            "dinner": {"open": dinner_open, "meal_date": today_str,    "target_label": "Today",
                       "label": "Dinner Late Thali", "status_text": reason(dinner_open, "08:30 PM"),
                       "timing": "09:00 AM - 08:30 PM (Today)"},
        }
    }


# ---------------------------------------------------------------------------
# Vercel handler base class with JSON helpers + CORS
# ---------------------------------------------------------------------------
from http.server import BaseHTTPRequestHandler

class ApiHandler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, format, *args):
        pass  # suppress noisy vercel logs
