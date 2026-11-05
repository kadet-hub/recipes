"""kadet-convert: a Helm chart and its values to a Kapitan project for the kadet-hub kubernetes
generator, proven against helm template with the comparison of check (docs/specs/converter.md).

  kadet-convert <chart> --name <release> --namespace <ns> [-f values.yaml]... --out <dir>
                [--repo <url>] [--version <v>] [--no-proof] [--node-image <image>] [--clusters <prefix>]

<chart> is a local chart directory or archive, or anything helm pull takes. Needs helm, kubectl,
kind, docker, oras and gh on PATH, as check does.
"""

import argparse
import base64
import collections
import concurrent.futures
import copy
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

import check
import compare

# Moves with Renovate like the other pins of check (RCP-30); a new version may need new mappings.
# renovate: datasource=docker depName=ghcr.io/kadet-hub/kubernetes
GENERATOR = "ghcr.io/kadet-hub/kubernetes:1.14.0@sha256:787129e1eaed6b9bc868fe4c4aec58d40de6a89fc3cc08424a4cb5822b855080"
RELEASE_NAME = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
CLUSTER_SCOPED = {
    "Namespace", "ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition", "PersistentVolume",
    "MutatingWebhookConfiguration", "ValidatingWebhookConfiguration", "StorageClass", "IngressClass",
    "PriorityClass", "APIService", "RuntimeClass",
}
WORKLOADS = ("Deployment", "StatefulSet", "DaemonSet")
# Labels that name Helm as the manager of an object the user now manages.
HELM_LABELS = {"app.kubernetes.io/managed-by", "heritage"}
APP_PROTOCOLS = {"http": "http", "https": "https", "h2c": "kubernetes.io/h2c", "ws": "kubernetes.io/ws",
                 "wss": "kubernetes.io/wss"}


def ident(o):
    return "/".join(p for p in (o["kind"], o["metadata"].get("namespace"), o["metadata"]["name"]) if p)


# Rendering (CNV-1 to CNV-3)


def fetch(chart, repo, version, work):
    """The chart archive or directory to render, and what the report says about it (CNV-1)."""
    local = Path(chart)
    if local.exists():
        path, digest = local, None
    else:
        out = work / "chart"
        out.mkdir()
        cmd = ["helm", "pull", chart, "-d", str(out)]
        cmd += ["--repo", repo] if repo else []
        cmd += ["--version", version] if version else []
        pulled = check.run(cmd) + "\n"
        digest = next((line.split()[-1] for line in pulled.splitlines() if line.startswith("Digest:")), None)
        (path,) = out.glob("*.tgz")
    meta = yaml.safe_load(check.run(["helm", "show", "chart", str(path)]))
    sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return path, {"chart": meta.get("name"), "version": str(meta.get("version")), "sha256": sha, "digest": digest}


def render(path, name, namespace, values):
    cmd = ["helm", "template", name, str(path), "-n", namespace, "--include-crds"]
    for v in values:
        cmd += ["-f", str(v)]
    return check.run(cmd)


def split(objs):
    crds, hooks, rest = [], [], []
    for o in objs:
        if o["kind"] == "CustomResourceDefinition":
            crds.append(o)
        elif "helm.sh/hook" in (o["metadata"].get("annotations") or {}):
            hooks.append(o)
        else:
            rest.append(o)
    return crds, hooks, rest


