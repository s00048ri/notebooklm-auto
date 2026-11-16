from __future__ import annotations

from pathlib import Path

from notebooklm_auto.config import Config


def test_defaults():
    c = Config()
    assert c.summary_prompt == "この動画の要点を日本語で要約してください"
    assert c.source_timeout == 300
    assert c.max_concurrent == 2
    assert c.output_format == "json"
    assert c.output_dir == "./output"
    assert c.max_retries == 3


def test_load_missing_file_returns_defaults(tmp_path):
    assert Config.load(tmp_path / "missing.yaml") == Config()


def test_load_empty_file_returns_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    assert Config.load(path) == Config()


def test_load_partial_overrides(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("max_concurrent: 5\noutput_format: markdown\n", encoding="utf-8")

    c = Config.load(str(path))

    assert c.max_concurrent == 5
    assert c.output_format == "markdown"
    assert c.source_timeout == 300  # 指定していない項目はデフォルト


def test_load_all_fields(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        'summary_prompt: "Summarize"\n'
        "source_timeout: 10\n"
        "max_concurrent: 1\n"
        "output_format: csv\n"
        "output_dir: /tmp/out\n"
        "max_retries: 0\n",
        encoding="utf-8",
    )
    assert Config.load(path) == Config(
        summary_prompt="Summarize",
        source_timeout=10,
        max_concurrent=1,
        output_format="csv",
        output_dir="/tmp/out",
        max_retries=0,
    )


def test_load_default_path_uses_repo_config_yaml():
    repo_config = Path(__file__).parent.parent / "config.yaml"
    assert Config.load() == Config.load(repo_config)
    assert Config.load().output_format == "csv"
