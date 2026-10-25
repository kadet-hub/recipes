"""check lint: the rules a recipe's files and its compiled output must follow."""

import hashlib
import os
import re
from pathlib import Path

import yaml

import compare

LEVELS = ("renders", "deploys", "migrates")
SOURCE_LINE = re.compile(r"^Source: `oci://(\S+?):(\S+?)@(sha256:[0-9a-f]{64})`$", re.M)
COMPOSE_LINE = re.compile(
    r"^Source: `https://github\.com/([\w.-]+/[\w.-]+)/blob/([0-9a-f]{40})/(\S+?)@(sha256:[0-9a-f]{64})`$", re.M
)
MANIFEST_LINE = re.compile(
    r"^Source: `https://github\.com/([\w.-]+/[\w.-]+)/releases/download/([^/\s`]+)/([^/\s`@]+)@(sha256:[0-9a-f]{64})`$", re.M
)
IMAGE_LINE = re.compile(r"^Source: `([a-z0-9.-]+\.[a-z]+/[\w./-]+):([\w.-]+)@(sha256:[0-9a-f]{64})`$", re.M)
LEVEL_LINE = re.compile(r"^Level: `(\w+)`$", re.M)
REQUIRES_LINE = re.compile(r"^Requires: (.*)$", re.M)
REQUIRES_ENTRIES = re.compile(r"^`[a-z0-9][a-z0-9-]*`(, `[a-z0-9][a-z0-9-]*`)*$")
GATEWAY_API = "gateway-api"
DEPENDENCY = re.compile(r"^ghcr\.io/kadet-hub/([a-z0-9][a-z0-9._-]*)(:[\w.-]+)?@sha256:[0-9a-f]{64}$")
PINNED = re.compile(r"@sha256:[0-9a-f]{64}$")
KUBERNETES = re.compile(r"^ghcr\.io/kadet-hub/kubernetes:(\d+)\.(\d+)\.(\d+)@")
IMAGE_ARG = re.compile(r"^--?[\w-]*image[\w-]*=(.+)$")
FORBIDDEN_RESOLVER = re.compile(r"\$\{\s*(from_file|write|oc\.env|filename|parent_filename|path|parent_path)\s*:")
SHA_COMMENT = re.compile(r"#.*SHA-256 ([0-9a-f]{64})")


def class_files(recipe):
    """Every file of the recipe that can act as a class: its YAML files but tests/ and copy inputs below the root (RCP-36)."""
    recipe = Path(recipe)
    prefix = f"inventory/classes/recipes/{recipe.name}/"
    files = sorted(
        p for p in recipe.rglob("*")
        if p.suffix in (".yml", ".yaml") and p.is_file() and p.relative_to(recipe).parts[0] != "tests"
    )
    data = set()
    for path in files:
        try:
            entries = yaml.safe_load(path.read_text())["parameters"]["kapitan"]["compile"]
            data.update(
                recipe / p.removeprefix(prefix)
                for e in entries if e["input_type"] == "copy"
                for p in e["input_paths"] if p.startswith(prefix)
            )
        except (yaml.YAMLError, LookupError, TypeError, AttributeError):
            continue
    return [p for p in files if p.parent == recipe or p not in data]


def resolve_class(recipe, f, cls):
    """The file Kapitan 0.36.3's omegaconf backend loads for class cls included from recipe/f, or None
    when it is not found or may lie outside the repository (RCP-36)."""
    base = os.path.dirname(f"recipes/{Path(recipe).name}/{f}") if cls.startswith(".") else ""
    parts = cls.split(".")
    for ext in (".yml", ".yaml"):
        for case in (
            os.path.join(base, *parts, "init" + ext),
            os.path.join(base, *parts) + ext,
            os.path.join(base, *parts[2:]) + ext,
            os.path.join(base, *parts[2:], "init" + ext),
        ):
            case = os.path.normpath(case)
            if not case.startswith("recipes/"):
                return None
            path = Path(recipe).parent / case.removeprefix("recipes/")
            if path.is_file():
                return path
    return None


