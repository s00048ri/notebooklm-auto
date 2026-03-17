"""Web UI server for NotebookLM Auto"""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from .config import Config
from .input_parser import UrlEntry, parse_csv, parse_txt, validate_youtube_url
from .models import BatchResult, NotebookResult

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# Active SSE jobs: job_id -> queue
_jobs: dict[str, queue.Queue] = {}


def _send_event(job_id: str, event: str, data: dict) -> None:
    """Send an SSE event to the client."""
    q = _jobs.get(job_id)
    if q:
        q.put({"event": event, "data": data})


async def _run_job(job_id: str, entries: list[UrlEntry], config: Config) -> None:
    """Run the NotebookLM processing and emit SSE events."""
    from notebooklm import NotebookLMClient

    from .processor import extract_video_id, fetch_video_title

    batch = BatchResult()
    total = len(entries)

    _send_event(job_id, "start", {"total": total})

    try:
        async with await NotebookLMClient.from_storage() as client:
            semaphore = asyncio.Semaphore(config.max_concurrent)

            async def process_one(index: int, entry: UrlEntry) -> NotebookResult:
                async with semaphore:
                    result = NotebookResult(youtube_url=entry.url)
                    start = time.time()

                    try:
                        video_id = extract_video_id(entry.url)
                        title = entry.title if entry.title else await fetch_video_title(entry.url)

                        _send_event(job_id, "progress", {
                            "index": index,
                            "step": "creating",
                            "title": title,
                            "url": entry.url,
                        })

                        nb = await client.notebooks.create(title)
                        result.notebook_id = nb.id
                        result.notebook_title = title

                        _send_event(job_id, "progress", {
                            "index": index,
                            "step": "adding_source",
                            "title": title,
                        })

                        await client.sources.add_url(nb.id, entry.url, wait=True)

                        _send_event(job_id, "progress", {
                            "index": index,
                            "step": "summarizing",
                            "title": title,
                        })

                        chat_result = await client.chat.ask(nb.id, config.summary_prompt)
                        result.summary = chat_result.answer

                        result.share_link = f"https://notebooklm.google.com/notebook/{nb.id}"
                        result.status = "success"

                    except Exception as e:
                        result.status = "error"
                        result.error_message = f"{type(e).__name__}: {e}"

                    result.processing_time = time.time() - start

                    _send_event(job_id, "result", {
                        "index": index,
                        "url": result.youtube_url,
                        "title": result.notebook_title,
                        "summary": result.summary,
                        "share_link": result.share_link,
                        "status": result.status,
                        "error": result.error_message or "",
                        "time": round(result.processing_time, 1),
                    })

                    return result

            tasks = [process_one(i, entry) for i, entry in enumerate(entries)]
            batch.results = await asyncio.gather(*tasks)

    except Exception as e:
        _send_event(job_id, "error", {"message": f"{type(e).__name__}: {e}"})
        return

    _send_event(job_id, "done", {
        "total": batch.total,
        "successful": batch.successful,
        "failed": batch.failed,
    })


def _run_in_thread(job_id: str, entries: list[UrlEntry], config: Config) -> None:
    """Run the async job in a new thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_job(job_id, entries, config))
    finally:
        loop.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/start", methods=["POST"])
def start_job():
    data = request.get_json()
    urls_text = data.get("urls", "").strip()
    prompt = data.get("prompt", "").strip()
    lang = data.get("lang", "ja")

    if not urls_text:
        return jsonify({"error": "URLが入力されていません"}), 400

    # Parse URLs: each line can be "url" or "title,url" or "url,title"
    entries: list[UrlEntry] = []
    for line in urls_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Try CSV-like: title, url or url, title
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            # Find which part is the URL
            if validate_youtube_url(parts[0]):
                entries.append(UrlEntry(url=parts[0], title=",".join(parts[1:])))
            elif validate_youtube_url(parts[-1]):
                entries.append(UrlEntry(url=parts[-1], title=",".join(parts[:-1])))
            else:
                # Try first part anyway
                if validate_youtube_url(parts[0]):
                    entries.append(UrlEntry(url=parts[0], title=""))
        elif validate_youtube_url(line):
            entries.append(UrlEntry(url=line, title=""))

    if not entries:
        return jsonify({"error": "有効なYouTube URLが見つかりませんでした"}), 400

    config = Config.load()
    if prompt:
        config.summary_prompt = prompt
    elif lang == "en":
        config.summary_prompt = "Summarize the key points of this video in English"

    job_id = str(uuid.uuid4())
    _jobs[job_id] = queue.Queue()

    thread = threading.Thread(target=_run_in_thread, args=(job_id, entries, config), daemon=True)
    thread.start()

    return jsonify({
        "job_id": job_id,
        "total": len(entries),
        "entries": [{"url": e.url, "title": e.title} for e in entries],
    })


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Handle CSV/TXT file upload and return parsed entries."""
    if "file" not in request.files:
        return jsonify({"error": "ファイルが選択されていません"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "ファイルが選択されていません"}), 400

    import tempfile
    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb") as tmp:
        file.save(tmp)
        tmp_path = Path(tmp.name)

    try:
        if suffix == ".csv":
            entries = parse_csv(tmp_path)
        else:
            entries = parse_txt(tmp_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        tmp_path.unlink(missing_ok=True)

    lines = []
    for e in entries:
        if e.title:
            lines.append(f"{e.title}, {e.url}")
        else:
            lines.append(e.url)

    return jsonify({"text": "\n".join(lines), "count": len(entries)})


@app.route("/api/stream/<job_id>")
def stream(job_id: str):
    """SSE endpoint for real-time progress."""
    q = _jobs.get(job_id)
    if not q:
        return jsonify({"error": "Job not found"}), 404

    def generate():
        while True:
            try:
                msg = q.get(timeout=300)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'], ensure_ascii=False)}\n\n"
                if msg["event"] in ("done", "error"):
                    # Cleanup
                    _jobs.pop(job_id, None)
                    break
            except queue.Empty:
                yield "event: ping\ndata: {}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Start the web UI server."""
    print(f"\n  NotebookLM Auto - Web UI")
    print(f"  http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_server(debug=True)
