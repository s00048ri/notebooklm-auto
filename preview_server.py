"""Simple markdown preview server"""
import http.server
import markdown
from pathlib import Path

MD_FILE = Path(__file__).parent / "note_article_draft.md"
PORT = 8787

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Note Article Preview</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans', sans-serif;
    max-width: 780px;
    margin: 0 auto;
    padding: 40px 24px;
    background: #fff;
    color: #333;
    line-height: 1.9;
    font-size: 16px;
  }
  h1 { font-size: 28px; margin-top: 48px; margin-bottom: 16px; border-bottom: 2px solid #eee; padding-bottom: 8px; }
  h2 { font-size: 22px; margin-top: 40px; margin-bottom: 12px; }
  h3 { font-size: 18px; margin-top: 32px; margin-bottom: 8px; }
  p { margin-bottom: 16px; }
  code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-size: 14px; }
  pre { background: #1e1e2e; color: #cdd6f4; padding: 16px 20px; border-radius: 8px; overflow-x: auto; margin: 16px 0; }
  pre code { background: none; padding: 0; color: inherit; font-size: 13px; }
  blockquote { border-left: 4px solid #6366f1; margin: 16px 0; padding: 8px 16px; background: #f8f8ff; color: #555; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; }
  th, td { border: 1px solid #ddd; padding: 10px 14px; text-align: left; font-size: 14px; }
  th { background: #f8f9fa; font-weight: 600; }
  hr { border: none; border-top: 1px solid #eee; margin: 32px 0; }
  a { color: #6366f1; }
  ul, ol { margin-bottom: 16px; padding-left: 24px; }
  li { margin-bottom: 6px; }
  strong { font-weight: 700; }
  .header-bar { background: #6366f1; color: #fff; padding: 12px 20px; border-radius: 8px; margin-bottom: 32px; font-size: 13px; }
</style>
</head>
<body>
<div class="header-bar">Note Article Preview &mdash; note_article_draft.md</div>
CONTENT
</body>
</html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        md_text = MD_FILE.read_text(encoding="utf-8")
        html_content = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
        page = HTML_TEMPLATE.replace("CONTENT", html_content)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"Preview: http://localhost:{PORT}")
    http.server.HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
