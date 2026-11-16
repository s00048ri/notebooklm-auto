from __future__ import annotations

import asyncio
import io
import json
import urllib.request

import pytest

from notebooklm_auto import processor
from notebooklm_auto.config import Config
from notebooklm_auto.input_parser import UrlEntry


@pytest.mark.parametrize(
    ("url", "video_id"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?list=PL1&v=abc123&t=10", "abc123"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=xyz", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/short1", "short1"),
        ("https://www.youtube.com/live/live1?si=xyz", "live1"),
        ("https://www.youtube.com/watch", "unknown"),
    ],
)
def test_extract_video_id(url, video_id):
    assert processor.extract_video_id(url) == video_id


def test_fetch_video_title_success(monkeypatch):
    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        return _Resp(json.dumps({"title": "動画タイトル"}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    title = asyncio.run(processor.fetch_video_title("https://youtu.be/abc"))

    assert title == "動画タイトル"
    assert seen["url"].startswith("https://www.youtube.com/oembed?url=https%3A%2F%2Fyoutu.be%2Fabc")


def test_fetch_video_title_falls_back_to_video_id():
    # conftest の _no_network でネットワークは常に失敗する
    assert asyncio.run(processor.fetch_video_title("https://youtu.be/abc")) == "abc"


def test_process_single_url_success_uses_given_title(fake_client):
    config = Config(summary_prompt="要約して")
    entry = UrlEntry(url="https://youtu.be/abc", title="手動タイトル")

    result = asyncio.run(processor.process_single_url(fake_client, entry, config))

    assert result.status == "success"
    assert result.error_message is None
    assert result.notebook_id == "nb-123"
    assert result.notebook_title == "手動タイトル"
    assert result.summary == "要約テキスト"
    assert result.share_link == "https://notebooklm.google.com/notebook/nb-123?share=1"
    assert result.processing_time >= 0

    fake_client.notebooks.create.assert_awaited_once_with("手動タイトル")
    fake_client.sources.add_url.assert_awaited_once_with("nb-123", "https://youtu.be/abc", wait=True)
    fake_client.chat.ask.assert_awaited_once_with("nb-123", "要約して")
    fake_client.sharing.set_public.assert_awaited_once_with("nb-123", True)


def test_process_single_url_fetches_title_when_missing(fake_client, monkeypatch):
    async def fake_title(url):
        return "取得したタイトル"

    monkeypatch.setattr(processor, "fetch_video_title", fake_title)

    result = asyncio.run(
        processor.process_single_url(fake_client, UrlEntry("https://youtu.be/abc", ""), Config())
    )

    assert result.notebook_title == "取得したタイトル"
    fake_client.notebooks.create.assert_awaited_once_with("取得したタイトル")


def test_process_single_url_share_link_fallback(fake_client):
    fake_client.sharing.get_status.return_value.share_url = None

    result = asyncio.run(
        processor.process_single_url(fake_client, UrlEntry("https://youtu.be/abc", "T"), Config())
    )

    assert result.share_link == "https://notebooklm.google.com/notebook/nb-123"


def test_process_single_url_error_is_captured(fake_client):
    fake_client.sources.add_url.side_effect = RuntimeError("source failed")

    result = asyncio.run(
        processor.process_single_url(fake_client, UrlEntry("https://youtu.be/abc", "T"), Config())
    )

    assert result.status == "error"
    assert result.error_message == "RuntimeError: source failed"
    assert result.notebook_id == "nb-123"  # 作成済みのIDは残る
    assert result.summary == ""
    fake_client.chat.ask.assert_not_awaited()


def test_process_all_urls(fake_notebooklm):
    entries = [UrlEntry(f"https://youtu.be/v{i}", f"T{i}") for i in range(3)]

    batch = asyncio.run(processor.process_all_urls(entries, Config(max_concurrent=2)))

    assert batch.total == 3
    assert batch.successful == 3
    assert [r.youtube_url for r in batch.results] == [e.url for e in entries]


def test_process_all_urls_respects_max_concurrent(fake_notebooklm):
    running = 0
    peak = 0

    async def slow_add_url(*args, **kwargs):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1

    fake_notebooklm.client.sources.add_url.side_effect = slow_add_url
    entries = [UrlEntry(f"https://youtu.be/v{i}", "T") for i in range(6)]

    asyncio.run(processor.process_all_urls(entries, Config(max_concurrent=2)))

    assert peak == 2


def test_process_all_urls_mixed_results(fake_notebooklm):
    calls = 0

    async def flaky_ask(nb_id, prompt):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("chat failed")
        from types import SimpleNamespace

        return SimpleNamespace(answer="ok")

    fake_notebooklm.client.chat.ask.side_effect = flaky_ask
    entries = [UrlEntry(f"https://youtu.be/v{i}", "T") for i in range(3)]

    batch = asyncio.run(processor.process_all_urls(entries, Config(max_concurrent=1)))

    assert (batch.successful, batch.failed) == (2, 1)
    assert batch.results[1].error_message == "ValueError: chat failed"


def test_process_all_urls_auth_error_shows_login_hint(fake_notebooklm, capsys):
    fake_notebooklm.storage_error = RuntimeError("Please run login first")

    with pytest.raises(RuntimeError):
        asyncio.run(processor.process_all_urls([UrlEntry("https://youtu.be/a", "")], Config()))

    assert "notebooklm login" in capsys.readouterr().out


def test_process_all_urls_other_fatal_error(fake_notebooklm, capsys):
    fake_notebooklm.storage_error = ConnectionError("network down")

    with pytest.raises(ConnectionError):
        asyncio.run(processor.process_all_urls([UrlEntry("https://youtu.be/a", "")], Config()))

    out = capsys.readouterr().out
    assert "致命的エラー" in out
    assert "notebooklm login" not in out


def test_process_single_url_reports_steps(fake_client):
    steps = []

    asyncio.run(
        processor.process_single_url(
            fake_client,
            UrlEntry("https://youtu.be/abc", "T"),
            Config(),
            on_step=lambda step, title: steps.append((step, title)),
        )
    )

    assert steps == [
        ("creating", "T"),
        ("adding_source", "T"),
        ("summarizing", "T"),
        ("sharing", "T"),
    ]


def test_process_single_url_stops_reporting_after_error(fake_client):
    fake_client.chat.ask.side_effect = RuntimeError("chat failed")
    steps = []

    asyncio.run(
        processor.process_single_url(
            fake_client,
            UrlEntry("https://youtu.be/abc", "T"),
            Config(),
            on_step=lambda step, title: steps.append(step),
        )
    )

    assert steps == ["creating", "adding_source", "summarizing"]


def test_process_all_urls_callbacks_carry_index(fake_notebooklm):
    entries = [UrlEntry(f"https://youtu.be/v{i}", f"T{i}") for i in range(3)]
    steps: list[tuple[int, str, str]] = []
    results: dict[int, str] = {}

    batch = asyncio.run(
        processor.process_all_urls(
            entries,
            Config(max_concurrent=2),
            on_step=lambda i, step, title: steps.append((i, step, title)),
            on_result=lambda i, r: results.__setitem__(i, r.youtube_url),
        )
    )

    assert results == {i: e.url for i, e in enumerate(entries)}
    assert len(steps) == 3 * 4
    for i in range(3):
        assert [s for idx, s, _ in steps if idx == i] == [
            "creating", "adding_source", "summarizing", "sharing"
        ]
        assert {t for idx, _, t in steps if idx == i} == {f"T{i}"}
    assert batch.successful == 3
