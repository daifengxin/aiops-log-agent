from __future__ import annotations

import json
from typing import Any

from aiops_agent.config import Settings


class GeminiLLMService:
    """Gemini JSON 生成服务，真实调用只在显式初始化时建立客户端。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        if not self.settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required")

        # 延迟导入避免测试 fake LLM 或普通模块导入时触发 google.genai 依赖初始化。
        from google import genai

        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    def generate_json(self, prompt: str) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
        )
        text = getattr(response, "text", "") or ""
        payload = json.loads(_strip_json_fence(text))
        if not isinstance(payload, dict):
            raise ValueError("Gemini response must be a JSON object")
        return payload


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    first = lines[0].strip().lower()
    if first in {"```", "```json"}:
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
