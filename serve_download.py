"""Tiny download server for FoodLabelReader.zip (dev sandbox convenience only)."""
import http.server
import os

PORT = 3000
ROOT = os.path.dirname(os.path.abspath(__file__))
ZIP_NAME = "FoodLabelReader.zip"

PAGE = """<!doctype html>
<html style="background:#0a0a0a">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FoodLabelReader — Download</title>
<style>
  body { margin:0; font-family:system-ui,-apple-system,sans-serif; background:#0a0a0a; color:#fafafa;
         min-height:100vh; display:flex; align-items:center; justify-content:center; }
  main { text-align:center; padding:2rem; max-width:28rem; }
  h1 { font-size:1.5rem; margin:0 0 0.5rem; }
  p { color:#a1a1aa; line-height:1.5; margin:0 0 1.5rem; }
  a.btn { display:inline-block; background:#fafafa; color:#0a0a0a; font-weight:600;
          padding:0.75rem 1.5rem; border-radius:0.5rem; text-decoration:none; }
  a.btn:hover { background:#e4e4e7; }
  .meta { margin-top:1rem; font-size:0.8rem; color:#71717a; }
</style>
</head>
<body>
<main>
  <h1>FoodLabelReader Backend</h1>
  <p>Complete FastAPI OCR backend &mdash; versioned API, lazy PaddleOCR engine, DI, centralized errors, and 13 passing tests.</p>
  <a class="btn" href="/FoodLabelReader.zip" download>Download FoodLabelReader.zip</a>
  <div class="meta">33 files &middot; ~27 KB &middot; backend/ + .gitignore</div>
</main>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" + ZIP_NAME:
            zip_path = os.path.join(ROOT, ZIP_NAME)
            with open(zip_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{ZIP_NAME}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):  # keep logs quiet
        pass


if __name__ == "__main__":
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler) as server:
        print(f"Serving download page on port {PORT}")
        server.serve_forever()
