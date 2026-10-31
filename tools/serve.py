#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Local development server for an HTML5 package of the UnrealEngine-WebGPU fork.

The page needs three things from the server:
- cross-origin isolation (COOP/COEP), without which the browser offers no shared memory and no threads;
- HTTP byte ranges (206 Partial Content), used to stream the pak/IoStore containers listed in HTML5Content.txt;
- application/wasm for the WebAssembly.

Usage: python serve.py PACKAGE_DIR [PORT]   (PACKAGE_DIR is the folder that holds HTML5Content.txt)
Then open http://127.0.0.1:PORT/<Project>/Binaries/HTML5/<Project>-HTML5-<Configuration>.html

Development only: it listens on 127.0.0.1 and disables caching. Public hosting must use HTTPS.
"""
import http.server
import os
import re
import socketserver
import sys

TYPES = {".wasm": "application/wasm", ".js": "text/javascript", ".mjs": "text/javascript", ".html": "text/html",
         ".json": "application/json", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml"}


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def guess_type(self, path):
        return TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")

    def send_head(self):
        header = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not header or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        match = re.match(r"bytes=(\d*)-(\d*)$", header.strip())
        if not match or not (match.group(1) or match.group(2)):
            self.send_error(416)
            return None
        if match.group(1):
            start = int(match.group(1))
            end = min(int(match.group(2)) if match.group(2) else size - 1, size - 1)
        else:
            start, end = max(0, size - int(match.group(2))), size - 1
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self.remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            block = source.read(min(1 << 20, remaining))
            if not block:
                break
            outputfile.write(block)
            remaining -= len(block)
        self.remaining = None

    def log_message(self, *args):
        pass


def main():
    if len(sys.argv) not in (2, 3) or not os.path.isfile(os.path.join(sys.argv[1], "HTML5Content.txt")):
        print(__doc__)
        return 2
    port = int(sys.argv[2]) if len(sys.argv) == 3 else 8000
    os.chdir(sys.argv[1])
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as server:
        print(f"Serving {os.getcwd()} at http://127.0.0.1:{port}/ (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
