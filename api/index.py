import os
import json
import datetime
import uuid
import socket
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from contextlib import contextmanager
import psycopg2
import psycopg2.extras

# Supabase PostgreSQL connection URL
DEFAULT_DB_URL = "postgresql://postgres:qefqa4-jihteF-huhdon@db.rpyeydssjmdfmlwavpac.supabase.co:5432/postgres"
DATABASE_URL = os.environ.get("DATABASE_URL") or DEFAULT_DB_URL

# Timing rules (IST)
OPEN_HOUR, OPEN_MINUTE = 9, 0
LUNCH_CLOSE_HOUR, LUNCH_CLOSE_MINUTE = 13, 30
DINNER_CLOSE_HOUR, DINNER_CLOSE_MINUTE = 20, 30
TIFFIN_CLOSE_HOUR, TIFFIN_CLOSE_MINUTE = 23, 0

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.datetime.now(IST)

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

# Ensure table exists
_db_initialized = False
def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id TEXT PRIMARY KEY,
                    student_name TEXT NOT NULL,
                    room_number TEXT NOT NULL DEFAULT '',
                    device_id TEXT NOT NULL DEFAULT '',
                    meal_type TEXT NOT NULL,
                    meal_date TEXT NOT NULL,
                    is_done INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_bk_meal_date ON bookings (meal_type, meal_date);
                CREATE INDEX IF NOT EXISTS idx_bk_device ON bookings (device_id, meal_type, meal_date);
            """)
        _db_initialized = True
    except Exception as e:
        print(f"init_db notice: {e}")

def get_current_status(device_id=None):
    now = get_ist_now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    cur_min = now.hour * 60 + now.minute
    open_min = OPEN_HOUR * 60 + OPEN_MINUTE
    is_after_open = cur_min >= open_min

    lunch_open  = is_after_open and cur_min <= (LUNCH_CLOSE_HOUR * 60 + LUNCH_CLOSE_MINUTE)
    dinner_open = is_after_open and cur_min <= (DINNER_CLOSE_HOUR * 60 + DINNER_CLOSE_MINUTE)
    tiffin_open = is_after_open and cur_min <= (TIFFIN_CLOSE_HOUR * 60 + TIFFIN_CLOSE_MINUTE)

    def reason(is_open, close_label):
        if is_open:
            return f"Open (Closes {close_label})"
        if not is_after_open:
            return "Closed (Opens at 09:00 AM)"
        return "Closed (Cut-off passed)"

    device_bookings = {"tiffin": None, "lunch": None, "dinner": None}
    if device_id:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT student_name, room_number, meal_date FROM bookings WHERE device_id=%s AND meal_type='tiffin' AND meal_date=%s",
                    (device_id, tomorrow_str)
                )
                row = fetchone(cur)
                if row:
                    device_bookings["tiffin"] = {"booked": True, **row}

                cur.execute(
                    "SELECT student_name, room_number, meal_date FROM bookings WHERE device_id=%s AND meal_type='lunch' AND meal_date=%s",
                    (device_id, today_str)
                )
                row = fetchone(cur)
                if row:
                    device_bookings["lunch"] = {"booked": True, **row}

                cur.execute(
                    "SELECT student_name, room_number, meal_date FROM bookings WHERE device_id=%s AND meal_type='dinner' AND meal_date=%s",
                    (device_id, today_str)
                )
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
            "tiffin": {
                "open": tiffin_open, "meal_date": tomorrow_str, "target_label": "Next Day",
                "label": "Morning Tiffin", "status_text": reason(tiffin_open, "11:00 PM"),
                "timing": "09:00 AM - 11:00 PM (Previous Day)"
            },
            "lunch": {
                "open": lunch_open, "meal_date": today_str, "target_label": "Today",
                "label": "Lunch Late Thali", "status_text": reason(lunch_open, "01:30 PM"),
                "timing": "09:00 AM - 01:30 PM (Today)"
            },
            "dinner": {
                "open": dinner_open, "meal_date": today_str, "target_label": "Today",
                "label": "Dinner Late Thali", "status_text": reason(dinner_open, "08:30 PM"),
                "timing": "09:00 AM - 08:30 PM (Today)"
            }
        }
    }

def resolve_target_path(path_candidate, headers_dict):
    for header_key in ('x-matched-path', 'x-forwarded-uri', 'request-uri'):
        val = headers_dict.get(header_key)
        if val and not val.startswith('/api/index'):
            return urlparse(val).path.rstrip('/')
    parsed = urlparse(path_candidate).path.rstrip('/')
    return parsed

# Core business dispatcher
def dispatch_api(method, path, query_params, body):
    init_db()
    method = method.upper()

    if method == "GET":
        if path.endswith("/status"):
            dev_id = query_params.get("device_id", [None])[0]
            return 200, get_current_status(dev_id)

        if path.endswith("/bookings"):
            date_filter = query_params.get("date", [None])[0]
            now = get_ist_now()
            today_str = now.strftime("%Y-%m-%d")
            tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            with get_db() as conn:
                cur = conn.cursor()
                if date_filter and date_filter != "active":
                    cur.execute(
                        "SELECT id, student_name, room_number, meal_type, meal_date, is_done, created_at FROM bookings WHERE meal_date=%s ORDER BY id ASC",
                        (date_filter,)
                    )
                    rows = fetchall(cur)
                    resp_date = date_filter
                else:
                    cur.execute("""
                        SELECT id, student_name, room_number, meal_type, meal_date, is_done, created_at
                        FROM bookings
                        WHERE (meal_type='tiffin' AND meal_date=%s)
                           OR (meal_type IN ('lunch','dinner') AND meal_date=%s)
                        ORDER BY id ASC
                    """, (tomorrow_str, today_str))
                    rows = fetchall(cur)
                    resp_date = "active"

            return 200, {
                "date": resp_date,
                "today": today_str,
                "tomorrow": tomorrow_str,
                "bookings": rows
            }

    elif method == "POST":
        if path.endswith("/bookings/toggle"):
            entry_id = body.get("id")
            is_done = 1 if body.get("is_done") else 0
            if not entry_id:
                return 400, {"error": "Missing booking ID."}
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE bookings SET is_done=%s WHERE id=%s", (is_done, entry_id))
            return 200, {"success": True, "id": entry_id, "is_done": is_done}

        if path.endswith("/bookings/clear"):
            date_filter = body.get("date")
            with get_db() as conn:
                cur = conn.cursor()
                if date_filter:
                    cur.execute("DELETE FROM bookings WHERE meal_date=%s", (date_filter,))
                else:
                    cur.execute("DELETE FROM bookings")
            return 200, {"success": True}

        if path.endswith("/bookings/delete"):
            entry_id = body.get("id")
            if not entry_id:
                return 400, {"error": "Missing booking ID."}
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM bookings WHERE id=%s", (entry_id,))
            return 200, {"success": True, "id": entry_id}

        if path.endswith("/bookings"):
            student_name = " ".join((body.get("student_name") or "").strip().split())
            room_number = " ".join((body.get("room_number") or "").strip().upper().split())
            device_id = (body.get("device_id") or "").strip()
            requested_meals = body.get("meals") or []

            if not student_name:
                return 400, {"error": "Student name is required."}
            if len(student_name) < 2:
                return 400, {"error": "Please enter a valid student name."}
            if not room_number:
                return 400, {"error": "Room number is required (e.g. 204 or B-102)."}
            if not device_id:
                return 400, {"error": "Device verification token missing. Please refresh your page."}
            if not requested_meals or not isinstance(requested_meals, list):
                return 400, {"error": "At least one meal option must be selected."}

            status = get_current_status(device_id)
            now_str = get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p")

            invalid_meals = []
            for meal in requested_meals:
                key = meal.lower()
                if key not in status["meals"]:
                    invalid_meals.append(meal)
                elif not status["meals"][key]["open"]:
                    m = status["meals"][key]
                    invalid_meals.append(f"{m['label']} ({m['status_text']})")
            if invalid_meals:
                return 400, {"error": f"Booking closed: {', '.join(invalid_meals)}"}

            with get_db() as conn:
                cur = conn.cursor()
                for meal in requested_meals:
                    key = meal.lower()
                    meta = status["meals"][key]
                    assigned_date = meta["meal_date"]

                    # 1. Device Check
                    cur.execute(
                        "SELECT id, student_name, room_number FROM bookings WHERE meal_type=%s AND meal_date=%s AND device_id=%s",
                        (key, assigned_date, device_id)
                    )
                    existing = fetchone(cur)
                    if existing:
                        return 400, {
                            "error": f"This phone has already booked {meta['label']} for {assigned_date} (for {existing['student_name']}, Room {existing['room_number']}). Only 1 booking per phone is allowed."
                        }

                    # 2. Unique Name Check
                    cur.execute(
                        "SELECT student_name, room_number FROM bookings WHERE meal_type=%s AND meal_date=%s",
                        (key, assigned_date)
                    )
                    for rec in fetchall(cur):
                        if " ".join(rec["student_name"].lower().split()) == student_name.lower():
                            return 400, {
                                "error": f"The name '{student_name}' is already registered for {meta['label']} on {assigned_date} (Room {rec['room_number']}). Duplicate names are not allowed."
                            }

                created = []
                for meal in requested_meals:
                    key = meal.lower()
                    meta = status["meals"][key]
                    assigned_date = meta["meal_date"]
                    eid = f"bk_{uuid.uuid4().hex[:10]}"
                    cur.execute(
                        "INSERT INTO bookings (id, student_name, room_number, device_id, meal_type, meal_date, is_done, created_at) VALUES (%s,%s,%s,%s,%s,%s,0,%s)",
                        (eid, student_name, room_number, device_id, key, assigned_date, now_str)
                    )
                    created.append({
                        "id": eid, "student_name": student_name, "room_number": room_number,
                        "meal_type": key, "meal_label": meta["label"],
                        "meal_date": assigned_date, "target_label": meta["target_label"]
                    })

            return 201, {
                "success": True, "student_name": student_name,
                "room_number": room_number, "created": created
            }

    return 404, {"error": f"Endpoint not found: {path}"}


# ---------------------------------------------------------------------------
# Standard WSGI Application Callable (app)
# Used when Vercel runs in framework mode via pyproject.toml [tool.vercel] entrypoint = "api.index:app"
# ---------------------------------------------------------------------------
def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()

    # CORS Preflight
    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
        ])
        return [b""]

    headers_dict = {}
    for k, v in environ.items():
        if k.startswith("HTTP_"):
            headers_dict[k[5:].lower().replace("_", "-")] = v

    path_raw = environ.get("PATH_INFO", "")
    path = resolve_target_path(path_raw, headers_dict)
    query_params = parse_qs(environ.get("QUERY_STRING", ""))

    body = {}
    if method == "POST":
        try:
            cl = int(environ.get("CONTENT_LENGTH") or 0)
            if cl > 0:
                body = json.loads(environ["wsgi.input"].read(cl).decode("utf-8"))
        except Exception:
            body = {}

    status_code, data = dispatch_api(method, path, query_params, body)
    resp_bytes = json.dumps(data).encode("utf-8")

    status_phrase = {
        200: "200 OK",
        201: "201 Created",
        400: "400 Bad Request",
        404: "404 Not Found"
    }.get(status_code, f"{status_code} Result")

    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(resp_bytes))),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
        ("Cache-Control", "no-cache, no-store, must-revalidate"),
    ]
    start_response(status_phrase, headers)
    return [resp_bytes]


# ---------------------------------------------------------------------------
# BaseHTTPRequestHandler fallback (handler)
# ---------------------------------------------------------------------------
class handler(BaseHTTPRequestHandler):
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

    def do_GET(self):
        headers_dict = {k.lower(): v for k, v in self.headers.items()}
        path = resolve_target_path(self.path, headers_dict)
        query_params = parse_qs(urlparse(self.path).query)
        status, data = dispatch_api("GET", path, query_params, {})
        self.send_json(status, data)

    def do_POST(self):
        headers_dict = {k.lower(): v for k, v in self.headers.items()}
        path = resolve_target_path(self.path, headers_dict)
        query_params = parse_qs(urlparse(self.path).query)
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                body = {}
        status, data = dispatch_api("POST", path, query_params, body)
        self.send_json(status, data)
