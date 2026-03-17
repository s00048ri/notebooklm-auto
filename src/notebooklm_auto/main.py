"""CLIエントリポイント"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console

from .config import Config
from .input_parser import parse_file, parse_urls
from .output_writer import print_summary_table, write_results
from .processor import process_all_urls

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notebooklm-auto",
        description="YouTubeのURLリストからNotebookLMノートブックを自動作成し、要約と共有リンクを返す",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file", "-f",
        help="URLリストのファイルパス (.txt または .csv)",
    )
    group.add_argument(
        "--urls", "-u",
        nargs="+",
        help="YouTube URLを直接指定",
    )
    parser.add_argument(
        "--prompt", "-p",
        help="要約プロンプト (config.yamlの設定を上書き)",
    )
    parser.add_argument(
        "--output-format", "-o",
        choices=["json", "csv", "markdown"],
        help="出力形式 (デフォルト: config.yamlの設定)",
    )
    parser.add_argument(
        "--output-dir",
        help="出力ディレクトリ",
    )
    parser.add_argument(
        "--config", "-c",
        help="設定ファイルのパス (デフォルト: config.yaml)",
    )
    return parser


def cli_main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # 設定読み込み
    config = Config.load(args.config)

    # CLI引数で上書き
    if args.prompt:
        config.summary_prompt = args.prompt
    if args.output_format:
        config.output_format = args.output_format
    if args.output_dir:
        config.output_dir = args.output_dir

    # URL解析
    if args.file:
        console.print(f"[bold]ファイル読み込み:[/] {args.file}")
        entries = parse_file(args.file)
    else:
        entries = parse_urls(args.urls)

    if not entries:
        console.print("[red]有効なYouTube URLが見つかりませんでした。[/]")
        sys.exit(1)

    console.print(f"[bold]{len(entries)} 件[/]のURLを処理します。\n")
    for e in entries:
        label = e.title if e.title else e.url
        console.print(f"  - {label}")
    console.print()

    # 処理実行
    try:
        batch = asyncio.run(process_all_urls(entries, config))
    except KeyboardInterrupt:
        console.print("\n[yellow]処理が中断されました。[/]")
        sys.exit(1)
    except Exception:
        sys.exit(1)

    # 結果出力
    print_summary_table(batch)
    write_results(batch, config.output_format, config.output_dir)


if __name__ == "__main__":
    cli_main()
