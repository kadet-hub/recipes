"""check: lint a recipe, or prove it against the chart it replaces.

  check lint <name>
  check <name> --level renders|deploys

Run from the repository root through uv: uv run --locked --project check check/check.py ...
Needs helm, kubectl, kind, docker, oras and gh on PATH (installed pinned by CI).
"""

import argparse
import concurrent.futures
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

VERSION = "0.1.0"
# The image the release notes of the kind version in .github/actions/tools
# list for its Kubernetes version; Renovate moves both together (RCP-30).
# renovate: datasource=docker depName=kindest/node
KIND_NODE_IMAGE = "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5"
# kapicorp/kapitan master plus open pull requests, built by kadet-hub/kapitan
# (RCP-24). Renovate moves the digest of the tag next (RCP-29).
# renovate: datasource=docker depName=ghcr.io/kadet-hub/kapitan
KAPITAN_NEXT = "ghcr.io/kadet-hub/kapitan:next@sha256:a7b7a163b89c8423a1789fe46b8b86420199443b0a9f4179a1b960359b2e43f3"
INDEX = "ghcr.io/kadet-hub/index"
RELEASE_IDENTITY = "https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main"
BUILTIN_ROLES = ("view", "edit", "admin")
SYSTEM_NAMESPACES = {"default", "kube-system", "kube-public", "kube-node-lease"}
WORKLOADS = ("Deployment", "StatefulSet", "DaemonSet")


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


def generator_sources(recipe):
    """The ghcr.io/kadet-hub/ dependencies the recipe pins."""
    out = []
    for path in lint.class_files(recipe):
        doc = yaml.safe_load(path.read_text()) or {}
        for dep in ((doc.get("parameters") or {}).get("kapitan") or {}).get("dependencies") or []:
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


def fetch_chart(source, work):
    """helm pull by digest; the chart's version must be the one the README names."""
    repo, version, digest = source
    out = work / "chart"
    out.mkdir()
    run(["helm", "pull", f"oci://{repo}@{digest}", "-d", str(out)])
    (tgz,) = out.glob("*.tgz")
    chart = yaml.safe_load(run(["helm", "show", "chart", str(tgz)]))
    if str(chart.get("version")) != version:
        raise Failed(f"oci://{repo}@{digest} is version {chart.get('version')}, the README names {version}")
    return tgz


def render_chart(name, recipe, tgz, namespace):
    """The chart's objects, and the hooks left out (RCP-25)."""
    text = run(["helm", "template", name, str(tgz), "-n", namespace, "-f", str(recipe / "tests/values.yaml"), "--include-crds"])
    objs, hooks = [], []
    for o in load_all(text):
        if "helm.sh/hook" in ((o.get("metadata") or {}).get("annotations") or {}):
            hooks.append(f"{o['kind']}/{o['metadata']['name']}")
        else:
            objs.append(o)
    return objs, hooks


def build_project(recipe, work):
    project = work / "project"
    shutil.copytree(recipe, project / "inventory/classes/recipes" / recipe.name, ignore=shutil.ignore_patterns("tests"))
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
        return compare.unwrap([json.loads(self.kubectl("apply", *flags, "-o", "json", "-f", "-", input=dump_all(objs)))])

    def wait_aggregation(self, objs, timeout=60):
        """The built-in roles carry the rules of the ClusterRoles that aggregate into them."""
        for role in BUILTIN_ROLES:
            want = [r for o in compare.aggregated(objs, role) for r in o.get("rules") or []]
            deadline = time.monotonic() + timeout
            while True:
                have = json.loads(self.kubectl("get", "clusterrole", role, "-o", "json")).get("rules") or []
                missing = [r for r in want if r not in have]
                if not missing:
                    break
                if time.monotonic() > deadline:
                    raise Failed(f"{self.name}: ClusterRole {role} did not aggregate {missing}")
                time.sleep(1)

    def can_i(self, subject, namespace):
        return compare.normalize_can_i(
            self.kubectl("auth", "can-i", "--list", "-n", namespace, *compare.impersonation(subject))
        )