def readme_fields(recipe):
    """Source and Level lines of the README (RCP-23). The source is ("chart", (repo, version, digest)),
    ("compose", (repo, commit, path, digest)), ("manifest", (repo, tag, file, digest)),
    ("design", (image, tag, digest)) or None."""
    text = (Path(recipe) / "README.md").read_text()
    chart, compose, image = SOURCE_LINE.search(text), COMPOSE_LINE.search(text), IMAGE_LINE.search(text)
    manifest = MANIFEST_LINE.search(text)
    level = LEVEL_LINE.search(text)
    return (
        ("chart", chart.groups()) if chart else ("compose", compose.groups()) if compose
        else ("manifest", manifest.groups()) if manifest else ("design", image.groups()) if image else None,
        level.group(1) if level else None,
    )


def requires(recipe):
    """The entries of the README's Requires line (RCP-54), [] without one, None when it is malformed."""
    m = REQUIRES_LINE.search((Path(recipe) / "README.md").read_text())
    if not m:
        return []
    if not REQUIRES_ENTRIES.match(m.group(1).strip()):
        return None
    return re.findall(r"`([a-z0-9-]+)`", m.group(1))


def included(recipe):
    """The recipes of this repository that a class file of the recipe includes as recipes.<other> (RCP-47)."""
    recipe = Path(recipe)
    out = set()
    for path in class_files(recipe):
        try:
            classes = (yaml.safe_load(path.read_text()) or {}).get("classes") or []
        except (yaml.YAMLError, AttributeError):
            continue
        for cls in classes:
            parts = str(cls).split(".")
            if parts[0] == "recipes" and len(parts) > 1 and parts[1] != recipe.name:
                out.add(parts[1])
    return sorted(out)


def _requires_errors(recipe):
    """RCP-54: entries are recipes of this repository or gateway-api, none also included, no cycle."""
    entries = requires(recipe)
    if entries is None:
        return ["README.md: the Requires line is not ``Requires: `<entry>`[, `<entry>`]`` (RCP-54)"]
    errors = []
    for entry in entries:
        if entry != GATEWAY_API and (entry == recipe.name or not (recipe.parent / entry / "init.yml").is_file()):
            errors.append(f"README.md: Requires {entry}, which is neither another recipe of this repository nor {GATEWAY_API} (RCP-54)")
        elif entry in included(recipe):
            errors.append(f"README.md: Requires {entry}, which the recipe also includes (RCP-54)")
    # A cycle through the prerequisites' own Requires lines.
    path, seen = [], set()

    def visit(name):
        if name == recipe.name and path:
            return " -> ".join([recipe.name, *path])
        if name in seen or name == GATEWAY_API or not (recipe.parent / name / "README.md").is_file():
            return None
        seen.add(name)
        for entry in requires(recipe.parent / name) or []:
            path.append(entry)
            found = visit(entry)
            if found:
                return found
            path.pop()
        return None

    for entry in entries:
        path[:] = [entry]
        cycle = visit(entry)
        if cycle:
            errors.append(f"README.md: requires itself through {cycle} (RCP-54)")
            break
    return errors


def _include_errors(recipe):
    """RCP-47: an included recipe includes no recipe; RCP-48: shared generators at the same source."""
    errors, pins = [], {}
    for r in [recipe, *(recipe.parent / o for o in included(recipe))]:
        if r != recipe and included(r):
            errors.append(f"includes {r.name}, which includes {', '.join(included(r))} itself (RCP-47)")
        for path in class_files(r):
            try:
                kapitan = ((yaml.safe_load(path.read_text()) or {}).get("parameters") or {}).get("kapitan") or {}
            except (yaml.YAMLError, AttributeError):
                continue
            for dep in kapitan.get("dependencies") or []:
                pins.setdefault(str(dep.get("output_path", "")).rstrip("/"), set()).add((str(dep.get("source")), r.name))
    for output_path, sources in sorted(pins.items()):
        if len({s for s, _ in sources}) > 1:
            listed = ", ".join(f"{s} ({n})" for s, n in sorted(sources))
            errors.append(f"{output_path} is pinned at different sources: {listed} (RCP-48)")
    return errors


