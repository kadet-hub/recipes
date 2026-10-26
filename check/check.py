"""check: lint a recipe and validate its Kapitan output on kind, or deploy it (DEC-19).

  check lint <name>
  check <name> --level renders|deploys
  check <name> --level renders --compiled <out>   (RCP-34)

Run from the repository root through uv: uv run --locked --project check check/check.py ...
Needs kubectl, kind, docker, oras and gh on PATH (installed pinned by CI).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import yaml

import compare
import lint

VERSION = "0.10.0"
# The image the release notes of the kind version in .github/actions/tools
# list for its Kubernetes version; Renovate moves both together (RCP-30).
# renovate: datasource=docker depName=kindest/node
KIND_NODE_IMAGE = "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
# kapicorp/kapitan master plus open pull requests, built by kadet-hub/kapitan
# (RCP-24). Renovate moves the digest of the tag next (RCP-29).
# renovate: datasource=docker depName=ghcr.io/kadet-hub/kapitan
KAPITAN_NEXT = "ghcr.io/kadet-hub/kapitan:next@sha256:fca6da0da9f5caebc285740cebe1720e6d8c66dc0f25f1f9fd3367703946aef4"
INDEX = "ghcr.io/kadet-hub/index"
RELEASE_IDENTITY = "https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main"
SYSTEM_NAMESPACES = {"default", "kube-system", "kube-public", "kube-node-lease"}
WORKLOADS = ("Deployment", "StatefulSet", "DaemonSet")
# What a renders proof applies for real of a prerequisite, as of the recipe (RCP-26, RCP-55).
GRANTING_KINDS = ("Namespace", "CustomResourceDefinition", "ServiceAccount", *compare.RBAC_KINDS)
# gateway-api (RCP-55): the Gateway a recipe's tests/target.yml attaches its routes to.
GATEWAY = {
    "apiVersion": "gateway.networking.k8s.io/v1",
    "kind": "Gateway",
    "metadata": {"name": "gateway", "namespace": "gateway"},
    "spec": {
        "gatewayClassName": "cloud-provider-kind",
        "listeners": [{"name": "http", "port": 80, "protocol": "HTTP", "allowedRoutes": {"namespaces": {"from": "All"}}}],
    },
}
GATEWAY_CRDS = ("gateways.gateway.networking.k8s.io", "httproutes.gateway.networking.k8s.io")


class Failed(Exception):
    pass


class Loader(yaml.CSafeLoader if hasattr(yaml, "CSafeLoader") else yaml.SafeLoader):
    """Safe loader that reads the YAML 1.1 value tag "=" as a plain string."""


Loader.add_constructor("tag:yaml.org,2002:value", lambda loader, node: loader.construct_scalar(node))


def load_all(text):
    return compare.unwrap(list(yaml.load_all(text, Loader=Loader)))


def dump_all(objs):
    return yaml.safe_dump_all(objs, sort_keys=False)


def run(cmd, *, cwd=None, env=None, input=None, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, env=env, input=input, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise Failed(f"{' '.join(map(str, cmd))} exited {p.returncode}:\n{p.stdout[-3000:]}{p.stderr[-3000:]}")
    return p.stdout


# Sources


def with_included(recipe):
    """The recipe and the recipes it includes, from the same commit (RCP-49)."""
    return [recipe, *(recipe.parent / name for name in lint.included(recipe))]


def generator_sources(recipe):
    """The ghcr.io/kadet-hub/ dependencies the recipe and the recipes it includes pin."""
    out = []
    for path in [p for r in with_included(recipe) for p in lint.class_files(r)]:
        doc = yaml.safe_load(path.read_text()) or {}
        for dep in ((doc.get("parameters") or {}).get("kapitan") or {}).get("dependencies") or []:
            if (dep["source"], dep["output_path"]) not in out:
                out.append((dep["source"], dep["output_path"]))
    return out


def fetch_generators(recipe, project, work):
    """Pull each generator as the consumers guide verifies it (RCP-27)."""
    index_digest = run(["oras", "resolve", f"{INDEX}:latest"]).strip()
    verify = ["gh", "attestation", "verify", "--owner", "kadet-hub", "--cert-identity", RELEASE_IDENTITY]
    run(verify[:3] + [f"oci://{INDEX}@{index_digest}"] + verify[3:])
    run(["oras", "pull", "-o", str(work / "index"), f"{INDEX}@{index_digest}"])
    index = json.loads((work / "index" / "index.json").read_text())
    pulled = []
    for source, output_path in generator_sources(recipe):
        repo, _, digest = source.partition("@")
        name, _, version = repo.removeprefix("ghcr.io/kadet-hub/").partition(":")
        listed = {v: e for v, e in (index["generators"].get(name) or {}).items() if e["digest"] == digest}
        if not listed or (version and version not in listed):
            raise Failed(f"{source}: the attested index {index['serial']} does not list this digest as {version or name}")
        entry = listed[version] if version else next(iter(listed.values()))
        if entry.get("yanked"):
            raise Failed(f"{source}: yanked: {entry['yanked']}")
        ref = f"ghcr.io/kadet-hub/{name}@{digest}"
        run(verify[:3] + [f"oci://{ref}"] + verify[3:])
        run(["oras", "pull", "-o", str(work / "oci" / name), ref])
        target = project / output_path
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(work / "oci" / name / f"{name}.tar") as tar:
            tar.extractall(target, filter="data")
        pulled.append(f"{name} {version or '?'} ({digest[:19]}, index serial {index['serial']})")
    return pulled


def build_project(recipe, work):
    project = work / "project"
    for r in with_included(recipe):
        shutil.copytree(r, project / "inventory/classes/recipes" / r.name, ignore=shutil.ignore_patterns("tests"))
    (project / "inventory/targets").mkdir(parents=True)
    shutil.copy(recipe / "tests/target.yml", project / "inventory/targets" / f"{recipe.name}.yml")
    (project / ".kapitan").write_text("global:\n  inventory-backend: omegaconf\n")
    return project


def compiled_files(out, name):
    root = out / "compiled" / name
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def compile_recipe(project, out):
    """Kapitan 0.36.3, the version this check's lock installs: decides the level."""
    kapitan = Path(sys.executable).parent / "kapitan"
    run([str(kapitan), "compile", "--output-path", str(out)], cwd=project)


