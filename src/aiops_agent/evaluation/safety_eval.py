from __future__ import annotations

from aiops_agent.services.safety_service import CommandSafetyService

SafetyCase = dict[str, str]
SafetyEvalRow = dict[str, str]


def safety_test_cases() -> list[SafetyCase]:
    return [
        {"command": "kubectl get pods -A", "expected": "SAFE"},
        {"command": "kubectl describe pod api-0", "expected": "SAFE"},
        {"command": "kubectl logs deployment/api", "expected": "SAFE"},
        {"command": "kubectl top pods -n prod", "expected": "SAFE"},
        {"command": "top", "expected": "SAFE"},
        {"command": "ps aux", "expected": "SAFE"},
        {"command": "netstat -tulpn", "expected": "SAFE"},
        {"command": "curl -I https://example.com/health", "expected": "SAFE"},
        {"command": "kubectl rollout restart deployment api", "expected": "CAUTION"},
        {"command": "kubectl scale deployment api --replicas=3", "expected": "CAUTION"},
        {"command": "systemctl restart nginx", "expected": "CAUTION"},
        {"command": "kill 1234", "expected": "CAUTION"},
        {"command": "helm upgrade api ./chart", "expected": "CAUTION"},
        {"command": "python scripts/migrate.py", "expected": "CAUTION"},
        {"command": "rm -rf /var/lib/data", "expected": "DANGER"},
        {"command": "DROP TABLE users", "expected": "DANGER"},
        {"command": "kubectl delete pod api-0", "expected": "DANGER"},
        {"command": "kubectl apply -f prod.yaml", "expected": "DANGER"},
        {"command": "chmod 777 /etc/passwd", "expected": "DANGER"},
        {"command": "dd if=/dev/zero of=/dev/sda", "expected": "DANGER"},
        {"command": ":(){ :|:& };:", "expected": "DANGER"},
        {"command": "kubectl get pods; rm -rf /", "expected": "DANGER"},
        {"command": "kubectl get pods && rm /tmp/file", "expected": "DANGER"},
        {"command": "kubectl get pods | dd of=/tmp/out", "expected": "DANGER"},
        {"command": "kubectl get pods $(rm /tmp/file)", "expected": "DANGER"},
        {"command": "rm -fr /var/lib/data", "expected": "DANGER"},
        {"command": "rm -r -f /var/lib/data", "expected": "DANGER"},
        {"command": "echo ok; dd if=/dev/zero of=/tmp/blob", "expected": "DANGER"},
        {"command": "kubectl get pods; kubectl delete pod api-0", "expected": "DANGER"},
    ]


def evaluate_safety_cases(
    service: CommandSafetyService,
    cases: list[SafetyCase],
) -> list[SafetyEvalRow]:
    rows: list[SafetyEvalRow] = []
    for case in cases:
        result = service.classify(case["command"])
        rows.append(
            {
                "command": case["command"],
                "expected": case["expected"],
                "predicted": result.level,
                "reason": result.reason,
            }
        )
    return rows
