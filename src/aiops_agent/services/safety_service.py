from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern

from aiops_agent.models.schemas import SafetyResult


@dataclass(frozen=True)
class _Rule:
    pattern: Pattern[str]
    level: str
    reason: str


class CommandSafetyService:
    """基于正则白/灰/黑名单的命令安全分级服务。"""

    def __init__(self) -> None:
        self._danger_rules = [
            _rule(r"\brm\s+(?=[^;&|$]*-[^\s;&|$]*r)(?=[^;&|$]*-[^\s;&|$]*f)", "DANGER", "包含 rm 递归强制删除操作。"),
            _rule(r"\bdrop\s+table\b", "DANGER", "包含 DROP TABLE 破坏性数据库操作。"),
            _rule(r"\bkubectl\s+delete\b", "DANGER", "包含 kubectl delete 删除集群资源。"),
            _rule(r"\bkubectl\s+apply\s+-f\b", "DANGER", "包含 kubectl apply -f 变更集群资源。"),
            _rule(r"\bchmod\s+777\b", "DANGER", "包含 chmod 777 高风险权限变更。"),
            _rule(r"\bdd\s+if=", "DANGER", "包含 dd if= 块设备写入风险命令。"),
            _rule(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "DANGER", "包含 fork bomb。"),
            _rule(r"(?:;|&&|\|\|?|`|\$\()\s*(?:sudo\s+)?rm\b", "DANGER", "包含 shell 注入 rm 命令。"),
            _rule(r"(?:;|&&|\|\|?|`|\$\()\s*(?:sudo\s+)?dd\b", "DANGER", "包含 shell 注入 dd 命令。"),
            _rule(r"(?:;|&&|\|\|?|`|\$\()\s*kubectl\s+delete\b", "DANGER", "包含 shell 注入 kubectl delete。"),
        ]
        self._caution_rules = [
            _rule(r"\bkubectl\s+rollout\s+restart\b", "CAUTION", "包含服务重启操作。"),
            _rule(r"\bkubectl\s+scale\b", "CAUTION", "包含副本数调整操作。"),
            _rule(r"\bsystemctl\s+restart\b", "CAUTION", "包含 systemctl restart 操作。"),
            _rule(r"(?:^|[;&|]\s*)kill\b", "CAUTION", "包含 kill 进程操作。"),
        ]
        self._safe_rules = [
            _rule(r"^\s*kubectl\s+get\b", "SAFE", "只读取 Kubernetes 资源列表。"),
            _rule(r"^\s*kubectl\s+describe\b", "SAFE", "只读取 Kubernetes 资源详情。"),
            _rule(r"^\s*kubectl\s+logs\b", "SAFE", "只读取 Kubernetes 日志。"),
            _rule(r"^\s*top\b", "SAFE", "只查看系统进程概览。"),
            _rule(r"^\s*ps\b", "SAFE", "只查看进程列表。"),
            _rule(r"^\s*netstat\b", "SAFE", "只查看网络连接状态。"),
            _rule(r"^\s*curl\s+-I\b", "SAFE", "只读取 HTTP 响应头。"),
        ]

    def classify(self, command: str) -> SafetyResult:
        normalized = command.strip()

        # 规则顺序有安全含义：危险操作和 shell 注入必须先匹配，避免读命令拼接破坏性命令后被误判安全。
        for rules in (self._danger_rules, self._caution_rules, self._safe_rules):
            for rule in rules:
                if rule.pattern.search(normalized):
                    return SafetyResult(
                        command=command,
                        level=rule.level,
                        reason=rule.reason,
                    )

        # 未知命令不直接放行，统一进入人工复核友好的谨慎级别。
        return SafetyResult(
            command=command,
            level="CAUTION",
            reason="未匹配到已知安全读操作，按未知命令谨慎处理。",
        )

    def classify_many(self, commands: list[str]) -> list[SafetyResult]:
        return [self.classify(command) for command in commands]


def _rule(pattern: str, level: str, reason: str) -> _Rule:
    return _Rule(
        pattern=re.compile(pattern, re.IGNORECASE),
        level=level,
        reason=reason,
    )
