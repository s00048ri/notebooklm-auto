"""データモデル定義"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NotebookResult:
    """各YouTube URLの処理結果"""

    youtube_url: str
    notebook_id: str = ""
    notebook_title: str = ""
    summary: str = ""
    share_link: str = ""
    status: str = "pending"  # "success" | "error" | "pending"
    error_message: str | None = None
    processing_time: float = 0.0


@dataclass
class BatchResult:
    """バッチ処理全体の結果"""

    run_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    results: list[NotebookResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def successful(self) -> int:
        return sum(1 for r in self.results if r.status == "success")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "error")