def _flow_errors(f, text):
    """RCP-4: flow style only for a node on one line of at most 80 characters."""
    lines = text.splitlines()
    errors = []

    def walk(node):
        if isinstance(node, (yaml.MappingNode, yaml.SequenceNode)) and node.flow_style:
            start, end = node.start_mark.line, node.end_mark.line
            if start != end or len(lines[start]) > 80:
                errors.append(f"{f}:{start + 1}: flow style on a line longer than 80 characters (RCP-4)")
            return
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                walk(k)
                walk(v)
        elif isinstance(node, yaml.SequenceNode):
            for v in node.value:
                walk(v)

    for doc in yaml.compose_all(text):
        if doc is not None:
            walk(doc)
    return errors


def _scoped(name, key):
    return key == name or key.startswith(name + "-")


def _parameter_errors(name, f, params):
    """RCP-2, RCP-7, RCP-17 (kapitan section) and RCP-18."""
    errors = []
    for top, value in params.items():
        if top == "components":
            for comp, body in (value or {}).items():
                if not _scoped(name, comp):
                    errors.append(f"{f}: components.{comp} is not below the recipe's name (RCP-18)")
                if (body or {}).get("application") != name:
                    errors.append(f"{f}: components.{comp} does not set application: {name} (RCP-2)")
        elif top == "applications":
            for app in value or {}:
                if app != name:
                    errors.append(f"{f}: applications.{app} is not the recipe's application (RCP-18)")
        elif top == "generators":
            for gen, sections in (value or {}).items():
                for section, entries in (sections or {}).items():
                    where = f"generators.{gen}.{section}"
                    if gen == "manifest" and section == "default_config":
                        errors.append(f"{f}: {where} is merged into every component of a target (RCP-2)")
                        continue
                    if section == "manifests":
                        errors.append(f"{f}: {where} copies whole objects through (RCP-7)")
                    if not isinstance(entries, dict):
                        errors.append(f"{f}: {where} is set for the whole target (RCP-18)")
                        continue
                    for entry in entries:
                        if not _scoped(name, entry):
                            errors.append(f"{f}: {where}.{entry} is not below the recipe's name (RCP-18)")
        elif top == "kapitan":
            for key in value or {}:
                if key not in ("dependencies", "compile"):
                    errors.append(f"{f}: kapitan.{key} is not a recipe's to set (RCP-18)")
        else:
            errors.append(f"{f}: parameters.{top} is not below the recipe's name (RCP-18)")
    return errors


def _dependency_errors(f, kapitan, pinned):
    """RCP-17: oci artifacts of ghcr.io/kadet-hub/ pinned by digest; adds their output paths to pinned."""
    errors = []
    for dep in kapitan.get("dependencies") or []:
        source = str(dep.get("source", ""))
        if dep.get("type") != "oci" or not DEPENDENCY.match(source):
            errors.append(f"{f}: dependency {source or dep} is not an oci artifact of ghcr.io/kadet-hub/ pinned by digest (RCP-17)")
            continue
        pinned.add(str(dep.get("output_path", "")).rstrip("/"))
    return errors


def _compile_errors(name, recipe, f, text, kapitan, pinned):
    """RCP-17: kadet entries on the recipe's pinned generators, copies with their hash."""
    errors = []
    hashes = set(SHA_COMMENT.findall(text))
    for entry in kapitan.get("compile") or []:
        kind = entry.get("input_type")
        paths = [str(p).rstrip("/") for p in entry.get("input_paths") or []]
        if kind == "kadet":
            for p in paths:
                if p not in pinned:
                    errors.append(f"{f}: kadet input {p} is not a generator the recipe pins (RCP-17)")
        elif kind == "copy":
            prefix = f"inventory/classes/recipes/{name}/"
            for p in paths:
                local = Path(recipe) / p[len(prefix):]
                if not p.startswith(prefix) or not local.is_file():
                    errors.append(f"{f}: copy input {p} is not a file of the recipe (RCP-17)")
                elif hashlib.sha256(local.read_bytes()).hexdigest() not in hashes:
                    errors.append(f"{f}: copy input {p} has no matching SHA-256 comment (RCP-17)")
                if local.is_file() and not local.with_name(local.name + ".LICENSE").is_file():
                    errors.append(f"{f}: copy input {p} has no {local.name}.LICENSE (RCP-35)")
        else:
            errors.append(f"{f}: compile entry of input_type {kind} (RCP-17)")
    return errors


