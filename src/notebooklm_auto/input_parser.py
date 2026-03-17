"""URL入力パーサー（txt/csv/CLI引数対応）"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import NamedTuple

YOUTUBE_PATTERN = re.compile(
    r"^https?://(www\.)?(youtube\.com/(watch\?v=|shorts/|live/)|youtu\.be/)[\w-]+"
)


class UrlEntry(NamedTuple):
    """URLとオプションのタイトルのペア"""
    url: str
    title: str  # 空文字の場合はprocessorがビデオIDから自動生成


def validate_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_PATTERN.match(url.strip()))


def parse_txt(path: Path) -> list[UrlEntry]:
    """テキストファイルから1行1URLで読み込み。空行と#コメント行はスキップ。"""
    entries: list[UrlEntry] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if validate_youtube_url(line):
                entries.append(UrlEntry(url=line, title=""))
            else:
                print(f"  [スキップ] 無効なURL: {line}")
    return entries


def _find_csv_column(fieldnames: list[str], candidates: list[str]) -> str | None:
    """列名の候補リストからCSVに存在する列名を探す"""
    lower_map = {name.lower().strip(): name for name in fieldnames}
    for candidate in candidates:
        if candidate.lower() in lower_map:
            return lower_map[candidate.lower()]
    return None


def parse_csv(path: Path) -> list[UrlEntry]:
    """CSVファイルからURLとタイトルを読み込み。"""
    entries: list[UrlEntry] = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        # URL列を探す（複数の列名パターンに対応）
        url_col = _find_csv_column(fieldnames, ["youtube url", "url", "youtube_url", "link"])
        if url_col is None:
            raise ValueError(
                f"CSVにURL列が見つかりません。対応する列名: 'YouTube URL', 'url', 'link'\n"
                f"検出された列: {fieldnames}"
            )

        # タイトル列を探す（オプション）
        title_col = _find_csv_column(
            fieldnames, ["session title", "title", "session_title", "name"]
        )

        for row in reader:
            url = row[url_col].strip()
            if not url:
                continue
            if validate_youtube_url(url):
                title = row.get(title_col, "").strip() if title_col else ""
                entries.append(UrlEntry(url=url, title=title))
            else:
                print(f"  [スキップ] 無効なURL: {url}")
    return entries


def parse_file(path: str | Path) -> list[UrlEntry]:
    """ファイル拡張子に応じてtxtまたはcsv形式で読み込み。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {path}")

    if path.suffix.lower() == ".csv":
        return parse_csv(path)
    return parse_txt(path)


def parse_urls(urls: list[str]) -> list[UrlEntry]:
    """CLI引数から渡されたURLリストをバリデーション。"""
    valid: list[UrlEntry] = []
    for url in urls:
        url = url.strip()
        if validate_youtube_url(url):
            valid.append(UrlEntry(url=url, title=""))
        else:
            print(f"  [スキップ] 無効なURL: {url}")
    return valid