def prove_side(cluster, objs, namespaces, namespace, subjects, rbac_namespaces):
    """RCP-8, RCP-26: the API server's view of one side and what each subject may do."""
    cluster.create()
    cluster.apply([{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": n}}
                   for n in sorted(namespaces - SYSTEM_NAMESPACES)])
    cluster.kubectl("config", "set-context", "--current", "--namespace", namespace)
    crds = [o for o in objs if o["kind"] == "CustomResourceDefinition"]
    rest = [o for o in objs if o["kind"] != "CustomResourceDefinition"]
    if crds:
        cluster.apply(crds)
        names = [f"crd/{o['metadata']['name']}" for o in crds]
        cluster.kubectl("wait", "--for", "condition=Established", "--timeout", "60s", *names)
        crds = compare.unwrap([json.loads(cluster.kubectl("get", *names, "-o", "json"))])
    stored = crds + cluster.apply(rest, "--dry-run=server")
    granting = [o for o in rest if o["kind"] in compare.RBAC_KINDS or o["kind"] == "ServiceAccount"]
    cluster.apply(granting)
    for role in BUILTIN_ROLES:
        cluster.kubectl("create", "clusterrolebinding", f"check-{role}", "--clusterrole", role, "--user", f"check-{role}")
    cluster.wait_aggregation(granting)
    permissions = {}
    for subject in sorted(subjects):
        kind, ns, name = subject
        for n in sorted(rbac_namespaces):
            permissions[f"{kind} {ns + '/' if ns else ''}{name} in {n}"] = cluster.can_i(subject, n)
    for role in BUILTIN_ROLES:
        permissions[f"User check-{role} (bound to {role}) in default"] = cluster.can_i(("User", "", f"check-{role}"), "default")
    return stored, permissions


def deploy(cluster, objs, recipe):
    """RCP-26: install for real, wait for every workload, run tests/smoke."""
    cluster.apply(objs)
    for o in objs:
        if o["kind"] in WORKLOADS:
            meta = o["metadata"]
            cluster.kubectl("rollout", "status", f"{o['kind'].lower()}/{meta['name']}",
                            "-n", meta.get("namespace", "default"), "--timeout", "300s")
    env = {**os.environ, "KUBECONFIG": str(cluster.kubeconfig)}
    return run([str((recipe / "tests/smoke").resolve())], cwd=recipe, env=env, timeout=600)


# Commands


def cmd_lint(recipe, work):
    errors = lint.lint_files(recipe)
    if errors:
        return errors, []
    source, _ = lint.readme_fields(recipe)
    namespace = yaml.safe_load((recipe / "tests/target.yml").read_text())["parameters"]["namespace"]
    project = build_project(recipe, work)
    notes = fetch_generators(recipe, project, work)
    compile_recipe(project, work / "out")
    chart, _ = render_chart(recipe.name, recipe, fetch_chart(source, work), namespace)
    errors = lint.lint_output(recipe.name, objects_of(compiled_files(work / "out", recipe.name)),
                              {o["metadata"]["name"] for o in chart})
    return errors, notes


def cmd_check(recipe, level, work, keep):
    report, failed = [], False

    def say(line=""):
        report.append(line)
        print(line, flush=True)

    errors, notes = cmd_lint(recipe, work)
    say(f"check {VERSION}: {recipe.name} at level {level}")
    for n in notes:
        say(f"generator: {n}, attestation and index verified")
    if errors:
        for e in errors:
            say(f"lint: {e}")
        return report, True
    source, _ = lint.readme_fields(recipe)
    namespace = yaml.safe_load((recipe / "tests/target.yml").read_text())["parameters"]["namespace"]
    say(f"chart: oci://{source[0]}:{source[1]}@{source[2]}, values tests/values.yaml")
    chart, hooks = render_chart(recipe.name, recipe, next((work / "chart").glob("*.tgz")), namespace)
    readme = (recipe / "README.md").read_text()
    for h in hooks:
        listed = f"`{h}`" in readme
        failed |= not listed
        say(f"hook left out: {h}" + ("" if listed else " NOT LISTED in README.md (RCP-25)"))
    files = compiled_files(work / "out", recipe.name)
    objs = objects_of(files)

    project = work / "project"
    next_error = compile_next(project, work / "next")
    if next_error:
        say(f"kapitan next ({KAPITAN_NEXT}): compile failed, not deciding: {next_error}")
    else:
        other = compiled_files(work / "next", recipe.name)
        changed = sorted(p for p in set(files) | set(other) if files.get(p) != other.get(p))
        say(f"kapitan next ({KAPITAN_NEXT}): "
            + (f"output differs in {', '.join(changed)}, not deciding" if changed else "same output as 0.36.3"))

    subjects = compare.rbac_subjects(chart) | compare.rbac_subjects(objs)
    rbac_ns = compare.rbac_namespaces(chart + objs, subjects)
    namespaces = {namespace} | {o["metadata"]["namespace"] for o in chart + objs if o["metadata"].get("namespace")}
    clusters = {side: Cluster(f"check-{recipe.name}-{side}-{os.getpid()}"[:50], work) for side in ("chart", "recipe")}
    try:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = {side: pool.submit(prove_side, clusters[side], side_objs, namespaces, namespace, subjects, rbac_ns)
                       for side, side_objs in (("chart", chart), ("recipe", objs))}
            (chart_stored, chart_perms), (recipe_stored, recipe_perms) = (futures[s].result() for s in ("chart", "recipe"))

        result = compare.compare(chart_stored, recipe_stored)
        say(f"objects outside RBAC: chart {result['objects'][0]}, recipe {result['objects'][1]}")
        for i in result["only_chart"]:
            failed = True
            say(f"only in the chart: {i}")
        for i in result["only_recipe"]:
            failed = True
            say(f"only in the recipe: {i}")
        for d in result["differences"]:
            failed |= not d.cls
            say(f"difference: {d}")
        for e in result["selector_errors"]:
            failed = True
            say(f"selector: {e}")
        if not result["selector_errors"]:
            say(f"selectors: {result['selection_equal']} select the same objects on both sides")
        perm_diff = compare.diff_permissions(chart_perms, recipe_perms)
        for line in perm_diff:
            failed = True
            say(f"permissions: {line}")
        if not perm_diff:
            say(f"permissions: equal for {len(subjects)} subjects in {', '.join(sorted(rbac_ns))}"
                f" and for users bound to {', '.join(BUILTIN_ROLES)}")
        for label in compare.untested_aggregation(chart + objs):
            say(f"permissions: not tested on kind: {label}")
        if not failed:
            say("renders: passed")
        if level in ("deploys", "migrates") and not failed:
            say("smoke: " + (deploy(clusters["recipe"], objs, recipe).strip().splitlines() or ["passed"])[-1])
            say("deploys: passed")
        if level == "migrates":
            failed = True
            say("migrates: not implemented in this version of check")
    finally:
        if not keep:
            for c in clusters.values():
                c.delete()
    return report, failed


def main(argv=None):
    parser = argparse.ArgumentParser(prog="check", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("args", nargs="+", metavar="lint <name> | <name>")
    parser.add_argument("--level", choices=lint.LEVELS, default="renders")
    parser.add_argument("--report", type=Path, help="also write the report to this file")
    parser.add_argument("--keep", action="store_true", help="keep the kind clusters and the work directory")
    args = parser.parse_args(argv)
    if args.args[0] == "lint" and len(args.args) == 2:
        mode, name = "lint", args.args[1]
    elif len(args.args) == 1:
        mode, name = "check", args.args[0]
    else:
        parser.error("usage: check lint <name> | check <name> --level <level>")
    recipe = Path(name.rstrip("/")).resolve()
    if not (recipe / "init.yml").is_file():
        parser.error(f"{name}: not a recipe directory")
    work = Path(tempfile.mkdtemp(prefix="check-"))
    try:
        if mode == "lint":
            errors, _ = cmd_lint(recipe, work)
            for e in errors:
                print(f"lint: {e}")
            print(f"lint: {recipe.name}: " + ("failed" if errors else "passed"))
            return 1 if errors else 0
        report, failed = cmd_check(recipe, args.level, work, args.keep)
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
