from _helpers import ApiHandler, get_db, q


class handler(ApiHandler):
    def do_POST(self):
        body = self.read_json_body()
        entry_id = body.get("id")

        if not entry_id:
            self.send_json(400, {"error": "Missing booking ID."}); return

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(q("DELETE FROM bookings WHERE id=?"), (entry_id,))

        self.send_json(200, {"success": True, "id": entry_id})