def compile_next(project, out):
    """The kadet-hub/kapitan next image: reported, never decides (RCP-24)."""
    out.mkdir()
    try:
        run(["docker", "run", "--rm", "--network", "none", "--user", f"{os.getuid()}:{os.getgid()}",
             "-v", f"{project}:/src:ro,z", "-v", f"{out}:/out:z", KAPITAN_NEXT,
             "compile", "--verbose", "--output-path", "/out"])
    except Failed as e:
        # Kapitan prints the cause only with --verbose, as "Compile failed: ...".
        lines = [line for line in str(e).splitlines() if "Compile failed" in line or "Error" in line]
        return (lines or str(e).splitlines())[-1].strip()
    return None


def objects_of(files):
    objs = []
    for path, data in files.items():
        if path.endswith((".yml", ".yaml")):
            objs += load_all(data.decode())
    return objs


# Clusters


def drop_nulls(value):
    """A null in a manifest leaves the field unset; a server-side apply rejects it instead."""
    if isinstance(value, dict):
        return {k: drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [drop_nulls(v) for v in value]
    return value


class Cluster:
    def __init__(self, name, work):
        self.name = name
        self.kubeconfig = work / f"{name}.kubeconfig"

    def kubectl(self, *args, input=None):
        return run(["kubectl", "--kubeconfig", str(self.kubeconfig), *args], input=input)

    def create(self):
        run(["kind", "create", "cluster", "--name", self.name, "--image", KIND_NODE_IMAGE,
             "--kubeconfig", str(self.kubeconfig), "--wait", "120s"])

    def delete(self):
        subprocess.run(["kind", "delete", "cluster", "--name", self.name], capture_output=True)

    def apply(self, objs, *flags):
        if not objs:
            return []
        # Server-side: a client-side apply stores the object as an annotation,
        # which the API rejects for CRDs above 256 KiB, such as CloudNativePG's.
        return compare.unwrap([json.loads(self.kubectl(
            "apply", "--server-side", "--field-manager", "check", *flags, "-o", "json", "-f", "-",
            input=dump_all([drop_nulls(o) for o in objs])))])

    def apply_for_real(self, objs, timeout=60):
        """CRDs first; an apply the API server rejects, such as a webhook not serving yet, again for a minute (RCP-55)."""
        crds = [o for o in objs if o["kind"] == "CustomResourceDefinition"]
        if crds:
            self.apply(crds)
            self.kubectl("wait", "--for", "condition=Established", "--timeout", "60s",
                         *[f"crd/{o['metadata']['name']}" for o in crds])
        rest = [o for o in objs if o["kind"] != "CustomResourceDefinition"]
        deadline = time.monotonic() + timeout
        while True:
            try:
                return self.apply(rest)
            except Failed:
                if time.monotonic() > deadline:
                    raise
                time.sleep(5)


def prepare(cluster, namespaces, namespace):
    """RCP-8: a fresh cluster with every namespace, the target namespace as the context's."""
    cluster.create()
    cluster.apply([{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": n}}
                   for n in sorted(namespaces - SYSTEM_NAMESPACES)])
    cluster.kubectl("config", "set-context", "--current", "--namespace", namespace)


def requirement_order(recipe):
    """The prerequisites of the recipe and its included recipes, each after the ones it requires (RCP-55)."""
    order, seen = [], set()

    def visit(r):
        for name in lint.requires(r) or []:
            if name in seen:
                continue
            seen.add(name)
            if name != lint.GATEWAY_API:
                visit(recipe.parent / name)
            order.append(name)

    for r in with_included(recipe):
        visit(r)
    return order


def prerequisites(recipe, work, compiled=None):
    """RCP-55: the recipes on the Requires lines of the recipe, its included recipes and, in turn,
    of those prerequisites, each once and after what it requires, compiled from its own tests/target.yml."""
    out = []
    for name in requirement_order(recipe):
        if name == lint.GATEWAY_API:
            out.append((name, None, []))
            continue
        if compiled:
            out.append((name, objects_of(compiled_files(compiled, name)), []))
            continue
        sub = work / "requires" / name
        sub.mkdir(parents=True)
        project = build_project(recipe.parent / name, sub)
        notes = fetch_generators(recipe.parent / name, project, sub)
        compile_recipe(project, sub / "out")
        out.append((name, objects_of(compiled_files(sub / "out", name)), notes))
    return out


def install(cluster, prereqs, full):
    """RCP-55: the prerequisites on one cluster, at renders what grants or defines, at deploys all of it."""
    for _, objs, _ in prereqs:
        if objs is None:
            install_gateway_api(cluster, full)
            continue
        if not full:
            objs = [o for o in objs if o["kind"] in GRANTING_KINDS]
        namespaces = sorted({o["metadata"]["namespace"] for o in objs if o["metadata"].get("namespace")} - SYSTEM_NAMESPACES)
        cluster.apply([{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": n}} for n in namespaces])
        cluster.apply_for_real(objs)
        if full:
            wait_rollouts(cluster, objs)


def install_gateway_api(cluster, full):
    """cloud-provider-kind installs the Gateway API CRDs on each kind cluster; at deploys add the Gateway."""
    deadline = time.monotonic() + 180
    while subprocess.run(["kubectl", "--kubeconfig", str(cluster.kubeconfig), "get", *[f"crd/{c}" for c in GATEWAY_CRDS]],
                         capture_output=True).returncode:
        if time.monotonic() > deadline:
            raise Failed(f"{cluster.name}: cloud-provider-kind installed no Gateway API CRDs")
        time.sleep(2)
    cluster.kubectl("wait", "--for", "condition=Established", "--timeout", "60s", *[f"crd/{c}" for c in GATEWAY_CRDS])
    if full:
        cluster.apply_for_real([{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "gateway"}}, GATEWAY])
        cluster.kubectl("wait", "-n", "gateway", "gateway/gateway", "--for", "condition=Programmed", "--timeout", "180s")


class GatewayProvider:
    """cloud-provider-kind for the duration of a proof that requires gateway-api (RCP-55). It manages every
    kind cluster on the Docker host, so it runs only where check's clusters are the only ones, as in CI."""

    def __init__(self, prereqs, work):
        self.proc = None
        if any(objs is None for _, objs, _ in prereqs):
            self.log = open(work / "cloud-provider-kind.log", "w")
            self.proc = subprocess.Popen(["cloud-provider-kind", "--enable-default-ingress=false"],
                                         stdout=self.log, stderr=subprocess.STDOUT)

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.log.close()


def wait_rollouts(cluster, objs):
    for o in objs:
        if o["kind"] in WORKLOADS:
            meta = o["metadata"]
            cluster.kubectl("rollout", "status", f"{o['kind'].lower()}/{meta['name']}",
                            "-n", meta.get("namespace", "default"), "--timeout", "300s")


def owned(recipe, objs, work, compiled=None):
    """RCP-49: the parent's objects, and those of each included recipe, which its own tests/target.yml renders."""
    included = {}
    for other in with_included(recipe)[1:]:
        sub = work / "included" / other.name
        if not compiled and not (sub / "out").is_dir():
            sub.mkdir(parents=True)
            project = build_project(other, sub)
            fetch_generators(other, project, sub)
            compile_recipe(project, sub / "out")
        included[other.name] = {(o["kind"], o["metadata"].get("name"))
                                for o in objects_of(compiled_files(compiled or sub / "out", other.name))}
    return partition(objs, included)


def partition(objs, included):
    """The objects whose kind and name an included recipe renders are its own, the rest the parent's."""
    own, parts = [], {name: [] for name in included}
    for o in objs:
        key = (o["kind"], o["metadata"].get("name"))
        owner = next((name for name, keys in included.items() if key in keys), None)
        (parts[owner] if owner else own).append(o)
    return own, parts


def apply_renders(cluster, objs, namespaces, namespace, prereqs=()):
    """RCP-8, RCP-26: CRDs, ServiceAccounts and RBAC for real, every other object in a server-side dry run."""
    prepare(cluster, namespaces, namespace)
    install(cluster, prereqs, full=False)
    crds = [o for o in objs if o["kind"] == "CustomResourceDefinition"]
    rest = [o for o in objs if o["kind"] != "CustomResourceDefinition"]
    if crds:
        cluster.apply(crds)
        cluster.kubectl("wait", "--for", "condition=Established", "--timeout", "60s",
                        *[f"crd/{o['metadata']['name']}" for o in crds])
    cluster.apply(rest, "--dry-run=server")
    cluster.apply([o for o in rest if o["kind"] in compare.RBAC_KINDS or o["kind"] == "ServiceAccount"])


def deploy(cluster, objs, recipe, prereqs=()):
    """RCP-26: install for real, wait for every workload, run tests/smoke."""
    install(cluster, prereqs, full=True)
    cluster.apply_for_real(objs)
    wait_rollouts(cluster, objs)
    env = {**os.environ, "KUBECONFIG": str(cluster.kubeconfig)}
    return run([str((recipe / "tests/smoke").resolve())], cwd=recipe, env=env, timeout=600)


# Commands


def cmd_lint(recipe, work, compiled=None):
    errors = lint.lint_files(recipe)
    if errors:
        return errors, []
    source, _ = lint.readme_fields(recipe)
    notes = []
    if compiled:
        for name in [r.name for r in with_included(recipe)] + requirement_order(recipe):
            if name != lint.GATEWAY_API and not (compiled / "compiled" / name).is_dir():
                raise Failed(f"{compiled / 'compiled' / name}: no compiled output of {name} (RCP-34)")
    else:
        project = build_project(recipe, work)
        notes = fetch_generators(recipe, project, work)
        compile_recipe(project, work / "out")
    objs = objects_of(compiled_files(compiled or work / "out", recipe.name))
    own, parts = owned(recipe, objs, work, compiled)
    errors = []
    for other, other_objs in parts.items():
        errors += lint.lint_output(other, other_objs, {o["metadata"]["name"] for o in other_objs})
    if source[0] == "compose":
        return errors + lint.lint_output(recipe.name, own, set()) + lint.lint_compose_output(own), notes
    if source[0] == "design":
        return errors + lint.lint_output(recipe.name, own, set()) + lint.lint_design_output(own, source[1]), notes
    # RCP-3: which names a chart or release manifest uses is the migration's to check (DEC-19).
    return errors + lint.lint_output(recipe.name, own, {o["metadata"]["name"] for o in own}), notes


def cmd_check(recipe, level, work, keep, compiled=None):
    report = []

    def say(line=""):
        report.append(line)
        print(line, flush=True)

    errors, notes = cmd_lint(recipe, work, compiled)
    say(f"check {VERSION}: {recipe.name} at level {level}")
    for n in notes:
        say(f"generator: {n}, attestation and index verified")
    if errors:
        for e in errors:
            say(f"lint: {e}")
        return report, True
    namespace = yaml.safe_load((recipe / "tests/target.yml").read_text())["parameters"]["namespace"]
    objs = objects_of(compiled_files(compiled or work / "out", recipe.name))
    if compiled:
        say(f"compiled: given in {compiled}, generators not verified by check")
    prereqs = prerequisites(recipe, work, compiled)
    for name, prereq_objs, prereq_notes in prereqs:
        if prereq_objs is None:
            say(f"requires: {name}, cloud-provider-kind with the Gateway gateway/gateway, installed before the proof")
            continue
        say(f"requires: {name}, {len(prereq_objs)} objects, installed before the proof")
        for n in prereq_notes:
            say(f"requires: {name}: generator: {n}, attestation and index verified")
    gateways = GatewayProvider(prereqs, work)
    try:
        failed = proof(recipe, level, work, keep, say, namespace, objs, prereqs, compiled)
    finally:
        gateways.stop()
    return report, failed


def proof(recipe, level, work, keep, say, namespace, objs, prereqs, compiled=None):
    if compiled:
        say(f"kapitan next ({KAPITAN_NEXT}): not compiled, the compiled output is given (RCP-34)")
    elif next_error := compile_next(work / "project", work / "next"):
        say(f"kapitan next ({KAPITAN_NEXT}): compile failed, not deciding: {next_error}")
    else:
        files = compiled_files(work / "out", recipe.name)
        other = compiled_files(work / "next", recipe.name)
        changed = sorted(p for p in set(files) | set(other) if files.get(p) != other.get(p))
        say(f"kapitan next ({KAPITAN_NEXT}): "
            + (f"output differs in {', '.join(changed)}, not deciding" if changed else "same output as 0.36.3"))

    _, parts = owned(recipe, objs, work, compiled)
    for other, other_objs in parts.items():
        for o in other_objs:
            say(f"included {other}: `{o['kind']}/{o['metadata']['name']}`")

    # RCP-8, RCP-26: one cluster, at renders the apply with its dry run, at deploys the recipe deployed for real.
    cluster = Cluster(f"check-{recipe.name}-{os.getpid()}"[:50], work)
    namespaces = {namespace} | {o["metadata"]["namespace"] for o in objs if o["metadata"].get("namespace")}
    failed = False
    try:
        if level == "renders":
            apply_renders(cluster, objs, namespaces, namespace, prereqs)
            say("renders: passed")
        else:
            prepare(cluster, namespaces, namespace)
            say("smoke: " + (deploy(cluster, objs, recipe, prereqs).strip().splitlines() or ["passed"])[-1])
            say("deploys: passed")
        if level == "migrates":
            failed = True
            say("migrates: not implemented in this version of check")
    finally:
        if not keep:
            cluster.delete()
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("args", nargs="+", metavar="lint <name> | <name>")
    parser.add_argument("--level", choices=lint.LEVELS, default="renders")
    parser.add_argument("--report", type=Path, help="also write the report to this file")
    parser.add_argument("--keep", action="store_true", help="keep the kind clusters and the work directory")
    parser.add_argument("--compiled", type=Path, metavar="OUT",
                        help="Kapitan output path with compiled/<recipe>/ of the recipe, its included recipes and prerequisites (RCP-34)")
    args = parser.parse_args(argv)
    if args.args[0] == "lint" and len(args.args) == 2:
        mode, name = "lint", args.args[1]
    elif len(args.args) == 1:
        mode, name = "check", args.args[0]
    else:
        parser.error("usage: check lint <name> | check <name> --level <level>")
    if args.compiled and (mode == "lint" or args.level != "renders"):
        parser.error("--compiled goes with check <name> --level renders (RCP-34)")
    recipe = Path(name.rstrip("/")).resolve()
    if not (recipe / "init.yml").is_file():
        parser.error(f"{name}: not a recipe directory")
    work = Path(tempfile.mkdtemp(prefix="check-"))
    try:
        if mode == "lint":
            errors, _ = cmd_lint(recipe, work)
            for e in errors:
                print(f"lint: {e}")
            for w in [] if errors else lint.lint_warnings(recipe):
                print(f"lint: warning: {w}")
            print(f"lint: {recipe.name}: " + ("failed" if errors else "passed"))
            return 1 if errors else 0
        report, failed = cmd_check(recipe, args.level, work, args.keep, args.compiled)
        if args.report:
            args.report.write_text("\n".join(report) + "\n")
        return 1 if failed else 0
    except Failed as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    finally:
        if args.keep:
            print(f"work directory: {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
