#!/usr/bin/env python3
"""
Adarsh Dining Hall - Backend Server
Features:
- Built-in SQLite database storage (mess.db)
- Live multi-device support over Wi-Fi / LAN
- Server-side strict time enforcement (9:00 AM open, exact meal cut-offs)
- Morning Tiffin auto-assigned to Next Day
- Lunch & Dinner auto-assigned to Today
- REST API for student bookings & manager checklist
"""

import os
import sys
import json
import sqlite3
import datetime
import uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", 3000))
BIND = "0.0.0.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "mess.db")

# Timing Rules
# All bookings open at 09:00 AM
OPEN_HOUR = 9
OPEN_MINUTE = 0

# Cut-offs
LUNCH_CLOSE_HOUR = 13      # 1:00 PM
LUNCH_CLOSE_MINUTE = 0

DINNER_CLOSE_HOUR = 20     # 8:30 PM
DINNER_CLOSE_MINUTE = 30

TIFFIN_CLOSE_HOUR = 23     # 11:00 PM
TIFFIN_CLOSE_MINUTE = 0


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                room_number TEXT NOT NULL DEFAULT '',
                device_id TEXT NOT NULL DEFAULT '',
                meal_type TEXT NOT NULL,
                meal_date TEXT NOT NULL,
                is_done INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        # Safe migration if table exists without new columns
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(bookings)")
        columns = [row["name"] for row in cur.fetchall()]
        if "room_number" not in columns:
            cur.execute("ALTER TABLE bookings ADD COLUMN room_number TEXT NOT NULL DEFAULT ''")
        if "device_id" not in columns:
            cur.execute("ALTER TABLE bookings ADD COLUMN device_id TEXT NOT NULL DEFAULT ''")
        conn.commit()


IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

def get_ist_now():
    return datetime.datetime.now(IST)


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
        return f"Closed (Cut-off passed)"

    device_bookings = {}
    if device_id:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT meal_type, meal_date, student_name, room_number FROM bookings WHERE device_id = ? AND meal_date IN (?, ?)",
                    (device_id, today_str, tomorrow_str)
                )
                for row in cur.fetchall():
                    key = f"{row['meal_date']}_{row['meal_type']}"
                    device_bookings[key] = {
                        "booked": True,
                        "student_name": row["student_name"],
                        "room_number": row["room_number"],
                        "meal_date": row["meal_date"],
                        "meal_type": row["meal_type"]
                    }
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
                "status_text": get_reason(lunch_open, "09:00 AM", "01:00 PM"),
                "timing": "09:00 AM - 01:00 PM (Today)"
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


class MessRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        # Prevent aggressive browser caching so mobile devices always see fresh data
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            qs = parse_qs(parsed.query)
            dev_id = qs.get("device_id", [None])[0]
            self.send_json_response(200, get_current_status(dev_id))
            return

        if path == "/api/bookings":
            qs = parse_qs(parsed.query)
            date_filter = qs.get("date", [None])[0]
            if not date_filter:
                date_filter = get_ist_now().strftime("%Y-%m-%d")

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, student_name, room_number, meal_type, meal_date, is_done, created_at FROM bookings WHERE meal_date = ? ORDER BY id ASC",
                    (date_filter,)
                )
                rows = [dict(r) for r in cur.fetchall()]

            self.send_json_response(200, {
                "date": date_filter,
                "bookings": rows
            })
            return

        # Fallback to static files
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if path == "/api/bookings":
            self.handle_create_booking(body)
            return

        if path == "/api/bookings/toggle":
            self.handle_toggle_booking(body)
            return

        if path == "/api/bookings/clear":
            self.handle_clear_bookings(body)
            return

        if path == "/api/bookings/delete":
            self.handle_delete_booking(body)
            return

        self.send_json_response(404, {"error": "Endpoint not found"})

    def handle_create_booking(self, body):
        student_name = " ".join((body.get("student_name") or "").strip().split())
        room_number = " ".join((body.get("room_number") or "").strip().upper().split())
        device_id = (body.get("device_id") or "").strip()
        requested_meals = body.get("meals") or []

        if not student_name:
            self.send_json_response(400, {"error": "Student name is required."})
            return

        if len(student_name) < 2:
            self.send_json_response(400, {"error": "Please enter a valid student name."})
            return

        if not room_number:
            self.send_json_response(400, {"error": "Room number is required (e.g. 204 or B-102)."})
            return

        if not device_id:
            self.send_json_response(400, {"error": "Device verification token missing. Please refresh your page."})
            return

        if not requested_meals or not isinstance(requested_meals, list):
            self.send_json_response(400, {"error": "At least one meal option must be selected."})
            return

        status = get_current_status(device_id)
        now_str = get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p")

        # Strict booking window validation
        invalid_meals = []
        for meal in requested_meals:
            meal_key = meal.lower()
            if meal_key not in status["meals"]:
                invalid_meals.append(meal)
            elif not status["meals"][meal_key]["open"]:
                meal_meta = status["meals"][meal_key]
                invalid_meals.append(f"{meal_meta['label']} ({meal_meta['status_text']})")

        if invalid_meals:
            err_msg = f"Booking closed: {', '.join(invalid_meals)}"
            self.send_json_response(400, {"error": err_msg})
            return

        # Anti-Duplication Verifications
        with get_db() as conn:
            cur = conn.cursor()
            for meal in requested_meals:
                meal_key = meal.lower()
                meal_meta = status["meals"][meal_key]
                assigned_date = meal_meta["meal_date"]

                # 1. Phone / Device Check (Strict 1 booking per phone per meal date)
                cur.execute(
                    "SELECT id, student_name, room_number FROM bookings WHERE meal_type = ? AND meal_date = ? AND device_id = ?",
                    (meal_key, assigned_date, device_id)
                )
                dev_existing = cur.fetchone()
                if dev_existing:
                    self.send_json_response(400, {
                        "error": f"This phone has already been used to reserve {meal_meta['label']} for {assigned_date} (for {dev_existing['student_name']}, Room {dev_existing['room_number']}). Only 1 booking per phone is allowed."
                    })
                    return

                # Fetch all existing bookings for this meal and date
                cur.execute(
                    "SELECT id, student_name, room_number FROM bookings WHERE meal_type = ? AND meal_date = ?",
                    (meal_key, assigned_date)
                )
                existing_for_meal = cur.fetchall()

                # 2. Strict Unique Name Check (No names can be repeated for the same meal on the same date)
                for rec in existing_for_meal:
                    rec_name_norm = " ".join(rec["student_name"].lower().split())
                    if rec_name_norm == student_name.lower():
                        self.send_json_response(400, {
                            "error": f"The student name '{student_name}' is already registered for {meal_meta['label']} on {assigned_date} (Room {rec['room_number']}). Duplicate names are strictly not allowed."
                        })
                        return

                # 3. Room Number Check (1 booking per room per meal date)
                for rec in existing_for_meal:
                    rec_room_norm = " ".join(rec["room_number"].upper().split())
                    if rec_room_norm == room_number:
                        self.send_json_response(400, {
                            "error": f"Room {room_number} has already reserved {meal_meta['label']} for {assigned_date} (by {rec['student_name']}). Maximum 1 meal per room is allowed to prevent food wastage."
                        })
                        return

            created_entries = []
            for meal in requested_meals:
                meal_key = meal.lower()
                meal_meta = status["meals"][meal_key]
                assigned_date = meal_meta["meal_date"]
                entry_id = f"bk_{uuid.uuid4().hex[:10]}"

                cur.execute(
                    "INSERT INTO bookings (id, student_name, room_number, device_id, meal_type, meal_date, is_done, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                    (entry_id, student_name, room_number, device_id, meal_key, assigned_date, now_str)
                )
                created_entries.append({
                    "id": entry_id,
                    "student_name": student_name,
                    "room_number": room_number,
                    "meal_type": meal_key,
                    "meal_label": meal_meta["label"],
                    "meal_date": assigned_date,
                    "target_label": meal_meta["target_label"]
                })
            conn.commit()

        self.send_json_response(201, {
            "success": True,
            "student_name": student_name,
            "room_number": room_number,
            "created": created_entries
        })

    def handle_toggle_booking(self, body):
        entry_id = body.get("id")
        is_done = 1 if body.get("is_done") else 0

        if not entry_id:
            self.send_json_response(400, {"error": "Missing booking ID."})
            return

        with get_db() as conn:
            conn.execute("UPDATE bookings SET is_done = ? WHERE id = ?", (is_done, entry_id))
            conn.commit()

        self.send_json_response(200, {"success": True, "id": entry_id, "is_done": is_done})

    def handle_clear_bookings(self, body):
        date_filter = body.get("date")
        with get_db() as conn:
            if date_filter:
                conn.execute("DELETE FROM bookings WHERE meal_date = ?", (date_filter,))
            else:
                conn.execute("DELETE FROM bookings")
            conn.commit()

        self.send_json_response(200, {"success": True})

    def handle_delete_booking(self, body):
        entry_id = body.get("id")
        if not entry_id:
            self.send_json_response(400, {"error": "Missing booking ID."})
            return

        with get_db() as conn:
            conn.execute("DELETE FROM bookings WHERE id = ?", (entry_id,))
            conn.commit()

        self.send_json_response(200, {"success": True, "id": entry_id})

    def send_json_response(self, status_code, data):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_bytes)


def main():
    init_db()
    server_address = (BIND, PORT)
    httpd = ThreadingHTTPServer(server_address, MessRequestHandler)
    print(f"Adarsh Dining Hall Server running at http://{BIND}:{PORT}")
    print(f"Database initialized at: {DB_PATH}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    main()
