import uuid
from _helpers import ApiHandler, get_db, get_current_status, get_ist_now, fetchall, fetchone, q
from urllib.parse import urlparse, parse_qs


class handler(ApiHandler):
    # -------------------------------------------------------------------
    # GET /api/bookings?view=active  or  ?date=YYYY-MM-DD
    # -------------------------------------------------------------------
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        date_filter = qs.get("date", [None])[0]

        now = get_ist_now()
        today_str    = now.strftime("%Y-%m-%d")
        tomorrow_str = (now.replace(hour=0, minute=0, second=0, microsecond=0)
                        + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")

        with get_db() as conn:
            cur = conn.cursor()
            if date_filter and date_filter != "active":
                cur.execute(q(
                    "SELECT id, student_name, room_number, meal_type, meal_date, is_done, created_at "
                    "FROM bookings WHERE meal_date=? ORDER BY id ASC"
                ), (date_filter,))
                rows = fetchall(cur)
                resp_date = date_filter
            else:
                cur.execute(q("""
                    SELECT id, student_name, room_number, meal_type, meal_date, is_done, created_at
                    FROM bookings
                    WHERE (meal_type='tiffin' AND meal_date=?)
                       OR (meal_type IN ('lunch','dinner') AND meal_date=?)
                    ORDER BY id ASC
                """), (tomorrow_str, today_str))
                rows = fetchall(cur)
                resp_date = "active"

        self.send_json(200, {
            "date": resp_date,
            "today": today_str,
            "tomorrow": tomorrow_str,
            "bookings": rows
        })

    # -------------------------------------------------------------------
    # POST /api/bookings  — create booking
    # -------------------------------------------------------------------
    def do_POST(self):
        body = self.read_json_body()

        student_name = " ".join((body.get("student_name") or "").strip().split())
        room_number  = " ".join((body.get("room_number")  or "").strip().upper().split())
        device_id    = (body.get("device_id") or "").strip()
        requested_meals = body.get("meals") or []

        if not student_name:
            self.send_json(400, {"error": "Student name is required."}); return
        if len(student_name) < 2:
            self.send_json(400, {"error": "Please enter a valid student name."}); return
        if not room_number:
            self.send_json(400, {"error": "Room number is required (e.g. 204 or B-102)."}); return
        if not device_id:
            self.send_json(400, {"error": "Device verification token missing. Please refresh your page."}); return
        if not requested_meals or not isinstance(requested_meals, list):
            self.send_json(400, {"error": "At least one meal option must be selected."}); return

        status = get_current_status(device_id)
        now_str = get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p")

        # Validate booking windows
        invalid_meals = []
        for meal in requested_meals:
            key = meal.lower()
            if key not in status["meals"]:
                invalid_meals.append(meal)
            elif not status["meals"][key]["open"]:
                m = status["meals"][key]
                invalid_meals.append(f"{m['label']} ({m['status_text']})")
        if invalid_meals:
            self.send_json(400, {"error": f"Booking closed: {', '.join(invalid_meals)}"}); return

        with get_db() as conn:
            cur = conn.cursor()
            # Pre-checks
            for meal in requested_meals:
                key  = meal.lower()
                meta = status["meals"][key]
                date = meta["meal_date"]

                # 1. Device/phone check
                cur.execute(q(
                    "SELECT id, student_name, room_number FROM bookings WHERE meal_type=? AND meal_date=? AND device_id=?"
                ), (key, date, device_id))
                existing = fetchone(cur)
                if existing:
                    self.send_json(400, {
                        "error": f"This phone has already booked {meta['label']} for {date} "
                                 f"(for {existing['student_name']}, Room {existing['room_number']}). "
                                 f"Only 1 booking per phone is allowed."
                    }); return

                # 2. Unique name check
                cur.execute(q(
                    "SELECT student_name, room_number FROM bookings WHERE meal_type=? AND meal_date=?"
                ), (key, date))
                for rec in fetchall(cur):
                    if " ".join(rec["student_name"].lower().split()) == student_name.lower():
                        self.send_json(400, {
                            "error": f"The name '{student_name}' is already registered for "
                                     f"{meta['label']} on {date} (Room {rec['room_number']}). "
                                     f"Duplicate names are not allowed."
                        }); return

            # Insert
            created = []
            for meal in requested_meals:
                key  = meal.lower()
                meta = status["meals"][key]
                date = meta["meal_date"]
                eid  = f"bk_{uuid.uuid4().hex[:10]}"
                cur.execute(q(
                    "INSERT INTO bookings (id, student_name, room_number, device_id, meal_type, meal_date, is_done, created_at) "
                    "VALUES (?,?,?,?,?,?,0,?)"
                ), (eid, student_name, room_number, device_id, key, date, now_str))
                created.append({
                    "id": eid, "student_name": student_name, "room_number": room_number,
                    "meal_type": key, "meal_label": meta["label"],
                    "meal_date": date, "target_label": meta["target_label"]
                })

        self.send_json(201, {
            "success": True, "student_name": student_name,
            "room_number": room_number, "created": created
        })