def lint_files(recipe):
    """The rules that need only the recipe's files. Returns a list of errors."""
    recipe = Path(recipe)
    name = recipe.name
    errors = []
    for required in ("init.yml", "README.md", "tests/target.yml"):
        if not (recipe / required).is_file():
            errors.append(f"{required} is missing (RCP-1)")
    if errors:
        return errors
    source, level = readme_fields(recipe)
    if not source:
        errors.append(
            "README.md has no line Source: `oci://<chart>:<version>@sha256:<digest>`,"
            " `https://github.com/<owner>/<repo>/blob/<commit>/<path>@sha256:<digest>`,"
            " `https://github.com/<owner>/<repo>/releases/download/<tag>/<file>@sha256:<digest>`"
            " or `<registry>/<repository>:<tag>@sha256:<digest>` (RCP-23)"
        )
    elif source[0] == "chart" and not (recipe / "tests/values.yaml").is_file():
        errors.append("tests/values.yaml is missing (RCP-1)")
    elif source[0] == "compose" and level != "deploys":
        errors.append(f"a compose source is proven at level deploys, not {level} (RCP-38)")
    elif source[0] == "design" and level != "deploys":
        errors.append(f"a designed recipe is proven at level deploys, not {level} (RCP-44)")
    sections = [section.partition("\n") for section in re.split(r"^## ", (recipe / "README.md").read_text(), flags=re.M)[1:]]
    headings = [heading.strip() for heading, _, _ in sections]
    after = headings.index("Include") + 1 if "Include" in headings else len(headings)
    if headings[after : after + 1] != ["Required parameters"] or not sections[after][2].strip():
        errors.append('README.md has no section "Required parameters" with text directly after "Include" (RCP-40)')
    if level not in LEVELS:
        errors.append(f"README.md has no line Level: `<{'|'.join(LEVELS)}>` (RCP-13)")
    elif level != "renders" and not (recipe / "tests/smoke").is_file():
        errors.append(f"tests/smoke is missing for level {level} (RCP-1)")

    errors += _requires_errors(recipe) + _include_errors(recipe)
    for path in sorted(recipe.rglob("*.py")):
        errors.append(f"{path.relative_to(recipe)}: a recipe contains no Python (RCP-33)")
    pinned, compiles = set(), []
    linted = class_files(recipe)
    for path in linted:
        f = path.relative_to(recipe).as_posix()
        text = path.read_text()
        if "?{" in text:
            errors.append(f"{f}: names a ref backend with ?{{ (RCP-19)")
        for m in FORBIDDEN_RESOLVER.finditer(text):
            errors.append(f"{f}: uses the resolver {m.group(1)} (RCP-17)")
        try:
            errors += _flow_errors(f, text)
            doc = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            errors.append(f"{f}: {e}")
            continue
        for key in doc:
            if key not in ("classes", "parameters"):
                errors.append(f"{f}: top-level key {key} (RCP-17)")
        for cls in doc.get("classes") or []:
            if not (str(cls).startswith(".") or str(cls).startswith("recipes.")):
                errors.append(f"{f}: includes class {cls} from outside recipes (RCP-18)")
                continue
            target = resolve_class(recipe, f, str(cls))
            if target is None:
                errors.append(f"{f}: class {cls} does not resolve to a file of this repository (RCP-36)")
                continue
            owner = recipe.parent / target.relative_to(recipe.parent).parts[0]
            if not (owner / "init.yml").is_file() or target not in (linted if owner == recipe else class_files(owner)):
                errors.append(f"{f}: class {cls} resolves to {target.relative_to(recipe.parent)}, which is not linted (RCP-36)")
        params = doc.get("parameters") or {}
        if f == "init.yml" and params.get("components"):
            errors.append("init.yml: components belong in their own files (RCP-1)")
        errors += _parameter_errors(name, f, params)
        errors += _dependency_errors(f, params.get("kapitan") or {}, pinned)
        compiles.append((f, text, params.get("kapitan") or {}))
    for f, text, kapitan in compiles:
        errors += _compile_errors(name, recipe, f, text, kapitan, pinned)
    return errors


