"""Bounded HTTP workload shared by the local container measurements."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

CGROUP = Path("/sys/fs/cgroup")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            result = {"ready": True}
        elif self.path == "/metrics":
            result = {}
            for name in ("cpu.stat", "cpu.max", "memory.current", "memory.peak", "memory.events"):
                path = CGROUP / name
                if path.is_file():
                    result[name] = path.read_text().strip()
        elif self.path == "/work":
            digest = hashlib.pbkdf2_hmac("sha256", b"fixed-input", b"fixed-salt", 70000)
            result = {"ok": True, "digest": digest.hex()}
        else:
            self.send_error(404)
            return
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
