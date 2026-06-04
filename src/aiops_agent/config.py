from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """项目运行配置，集中管理路径和 Gemini 环境变量。"""

    project_root: Path
    data_dir: Path
    logs_dir: Path
    rag_dir: Path
    eval_dir: Path
    reports_dir: Path
    figures_dir: Path
    gemini_api_key: str | None
    gemini_model: str

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        load_dotenv()
        root = project_root or Path.cwd()
        # 以项目根目录为基准派生所有默认路径，避免调用方依赖硬编码目录。
        data_dir = root / "data"
        return cls(
            project_root=root,
            data_dir=data_dir,
            logs_dir=data_dir / "logs",
            rag_dir=data_dir / "rag",
            eval_dir=data_dir / "eval",
            reports_dir=root / "reports",
            figures_dir=root / "reports" / "figures",
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        )

    def ensure_dirs(self) -> None:
        for path in [self.logs_dir, self.rag_dir, self.eval_dir, self.figures_dir]:
            path.mkdir(parents=True, exist_ok=True)
