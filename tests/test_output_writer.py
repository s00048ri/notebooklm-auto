from __future__ import annotations

import csv
import json

import pytest

from notebooklm_auto import output_writer
from notebooklm_auto.models import BatchResult, NotebookResult


@pytest.fixture
def batch() -> BatchResult:
    return BatchResult(
        run_timestamp="2026-01-01T00:00:00",
        results=[
            NotebookResult(
                youtube_url="https://youtu.be/aaa",
                notebook_id="nb1",
                notebook_title="動画A, カンマ入り",
                summary="1行目\n2行目",
                share_link="https://notebooklm.google.com/notebook/nb1",
                status="success",
                processing_time=12.345,
            ),
            NotebookResult(
                youtube_url="https://youtu.be/bbb",
                status="error",
                error_message="RuntimeError: boom",
                processing_time=1.0,
            ),
        ],
    )


def test_write_json(batch, tmp_path):
    path = output_writer.write_json(batch, tmp_path)

    assert path.suffix == ".json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_timestamp"] == "2026-01-01T00:00:00"
    assert data["results"][0]["notebook_title"] == "動画A, カンマ入り"
    assert data["results"][1]["error_message"] == "RuntimeError: boom"
    # 日本語がエスケープされずに書かれていること
    assert "動画A" in path.read_text(encoding="utf-8")


def test_write_csv(batch, tmp_path):
    path = output_writer.write_csv(batch, tmp_path)

    assert path.suffix == ".csv"
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert "notebook_id" not in rows[0]
    assert rows[0]["notebook_title"] == "動画A, カンマ入り"
    assert rows[0]["summary"] == "1行目\n2行目"
    assert rows[0]["status"] == "success"
    assert rows[1]["error_message"] == "RuntimeError: boom"
    assert rows[0]["error_message"] == ""


def test_write_markdown(batch, tmp_path):
    path = output_writer.write_markdown(batch, tmp_path)

    text = path.read_text(encoding="utf-8")
    assert path.suffix == ".md"
    assert "合計: 2 件 (成功: 1, 失敗: 1)" in text
    assert "## 動画A, カンマ入り" in text
    assert "## https://youtu.be/bbb" in text  # タイトルが無ければURLを見出しに
    assert "- **共有リンク**: https://notebooklm.google.com/notebook/nb1" in text
    assert "- **処理時間**: 12.3秒" in text
    assert "### 要約\n\n1行目\n2行目" in text
    assert "```\nRuntimeError: boom\n```" in text
    # 失敗した行には共有リンク・要約が出ない
    failed_section = text.split("## https://youtu.be/bbb")[1]
    assert "共有リンク" not in failed_section
    assert "### 要約" not in failed_section


@pytest.mark.parametrize(
    ("fmt", "suffix"),
    [("json", ".json"), ("csv", ".csv"), ("markdown", ".md"), ("unknown", ".json")],
)
def test_write_results_creates_dir_and_picks_writer(batch, tmp_path, fmt, suffix):
    out_dir = tmp_path / "nested" / "out"

    path = output_writer.write_results(batch, fmt, str(out_dir))

    assert out_dir.is_dir()
    assert path.parent == out_dir
    assert path.suffix == suffix
    assert path.exists()


def test_print_summary_table(batch, capsys):
    output_writer.print_summary_table(batch)
    out = capsys.readouterr().out
    assert "処理結果サマリー" in out
    assert "成功" in out and "失敗" in out
