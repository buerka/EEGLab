"""Makers Python Handler: all /api/* routes share the existing backend code."""
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / '_vendor'))
from app.cloud_api import dispatch


class handler(BaseHTTPRequestHandler):
    def _handle(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = -1
        if length < 0 or length > 8192:
            self.send_response(413 if length > 8192 else 400)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        status, headers, body = dispatch(
            self.command, self.path, dict(self.headers), self.rfile.read(length)
        )
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    do_GET = do_POST = do_OPTIONS = do_HEAD = do_PUT = do_DELETE = _handle
