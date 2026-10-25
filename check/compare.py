"""Object comparison of the chart side and the recipe side (RCP-9 to RCP-12).

Pure functions on lists of Kubernetes objects as the API server returns them,
so the tests run without a cluster.
"""

import copy
import json
import re
from dataclasses import dataclass

MISSING = "<unset>"

DROP_METADATA = ("uid", "resourceVersion", "creationTimestamp", "managedFields", "generation")
DROP_LABELS = {
    "app.kubernetes.io/managed-by",
    "app.kubernetes.io/version",
    "app",
    "name",
    "app.kubernetes.io/name",
    "app.kubernetes.io/instance",
    "app.kubernetes.io/component",
    "app.kubernetes.io/part-of",
}
DROP_ANNOTATIONS = {"kubectl.kubernetes.io/last-applied-configuration"}
HELM_PREFIXES = ("helm.sh/", "meta.helm.sh/")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}")

WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job"}
RBAC_KINDS = {"Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding"}
WEBHOOK_KINDS = {"MutatingWebhookConfiguration", "ValidatingWebhookConfiguration"}

SELECTOR_SCHEME = "Selector scheme"
EXPLICIT_DEFAULT = "Explicit default"
PORT_BY_NAME = "Port by name"
DERIVED_NAME = "Derived name"


def ident(obj):
    """Kind/namespace/name, the key both sides are paired by."""
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


def _clean_metadata(meta):
    labels = {
        k: v
        for k, v in (meta.get("labels") or {}).items()
        if k not in DROP_LABELS and not k.startswith(HELM_PREFIXES)
    }
    annotations = {
        k: v
        for k, v in (meta.get("annotations") or {}).items()
        if k not in DROP_ANNOTATIONS and not k.startswith(HELM_PREFIXES)
    }
    for key, value in (("labels", labels), ("annotations", annotations)):
        if value:
            meta[key] = value
        else:
            meta.pop(key, None)


def normalize(obj, side):
    """RCP-9: drop exactly the listed fields and nothing else."""
    obj = copy.deepcopy(obj)
    obj.pop("status", None)
    meta = obj.setdefault("metadata", {})
    for key in DROP_METADATA:
        meta.pop(key, None)
    _clean_metadata(meta)
    for _, template in pod_templates(obj):
        _clean_metadata(template.setdefault("metadata", {}))
        if not template["metadata"]:
            del template["metadata"]
        if side == "recipe":
            pod = template.get("spec") or {}
            for key in ("initContainers", "containers"):
                for container in pod.get(key) or []:
                    if "image" in container:
                        container["image"] = DIGEST.sub("", container["image"])
                    if "args" in container:
                        container["args"] = [DIGEST.sub("", a) for a in container["args"]]
    if obj.get("kind") == "Secret":
        for key in ("data", "stringData"):
            if key in obj:
                obj[key] = {k: "" for k in obj[key]}
    if not meta:
        del obj["metadata"]
    return obj


