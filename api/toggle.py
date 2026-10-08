from _helpers import ApiHandler, get_db, q


class handler(ApiHandler):
    def do_POST(self):
        body = self.read_json_body()
        entry_id = body.get("id")
        is_done  = 1 if body.get("is_done") else 0

        if not entry_id:
            self.send_json(400, {"error": "Missing booking ID."}); return

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(q("UPDATE bookings SET is_done=? WHERE id=?"), (is_done, entry_id))

        self.send_json(200, {"success": True, "id": entry_id, "is_done": is_done})
