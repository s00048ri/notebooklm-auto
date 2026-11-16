from __future__ import annotations

import sys

import pytest

from notebooklm_auto import main
from notebooklm_auto.models import BatchResult, NotebookResult


@pytest.fixture
def run_cli(monkeypatch, tmp_path):
    """process_all_urls を差し替えて cli_main を実行するヘルパー"""
    captured = {}

    async def fake_process_all_urls(entries, config):
        captured["entries"] = entries
        captured["config"] = config
        return BatchResult(
            results=[NotebookResult(e.url, status="success", share_link="L") for e in entries]
        )

    monkeypatch.setattr(main, "process_all_urls", fake_process_all_urls)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"output_dir: {tmp_path / 'out'}\noutput_format: json\n", encoding="utf-8")

    def _run(*args: str):
        monkeypatch.setattr(sys, "argv", ["notebooklm-auto", "--config", str(config_path), *args])
        main.cli_main()
        return captured

    return _run


def test_parser_requires_file_or_urls():
    parser = main.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
    with pytest.raises(SystemExit):
        parser.parse_args(["--file", "a.txt", "--urls", "https://youtu.be/a"])


def test_parser_rejects_unknown_output_format():
    with pytest.raises(SystemExit):
        main.build_parser().parse_args(["-u", "https://youtu.be/a", "-o", "xml"])


def test_cli_with_urls_and_overrides(run_cli, tmp_path):
    out_dir = tmp_path / "custom"

    captured = run_cli(
        "--urls", "https://youtu.be/a", "invalid",
        "--prompt", "英語で要約",
        "--output-format", "markdown",
        "--output-dir", str(out_dir),
    )

    assert [e.url for e in captured["entries"]] == ["https://youtu.be/a"]
    assert captured["config"].summary_prompt == "英語で要約"
    assert captured["config"].output_format == "markdown"
    assert len(list(out_dir.glob("results_*.md"))) == 1


def test_cli_with_file_uses_config(run_cli, tmp_path):
    url_file = tmp_path / "urls.csv"
    url_file.write_text("title,url\nTalk,https://youtu.be/a\n", encoding="utf-8")

    captured = run_cli("--file", str(url_file))

    assert captured["entries"][0].title == "Talk"
    assert len(list((tmp_path / "out").glob("results_*.json"))) == 1


def test_cli_exits_when_no_valid_urls(run_cli):
    with pytest.raises(SystemExit) as exc:
        run_cli("--urls", "not-a-url")
    assert exc.value.code == 1


def test_cli_exits_when_processing_fails(run_cli, monkeypatch, tmp_path):
    async def boom(entries, config):
        raise RuntimeError("fatal")

    monkeypatch.setattr(main, "process_all_urls", boom)

    with pytest.raises(SystemExit) as exc:
        run_cli("--urls", "https://youtu.be/a")
    assert exc.value.code == 1
    assert not (tmp_path / "out").exists()
