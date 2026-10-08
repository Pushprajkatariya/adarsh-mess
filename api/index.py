import os
import json
import datetime
import uuid
import socket
import urllib.request
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from contextlib import contextmanager

# Supabase direct & pooler configuration
SUPABASE_URL = "https://rpyeydssjmdfmlwavpac.supabase.co"
SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJweWV5ZHNzam1kZm1sd2F2cGFjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MTQ3ODY0NiwiZXhwIjoyMTA3MDU0NjQ2fQ.y9RLhZiE8u6xk1xY39MePVtpmW6JRr92L18WkET4DMI"

REST_HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

DEFAULT_DB_URL = "postgresql://postgres.rpyeydssjmdfmlwavpac:qefqa4-jihteF-huhdon@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
DATABASE_URL = os.environ.get("DATABASE_URL") or DEFAULT_DB_URL

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.datetime.now(IST)

# ---------------------------------------------------------------------------
# Supabase REST API Data Layer (Ultra-reliable HTTPS on port 443)
# ---------------------------------------------------------------------------
def rest_get_bookings(date_filter=None):
    try:
        url = f"{SUPABASE_URL}/rest/v1/bookings?select=*&order=id.asc"
        if date_filter and date_filter not in ("active", "all"):
            url += f"&meal_date=eq.{date_filter}"
        req = urllib.request.Request(url, headers=REST_HEADERS, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"REST get error: {e}")
        return []

def rest_insert_booking(record):
    try:
        url = f"{SUPABASE_URL}/rest/v1/bookings"
        body = json.dumps([record]).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=REST_HEADERS, method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"REST insert error: {e}")
        return None

def rest_toggle_booking(entry_id, is_done):
    try:
        url = f"{SUPABASE_URL}/rest/v1/bookings?id=eq.{entry_id}"
        body = json.dumps({"is_done": is_done}).encode("utf-8")
        headers = dict(REST_HEADERS)
        headers["Prefer"] = "return=minimal"
        req = urllib.request.Request(url, data=body, headers=headers, method="PATCH")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True
    except Exception as e:
        print(f"REST toggle error: {e}")
        return False

def rest_delete_booking(entry_id):
    try:
        url = f"{SUPABASE_URL}/rest/v1/bookings?id=eq.{entry_id}"
        headers = dict(REST_HEADERS)
        headers["Prefer"] = "return=minimal"
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True
    except Exception as e:
        print(f"REST delete error: {e}")
        return False

def rest_clear_bookings(date_filter=None):
    try:
        url = f"{SUPABASE_URL}/rest/v1/bookings"
        if date_filter:
            url += f"?meal_date=eq.{date_filter}"
        else:
            url += "?id=neq.none"
        headers = dict(REST_HEADERS)
        headers["Prefer"] = "return=minimal"
        req = urllib.request.Request(url, headers=headers, method="DELETE")
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True
    except Exception as e:
        print(f"REST clear error: {e}")
        return False

# ---------------------------------------------------------------------------
# Status & Timing
# ---------------------------------------------------------------------------
def get_current_status(device_id=None):
    now = get_ist_now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    current_minutes = now.hour * 60 + now.minute
    open_minutes = OPEN_HOUR * 60 + OPEN_MINUTE

    lunch_close_minutes = LUNCH_CLOSE_HOUR * 60 + LUNCH_CLOSE_MINUTE
    dinner_close_minutes = DINNER_CLOSE_HOUR * 60 + DINNER_CLOSE_MINUTE
    tiffin_close_minutes = TIFFIN_CLOSE_HOUR * 60 + TIFFIN_CLOSE_MINUTE

    is_after_open = current_minutes >= open_minutes

    lunch_open = is_after_open and (current_minutes <= lunch_close_minutes)
    dinner_open = is_after_open and (current_minutes <= dinner_close_minutes)
    tiffin_open = is_after_open and (current_minutes <= tiffin_close_minutes)

    def get_reason(is_open, open_time, close_label):
        if is_open:
            return f"Open (Closes {close_label})"
        if not is_after_open:
            return "Closed (Opens at 09:00 AM)"
        return "Closed (Cut-off passed)"

    device_bookings = {"tiffin": None, "lunch": None, "dinner": None}
    if device_id:
        all_bookings = rest_get_bookings()
        for b in all_bookings:
            if b.get("device_id") == device_id:
                mtype = b.get("meal_type")
                if mtype in device_bookings:
                    device_bookings[mtype] = {
                        "booked": True,
                        "student_name": b.get("student_name"),
                        "room_number": b.get("room_number"),
                        "meal_date": b.get("meal_date")
                    }

    return {
        "current_time": now.strftime("%I:%M:%S %p"),
        "today": today_str,
        "tomorrow": tomorrow_str,
        "is_after_open": is_after_open,
        "device_bookings": device_bookings,
        "meals": {
            "tiffin": {
                "open": tiffin_open,
                "meal_date": tomorrow_str,
                "target_label": "Next Day",
                "label": "Morning Tiffin",
                "status_text": get_reason(tiffin_open, "09:00 AM", "11:00 PM"),
                "timing": "09:00 AM - 11:00 PM (Previous Day)"
            },
            "lunch": {
                "open": lunch_open,
                "meal_date": today_str,
                "target_label": "Today",
                "label": "Lunch Late Thali",
                "status_text": get_reason(lunch_open, "09:00 AM", "01:30 PM"),
                "timing": "09:00 AM - 01:30 PM (Today)"
            },
            "dinner": {
                "open": dinner_open,
                "meal_date": today_str,
                "target_label": "Today",
                "label": "Dinner Late Thali",
                "status_text": get_reason(dinner_open, "09:00 AM", "08:30 PM"),
                "timing": "09:00 AM - 08:30 PM (Today)"
            }
        }
    }

