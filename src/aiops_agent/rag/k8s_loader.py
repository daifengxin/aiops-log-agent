from __future__ import annotations


def load_curated_k8s_docs() -> list[dict[str, str]]:
    """加载离线 Kubernetes 运维语料，保证评测不依赖网络。"""

    return [
        {
            "title": "Debug Pods",
            "source": "https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/",
            "text": """# Debug Pods
Pod debugging starts by listing pods, checking pod status, and reading recent events.
Use describe output to inspect scheduling failures, image pull errors, probe failures,
container restarts, and volume mount problems. Logs show the application symptom,
while events explain what Kubernetes did around the pod.

```bash
kubectl get pods -A
kubectl describe pod <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
```

When latency or errors appear after a rollout, compare the affected pod names,
restart counts, readiness state, and warning events before changing workload state.""",
        },
        {
            "title": "Resource Management",
            "source": "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/",
            "text": """# Resource Management
CPU and memory requests influence scheduling decisions. Limits protect the node but
can cause CPU throttling or OOM kills when they are too low for traffic demand.
Latency spikes often appear when a container is CPU throttled, while sudden restarts
with exit code 137 usually indicate memory pressure.

```bash
kubectl top pods -A
kubectl describe pod <pod-name> -n <namespace>
kubectl get pod <pod-name> -n <namespace> -o yaml
```

Compare current usage with requests and limits before increasing replicas or changing
resource values. Node pressure events can also explain pending pods and evictions.""",
        },
        {
            "title": "Probes",
            "source": "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
            "text": """# Probes
Readiness probes decide whether a pod receives service traffic. Liveness probes
restart containers that are stuck or unhealthy. Startup probes protect slow booting
applications from early liveness failures.

```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

Probe failure events can explain intermittent 5xx responses, traffic imbalance,
rollout stalls, and latency during dependency outages. Check probe path, timeout,
period, and failure threshold against real application startup and dependency timing.""",
        },
        {
            "title": "DNS Troubleshooting",
            "source": "https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/",
            "text": """# DNS Troubleshooting
Kubernetes DNS resolves service names through CoreDNS. DNS failures often surface as
connection timeouts, dependency errors, or service discovery failures. Confirm the
service name, namespace, search path, and CoreDNS health before blaming the application.

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
kubectl exec -n <namespace> <pod-name> -- nslookup <service>.<namespace>.svc.cluster.local
```

If only one namespace fails, inspect service selectors and NetworkPolicy. If many
namespaces fail, check CoreDNS pods, kube-dns service endpoints, and node networking.""",
        },
        {
            "title": "Events",
            "source": "https://kubernetes.io/docs/reference/kubectl/generated/kubectl_events/",
            "text": """# Events
Kubernetes events provide a timestamped audit trail for scheduling, pulling images,
creating containers, probe failures, killing containers, and evicting pods. Events
are useful for correlating an application metric spike with cluster behavior.

```bash
kubectl get events -A --sort-by=.lastTimestamp
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```

Warnings near the anomaly window are stronger evidence than old normal events. Keep
event output with pod logs when building an incident timeline.""",
        },
        {
            "title": "Deployments",
            "source": "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/",
            "text": """# Deployments
Deployments manage ReplicaSets and rollouts for stateless applications. A rollout can
introduce new pods, remove old pods, pause progress, or fail because pods never become
ready. Deployment status explains whether a change is still progressing.

```bash
kubectl rollout status deployment/<name> -n <namespace>
kubectl describe deployment <name> -n <namespace>
kubectl rollout history deployment/<name> -n <namespace>
```

Use rollout history and ReplicaSet events to connect latency or errors to a new image,
configuration change, or readiness regression. Restarting or undoing a rollout changes
application state and should be treated as an operator action.""",
        },
    ]
