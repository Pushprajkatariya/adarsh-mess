from _helpers import ApiHandler, get_db, q


class handler(ApiHandler):
    def do_POST(self):
        body = self.read_json_body()
        date_filter = body.get("date")

        with get_db() as conn:
            cur = conn.cursor()
            if date_filter:
                cur.execute(q("DELETE FROM bookings WHERE meal_date=?"), (date_filter,))
            else:
                cur.execute("DELETE FROM bookings")

        self.send_json(200, {"success": True})