def tree_diff(a, b, path=()):
    """(kind, path, a, b): 'leaf' for a changed value, 'added' for a scalar key only b has,
    'structural' for other keys or list lengths that differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a and not isinstance(b[k], (dict, list)):
                out.append(("added", path + (k,), None, b[k]))
            elif k not in a or k not in b:
                out.append(("structural", path + (k,), a.get(k), b.get(k)))
            else:
                out += tree_diff(a[k], b[k], path + (k,))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [("structural", path, a, b)]
        return [d for i, (x, y) in enumerate(zip(a, b, strict=True)) for d in tree_diff(x, y, path + (i,))]
    return [] if a == b else [("leaf", path, a, b)]


def generated(first, second):
    """CNV-3: fields outside hooks that differ between two renders, as '<object> <path>'."""
    by_id = {ident(o): o for o in second}
    out = []
    for o in first:
        other = by_id.get(ident(o))
        if other is None:
            out.append(f"{ident(o)} (only in one render)")
            continue
        out += [f"{ident(o)} {'.'.join(map(str, d[1]))}" for d in tree_diff(o, other)]
    return out


# Mapping (CNV-4 to CNV-10)


class Mapper:
    """Rendered objects to generator input. Every field it cannot place is recorded as not mappable."""

    def __init__(self, release, namespace):
        self.release, self.ns = release, namespace
        self.p = {"components": {}, "generators": {"kubernetes": {}}, "ingresses": {}}
        self.rows = []  # (object, section, mapped, reason)
        self.not_mappable = collections.defaultdict(list)
        self.renamed = []
        self.secrets = []  # (secret, key, parameter): data that goes to the secrets class (CNV-10)

    def section(self, key):
        return self.p["generators"]["kubernetes"].setdefault(key, {})

    def gap(self, obj, path):
        self.not_mappable[ident(obj)].append(path)

    def mapped(self, obj, section):
        self.rows.append((ident(obj), section, True, ""))

    def meta(self, obj, entry, labels=True, annotations=True):
        m = obj["metadata"]
        if m.get("namespace") and m["namespace"] != self.ns:
            entry["namespace"] = m["namespace"]
        kept = {k: v for k, v in (m.get("labels") or {}).items() if k not in HELM_LABELS and not k.startswith("helm.sh/")}
        if kept and labels:
            entry["labels"] = kept
        if m.get("annotations") and annotations:
            entry["annotations"] = dict(m["annotations"])
        return entry

    def container(self, obj, c, where):
        c = dict(c)
        c.pop("name")
        out = {"image": c.pop("image")}
        tag = out["image"].rsplit("/", 1)[-1].partition(":")[2]
        api_default = "Always" if "@" not in out["image"] and tag in ("", "latest") else "IfNotPresent"
        policy = c.pop("imagePullPolicy", api_default)
        if policy != "IfNotPresent":  # the generator's default
            out["pull_policy"] = policy
        for field, key in (("command", "command"), ("args", "args"), ("resources", "resources"),
                           ("lifecycle", "lifecycle"), ("securityContext", "security_context"),
                           ("tty", "tty"), ("stdin", "stdin")):
            if field in c:
                out[key] = c.pop(field)
        env = {}
        for e in c.pop("env", None) or []:
            source = e.get("valueFrom")
            if source is None:
                env[e["name"]] = e.get("value", "")
            elif set(source) <= {"fieldRef", "secretKeyRef", "configMapKeyRef"}:
                env[e["name"]] = source
            else:
                self.gap(obj, f"{where}.env[{e['name']}].valueFrom.{next(iter(source))}")
        if env:
            out["env"] = env
        refs = []
        for ref in c.pop("envFrom", None) or []:
            kind = "secretRef" if "secretRef" in ref else "configMapRef"
            if set(ref) - {kind} or set(ref[kind]) - {"name"}:
                self.gap(obj, f"{where}.envFrom[{ref[kind].get('name')}] prefix or optional")
            refs.append({kind: {"name": ref[kind]["name"]}})
        if refs:
            out["env_from"] = {"chart": refs}
        ports = {}
        for port in c.pop("ports", None) or []:
            port = dict(port)
            name = port.pop("name", None)
            if name is None:
                name = f"port-{port['containerPort']}"
                self.gap(obj, f"{where}.ports[{port['containerPort']}] without name")
            entry = {"container_port": port.pop("containerPort")}
            protocol = port.pop("protocol", "TCP")
            if protocol != "TCP":
                entry["protocol"] = protocol
            for k in port:
                self.gap(obj, f"{where}.ports[{name}].{k}")
            ports[name] = entry
        if ports:
            out["ports"] = ports
        mounts = {}
        for m in c.pop("volumeMounts", None) or []:
            m = dict(m)
            volume = m.pop("name")
            entry = {"mount_path": m.pop("mountPath")}
            key = volume
            if key in mounts:  # a key names the volume, unless volume does
                key = f"{volume}-{len(mounts)}"
                entry["volume"] = volume
            for field, k in (("subPath", "sub_path"), ("readOnly", "read_only"), ("mountPropagation", "mount_propagation")):
                if field in m:
                    entry[k] = m.pop(field)
            for k in m:
                self.gap(obj, f"{where}.volumeMounts[{volume}].{k}")
            mounts[key] = entry
        if mounts:
            out["volume_mounts"] = mounts
        health = {key: self.probe(obj, c.pop(field), f"{where}.{field}")
                  for field, key in (("startupProbe", "startup"), ("livenessProbe", "liveness"), ("readinessProbe", "readiness"))
                  if field in c}
        if health:
            out["healthcheck"] = health
        for k in c:
            self.gap(obj, f"{where}.{k}")
        return out

    def probe(self, obj, p, where):
        p = dict(p)
        out = {}
        for field, kind in (("httpGet", "http"), ("tcpSocket", "tcp"), ("exec", "command"), ("grpc", "grpc")):
            if field not in p:
                continue
            h = dict(p.pop(field))
            out["type"] = kind
            if kind == "command":
                out["command"] = h.pop("command")
            else:
                out["port"] = h.pop("port")
            if kind == "http":
                out["path"] = h.pop("path", None)
                scheme = h.pop("scheme", "HTTP")
                if scheme != "HTTP":
                    out["scheme"] = scheme
                if "httpHeaders" in h:
                    out["httpHeaders"] = h.pop("httpHeaders")
            for k in h:
                self.gap(obj, f"{where}.{field}.{k}")
        # CNV-6: the API default where the chart leaves a field unset, written where the generator's differs.
        for field, key, api, generator in (("initialDelaySeconds", "initial_delay_seconds", 0, 0),
                                           ("periodSeconds", "period_seconds", 10, 10),
                                           ("timeoutSeconds", "timeout_seconds", 1, 5),
                                           ("successThreshold", "success_threshold", 1, 1),
                                           ("failureThreshold", "failure_threshold", 3, 3)):
            value = p.pop(field, api)
            if value != generator:
                out[key] = value
        for k in p:
            self.gap(obj, f"{where}.{k}")
        return out

    def pod(self, obj, spec, comp):
        spec = dict(spec)
        where = "spec.template.spec"
        containers = spec.pop("containers")
        comp.update(self.container(obj, containers[0], f"{where}.containers[{containers[0]['name']}]"))
        if len(containers) > 1:
            comp["additional_containers"] = {
                c["name"]: self.container(obj, c, f"{where}.containers[{c['name']}]") for c in containers[1:]}
        if spec.get("initContainers"):
            comp["init_containers"] = {
                c["name"]: self.container(obj, c, f"{where}.initContainers[{c['name']}]") for c in spec.pop("initContainers")}
        if spec.get("volumes"):
            comp["volumes"] = {v["name"]: {k: x for k, x in v.items() if k != "name"} for v in spec.pop("volumes")}
        account = spec.pop("serviceAccountName", None)
        spec.pop("serviceAccount", None)  # the deprecated alias of serviceAccountName
        if account:
            comp["service_account"] = {"enabled": True, "name": account}
        # CNV-6: unset, the pod mounts the token unless its ServiceAccount opts out.
        comp["automount_service_account_token"] = spec.pop("automountServiceAccountToken", True)
        if spec.get("securityContext"):
            comp["workload_security_context"] = spec.pop("securityContext")
        spec.pop("securityContext", None)
        for field, key in (("nodeSelector", "node_selector"), ("tolerations", "tolerations"), ("affinity", "affinity"),
                           ("priorityClassName", "priority_class_name"), ("imagePullSecrets", "image_pull_secrets"),
                           ("dnsPolicy", "dns_policy"), ("terminationGracePeriodSeconds", "grace_period"),
                           ("hostNetwork", "host_network"), ("hostPID", "host_pid"), ("hostIPC", "host_ipc"),
                           ("enableServiceLinks", "enable_service_links"), ("resourceClaims", "resource_claims")):
            if field in spec:
                comp[key] = spec.pop(field)
        restart = spec.pop("restartPolicy", "Always")
        if restart != "Always":
            comp["restart_policy"] = restart
        for k in spec:
            self.gap(obj, f"{where}.{k}")

    def workload(self, o):
        kind, spec = o["kind"], dict(o["spec"])
        comp = {} if kind == "Deployment" else {"type": kind.lower()}
        self.meta(o, comp)
        tmeta = spec["template"].get("metadata") or {}
        if tmeta.get("labels"):
            comp["pod_labels"] = dict(tmeta["labels"])
        if tmeta.get("annotations"):
            comp["pod_annotations"] = dict(tmeta["annotations"])
        spec.pop("selector")  # the generator selects on its name label (CNV-17)
        if "replicas" in spec:
            comp["replicas"] = spec.pop("replicas")
        for field in ("strategy", "updateStrategy"):
            if field in spec:
                comp["update_strategy"] = spec.pop(field)
        for field, key in (("revisionHistoryLimit", "revision_history_limit"), ("minReadySeconds", "min_ready_seconds"),
                           ("progressDeadlineSeconds", "deployment_progress_deadline_seconds")):
            if field in spec:
                value = spec.pop(field)
                if value:  # the generator writes these only when truthy
                    comp[key] = value
                else:
                    self.gap(o, f"spec.{field}: {value}")
        if kind == "StatefulSet":
            service = spec.pop("serviceName", None)
            if service and service != o["metadata"]["name"]:
                self.gap(o, f"spec.serviceName: {service}")
            claims = {}
            for t in spec.pop("volumeClaimTemplates", None) or []:
                t = copy.deepcopy(t)
                name = t["metadata"].pop("name")
                if not t["metadata"]:
                    t.pop("metadata")
                claims[name] = t
            if claims:
                comp["volume_claims"] = claims
        self.pod(o, spec.pop("template")["spec"], comp)
        for k in spec:
            self.gap(o, f"spec.{k}")
        self.p["components"][o["metadata"]["name"]] = comp
        self.mapped(o, f"components.{o['metadata']['name']}")

    def service(self, o):
        spec = dict(o["spec"])
        entry = self.meta(o, {})
        if "type" in spec:
            entry["type"] = spec.pop("type")
        if spec.get("clusterIP") == "None":
            spec.pop("clusterIP")
            entry["headless"] = True
        if spec.pop("publishNotReadyAddresses", False):
            entry["publish_not_ready_address"] = True
        if "sessionAffinity" in spec:
            entry["session_affinity"] = spec.pop("sessionAffinity")
        if spec.get("selector"):
            entry["selector"] = spec.pop("selector")
        ports = {}
        for port in spec.pop("ports", None) or []:
            port = dict(port)
            name = port.pop("name", None)
            if name is None:
                name = f"port-{port['port']}"
                self.gap(o, f"spec.ports[{port['port']}] without name")
            e = {"service_port": port.pop("port")}
            e["container_port"] = port.pop("targetPort", e["service_port"])  # the API's default targetPort
            protocol = port.pop("protocol", "TCP")
            if protocol != "TCP":
                e["protocol"] = protocol
            app = port.pop("appProtocol", None)
            if app != APP_PROTOCOLS.get(name):  # CNV-6: the generator derives it from the port name
                e["app_protocol"] = app or ""
            for k in port:
                self.gap(o, f"spec.ports[{name}].{k}")
            ports[name] = e
        if ports:
            entry["ports"] = ports
        for k in spec:
            self.gap(o, f"spec.{k}")
        self.section("services")[o["metadata"]["name"]] = entry
        self.mapped(o, f"generators.kubernetes.services.{o['metadata']['name']}")

    def config(self, o):
        entry = self.meta(o, {})
        if o.get("data"):
            entry["data"] = {k: {"value": v} for k, v in o["data"].items()}
        for k in set(o) - {"apiVersion", "kind", "metadata", "data"}:
            self.gap(o, k)
        self.section("configs")[o["metadata"]["name"]] = entry
        self.mapped(o, f"generators.kubernetes.configs.{o['metadata']['name']}")

    def secret(self, o):
        name = o["metadata"]["name"]
        entry = self.meta(o, {})
        if o.get("type", "Opaque") != "Opaque":
            entry["type"] = o["type"]
        data = dict(o.get("data") or {})
        for k, v in (o.get("stringData") or {}).items():  # helm template keeps stringData as the chart wrote it
            data[k] = base64.b64encode(str(v).encode()).decode()
        if data:
            entry["data"] = {}
            for k, v in data.items():
                param = re.sub(r"[^A-Za-z0-9_]", "_", f"{name}__{k}")
                while param in {s[2] for s in self.secrets}:
                    param += "_"
                self.secrets.append((name, k, param))
                entry["data"][k] = {"value": v, "b64_encode": False}
        for k in set(o) - {"apiVersion", "kind", "metadata", "type", "data", "stringData"}:
            self.gap(o, k)
        self.section("secrets")[name] = entry
        self.mapped(o, f"generators.kubernetes.secrets.{name}")

    def service_account(self, o):
        entry = self.meta(o, {}, labels=False, annotations=False)
        account = {"automount_service_account_token": o.get("automountServiceAccountToken", True)}  # CNV-6
        if o["metadata"].get("annotations"):
            account["annotations"] = dict(o["metadata"]["annotations"])
        entry["service_account"] = account
        if o.get("imagePullSecrets"):
            entry["image_pull_secrets"] = o["imagePullSecrets"]
        for k in set(o) - {"apiVersion", "kind", "metadata", "automountServiceAccountToken", "imagePullSecrets"}:
            self.gap(o, k)
        self.section("service_accounts")[o["metadata"]["name"]] = entry
        self.mapped(o, f"generators.kubernetes.service_accounts.{o['metadata']['name']}")

    def ingress(self, o):
        spec = dict(o["spec"])
        entry = self.meta(o, {})
        if "ingressClassName" in spec:
            entry["ingress_class"] = spec.pop("ingressClassName")
        if "tls" in spec:
            entry["tls"] = spec.pop("tls")
        if "defaultBackend" in spec:
            svc = spec.pop("defaultBackend")["service"]
            entry["default_backend"] = {"name": svc["name"], "port": svc["port"].get("number", svc["port"].get("name"))}
        hosts = []
        for rule in spec.pop("rules", None) or []:
            paths = []
            for path in (rule.get("http") or {}).get("paths") or []:
                svc = path["backend"]["service"]
                p = {"path": path.get("path"), "path_type": path["pathType"], "backend_name": svc["name"]}
                p.update({"port_name": svc["port"]["name"]} if "name" in svc["port"] else {"port_number": svc["port"]["number"]})
                paths.append(p)
            hosts.append({"name": rule.get("host"), "paths": paths})
        entry["hosts"] = hosts
        for k in spec:
            self.gap(o, f"spec.{k}")
        self.p["ingresses"][o["metadata"]["name"]] = entry
        self.mapped(o, f"ingresses.{o['metadata']['name']}")

    def claim(self, o):
        entry = self.meta(o, {}, labels=False, annotations=False)
        entry["spec"] = o["spec"]
        if o["metadata"].get("annotations"):
            self.gap(o, "metadata.annotations")
        self.section("persistent_volume_claims")[o["metadata"]["name"]] = entry
        self.mapped(o, f"generators.kubernetes.persistent_volume_claims.{o['metadata']['name']}")

    def rbac_name(self, name):
        safe = name.replace(":", "-")
        if safe != name and (name, safe) not in self.renamed:
            self.renamed.append((name, safe))
        return safe

    def rbac(self, objs):
        """CNV-8: one entry per role with the bindings that bind it; other bindings get entries of their own."""
        roles = {(o["kind"], (o["metadata"].get("namespace") or self.ns) if o["kind"] == "Role" else None, o["metadata"]["name"]): o
                 for o in objs if o["kind"] in ("Role", "ClusterRole")}
        entries = self.section("rbac")
        subjects_of = {}
        for (kind, ns, name), o in roles.items():
            entry = self.meta(o, {})
            entry.pop("namespace", None)
            if kind == "Role":
                entry["namespace"] = ns or self.ns
            entry["rules"] = o.get("rules") or []
            if o.get("aggregationRule"):
                entry["aggregation_rule"] = o["aggregationRule"]
            entries[self.rbac_name(name)] = entry
            self.mapped(o, f"generators.kubernetes.rbac.{self.rbac_name(name)}")
        for b in [o for o in objs if o["kind"] in ("RoleBinding", "ClusterRoleBinding")]:
            ref, ns = b["roleRef"], b["metadata"].get("namespace") or self.ns
            subjects = self.subjects(b.get("subjects") or [], ns)
            key = ("Role", ns, ref["name"]) if ref["kind"] == "Role" else ("ClusterRole", None, ref["name"])
            name = self.rbac_name(ref["name"])
            if key not in roles or subjects_of.get(name, subjects) != subjects:
                name = self.rbac_name(b["metadata"]["name"])
                if name in entries:
                    name = f"{name}-{b['kind'].lower()}"
                entry = entries.setdefault(name, {})
                role = self.rbac_name(ref["name"]) if key in roles else ref["name"]  # a renamed role of the chart
                entry.update({"role": role, "namespace": ns} if ref["kind"] == "Role" else {"cluster_role": role})
            entry = entries[name]
            subjects_of[name] = subjects
            entry.update(subjects)
            if b["kind"] == "ClusterRoleBinding":
                entry["cluster_wide"] = True
            elif ref["kind"] == "ClusterRole":
                entry.setdefault("namespaces", []).append(ns)
            self.mapped(b, f"generators.kubernetes.rbac.{name}")

    @staticmethod
    def subjects(subjects, ns):
        out = {}
        for s in subjects:
            if s["kind"] == "ServiceAccount":
                out.setdefault("service_accounts", []).append(f"{s.get('namespace') or ns}/{s['name']}")
            else:
                out.setdefault(s["kind"].lower() + "s", []).append(s["name"])
        return out

    def webhooks(self, o):
        """A webhook configuration goes to the component whose pods its Service selects."""
        key = "webhooks" if o["kind"] == "MutatingWebhookConfiguration" else "validating_webhooks"
        services = {((w.get("clientConfig") or {}).get("service") or {}).get("name") for w in o.get("webhooks") or []}
        selector = (self.section("services").get(services.pop()) or {}).get("selector") if len(services) == 1 else None
        owner = next((n for n, c in self.p["components"].items()
                      if selector and all((c.get("pod_labels") or {}).get(k) == v for k, v in selector.items())), None)
        if owner is None:
            return False
        comp = self.p["components"][owner]
        # CNV-6: {} where the chart has none; the generator would exclude the webhook's own namespace.
        comp[key] = [dict(w, namespaceSelector=w.get("namespaceSelector", {})) for w in o["webhooks"]]
        comp["webhook_configuration_name" if key == "webhooks" else "validating_webhook_configuration_name"] = o["metadata"]["name"]
        if o["metadata"].get("annotations"):
            comp["webhook_annotations"] = dict(o["metadata"]["annotations"])
        self.mapped(o, f"components.{owner}.{key}")
        return True

    def map(self, objs):
        handlers = {"Deployment": self.workload, "StatefulSet": self.workload, "DaemonSet": self.workload,
                    "Service": self.service, "ConfigMap": self.config, "Secret": self.secret,
                    "ServiceAccount": self.service_account, "Ingress": self.ingress,
                    "PersistentVolumeClaim": self.claim}
        for o in objs:
            if o["kind"] in handlers:
                handlers[o["kind"]](o)
        self.rbac([o for o in objs if o["kind"] in compare.RBAC_KINDS])
        for o in objs:
            if o["kind"] in compare.WEBHOOK_KINDS:
                if not self.webhooks(o):
                    self.rows.append((ident(o), "", False, "no component serves its Service"))
            elif o["kind"] not in handlers and o["kind"] not in compare.RBAC_KINDS:
                self.rows.append((ident(o), "", False, f"the converter does not map {o['kind']}"))
        return self.p


# Output (CNV-7, CNV-9, CNV-10, CNV-18)


INTERPOLATION = re.compile(r"(\\*)\$\{([^{}]*)\}")


def escape(value):
    """CNV-7: OmegaConf would interpolate ${...} in chart text, such as shell scripts in ConfigMaps.

    Each ${...} becomes Kapitan's ${escape:'...'} resolver, which emits it literally:
    https://github.com/kapicorp/kapitan/blob/master/docs/pages/inventory/omegaconf.md
    In the quoted argument, backslashes before a quote and at the end are doubled and the quote
    escaped; backslashes in front of the ${ are doubled, since OmegaConf reads them once.
    """
    if isinstance(value, dict):
        return {k: escape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [escape(v) for v in value]
    if not isinstance(value, str) or "${" not in value:
        return value
    if "${" in INTERPOLATION.sub("", value):
        return escape_nested(value)

    def resolver(m):
        arg = re.sub(r"(\\*)'", lambda q: q.group(1) * 2 + "\\'", m.group(2))
        arg = re.sub(r"(\\+)$", lambda q: q.group(1) * 2, arg)
        return m.group(1) * 2 + "${escape:'" + arg + "'}"

    return INTERPOLATION.sub(resolver, value)


def escape_nested(text):
    """A nested ${A${B}} or an unclosed ${, which ${escape:...} cannot emit: Kapitan 0.36.3 resolves a
    value three times (two OmegaConf.resolve passes and to_container), and each pass reads one level of
    backslash escaping, so the backslashes before ${ are doubled and one added, three times over.
    """
    for _ in range(3):
        text = re.sub(r"(\\*)\$\{", lambda m: m.group(1) * 2 + "\\${", text)
    return text


def prune(d):
    return {k: v for k, v in d.items() if v not in ({}, None)}


def dump(data):
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False, width=1000, allow_unicode=True)


def write_project(project, release, namespace, mapper, crds):
    """The converted class, the secrets class, vendored CRDs and the target; returns the class directory."""
    classes = project / "inventory/classes/converted" / release
    classes.mkdir(parents=True)
    (project / "inventory/targets").mkdir(parents=True)
    (project / ".kapitan").write_text("global:\n  inventory-backend: omegaconf\n")
    compile_entries = [{"input_type": "kadet", "input_paths": ["lib/kubernetes"], "output_path": "manifests/",
                        "output_type": "yml"}]
    vendored = []
    for crd in crds:
        path = classes / "vendor" / f"{crd['metadata']['name']}.yaml"
        path.parent.mkdir(exist_ok=True)
        path.write_text(yaml.safe_dump(crd, sort_keys=False))
        vendored.append(str(path.relative_to(project)))
    if vendored:
        compile_entries.append({"input_type": "copy", "input_paths": vendored, "output_path": "crds/"})
    params = escape(mapper.p)
    values = {}
    for secret, key, param in mapper.secrets:
        entry = params["generators"]["kubernetes"]["secrets"][secret]["data"][key]
        values[param] = entry["value"]
        entry["value"] = f"${{applications.{release}.secrets.{param}}}"
    params["generators"]["kubernetes"] = prune(params["generators"]["kubernetes"])
    params["generators"] = prune(params["generators"])
    body = {"kapitan": {"dependencies": [{"type": "oci", "source": GENERATOR, "output_path": "lib/kubernetes"}],
                        "compile": compile_entries}}
    body.update(prune(params))
    (classes / "init.yml").write_text(dump({"parameters": body}))
    (classes / "secrets.yml").write_text(
        "# Secret data of the chart's render. Keep this file out of git and replace each value with a ref\n"
        "# that holds the same base64 value, such as ?{gpg:...} (docs/specs/converter.md CNV-10).\n"
        + dump({"parameters": {"applications": {release: {"secrets": values}}}}))
    (project / ".gitignore").write_text(f"{(classes / 'secrets.yml').relative_to(project)}\n")
    target = {"classes": [f"converted.{release}", f"converted.{release}.secrets"],
              "parameters": {"namespace": namespace, "kapitan": {"vars": {"target": release}}}}
    (project / f"inventory/targets/{release}.yml").write_text(dump(target))
    return classes


# Values (CNV-12)


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def effective_values(chart_dir, user_files):
    values = yaml.safe_load((chart_dir / "values.yaml").read_text()) or {}
    for dep in (yaml.safe_load((chart_dir / "Chart.yaml").read_text()) or {}).get("dependencies") or []:
        sub = chart_dir / "charts" / dep["name"] / "values.yaml"
        if sub.is_file():
            key = dep.get("alias") or dep["name"]
            values[key] = deep_merge(yaml.safe_load(sub.read_text()) or {}, values.get(key) or {})
    for f in user_files:
        values = deep_merge(values, yaml.safe_load(Path(f).read_text()) or {})
    return values


def leaves(v, path=()):
    if isinstance(v, dict) and v:
        for k, x in v.items():
            yield from leaves(x, path + (k,))
    elif isinstance(v, list) and v:
        for i, x in enumerate(v):
            yield from leaves(x, path + (i,))
    elif not isinstance(v, (dict, list)):
        yield path, v


def changed(v):
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + 7919
    if isinstance(v, float):
        return v + 0.5
    return f"{'' if v is None else v}zq9"


def text(v):
    return json.dumps(v) if isinstance(v, bool) or v is None else str(v)


def b64(s):
    try:
        return base64.b64decode(s, validate=True).decode()
    except (ValueError, UnicodeDecodeError):
        return None


# Fields Mapper leaves out where they equal the generator's default.
OMITTED = {"pull_policy", "initial_delay_seconds", "period_seconds", "timeout_seconds", "success_threshold",
           "failure_threshold", "restart_policy", "protocol", "scheme"}


def reaches(change, orig, new):
    """True when the changed field holds the value, the old string with it replaced, or its base64."""
    kind, path, a, b = change
    if kind == "added":
        return path[-1] in OMITTED and b == new
    if kind != "leaf":
        return False
    if a == orig and b == new and type(a) is type(orig):
        return True
    if any(isinstance(p, str) and p.startswith("checksum/") for p in path):
        return True  # charts restart pods by a checksum of their config
    o, n = text(orig), text(new)
    for x, y in ((a, b), (b64(a) if isinstance(a, str) else None, b64(b) if isinstance(b, str) else None)):
        if isinstance(x, str) and isinstance(y, str) and o and o in x and y == n.join(x.split(o)):
            return True
    return False


def classify(values, path, orig, changes):
    if not changes:
        off = any(isinstance(node, dict) and node.get(switch) is False
                  for i in range(len(path)) for node in [get(values, path[:i])] for switch in ("enabled", "create", "enable"))
        return "no effect, below a switch that is off" if off else "no effect"
    if any(c[0] == "structural" or (c[0] == "added" and c[1][-1] not in OMITTED) for c in changes):
        return "switch"
    return "reached" if all(reaches(c, orig, changed(orig)) for c in changes) else "derived"


def get(tree, path):
    for p in path:
        tree = tree[p]
    return tree


def value_map(chart_dir, release, namespace, user_files):
    """CNV-12: every scalar value of the effective values, rendered changed, mapped and diffed."""
    values = effective_values(chart_dir, user_files)

    def mapped(vals):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml") as f:
            yaml.safe_dump(vals, f)
            f.flush()
            _, _, rest = split(check.load_all(render(chart_dir, release, namespace, [f.name])))
        return Mapper(release, namespace).map(rest)

    base = mapped(values)  # the same values as one file, so a diff shows only the changed value

    def one(item):
        path, orig = item
        changed_values = copy.deepcopy(values)
        node = changed_values
        for p in path[:-1]:
            node = node[p]
        node[path[-1]] = changed(orig)
        try:
            changes = tree_diff(base, mapped(changed_values))
        except check.Failed as e:
            return {"value": path, "class": "render error", "error": str(e).strip().splitlines()[-1][:200]}
        rec = {"value": path, "class": classify(values, path, orig, changes)}
        if rec["class"] in ("reached", "derived"):
            rec["fields"] = [".".join(map(str, c[1])) for c in changes]
        return rec

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        out = list(pool.map(one, leaves(values)))
    for rec in out:
        rec["value"] = ".".join(map(str, rec["value"]))
    return out


# Proof (CNV-14) and report (CNV-15 to CNV-17)


def with_namespace(objs, namespace):
    """helm template leaves metadata.namespace out where the template does; kubectl applies it there."""
    out = copy.deepcopy(objs)
    for o in out:
        if o["kind"] not in CLUSTER_SCOPED:
            o["metadata"].setdefault("namespace", namespace)
    return out


def prove(chart_objs, recipe_objs, namespace, release, prefix, work, node_image):
    subjects = compare.rbac_subjects(chart_objs) | compare.rbac_subjects(recipe_objs)
    rbac_ns = compare.rbac_namespaces(chart_objs + recipe_objs, subjects, namespace)
    namespaces = {namespace} | {o["metadata"]["namespace"] for o in chart_objs + recipe_objs if o["metadata"].get("namespace")}
    clusters = {side: check.Cluster(f"{prefix}-{release}-{side}"[:50], work, node_image) for side in ("chart", "recipe")}
    try:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = {side: pool.submit(check.prove_side, clusters[side], objs, namespaces, namespace, subjects, rbac_ns)
                       for side, objs in (("chart", chart_objs), ("recipe", recipe_objs))}
            results = {side: f.result() for side, f in futures.items()}
    finally:
        for c in clusters.values():
            c.delete()
    result = compare.compare(results["chart"][0], results["recipe"][0])
    result["permissions"] = compare.diff_permissions(results["chart"][1], results["recipe"][1])
    result["subjects"] = sorted(" ".join(p for p in s if p) for s in subjects)
    return result


def classes_of(mapper, result, crds, recipe_crds, hooks):
    """CNV-15: each object in exactly one class."""
    by_name = collections.defaultdict(list)
    for d in (result or {}).get("differences", []):
        kind, _, rest = d.obj.partition("/")
        by_name[(kind.split(".")[0], rest.rsplit("/", 1)[-1])].append(d)
    only = {(i.split("/")[0].split(".")[0], i.rsplit("/", 1)[-1]) for i in (result or {}).get("only_chart", [])}
    rows = []
    for obj, section, mapped, reason in mapper.rows:
        kind, name = obj.split("/")[0], obj.rsplit("/", 1)[-1]
        if not mapped:
            rows.append((obj, "not mapped", reason))
        elif kind in compare.RBAC_KINDS:
            rows.append((obj, "RBAC, proven by permissions", section))
        elif result is None:
            rows.append((obj, "mapped, not proven", section))
        elif (kind, name) in only:
            rows.append((obj, "mapped with differences", "missing in the converted output"))
        else:
            diffs = by_name.get((kind, name), [])
            if not diffs:
                rows.append((obj, "exact", section))
            elif all(d.cls for d in diffs):
                rows.append((obj, "equal up to accepted classes", ", ".join(sorted({d.cls for d in diffs}))))
            else:
                rows.append((obj, "mapped with differences", "; ".join(str(d) for d in diffs if not d.cls)))
    for c in crds:
        rows.append((ident(c), "CRD copied" if c in recipe_crds else "CRD copied, differs", "vendored"))
    for h in hooks:
        rows.append((ident(h), "hook left out", "runs inside helm install only"))
    return rows


def md(cell):
    return str(cell).replace("|", "\\|").replace("\n", " ")


def report(out, source, release, namespace, mapper, rows, result, regenerated, values, proof_ran):
    lines = [f"# kadet-convert report: {release}", "", "## Source", "",
             f"Chart `{source['chart']}` {source['version']}"
             + (f", archive SHA-256 `{source['sha256']}`" if source["sha256"] else ", a local directory")
             + (f", OCI digest `{source['digest']}`" if source["digest"] else "")
             + f"; release `{release}`, namespace `{namespace}`.", "",
             "## Objects", ""]
    counts = collections.Counter(r[1] for r in rows)
    lines += [", ".join(f"{n} {c}" for c, n in counts.most_common()) + ".", "",
              "| Object | Class | Details |", "|---|---|---|"]
    lines += [f"| `{md(o)}` | {c} | {md(d)} |" for o, c, d in rows]
    lines.append("")
    if not proof_ran:
        lines += ["The proof did not run (`--no-proof`), so no object is called equal.", ""]
    if any("Selector scheme" in r[2] for r in rows):
        lines += ["The converted workloads select their pods by the generator's `name` label. A selector is "
                  "immutable, so `kubectl apply` over a running Helm release fails on these workloads: delete "
                  "them with `--cascade=orphan` first (CNV-17).", ""]
    if mapper.not_mappable:
        lines += ["## Not mappable fields", "",
                  "The `kubernetes` generator cannot set these fields. They count only where the proof shows a "
                  "difference.", ""]
        lines += [f"- `{o}`: " + ", ".join(f"`{f}`" for f in fields) for o, fields in mapper.not_mappable.items()]
        lines.append("")
    if regenerated:
        lines += ["## Generated at render time", "",
                  "These fields differ between two renders. The conversion keeps the first render's value; "
                  "replace it.", ""]
        lines += [f"- `{g}`" for g in regenerated] + [""]
    if mapper.renamed:
        lines += ["## Renamed RBAC objects", ""] + [f"- `{a}` to `{b}`" for a, b in mapper.renamed] + [""]
    if result is not None:
        lines += ["## Permissions", ""]
        lines += ([f"- {p}" for p in result["permissions"]] or
                  [(f"Equal for {len(result['subjects'])} subjects: " + ", ".join(f"`{s}`" for s in result["subjects"])
                    if result["subjects"] else "No subject is bound.")
                   + " Equal for users bound to view, edit and admin."])
        lines += [f"- selector: {e}" for e in result["selector_errors"]]
        lines += [f"- only in the converted output: `{i}`" for i in result["only_recipe"]] + [""]
    if mapper.secrets:
        lines += ["## Secrets", "",
                  f"The data of {len({s[0] for s in mapper.secrets})} Secret(s) is in "
                  f"`inventory/classes/converted/{release}/secrets.yml`, listed in `.gitignore`. Keep it out of "
                  "git and replace each value with a ref that holds the same base64 value.", ""]
    values_counts = collections.Counter(v["class"] for v in values)
    lines += ["## Values", "",
              f"{len(values)} values: " + ", ".join(f"{n} {c}" for c, n in values_counts.most_common())
              + ". The full map is `value-map.json`. These values reached inventory fields:", "",
              "| Value | Inventory fields |", "|---|---|"]
    lines += [f"| `{md(v['value'])}` | " + ", ".join(f"`{md(f)}`" for f in v["fields"]) + " |"
              for v in values if v["class"] == "reached"]
    (out / "report.md").write_text("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kadet-convert", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chart")
    ap.add_argument("--name", required=True, help="release name, also the name of the converted class")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("-f", "--values", action="append", default=[], type=Path)
    ap.add_argument("--repo", help="chart repository URL, as helm pull --repo takes it")
    ap.add_argument("--version", help="chart version, as helm pull --version takes it")
    ap.add_argument("--out", required=True, type=Path, help="new directory for the project and the report")
    ap.add_argument("--no-proof", action="store_true", help="convert and compile only, without kind clusters")
    ap.add_argument("--node-image", help="kind node image of the clusters, kind's default without it")
    ap.add_argument("--clusters", default="convert", help="prefix of the kind cluster names (default: convert)")
    a = ap.parse_args(argv)
    if not RELEASE_NAME.match(a.name):
        ap.error(f"--name {a.name!r}: lowercase letters, digits and '-' only, as an inventory key")
    if a.out.exists() and any(a.out.iterdir()):
        ap.error(f"--out {a.out}: not empty")
    a.out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="convert-"))
    try:
        path, source = fetch(a.chart, a.repo, a.version, work)
        chart_dir = path
        if path.is_file():
            with tarfile.open(path) as tar:
                tar.extractall(work / "src", filter="data")
            (chart_dir,) = [p for p in (work / "src").iterdir() if p.is_dir()]
        rendered = render(path, a.name, a.namespace, a.values)
        (a.out / "render.yaml").write_text(rendered)
        crds, hooks, rest = split(check.load_all(rendered))
        _, _, again = split(check.load_all(render(path, a.name, a.namespace, a.values)))
        regenerated = generated(rest, again)
        mapper = Mapper(a.name, a.namespace)
        mapper.map(rest)
        project = a.out / "project"
        classes = write_project(project, a.name, a.namespace, mapper, crds)
        for note in check.fetch_generators(classes, project, work):
            print(f"generator: {note}, attestation and index verified", file=sys.stderr)
        check.compile_recipe(project, work / "out")
        converted = check.objects_of(check.compiled_files(work / "out", a.name))
        recipe_crds = [o for o in converted if o["kind"] == "CustomResourceDefinition"]
        converted = [o for o in converted if o["kind"] != "CustomResourceDefinition"]
        result = None if a.no_proof else prove(with_namespace(rest, a.namespace), converted, a.namespace, a.name,
                                               a.clusters, work, a.node_image)
        values = value_map(chart_dir, a.name, a.namespace, a.values)
        (a.out / "value-map.json").write_text(json.dumps(values, indent=1, default=str) + "\n")
        rows = classes_of(mapper, result, crds, recipe_crds, hooks)
        report(a.out, source, a.name, a.namespace, mapper, rows, result, regenerated, values, result is not None)
        print((a.out / "report.md").read_text())
        bad = {"not mapped", "mapped with differences", "CRD copied, differs"}
        failed = any(r[1] in bad for r in rows) or bool(result and (result["permissions"] or result["selector_errors"] or result["only_recipe"]))
        return 1 if failed else 0
    except check.Failed as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
