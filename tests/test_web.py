from __future__ import annotations

import asyncio
import io
import json
import queue

import pytest

from notebooklm_auto import web
from notebooklm_auto.config import Config
from notebooklm_auto.input_parser import UrlEntry


@pytest.fixture
def client():
    web.app.config["TESTING"] = True
    with web.app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_jobs():
    web._jobs.clear()
    yield
    web._jobs.clear()


@pytest.fixture
def started_jobs(monkeypatch):
    """バックグラウンドスレッドを起動せず、渡された引数だけ記録する"""
    jobs = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            jobs.append(args)

        def start(self):
            pass

    monkeypatch.setattr(web.threading, "Thread", FakeThread)
    monkeypatch.setattr(web.Config, "load", classmethod(lambda cls, path=None: Config()))
    return jobs


def _sse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<html" in resp.data.lower()


def test_start_requires_urls(client, started_jobs):
    resp = client.post("/api/start", json={"urls": "   "})
    assert resp.status_code == 400
    assert started_jobs == []


def test_start_rejects_when_no_valid_urls(client, started_jobs):
    resp = client.post("/api/start", json={"urls": "foo\nhttps://example.com/x"})
    assert resp.status_code == 400
    assert started_jobs == []


def test_start_parses_lines(client, started_jobs):
    urls = "\n".join(
        [
            "# comment",
            "https://youtu.be/plain",
            "Title A, https://youtu.be/a",
            "https://youtu.be/b, Title B",
            "Title, with comma, https://youtu.be/c",
            "garbage, more garbage",
            "",
        ]
    )

    resp = client.post("/api/start", json={"urls": urls})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 4
    assert data["entries"] == [
        {"url": "https://youtu.be/plain", "title": ""},
        {"url": "https://youtu.be/a", "title": "Title A"},
        {"url": "https://youtu.be/b", "title": "Title B"},
        {"url": "https://youtu.be/c", "title": "Title,with comma"},
    ]
    assert data["job_id"] in web._jobs
    job_id, entries, config = started_jobs[0]
    assert job_id == data["job_id"]
    assert len(entries) == 4


@pytest.mark.parametrize(
    ("payload", "expected_prompt"),
    [
        ({}, Config().summary_prompt),
        ({"lang": "en"}, "Summarize the key points of this video in English"),
        ({"lang": "en", "prompt": "  Custom  "}, "Custom"),
    ],
)
def test_start_prompt_selection(client, started_jobs, payload, expected_prompt):
    resp = client.post("/api/start", json={"urls": "https://youtu.be/a", **payload})
    assert resp.status_code == 200
    assert started_jobs[0][2].summary_prompt == expected_prompt


def test_upload_requires_file(client):
    assert client.post("/api/upload", data={}).status_code == 400
    resp = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b""), "")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_upload_csv(client):
    content = "Session Title,YouTube URL\nTalk,https://youtu.be/a\n,https://youtu.be/b\n"
    resp = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(content.encode()), "list.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json() == {"text": "Talk, https://youtu.be/a\nhttps://youtu.be/b", "count": 2}


def test_upload_txt(client):
    resp = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"# c\nhttps://youtu.be/a\n"), "urls.txt")},
        content_type="multipart/form-data",
    )
    assert resp.get_json() == {"text": "https://youtu.be/a", "count": 1}


def test_upload_csv_without_url_column(client):
    resp = client.post(
        "/api/upload",
        data={"file": (io.BytesIO(b"a,b\n1,2\n"), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "URL" in resp.get_json()["error"]


def test_stream_unknown_job(client):
    assert client.get("/api/stream/nope").status_code == 404


def test_stream_emits_events_and_cleans_up(client):
    q = queue.Queue()
    web._jobs["job1"] = q
    q.put({"event": "start", "data": {"total": 1}})
    q.put({"event": "done", "data": {"total": 1, "successful": 1, "failed": 0}})

    resp = client.get("/api/stream/job1")

    assert resp.mimetype == "text/event-stream"
    events = _sse_events(resp.get_data(as_text=True))
    assert [e[0] for e in events] == ["start", "done"]
    assert "job1" not in web._jobs


def _drain(q: queue.Queue) -> list[dict]:
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def test_run_job_success(fake_notebooklm):
    web._jobs["j"] = queue.Queue()
    entries = [UrlEntry("https://youtu.be/a", "A"), UrlEntry("https://youtu.be/b", "B")]

    asyncio.run(web._run_job("j", entries, Config()))

    events = _drain(web._jobs["j"])
    names = [e["event"] for e in events]
    assert names[0] == "start"
    assert names[-1] == "done"
    assert names.count("result") == 2
    assert events[-1]["data"] == {"total": 2, "successful": 2, "failed": 0}
    results = [e["data"] for e in events if e["event"] == "result"]
    assert {r["status"] for r in results} == {"success"}
    assert all(r["share_link"] for r in results)
    steps = [e["data"]["step"] for e in events if e["event"] == "progress" and e["data"]["index"] == 0]
    assert steps == ["creating", "adding_source", "summarizing"]


def test_run_job_item_error(fake_notebooklm):
    fake_notebooklm.client.notebooks.create.side_effect = RuntimeError("quota")
    web._jobs["j"] = queue.Queue()

    asyncio.run(web._run_job("j", [UrlEntry("https://youtu.be/a", "A")], Config()))

    events = _drain(web._jobs["j"])
    result = next(e["data"] for e in events if e["event"] == "result")
    assert result["status"] == "error"
    assert result["error"] == "RuntimeError: quota"
    assert events[-1]["data"]["failed"] == 1


def test_run_job_fatal_error(fake_notebooklm):
    fake_notebooklm.storage_error = RuntimeError("no auth")
    web._jobs["j"] = queue.Queue()

    asyncio.run(web._run_job("j", [UrlEntry("https://youtu.be/a", "A")], Config()))

    events = _drain(web._jobs["j"])
    assert [e["event"] for e in events] == ["start", "error"]
    assert events[-1]["data"]["message"] == "RuntimeError: no auth"


def test_send_event_ignores_unknown_job():
    web._send_event("missing", "start", {})  # 例外にならないこと
