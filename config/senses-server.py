"""
senses-server.py — local HTTP sidecar for the sense-toggle UI.

Binds 127.0.0.1:7899. Exposes:
  GET  /senses   -> current config/senses.json (or defaults)
  POST /senses   -> atomic-write config/senses.json from JSON body

web-face.html (served from file://) posts here to persist toggle state.
Readers (vision.py, listener.py, speak.py, face-engine.py) fail-open if
the file is missing or malformed, so this sidecar is optional.

Start manually: `python config/senses-server.py`
face-engine auto-spawns one on launch if 7899 is free.
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENSES_FILE = ROOT / "config" / "senses.json"

DEFAULTS = {
    "schema_version": 1,
    "eyes": True,
    "ears": True,
    "voice": True,
    "voice_elevenlabs": True,
    "updated_at": None,
    "updated_by": "defaults",
}


def _read():
    try:
        with open(SENSES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return dict(DEFAULTS)


def _write_atomic(payload):
    SENSES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(SENSES_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, SENSES_FILE)


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] != "/senses":
            self.send_error(404)
            return
        body = json.dumps(_read()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] != "/senses":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(raw)
            clean = {
                "schema_version": 1,
                "eyes": bool(payload.get("eyes", True)),
                "ears": bool(payload.get("ears", True)),
                "voice": bool(payload.get("voice", True)),
                "voice_elevenlabs": bool(payload.get("voice_elevenlabs", True)),
                "updated_at": payload.get("updated_at") or time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "updated_by": payload.get("updated_by") or "web-face",
            }
            _write_atomic(clean)
        except Exception as e:
            self.send_response(500)
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, fmt, *args):
        return  # Quiet. Uncomment for debug.


def main():
    host, port = "127.0.0.1", 7899
    try:
        srv = HTTPServer((host, port), Handler)
    except OSError as e:
        print(f"[senses-server] bind failed ({e}) — likely already running", flush=True)
        sys.exit(0)
    print(f"[senses-server] listening on http://{host}:{port}/senses", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[senses-server] stopped", flush=True)


if __name__ == "__main__":
    main()
