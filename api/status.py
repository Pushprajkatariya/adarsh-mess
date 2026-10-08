from _helpers import ApiHandler, get_current_status
from urllib.parse import urlparse, parse_qs


class handler(ApiHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        dev_id = qs.get("device_id", [None])[0]
        self.send_json(200, get_current_status(dev_id))
