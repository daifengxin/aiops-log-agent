from __future__ import annotations

import json
from pathlib import Path


_OFFICIAL_DOCS_CACHE = Path("data/rag/k8s_official_docs.json")


def load_curated_k8s_docs() -> list[dict[str, object]]:
    """加载离线 Kubernetes 运维语料清单，保证评测不依赖网络。"""

    cached_docs = _load_official_docs_cache()
    if cached_docs:
        return cached_docs

    return [
        _doc(
            "Debug Pods",
            "https://kubernetes.io/docs/tasks/debug/debug-application/debug-pods/",
            4,
            """# Debug Pods
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
        ),
        _doc(
            "Resource Management",
            "https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/",
            6,
            """# Resource Management
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
        ),
        _doc(
            "Probes",
            "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
            5,
            """# Probes
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
        ),
        _doc(
            "DNS Troubleshooting",
            "https://kubernetes.io/docs/tasks/administer-cluster/dns-debugging-resolution/",
            4,
            """# DNS Troubleshooting
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
        ),
        _doc(
            "Events",
            "https://kubernetes.io/docs/reference/kubectl/generated/kubectl_events/",
            2,
            """# Events
Kubernetes events provide a timestamped audit trail for scheduling, pulling images,
creating containers, probe failures, killing containers, and evicting pods. Events
are useful for correlating an application metric spike with cluster behavior.

```bash
kubectl get events -A --sort-by=.lastTimestamp
kubectl get events -n <namespace> --field-selector involvedObject.name=<pod-name>
```

Warnings near the anomaly window are stronger evidence than old normal events. Keep
event output with pod logs when building an incident timeline.""",
        ),
        _doc(
            "Deployments",
            "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/",
            7,
            """# Deployments
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
        ),
        _doc(
            "Services",
            "https://kubernetes.io/docs/concepts/services-networking/service/",
            6,
            """# Services
Services provide stable virtual IPs and DNS names for pods selected by labels. When
traffic reaches the wrong pods or no pods, compare service selectors, endpoints, and
ready pod labels before changing workloads.

```bash
kubectl get service,endpoints,endpointslice -n <namespace>
kubectl describe service <name> -n <namespace>
kubectl get pods -n <namespace> --show-labels
```

Missing endpoints often explain timeouts after deployments, probe failures, or label
changes. For latency, separate service routing issues from application saturation by
checking whether every endpoint receives traffic and stays ready.""",
        ),
        _doc(
            "Troubleshoot Applications",
            "https://kubernetes.io/docs/tasks/debug/debug-application/",
            6,
            """# Troubleshoot Applications
Application troubleshooting combines pod status, events, logs, deployment history, and
resource usage. Start with read-only evidence and build a timeline around the anomaly
window so operator actions do not erase useful state.

```bash
kubectl get all -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
kubectl logs <pod-name> -n <namespace> --since=10m
```

For repeated incidents, compare affected services, dependencies, and recent rollout
changes. Only restart or scale after evidence points to a state-changing mitigation.""",
        ),
        _doc(
            "Nodes",
            "https://kubernetes.io/docs/concepts/architecture/nodes/",
            5,
            """# Nodes
Node conditions describe whether kubelet, runtime, disk, memory, and network resources
are healthy enough to run pods. Node pressure can create latency, evictions, or pending
workloads across multiple services at the same time.

```bash
kubectl get nodes
kubectl describe node <node-name>
kubectl top nodes
```

When anomalies appear in several services together, check whether their pods share a
node and whether node conditions changed near the same timestamp.""",
        ),
        _doc(
            "Jobs",
            "https://kubernetes.io/docs/concepts/workloads/controllers/job/",
            4,
            """# Jobs
Jobs run finite workloads and can overload shared dependencies if parallelism, retries,
or backoff settings are too aggressive. Failed jobs and retry storms can look like
application latency or database contention.

```bash
kubectl get jobs,pods -n <namespace>
kubectl describe job <job-name> -n <namespace>
kubectl logs job/<job-name> -n <namespace>
```

Correlate job start time, retry count, and dependency metrics before blaming stateless
services that only expose the downstream symptom.""",
        ),
        _doc(
            "ConfigMaps",
            "https://kubernetes.io/docs/concepts/configuration/configmap/",
            4,
            """# ConfigMaps
ConfigMaps provide non-secret configuration to pods. A bad configuration rollout can
change endpoints, feature flags, timeouts, or probe paths without changing application
images, so deployment history alone is not enough.

```bash
kubectl get configmap <name> -n <namespace> -o yaml
kubectl describe pod <pod-name> -n <namespace>
```

Compare mounted values and environment variables for healthy and unhealthy pods. Treat
configuration edits as state-changing operations that need review before applying.""",
        ),
        _doc(
            "Network Policies",
            "https://kubernetes.io/docs/concepts/services-networking/network-policies/",
            5,
            """# Network Policies
Network policies control pod-to-pod and pod-to-external communication. A policy change
can create selective dependency timeouts while pods, services, and DNS still appear
healthy.

```bash
kubectl get networkpolicy -n <namespace>
kubectl describe networkpolicy <name> -n <namespace>
kubectl exec -n <namespace> <pod-name> -- curl -I <dependency>
```

When only one namespace or app path fails, inspect ingress and egress policy selectors
alongside service selectors and pod labels.""",
        ),
        _doc(
            "Persistent Volumes",
            "https://kubernetes.io/docs/concepts/storage/persistent-volumes/",
            5,
            """# Persistent Volumes
Persistent volumes and claims bind storage to pods. Mount failures, slow disks, or full
volumes can trigger startup delays, probe failures, and application latency that looks
like compute saturation.

```bash
kubectl get pv,pvc -A
kubectl describe pvc <claim> -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
```

Use pod events and claim status to separate storage attach problems from application
errors. Avoid deleting claims during diagnosis unless the data impact is understood.""",
        ),
        _doc(
            "kubectl Logs",
            "https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/",
            3,
            """# kubectl Logs
Logs expose application errors, dependency timeouts, and restart context. Previous
container logs are important when a pod restarted after a liveness failure or OOM kill.

```bash
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> --previous
kubectl logs deployment/<name> -n <namespace> --since=10m
```

Use logs with events and resource metrics. Logs alone show symptoms, while Kubernetes
metadata explains scheduling, lifecycle, and rollout state.""",
        ),
    ]


def _doc(title: str, source: str, estimated_pages: int, text: str) -> dict[str, object]:
    appendix = _DOC_APPENDIX.get(title, _DEFAULT_APPENDIX)
    return {
        "title": title,
        "source": source,
        "estimated_pages": estimated_pages,
        "text": f"{text.strip()}\n\n{appendix.strip()}",
    }


def _load_official_docs_cache() -> list[dict[str, object]]:
    if not _OFFICIAL_DOCS_CACHE.is_file():
        return []

    payload = json.loads(_OFFICIAL_DOCS_CACHE.read_text(encoding="utf-8"))
    docs: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        text = str(item.get("text", "")).strip()
        if not title or not source or not text:
            continue
        docs.append(
            {
                "title": title,
                "source": source,
                "raw_source": item.get("raw_source"),
                "estimated_pages": int(item.get("estimated_pages", 0)),
                "text": text,
            }
        )
    return docs


_DEFAULT_APPENDIX = """
For production troubleshooting, keep the investigation read-only until the timeline is
clear. Capture the resource state, warning events, relevant logs, and recent changes in
the same time window as the symptom. Prefer commands that can be repeated safely and
compare healthy and unhealthy objects before suggesting any state-changing mitigation.
"""

_DOC_APPENDIX = {
    "Debug Pods": """
During pod diagnosis, separate evidence collection from mitigation. First confirm the
pod phase, container state, restart count, readiness condition, assigned node, and
recent warning events. Then compare current logs with previous container logs when a
restart is suspected. This longer page text intentionally keeps commands, events, and
logs in different paragraphs so paragraph-level RAG ground truth can distinguish them.
""",
    "Resource Management": """
Resource investigations should compare requests, limits, observed CPU, observed memory,
and node pressure at the same timestamp. CPU throttling commonly raises latency without
creating Kubernetes errors, while memory pressure can create restarts or OOMKilled
states. A safe diagnosis preserves the observed values before changing limits or
replicas.
""",
    "Probes": """
Probe failures need timeline context. Readiness failures remove a pod from service
traffic and can explain intermittent 5xx responses. Liveness failures restart the
container and can hide the original symptom unless previous logs and events are saved.
Probe path, timeout, period, and failure threshold should be compared with real
application startup and dependency latency.
""",
    "DNS Troubleshooting": """
DNS diagnosis starts by checking whether the failure is local to one namespace, one
service, or the whole cluster. Inspect CoreDNS pods, kube-dns service endpoints, network
policies, service names, and search paths. Application logs often show dependency
timeouts, but DNS events and CoreDNS logs explain whether service discovery was the
cause.
""",
    "Events": """
Events are most useful when filtered near the anomaly window. Sort events by timestamp,
keep warning events with pod names, and correlate them with rollouts, restarts, image
pulls, evictions, and probe transitions. Old normal events are weaker evidence than a
warning that appears during the same latency or error spike.
""",
    "Deployments": """
Deployment troubleshooting compares desired replicas, available replicas, rollout
status, ReplicaSet history, and readiness. A new image or configuration can introduce
latency before it fully fails. Rollback, restart, and scale operations change workload
state, so they should be suggested only after read-only evidence points to the rollout.
""",
    "Services": """
Service routing diagnosis compares selectors, endpoints, endpoint slices, and ready pod
labels. Missing endpoints can cause timeouts even when pods are running. When latency
appears after a deployment, verify that each endpoint is ready and receiving traffic
before changing replicas or service definitions.
""",
    "Troubleshoot Applications": """
Application troubleshooting combines Kubernetes metadata with application symptoms. A
good runbook builds a timeline from logs, events, deployment history, resource usage,
and dependency status. Repeated incidents should be grouped by service, dependency, and
root cause so alert suppression does not hide distinct failures.
""",
    "Nodes": """
Node checks matter when several services degrade together. Compare pod placement,
NodeReady status, memory pressure, disk pressure, PID pressure, kubelet health, and node
resource usage. A node-level problem can create application latency without a change in
the application deployment.
""",
    "Jobs": """
Job and CronJob workloads can create short dependency saturation. Check start times,
parallelism, retry count, backoff settings, failed pods, and logs from the job pods.
Correlating those values with application latency helps distinguish a true service bug
from shared database or queue pressure.
""",
    "ConfigMaps": """
Configuration diagnosis compares mounted files, environment variables, rollout history,
and healthy versus unhealthy pods. A configuration change can alter timeouts, endpoints,
feature flags, or probe paths without changing an image. Applying a new ConfigMap is a
state-changing action and should be reviewed separately from evidence collection.
""",
    "Network Policies": """
Network policy issues often appear as selective dependency timeouts. Inspect ingress and
egress selectors, namespace labels, pod labels, and whether DNS and service endpoints
are reachable from the affected workload. Read-only checks should identify the blocked
path before any policy update is proposed.
""",
    "Persistent Volumes": """
Storage problems can look like startup latency, probe failures, or application errors.
Check PVC binding, mount events, volume attach warnings, disk pressure, and pod events.
Do not delete claims during diagnosis unless the data impact is understood and approved.
""",
    "kubectl Logs": """
Logs should be scoped to the incident window and paired with Kubernetes events. Current
logs show application symptoms, while previous container logs are required after
restarts or OOM kills. Use labels and since filters to reduce noise while preserving the
timeline needed for diagnosis.
""",
}
