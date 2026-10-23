"""check lint: the rules a recipe's files and its compiled output must follow."""

import hashlib
import re
from pathlib import Path

import yaml

LEVELS = ("renders", "deploys", "migrates")
SOURCE_LINE = re.compile(r"^Source: `oci://(\S+?):(\S+?)@(sha256:[0-9a-f]{64})`$", re.M)
LEVEL_LINE = re.compile(r"^Level: `(\w+)`$", re.M)
DEPENDENCY = re.compile(r"^ghcr\.io/kadet-hub/([a-z0-9][a-z0-9._-]*)(:[\w.-]+)?@sha256:[0-9a-f]{64}$")
PINNED = re.compile(r"@sha256:[0-9a-f]{64}$")
IMAGE_ARG = re.compile(r"^--?[\w-]*image[\w-]*=(.+)$")
FORBIDDEN_RESOLVER = re.compile(r"\$\{\s*(from_file|write|oc\.env|filename|parent_filename|path|parent_path)\s*:")
SHA_COMMENT = re.compile(r"#.*SHA-256 ([0-9a-f]{64})")


def class_files(recipe):
    return sorted(Path(recipe).glob("*.yml"))


def readme_fields(recipe):
    """Source and Level lines of the README (RCP-23)."""
    text = (Path(recipe) / "README.md").read_text()
    source, level = SOURCE_LINE.search(text), LEVEL_LINE.search(text)
    return (
        source.groups() if source else None,
        level.group(1) if level else None,
    )


def _flow_errors(path, text):
    """RCP-4: flow style only for a node on one line of at most 80 characters."""
    lines = text.splitlines()
    errors = []

    def walk(node):
        if isinstance(node, (yaml.MappingNode, yaml.SequenceNode)) and node.flow_style:
            start, end = node.start_mark.line, node.end_mark.line
            if start != end or len(lines[start]) > 80:
                errors.append(f"{path.name}:{start + 1}: flow style on a line longer than 80 characters (RCP-4)")
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
        else:
            errors.append(f"{f}: compile entry of input_type {kind} (RCP-17)")
    return errors


def lint_files(recipe):
    """The rules that need only the recipe's files. Returns a list of errors."""
    recipe = Path(recipe)
    name = recipe.name
    errors = []
    for required in ("init.yml", "README.md", "tests/values.yaml", "tests/target.yml"):
        if not (recipe / required).is_file():
            errors.append(f"{required} is missing (RCP-1)")
    if errors:
        return errors
    source, level = readme_fields(recipe)
    if not source:
        errors.append("README.md has no line Source: `oci://<chart>:<version>@sha256:<digest>` (RCP-23)")
    if level not in LEVELS:
        errors.append(f"README.md has no line Level: `<{'|'.join(LEVELS)}>` (RCP-13)")
    elif level != "renders" and not (recipe / "tests/smoke").is_file():
        errors.append(f"tests/smoke is missing for level {level} (RCP-1)")

    pinned, compiles = set(), []
    for path in class_files(recipe):
        f = path.name
        text = path.read_text()
        if "?{" in text:
            errors.append(f"{f}: names a ref backend with ?{{ (RCP-19)")
        for m in FORBIDDEN_RESOLVER.finditer(text):
            errors.append(f"{f}: uses the resolver {m.group(1)} (RCP-17)")
        try:
            errors += _flow_errors(path, text)
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
        params = doc.get("parameters") or {}
        if f == "init.yml" and params.get("components"):
            errors.append("init.yml: components belong in their own files (RCP-1)")
        errors += _parameter_errors(name, f, params)
        errors += _dependency_errors(f, params.get("kapitan") or {}, pinned)
        compiles.append((f, text, params.get("kapitan") or {}))
    for f, text, kapitan in compiles:
        errors += _compile_errors(name, recipe, f, text, kapitan, pinned)
    return errors


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