def lint_warnings(recipe):
    """RCP-43: on the kubernetes generator 1.7.0 or later, every args list of a component."""
    docs = [(p.relative_to(recipe).as_posix(), yaml.safe_load(p.read_text()) or {}) for p in class_files(recipe)]
    versions = [
        tuple(map(int, m.groups()))
        for _, doc in docs
        for dep in ((doc.get("parameters") or {}).get("kapitan") or {}).get("dependencies") or []
        if (m := KUBERNETES.match(str(dep.get("source", ""))))
    ]
    if not versions or max(versions) < (1, 7, 0):
        return []
    warnings = []
    for f, doc in docs:
        for comp, body in ((doc.get("parameters") or {}).get("components") or {}).items():
            containers = [(f"components.{comp}", body or {})]
            for key in ("additional_containers", "init_containers"):
                containers += [(f"components.{comp}.{key}.{n}", c or {}) for n, c in ((body or {}).get(key) or {}).items()]
            warnings += [f"{f}: {where}.args is a list, write it as a mapping (RCP-43)"
                         for where, c in containers if isinstance(c.get("args"), list)]
    return warnings

def lint_output(name, objects, chart_names):
    """The rules on the compiled output: RCP-3 names and RCP-6 images."""
    errors = []
    for o in objects:
        meta = o.get("metadata") or {}
        obj_name = meta.get("name", "")
        if not obj_name.startswith(name) and obj_name not in chart_names:
            errors.append(f"{o.get('kind')}/{obj_name}: name neither starts with {name} nor is one the chart uses (RCP-3)")
        spec = o.get("spec") or {}
        templates = [spec.get("template"), ((spec.get("jobTemplate") or {}).get("spec") or {}).get("template")]
        for template in filter(None, templates):
            pod = template.get("spec") or {}
            for c in (pod.get("initContainers") or []) + (pod.get("containers") or []):
                images = [c.get("image", "")]
                images += [m.group(1) for a in c.get("args") or [] if (m := IMAGE_ARG.match(str(a)))]
                for image in images:
                    if not PINNED.search(image):
                        errors.append(f"{o.get('kind')}/{obj_name}: image {image} is not pinned by digest (RCP-6)")
    return errors


def lint_compose_output(objects):
    """RCP-38: what a compose recipe proves without a reference to compare with."""
    errors = [
        f"{compare.ident(o)}: RBAC object, the source grants no API access (RCP-38)"
        for o in objects if o.get("kind") in compare.RBAC_KINDS
    ]
    selected, own = compare.selections(objects)
    errors += [f"{e} (RCP-38)" for e in own]
    errors += [f"{i}: selector selects no pods (RCP-38)" for i, s in sorted(selected.items()) if not s]
    return errors


def lint_design_output(objects, source):
    """RCP-44: a designed recipe is linted as a compose one (RCP-38); RCP-23: it runs its Source image,
    in a container or, through an operator, as spec.image of a custom resource (RCP-58)."""
    image = "{}:{}@{}".format(*source)
    errors = lint_compose_output(objects)
    images = {c.get("image") for o in objects for _, t in compare.pod_templates(o) for c in (t.get("spec") or {}).get("containers") or []}
    images |= {(o.get("spec") or {}).get("image") for o in objects}
    if image not in images:
        errors.append(f"no container runs the Source image {image} (RCP-23)")
    return errors
