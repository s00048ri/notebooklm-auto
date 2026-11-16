"""共通フィクスチャ: NotebookLMクライアントのフェイクなど"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def make_fake_client(
    notebook_id: str = "nb-123",
    answer: str = "要約テキスト",
    share_url: str | None = "https://notebooklm.google.com/notebook/nb-123?share=1",
) -> SimpleNamespace:
    """notebooklm-py の NotebookLMClient と同じ形をしたフェイクを作る"""
    client = SimpleNamespace(
        notebooks=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id=notebook_id))),
        sources=SimpleNamespace(add_url=AsyncMock(return_value=None)),
        chat=SimpleNamespace(ask=AsyncMock(return_value=SimpleNamespace(answer=answer))),
        sharing=SimpleNamespace(
            set_public=AsyncMock(return_value=None),
            get_status=AsyncMock(return_value=SimpleNamespace(share_url=share_url)),
        ),
    )
    return client


@pytest.fixture
def fake_client() -> SimpleNamespace:
    return make_fake_client()


@pytest.fixture
def fake_notebooklm(monkeypatch):
    """`notebooklm` モジュールを差し替え、from_storage() がフェイクを返すようにする。

    返り値の namespace の `client` 属性を書き換えれば挙動を変えられる。
    `storage_error` に例外を入れると from_storage() がそれを送出する。
    """
    state = SimpleNamespace(client=make_fake_client(), storage_error=None)

    class _Ctx:
        def __init__(self, client):
            self._client = client

        async def __aenter__(self):
            return self._client

        async def __aexit__(self, *exc):
            return False

    class NotebookLMClient:
        @classmethod
        async def from_storage(cls):
            if state.storage_error is not None:
                raise state.storage_error
            return _Ctx(state.client)

    module = types.ModuleType("notebooklm")
    module.NotebookLMClient = NotebookLMClient
    monkeypatch.setitem(sys.modules, "notebooklm", module)
    return state


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """テスト中に YouTube oEmbed へ実際にアクセスしないようにする"""
    import urllib.request

    def _blocked(*args, **kwargs):
        raise OSError("network disabled in tests")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked)
