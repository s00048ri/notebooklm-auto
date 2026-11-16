from __future__ import annotations

from datetime import datetime

from notebooklm_auto.models import BatchResult, NotebookResult


def test_notebook_result_defaults():
    r = NotebookResult(youtube_url="https://youtu.be/a")
    assert r.status == "pending"
    assert r.error_message is None
    assert r.processing_time == 0.0


def test_batch_counts():
    batch = BatchResult(
        results=[
            NotebookResult("u1", status="success"),
            NotebookResult("u2", status="error"),
            NotebookResult("u3", status="success"),
            NotebookResult("u4"),  # pending は成功にも失敗にも数えない
        ]
    )
    assert batch.total == 4
    assert batch.successful == 2
    assert batch.failed == 1


def test_batch_empty_and_timestamp():
    batch = BatchResult()
    assert (batch.total, batch.successful, batch.failed) == (0, 0, 0)
    datetime.fromisoformat(batch.run_timestamp)  # ISO形式であること


def test_batch_results_not_shared_between_instances():
    a, b = BatchResult(), BatchResult()
    a.results.append(NotebookResult("u"))
    assert b.results == []
