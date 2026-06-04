from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


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
        """从环境变量和项目根目录的 .env 文件创建配置。"""

        root = project_root or Path.cwd()
        # 只读取指定根目录的 .env 内容，不写入 os.environ，避免不同项目根目录互相污染。
        env_file = dotenv_values(root / ".env")
        # 真实环境变量优先，其次使用 .env，最后落到默认模型。
        gemini_api_key = os.environ.get("GEMINI_API_KEY", env_file.get("GEMINI_API_KEY"))
        gemini_model = os.environ.get(
            "GEMINI_MODEL",
            env_file.get("GEMINI_MODEL") or "gemini-3.5-flash",
        )
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
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
        )

    def ensure_dirs(self) -> None:
        """创建运行时需要的日志、RAG、评估和图表目录。"""

        for path in [self.logs_dir, self.rag_dir, self.eval_dir, self.figures_dir]:
            path.mkdir(parents=True, exist_ok=True)