def resolve_target_path(path_candidate, headers_dict):
    for header_key in ('x-matched-path', 'x-forwarded-uri', 'request-uri'):
        val = headers_dict.get(header_key)
        if val and not val.startswith('/api/index'):
            return urlparse(val).path.rstrip('/')
    return urlparse(path_candidate).path.rstrip('/')

# ---------------------------------------------------------------------------
# Core business dispatcher
# ---------------------------------------------------------------------------
def dispatch_api(method, path, query_params, body):
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

            rows = rest_get_bookings(date_filter)

            return 200, {
                "date": date_filter or "all",
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
            rest_toggle_booking(entry_id, is_done)
            return 200, {"success": True, "id": entry_id, "is_done": is_done}

        if path.endswith("/bookings/clear"):
            date_filter = body.get("date")
            rest_clear_bookings(date_filter)
            return 200, {"success": True}

        if path.endswith("/bookings/delete"):
            entry_id = body.get("id")
            if not entry_id:
                return 400, {"error": "Missing booking ID."}
            rest_delete_booking(entry_id)
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

            # Strict cut-off check
            invalid_meals = []
            for meal in requested_meals:
                key = meal.lower()
                if key not in status["meals"]:
                    invalid_meals.append(meal)
                elif not status["meals"][key]["open"]:
                    meta = status["meals"][key]
                    invalid_meals.append(f"{meta['label']} ({meta['status_text']})")

            if invalid_meals:
                return 400, {"error": f"Booking closed: {', '.join(invalid_meals)}"}

            existing_bookings = rest_get_bookings()

            for meal in requested_meals:
                key = meal.lower()
                if key not in status["meals"]:
                    continue
                meta = status["meals"][key]
                assigned_date = meta["meal_date"]

                # 1. Device check
                for b in existing_bookings:
                    if b.get("meal_type") == key and b.get("meal_date") == assigned_date and b.get("device_id") == device_id:
                        return 400, {
                            "error": f"This phone has already booked {meta['label']} for {assigned_date} (for {b.get('student_name')}, Room {b.get('room_number')}). Only 1 booking per phone is allowed."
                        }

                # 2. Unique name check
                for b in existing_bookings:
                    if b.get("meal_type") == key and b.get("meal_date") == assigned_date:
                        if " ".join((b.get("student_name") or "").lower().split()) == student_name.lower():
                            return 400, {
                                "error": f"The name '{student_name}' is already registered for {meta['label']} on {assigned_date} (Room {b.get('room_number')}). Duplicate names are not allowed."
                            }

            created = []
            for meal in requested_meals:
                key = meal.lower()
                meta = status["meals"][key]
                assigned_date = meta["meal_date"]
                eid = f"bk_{uuid.uuid4().hex[:10]}"
                record = {
                    "id": eid,
                    "student_name": student_name,
                    "room_number": room_number,
                    "device_id": device_id,
                    "meal_type": key,
                    "meal_date": assigned_date,
                    "is_done": 0,
                    "created_at": now_str
                }
                rest_insert_booking(record)
                created.append({
                    "id": eid,
                    "student_name": student_name,
                    "room_number": room_number,
                    "meal_type": key,
                    "meal_label": meta["label"],
                    "meal_date": assigned_date,
                    "target_label": meta["target_label"]
                })

            return 201, {
                "success": True,
                "student_name": student_name,
                "room_number": room_number,
                "created": created
            }

    return 404, {"error": f"Endpoint not found: {path}"}

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/messmanager.html": ("messmanager.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/manager.js": ("manager.js", "application/javascript; charset=utf-8"),
}

def get_static_response(path):
    clean = (path or "").strip()
    if not clean:
        clean = "/"
    base = os.path.basename(clean)

    filename = None
    mime = None

    if clean in STATIC_FILES:
        filename, mime = STATIC_FILES[clean]
    elif base in ("index.html", "messmanager.html", "styles.css", "app.js", "manager.js"):
        mime = {
            "index.html": "text/html; charset=utf-8",
            "messmanager.html": "text/html; charset=utf-8",
            "styles.css": "text/css; charset=utf-8",
            "app.js": "application/javascript; charset=utf-8",
            "manager.js": "application/javascript; charset=utf-8"
        }[base]
        filename = base
    else:
        return None, None

    for candidate_dir in (ROOT_DIR, os.path.join(ROOT_DIR, "public")):
        fpath = os.path.join(candidate_dir, filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, "rb") as f:
                    return mime, f.read()
            except Exception:
                pass

    return None, None

# ---------------------------------------------------------------------------
# Standard WSGI Application Callable (app)
# ---------------------------------------------------------------------------
def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()

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

    # 1. Check static file serving for GET requests
    if method == "GET":
        mime, content = get_static_response(path)
        if content is not None:
            start_response("200 OK", [
                ("Content-Type", mime),
                ("Content-Length", str(len(content))),
                ("Cache-Control", "public, max-age=0, must-revalidate"),
            ])
            return [content]

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

        # Check static file
        mime, content = get_static_response(path)
        if content is not None:
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "public, max-age=0, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
            return

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
