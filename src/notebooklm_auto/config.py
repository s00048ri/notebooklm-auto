"""設定管理"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    summary_prompt: str = "この動画の要点を日本語で要約してください"
    source_timeout: int = 300
    max_concurrent: int = 2
    output_format: str = "json"  # json / csv / markdown
    output_dir: str = "./output"
    max_retries: int = 3

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> Config:
        """config.yamlから設定を読み込む。ファイルが無ければデフォルト値を使用。"""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        config_path = Path(config_path)

        if not config_path.exists():
            return cls()

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(
            summary_prompt=data.get("summary_prompt", cls.summary_prompt),
            source_timeout=data.get("source_timeout", cls.source_timeout),
            max_concurrent=data.get("max_concurrent", cls.max_concurrent),
            output_format=data.get("output_format", cls.output_format),
            output_dir=data.get("output_dir", cls.output_dir),
            max_retries=data.get("max_retries", cls.max_retries),
        )