# Label selectors


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
    """What each selector selects, by object ident: RCP-10.

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


def check_selectors(chart, recipe, pairs):
    """RCP-10 on pre-normalization objects: same selection on both sides.

    pairs maps chart idents to recipe idents. Returns (idents whose selection
    is equal, [errors]).
    """
    chart_sel, errors = selections(chart)
    recipe_sel, recipe_errors = selections(recipe)
    errors += recipe_errors
    # A workload whose selector selects its own pods on both sides.
    failing = {e.split(":")[0] for e in errors}
    equal = {
        pairs[ident(o)]
        for o in chart
        if o.get("kind") in WORKLOAD_KINDS and ident(o) in pairs
        and ident(o) not in failing and pairs[ident(o)] not in failing
    }
    for chart_id, chart_targets in chart_sel.items():
        recipe_id = pairs.get(chart_id)
        if recipe_id is None:
            continue
        if recipe_id not in recipe_sel:
            errors.append(f"{recipe_id}: no selector, the chart's selects {sorted(chart_targets)}")
            continue
        mapped = {pairs.get(t, t) for t in chart_targets}
        if mapped == recipe_sel[recipe_id]:
            equal.add(recipe_id)
        else:
            errors.append(
                f"{recipe_id}: selects {sorted(recipe_sel[recipe_id])}, the chart's {sorted(mapped)}"
            )
    reverse = {v: k for k, v in pairs.items()}
    for recipe_id in recipe_sel:
        if recipe_id in reverse and reverse[recipe_id] not in chart_sel:
            errors.append(f"{recipe_id}: has a selector the chart's object does not have")
    return equal, errors


# Pairing and diff


def pair(chart, recipe):
    """Pair objects by ident, then webhook configurations by their webhook names.

    Returns (pairs chart->recipe ident, renamed [(chart, recipe)], only chart, only recipe).
    """
    chart_ids = {ident(o): o for o in chart}
    recipe_ids = {ident(o): o for o in recipe}
    pairs = {i: i for i in chart_ids if i in recipe_ids}
    renamed = []
    left = {i: o for i, o in chart_ids.items() if i not in pairs}
    right = {i: o for i, o in recipe_ids.items() if i not in pairs}

    def hooks(o):
        return (o.get("kind"), tuple(sorted(w.get("name", "") for w in o.get("webhooks") or [])))

    for kind in WEBHOOK_KINDS:
        lw = [i for i, o in left.items() if o.get("kind") == kind]
        rw = [i for i, o in right.items() if o.get("kind") == kind]
        for li in lw:
            same = [ri for ri in rw if hooks(right[ri]) == hooks(left[li])]
            if len(same) == 1:
                pairs[li] = same[0]
                renamed.append((li, same[0]))
                rw.remove(same[0])
                del right[same[0]]
        for li, _ in renamed:
            left.pop(li, None)
    return pairs, renamed, sorted(left), sorted(right)


@dataclass
class Difference:
    obj: str
    path: list
    chart: object
    recipe: object
    cls: str = ""

    def where(self):
        out = ""
        for p in self.path:
            out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else p)
        return out

    def __str__(self):
        cls = self.cls or "NOT ACCEPTED"
        fmt = lambda v: v if v is MISSING else json.dumps(v, sort_keys=True)  # noqa: E731
        return f"{cls}: {self.obj} {self.where()}: chart {fmt(self.chart)}, recipe {fmt(self.recipe)}"


def _canon(v):
    return json.dumps(v, sort_keys=True)


def diff(a, b, path=()):
    """Differences between two normalized values; a list that is a
    permutation of the other is one difference at the list."""
    path = list(path)
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            out += diff(a.get(key, MISSING), b.get(key, MISSING), path + [key])
        return out
    if isinstance(a, list) and isinstance(b, list):
        if a == b:
            return []
        if len(a) == len(b) and sorted(map(_canon, a)) == sorted(map(_canon, b)):
            return [(path, a, b)]
        if len(a) != len(b):
            return [(path, a, b)]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, path + [i])
        return out
    return [] if a == b else [(path, a, b)]


def _get(obj, path):
    for p in path:
        if isinstance(p, int):
            obj = obj[p] if isinstance(obj, list) and p < len(obj) else None
        else:
            obj = obj.get(p) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return obj


def _container_ports(pod):
    ports = {}
    for c in (pod or {}).get("containers") or []:
        for p in c.get("ports") or []:
            if "name" in p:
                ports[p["name"]] = p["containerPort"]
    return ports


def _resolves(named, number, ports):
    return isinstance(named, str) and isinstance(number, int) and ports.get(named) == number


def classify(d, chart_obj, recipe_obj, ctx):
    """The RCP-12 class of one difference, or "" if it is not accepted."""
    path, kind = d.path, recipe_obj.get("kind")
    last = path[-1] if path else None

    if d.obj in ctx["selection_equal"] and (
        path[:2] == ["spec", "selector"] or path[:2] == ["spec", "podSelector"]
    ):
        return SELECTOR_SCHEME

    if last == "automountServiceAccountToken":
        unset_side = "chart" if d.chart is MISSING else "recipe" if d.recipe is MISSING else None
        value = d.recipe if unset_side == "chart" else d.chart
        if unset_side and value is True:
            if kind == "ServiceAccount":
                return EXPLICIT_DEFAULT
            obj = chart_obj if unset_side == "chart" else recipe_obj
            pod = _get(obj, path[:-1]) or {}
            sa = ctx[unset_side + "_by_id"].get(
                f"ServiceAccount/{obj['metadata'].get('namespace')}/{pod.get('serviceAccountName', 'default')}"
            )
            if sa is None or sa.get("automountServiceAccountToken") is not False:
                return EXPLICIT_DEFAULT

    if last in ("targetPort", "port"):
        if kind == "Service" and last == "targetPort":
            for side, value, other in (("chart", d.chart, d.recipe), ("recipe", d.recipe, d.chart)):
                obj_id = d.obj if side == "recipe" else ctx["reverse"].get(d.obj, d.obj)
                for target in ctx[side + "_selected"].get(obj_id, ()):
                    pod = _get(ctx[side + "_by_id"][target], ["spec", "template", "spec"])
                    if _resolves(value, other, _container_ports(pod)):
                        return PORT_BY_NAME
        elif "containers" in path:
            i = path.index("containers")
            for value, other, obj in ((d.chart, d.recipe, chart_obj), (d.recipe, d.chart, recipe_obj)):
                if _resolves(value, other, _container_ports(_get(obj, path[:i]))):
                    return PORT_BY_NAME

    # The generator names a workload's container after the component, sorts
    # container ports by name and names webhook configurations <namespace>-<component>.
    if len(path) == 6 and path[3] == "containers" and path[4] == 0 and last == "name":
        if d.recipe == recipe_obj["metadata"]["name"]:
            return DERIVED_NAME
    if last == "ports" and "containers" in path and isinstance(d.chart, list) and isinstance(d.recipe, list):
        if sorted(map(_canon, d.chart)) == sorted(map(_canon, d.recipe)) and d.recipe == sorted(
            d.recipe, key=lambda p: p.get("name", "")
        ):
            return DERIVED_NAME
    if path == ["metadata", "name"] and kind in WEBHOOK_KINDS:
        services = {((w.get("clientConfig") or {}).get("service") or {}).get("namespace") for w in recipe_obj.get("webhooks") or []}
        if len(services) == 1 and str(d.recipe).startswith(f"{services.pop()}-"):
            return DERIVED_NAME
    return ""


def compare(chart_raw, recipe_raw):
    """RCP-9, RCP-10 and RCP-12 on the objects outside RBAC.

    chart_raw and recipe_raw are the API server's objects before
    normalization. Returns a dict with the differences, selector errors and
    unpaired objects.
    """
    chart_raw = [o for o in chart_raw if o.get("kind") not in RBAC_KINDS]
    recipe_raw = [o for o in recipe_raw if o.get("kind") not in RBAC_KINDS]
    pairs, renamed, only_chart, only_recipe = pair(chart_raw, recipe_raw)
    selection_equal, selector_errors = check_selectors(chart_raw, recipe_raw, pairs)
    ctx = {
        "selection_equal": selection_equal,
        "reverse": {v: k for k, v in pairs.items()},
        "chart_by_id": {ident(o): o for o in chart_raw},
        "recipe_by_id": {ident(o): o for o in recipe_raw},
        "chart_selected": selections(chart_raw)[0],
        "recipe_selected": selections(recipe_raw)[0],
    }
    chart_n = {ident(o): normalize(o, "chart") for o in chart_raw}
    recipe_n = {ident(o): normalize(o, "recipe") for o in recipe_raw}
    differences = []
    for chart_id, recipe_id in sorted(pairs.items()):
        for path, a, b in diff(chart_n[chart_id], recipe_n[recipe_id]):
            d = Difference(recipe_id, path, a, b)
            d.cls = classify(d, ctx["chart_by_id"][chart_id], ctx["recipe_by_id"][recipe_id], ctx)
            differences.append(d)
    return {
        "objects": (len(chart_raw), len(recipe_raw)),
        "differences": differences,
        "renamed": renamed,
        "only_chart": only_chart,
        "only_recipe": only_recipe,
        "selector_errors": selector_errors,
        "selection_equal": len(selection_equal),
    }


# RBAC (RCP-11)


def rbac_subjects(objs):
    """Every subject a RoleBinding or ClusterRoleBinding names, as (kind, namespace, name)."""
    out = set()
    for o in objs:
        if o.get("kind") not in ("RoleBinding", "ClusterRoleBinding"):
            continue
        for s in o.get("subjects") or []:
            ns = s.get("namespace", "") if s["kind"] == "ServiceAccount" else ""
            out.add((s["kind"], ns, s["name"]))
    return out


def rbac_namespaces(objs, subjects, namespace):
    """Namespaces with a RoleBinding on either side, plus each ServiceAccount's own. A RoleBinding
    without a namespace binds in the target namespace, where it is applied (RCP-11)."""
    out = {o["metadata"].get("namespace", namespace) for o in objs if o.get("kind") == "RoleBinding"}
    out |= {ns for kind, ns, _ in subjects if kind == "ServiceAccount"}
    return out


def impersonation(subject):
    """kubectl flags that act as the subject."""
    kind, ns, name = subject
    if kind == "ServiceAccount":
        return ["--as", f"system:serviceaccount:{ns}:{name}"]
    if kind == "User":
        return ["--as", name]
    return ["--as", "check-group-member", "--as-group", name]


CAN_I_LINE = re.compile(r"^(\S*)\s*(\[[^\]]*\])\s+(\[[^\]]*\])\s+(\[[^\]]*\])\s*$")


def normalize_can_i(text):
    """kubectl auth can-i --list output as sorted lines with sorted verbs."""
    lines = []
    for line in text.splitlines():
        m = CAN_I_LINE.match(line.strip())
        if not m:
            continue
        resource, urls, names, verbs = m.groups()
        verbs = "[" + " ".join(sorted(verbs[1:-1].split())) + "]"
        lines.append(" ".join(p for p in (resource, urls, names, verbs) if p))
    return sorted(set(lines))


def diff_permissions(chart, recipe):
    """chart and recipe map a label such as 'Group/x in ns' to normalized lines."""
    out = []
    for key in sorted(set(chart) | set(recipe)):
        a, b = set(chart.get(key, [])), set(recipe.get(key, []))
        out += [f"{key}: only chart: {line}" for line in sorted(a - b)]
        out += [f"{key}: only recipe: {line}" for line in sorted(b - a)]
    return out


def aggregated(objs, role):
    """ClusterRoles that aggregate into a built-in role."""
    label = f"rbac.authorization.k8s.io/aggregate-to-{role}"
    return [
        o
        for o in objs
        if o.get("kind") == "ClusterRole" and (o["metadata"].get("labels") or {}).get(label) == "true"
    ]


def untested_aggregation(objs, tested=("view", "edit", "admin")):
    """aggregate-to-* labels of roles kind does not have, such as OpenShift's cluster-reader."""
    out = set()
    for o in objs:
        if o.get("kind") != "ClusterRole":
            continue
        for label, value in (o["metadata"].get("labels") or {}).items():
            prefix = "rbac.authorization.k8s.io/aggregate-to-"
            if label.startswith(prefix) and value == "true" and label[len(prefix):] not in tested:
                out.add(f"{label} ({o['metadata']['name']})")
    return sorted(out)
