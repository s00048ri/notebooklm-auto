"""コアプロセッサ: NotebookLM操作（ノートブック作成→ソース追加→要約→共有）"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from collections.abc import Callable
from urllib.parse import parse_qs, quote, urlparse

from rich.console import Console

from .config import Config
from .input_parser import UrlEntry
from .models import BatchResult, NotebookResult

console = Console()


def extract_video_id(url: str) -> str:
    """YouTube URLからビデオIDを抽出"""
    parsed = urlparse(url)
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/")
    if "shorts" in parsed.path:
        return parsed.path.split("/shorts/")[-1]
    if "live" in parsed.path:
        return parsed.path.split("/live/")[-1].split("?")[0]
    return parse_qs(parsed.query).get("v", ["unknown"])[0]


async def fetch_video_title(url: str) -> str:
    """YouTube oEmbed APIで動画タイトルを取得。失敗時はビデオIDを返す。"""
    import urllib.request

    oembed_url = f"https://www.youtube.com/oembed?url={quote(url, safe='')}&format=json"
    loop = asyncio.get_event_loop()
    try:
        def _fetch():
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())

        data = await loop.run_in_executor(None, _fetch)
        return data.get("title", extract_video_id(url))
    except Exception:
        return extract_video_id(url)


# 進捗コールバック: (step, title) を受け取る。
# step は "creating" / "adding_source" / "summarizing" / "sharing" のいずれか。
StepCallback = Callable[[str, str], None]
# バッチ用コールバック: 先頭に入力リスト内のインデックスが付く。
BatchStepCallback = Callable[[int, str, str], None]
BatchResultCallback = Callable[[int, NotebookResult], None]

_STEP_MESSAGES = {
    "creating": "ノートブック作成中...",
    "adding_source": "ソース追加中...",
    "summarizing": "要約生成中...",
    "sharing": "共有設定中... Anyone with a link",
}


async def process_single_url(
    client,
    entry: UrlEntry,
    config: Config,
    on_step: StepCallback | None = None,
) -> NotebookResult:
    """1つのYouTube URLに対してノートブック作成→要約→共有リンク取得を実行。

    CLIとWeb UIの両方から使う共通処理。`on_step` を渡すと各ステップ開始時に呼ばれる。
    """
    result = NotebookResult(youtube_url=entry.url)
    start = time.time()

    def step(name: str, title: str) -> None:
        console.print(f"  [cyan]{_STEP_MESSAGES[name]}[/] {title}")
        if on_step is not None:
            on_step(name, title)

    try:
        title = entry.title if entry.title else await fetch_video_title(entry.url)

        # 1. ノートブック作成
        step("creating", title)
        nb = await client.notebooks.create(title)
        result.notebook_id = nb.id
        result.notebook_title = title

        # 2. YouTubeソース追加（処理完了まで待機）
        step("adding_source", title)
        await client.sources.add_url(nb.id, entry.url, wait=True)

        # 3. 要約生成
        step("summarizing", title)
        chat_result = await client.chat.ask(nb.id, config.summary_prompt)
        result.summary = chat_result.answer

        # 4. 共有設定: "Anyone with a link" に設定
        step("sharing", title)
        await client.sharing.set_public(nb.id, True)
        share_status = await client.sharing.get_status(nb.id)
        result.share_link = share_status.share_url or f"https://notebooklm.google.com/notebook/{nb.id}"

        result.status = "success"
        console.print(f"  [green]完了![/] {title}")

    except Exception as e:
        result.status = "error"
        result.error_message = f"{type(e).__name__}: {e}"
        console.print(f"  [red]エラー:[/] {result.error_message}")
        traceback.print_exc()

    result.processing_time = time.time() - start
    return result


async def process_all_urls(
    entries: list[UrlEntry],
    config: Config,
    on_step: BatchStepCallback | None = None,
    on_result: BatchResultCallback | None = None,
) -> BatchResult:
    """複数のURLをバッチ処理（並行数制限付き）。

    `on_step(index, step, title)` は各ステップ開始時、`on_result(index, result)` は
    1件の処理が終わるたびに呼ばれる。結果は入力と同じ順序で返す。
    """
    from notebooklm import NotebookLMClient

    batch = BatchResult()
    semaphore = asyncio.Semaphore(config.max_concurrent)

    async def _process_with_semaphore(client, index: int, entry: UrlEntry) -> NotebookResult:
        async with semaphore:
            step_cb: StepCallback | None = None
            if on_step is not None:
                step_cb = lambda step, title: on_step(index, step, title)  # noqa: E731

            result = await process_single_url(client, entry, config, on_step=step_cb)
            if on_result is not None:
                on_result(index, result)
            return result

    console.print(f"\n[bold]NotebookLM処理開始[/] ({len(entries)} 件)")
    console.print(f"  並行数: {config.max_concurrent}, タイムアウト: {config.source_timeout}s\n")

    try:
        async with await NotebookLMClient.from_storage() as client:
            tasks = [_process_with_semaphore(client, i, entry) for i, entry in enumerate(entries)]
            batch.results = await asyncio.gather(*tasks)
    except Exception as e:
        error_name = type(e).__name__
        if "auth" in error_name.lower() or "login" in str(e).lower():
            console.print(
                "\n[bold red]認証エラー:[/] セッションが切れています。"
                "\n以下のコマンドで再ログインしてください:"
                "\n  [bold]notebooklm login[/]\n"
            )
        else:
            console.print(f"\n[bold red]致命的エラー:[/] {error_name}: {e}")
        raise

    console.print(
        f"\n[bold]処理完了:[/] 成功 {batch.successful}/{batch.total}, "
        f"失敗 {batch.failed}/{batch.total}\n"
    )
    return batch
