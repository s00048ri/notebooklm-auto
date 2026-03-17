"""結果出力（JSON/CSV/Markdown）"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .models import BatchResult

console = Console()


def write_json(batch: BatchResult, output_dir: Path) -> Path:
    path = output_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(batch), f, ensure_ascii=False, indent=2)
    return path


def write_csv(batch: BatchResult, output_dir: Path) -> Path:
    path = output_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fieldnames = [
        "youtube_url",
        "notebook_title",
        "summary",
        "share_link",
        "status",
        "error_message",
        "processing_time",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in batch.results:
            writer.writerow({k: getattr(r, k) for k in fieldnames})
    return path


def write_markdown(batch: BatchResult, output_dir: Path) -> Path:
    path = output_dir / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    lines = [
        f"# NotebookLM 要約結果",
        f"",
        f"実行日時: {batch.run_timestamp}",
        f"合計: {batch.total} 件 (成功: {batch.successful}, 失敗: {batch.failed})",
        f"",
        f"---",
        f"",
    ]
    for r in batch.results:
        lines.append(f"## {r.notebook_title or r.youtube_url}")
        lines.append(f"")
        lines.append(f"- **URL**: {r.youtube_url}")
        lines.append(f"- **ステータス**: {r.status}")
        if r.share_link:
            lines.append(f"- **共有リンク**: {r.share_link}")
        lines.append(f"- **処理時間**: {r.processing_time:.1f}秒")
        lines.append(f"")
        if r.summary:
            lines.append(f"### 要約")
            lines.append(f"")
            lines.append(r.summary)
            lines.append(f"")
        if r.error_message:
            lines.append(f"### エラー")
            lines.append(f"")
            lines.append(f"```\n{r.error_message}\n```")
            lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def write_results(batch: BatchResult, output_format: str, output_dir: str) -> Path:
    """設定に応じた形式で結果を出力"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    writers = {
        "json": write_json,
        "csv": write_csv,
        "markdown": write_markdown,
    }
    writer = writers.get(output_format, write_json)
    path = writer(batch, out)
    console.print(f"[green]結果を保存しました:[/] {path}")
    return path


def print_summary_table(batch: BatchResult) -> None:
    """ターミナルにサマリーテーブルを表示"""
    table = Table(title="処理結果サマリー")
    table.add_column("URL", style="cyan", max_width=50)
    table.add_column("ステータス", justify="center")
    table.add_column("共有リンク", style="blue", max_width=60)
    table.add_column("時間(秒)", justify="right")

    for r in batch.results:
        status = "[green]成功[/]" if r.status == "success" else "[red]失敗[/]"
        table.add_row(
            r.youtube_url[:50],
            status,
            r.share_link[:60] if r.share_link else "-",
            f"{r.processing_time:.1f}",
        )

    console.print(table)
