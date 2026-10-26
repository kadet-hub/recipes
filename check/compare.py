"""Object helpers of check lint: idents, pod templates and what selectors select (RCP-38).

Pure functions on lists of Kubernetes objects, so the tests run without a cluster.
"""

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job"}
RBAC_KINDS = {"Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding"}


def ident(obj):
    """Kind/namespace/name of an object."""
    meta = obj.get("metadata", {})
    group = obj.get("apiVersion", "").rpartition("/")[0]
    kind = f"{obj.get('kind')}.{group}" if group else obj.get("kind")
    return "/".join(p for p in (kind, meta.get("namespace"), meta.get("name")) if p)


def unwrap(docs):
    """Objects from documents that may be a kind: List."""
    out = []
    for doc in docs:
        if not doc:
            continue
        if doc.get("kind") == "List" or (doc.get("kind", "").endswith("List") and "items" in doc):
            out += [o for o in doc.get("items") or [] if o]
        else:
            out.append(doc)
    return out


def pod_templates(obj):
    """The pod templates of a workload, with the path to each."""
    spec = obj.get("spec") or {}
    if "template" in spec:
        yield ["spec", "template"], spec["template"]
    job = (spec.get("jobTemplate") or {}).get("spec") or {}
    if "template" in job:
        yield ["spec", "jobTemplate", "spec", "template"], job["template"]


def matches(selector, labels):
    """A LabelSelector (matchLabels/matchExpressions) or a plain map against labels."""
    if selector is None:
        return False
    labels = labels or {}
    if "matchLabels" in selector or "matchExpressions" in selector:
        plain = selector.get("matchLabels") or {}
        expressions = selector.get("matchExpressions") or []
    else:
        plain, expressions = selector, []
    if any(labels.get(k) != v for k, v in plain.items()):
        return False
    for e in expressions:
        key, op, values = e["key"], e["operator"], e.get("values") or []
        if op == "In" and labels.get(key) not in values:
            return False
        if op == "NotIn" and key in labels and labels[key] in values:
            return False
        if op == "Exists" and key not in labels:
            return False
        if op == "DoesNotExist" and key in labels:
            return False
    return True


def _namespace(obj):
    return obj.get("metadata", {}).get("namespace")


def _pod_labels(obj):
    for _, template in pod_templates(obj):
        return (template.get("metadata") or {}).get("labels") or {}
    return {}


def selections(objs):
    """What each selector selects, by object ident: RCP-38.

    Returns ({ident: set of selected idents}, [errors]). A workload that does
    not select its own pods is an error on its own.
    """
    workloads = [o for o in objs if o.get("kind") in WORKLOAD_KINDS]
    services = [o for o in objs if o.get("kind") == "Service"]
    selected, errors = {}, []
    for w in workloads:
        selector = (w.get("spec") or {}).get("selector")
        if w.get("kind") == "Job" and selector is None:
            continue
        if not matches(selector, _pod_labels(w)):
            errors.append(f"{ident(w)}: selector does not select its own pods")
    for o in objs:
        kind, spec = o.get("kind"), o.get("spec") or {}
        if kind == "Service" and spec.get("selector"):
            selector, pool = spec["selector"], workloads
        elif kind == "NetworkPolicy":
            selector, pool = spec.get("podSelector"), workloads
        elif kind == "PodDisruptionBudget":
            selector, pool = spec.get("selector"), workloads
        elif kind == "ServiceMonitor":
            selector, pool = spec.get("selector"), services
        else:
            continue
        if kind == "ServiceMonitor":
            names = (spec.get("namespaceSelector") or {}).get("matchNames")
            any_ns = (spec.get("namespaceSelector") or {}).get("any")
            in_scope = lambda t: any_ns or _namespace(t) in (names or [_namespace(o)])  # noqa: E731
        else:
            in_scope = lambda t: _namespace(t) == _namespace(o)  # noqa: E731
        labels = (lambda t: t.get("metadata", {}).get("labels")) if kind == "ServiceMonitor" else _pod_labels
        selected[ident(o)] = {ident(t) for t in pool if in_scope(t) and matches(selector, labels(t))}
    return selected, errors
