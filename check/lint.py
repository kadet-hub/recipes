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
HTTP_LINE = re.compile(r"^Source: `(https://\S+)/([\w.-]+):(\S+?)@(sha256:[0-9a-f]{64})`$", re.M)
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
DESCRIPTION_LIMIT = 300
DESCRIPTION_CHAR = re.compile(r"[\x00-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")
# RCP-260: the file that declares the required parameters and the inventory backends.
META = "recipe.yaml"
BACKENDS = ("omegaconf", "reclass", "reclass-rs")
PARAMETER_PATH = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*$")
SECTION_PATH = re.compile(r"`((?:applications|components|generators)(?:\.[A-Za-z0-9_-]+)+)`")
NO_PARAMETER = "No parameter has to be set."
# RCP-308: the verbs a designed recipe's roles may grant.
READ_VERBS = {"get", "list", "watch"}


def class_files(recipe):
    """Every file of the recipe that can act as a class: its YAML files but tests/ and copy inputs below the root (RCP-36)."""
    recipe = Path(recipe)
    prefix = f"inventory/classes/recipes/{recipe.name}/"
    files = sorted(
        p for p in recipe.rglob("*")
        if p.suffix in (".yml", ".yaml") and p.is_file() and p.relative_to(recipe).parts[0] not in ("tests", META)
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
    ("http", (repository, chart, version, digest)), ("design", (image, tag, digest)) or None."""
    text = (Path(recipe) / "README.md").read_text()
    chart, compose, image = SOURCE_LINE.search(text), COMPOSE_LINE.search(text), IMAGE_LINE.search(text)
    manifest, http = MANIFEST_LINE.search(text), HTTP_LINE.search(text)
    level = LEVEL_LINE.search(text)
    return (
        ("chart", chart.groups()) if chart else ("compose", compose.groups()) if compose
        else ("manifest", manifest.groups()) if manifest else ("http", http.groups()) if http
        else ("design", image.groups()) if image else None,
        level.group(1) if level else None,
    )


def section(recipe, heading):
    """The body of the README section `## <heading>`, "" without one."""
    for part in re.split(r"^## ", (Path(recipe) / "README.md").read_text(), flags=re.M)[1:]:
        title, _, body = part.partition("\n")
        if title.strip() == heading:
            return body
    return ""


def include_snippet(recipe):
    """The target of the README's Include section, its first yaml code block (RCP-261), or None."""
    m = re.search(r"^```yaml\n(.*?)^```", section(recipe, "Include"), re.M | re.S)
    try:
        doc = yaml.safe_load(m.group(1)) if m else None
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) and isinstance(doc.get("parameters"), dict) else None


def lookup(params, path):
    """(value, True) at the dotted path of params, (None, False) when it is not set."""
    for key in path.split("."):
        if not isinstance(params, dict) or key not in params:
            return None, False
        params = params[key]
    return params, True


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


def _meta_errors(recipe):
    """RCP-260: recipe.yaml's keys; RCP-261: its match with the README's Required parameters and Include snippet."""
    path = recipe / META
    if not path.is_file():
        return [f"{META} is missing (RCP-260)"]
    text = path.read_text()
    try:
        errors = _anchor_errors(META, text) + _flow_errors(META, text)
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [f"{META}: {e}"]
    if not isinstance(doc, dict) or set(doc) != {"backends", "required"}:
        return errors + [f"{META} has the keys backends and required and no other (RCP-260)"]
    backends, required = doc["backends"], doc["required"]
    names = [str(b) for b in backends] if isinstance(backends, list) else []
    if "omegaconf" not in names or len(set(names)) != len(names) or not set(names) <= set(BACKENDS):
        errors.append(f"{META}: backends lists omegaconf and may list reclass and reclass-rs, each once (RCP-260)")
    if not isinstance(required, list):
        return errors + [f"{META}: required is a list (RCP-260)"]
    entries = []
    for n, e in enumerate(required):
        where = f"{META}: required[{n}]"
        if not isinstance(e, dict) or not {"path", "description", "secret"} <= set(e) <= {"path", "description", "secret", "option"}:
            errors.append(f"{where} has path, description, secret and, for an option, option (RCP-260)")
            continue
        if not isinstance(e["path"], str) or not PARAMETER_PATH.match(e["path"]):
            errors.append(f"{where}: path {e['path']} is no dotted parameter path (RCP-260)")
            continue
        d = e["description"]
        if not isinstance(d, str) or not d.strip() or len(d) > DESCRIPTION_LIMIT or DESCRIPTION_CHAR.search(d):
            errors.append(f"{where}: description is one line of at most {DESCRIPTION_LIMIT} characters (RCP-260)")
        if not isinstance(e["secret"], bool):
            errors.append(f"{where}: secret is true or false (RCP-260)")
        if "option" in e and not isinstance(e["option"], str):
            errors.append(f"{where}: option is the name of an option (RCP-260)")
        if e["path"] in [x["path"] for x in entries]:
            errors.append(f"{where}: path {e['path']} is listed twice (RCP-260)")
        entries.append(e)

    paths = {e["path"] for e in entries}
    body = section(recipe, "Required parameters")
    named = set(SECTION_PATH.findall(body))
    errors += [f"README.md: Required parameters does not name {p} in backticks (RCP-261)" for p in sorted(paths - named)]
    errors += [f"README.md: Required parameters names {p}, which {META} does not list (RCP-261)" for p in sorted(named - paths)]
    if (NO_PARAMETER in body) == bool(required):
        errors.append(f'README.md: Required parameters says "{NO_PARAMETER}" exactly when {META} lists no parameter (RCP-261)')
    snippet = include_snippet(recipe)
    if snippet is None:
        return errors + ["README.md: the Include section has no yaml block with a target (RCP-261)"]
    classes = [str(c) for c in snippet.get("classes") or []]
    for e in entries:
        value, found = lookup(snippet["parameters"], e["path"])
        if not found:
            errors.append(f"README.md: the Include snippet does not set {e['path']} (RCP-261)")
        elif (value == "<ref>") != (e["secret"] is True):
            errors.append(f"README.md: the Include snippet sets {e['path']} to {value}, and {META} has secret: {e['secret']} (RCP-261)")
        if "option" in e and f"recipes.{recipe.name}.{e['option']}" not in classes:
            errors.append(f"README.md: the Include snippet does not include recipes.{recipe.name}.{e['option']} (RCP-261)")
    return errors


def _include_errors(recipe):
    """RCP-47: an included recipe includes no recipe; RCP-48: the recipe, its included recipes and the
    recipes next to it pin the generators of the first two at the same source."""
    errors, pins = [], {}
    group = [recipe, *(recipe.parent / o for o in included(recipe))]
    others = [d for d in sorted(recipe.parent.iterdir()) if (d / "init.yml").is_file() and d not in group]
    for r in group + others:
        if r in group[1:] and included(r):
            errors.append(f"includes {r.name}, which includes {', '.join(included(r))} itself (RCP-47)")
        for path in class_files(r):
            try:
                kapitan = ((yaml.safe_load(path.read_text()) or {}).get("parameters") or {}).get("kapitan") or {}
            except (yaml.YAMLError, AttributeError):
                continue
            for dep in kapitan.get("dependencies") or []:
                output_path = str(dep.get("output_path", "")).rstrip("/")
                if r in group or output_path in pins:
                    pins.setdefault(output_path, {}).setdefault(str(dep.get("source")), set()).add(r.name)
    for output_path, sources in sorted(pins.items()):
        if len(sources) > 1:
            listed = ", ".join(f"{s} ({', '.join(sorted(names))})" for s, names in sorted(sources.items()))
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


def _anchor_errors(f, text):
    """RCP-4a: no anchors, aliases or merge keys."""
    errors = []
    for ev in yaml.parse(text):
        line = ev.start_mark.line + 1
        if isinstance(ev, yaml.AliasEvent):
            errors.append(f"{f}:{line}: YAML alias *{ev.anchor} (RCP-4a)")
        elif getattr(ev, "anchor", None):
            errors.append(f"{f}:{line}: YAML anchor &{ev.anchor} (RCP-4a)")
        elif isinstance(ev, yaml.ScalarEvent) and ev.value == "<<" and ev.implicit[0]:
            errors.append(f"{f}:{line}: YAML merge key << (RCP-4a)")
    return errors


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


def _description_errors(text):
    """RCP-32: the first non-empty block of lines after the first line starting with #, whitespace collapsed."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("#")), len(lines))
    block = []
    for line in lines[start + 1 :]:
        if line.strip(" \t"):
            block.append(line)
        elif block:
            break
    if not block:
        return ["README.md has no paragraph after the heading (RCP-32)"]
    description = re.sub(r"[ \t\n]+", " ", "\n".join(block)).strip(" ")
    errors = []
    if len(description) > DESCRIPTION_LIMIT:
        errors.append(f"README.md: the first paragraph is {len(description)} characters, at most {DESCRIPTION_LIMIT} (RCP-32)")
    if m := DESCRIPTION_CHAR.search(description):
        errors.append(f"README.md: the first paragraph contains U+{ord(m.group()):04X}, a control or bidirectional formatting character (RCP-32)")
    if description.endswith(":"):
        errors.append("README.md: the first paragraph ends with a colon (RCP-32)")
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
            " `https://github.com/<owner>/<repo>/releases/download/<tag>/<file>@sha256:<digest>`,"
            " `https://<repository>/<chart>:<version>@sha256:<digest>`"
            " or `<registry>/<repository>:<tag>@sha256:<digest>` (RCP-23)"
        )
    elif source[0] in ("chart", "http") and not (recipe / "tests/values.yaml").is_file():
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
    errors += _description_errors((recipe / "README.md").read_text())
    errors += _meta_errors(recipe)
    if level not in LEVELS:
        errors.append(f"README.md has no line Level: `<{'|'.join(LEVELS)}>` (RCP-13)")
    elif level != "renders" and not (recipe / "tests/smoke").is_file():
        errors.append(f"tests/smoke is missing for level {level} (RCP-1)")

    errors += _requires_errors(recipe) + _include_errors(recipe)
    for path in sorted(recipe.rglob("*.py")):
        errors.append(f"{path.relative_to(recipe)}: a recipe contains no Python (RCP-33)")
    pinned, compiles = set(), []
    linted = class_files(recipe)
    tests = sorted(p for p in (recipe / "tests").rglob("*") if p.suffix in (".yml", ".yaml") and p.is_file())
    for path in [*linted, *tests]:
        try:
            errors += _anchor_errors(path.relative_to(recipe).as_posix(), path.read_text())
        except yaml.YAMLError:
            pass  # reported for class files below; chart values are not parsed here
    for path in linted:
        f = path.relative_to(recipe).as_posix()
        text = path.read_text()
        if "?{" in text:
            errors.append(f"{f}: names a ref backend with ?{{ (RCP-19)")
        for m in FORBIDDEN_RESOLVER.finditer(text):
            errors.append(f"{f}: uses the resolver {m.group(1)} (RCP-17)")
        for n, line in enumerate(text.splitlines(), 1):
            if "@sha256:" in line and "${" in line:
                errors.append(f"{f}:{n}: image reference takes its tag from an interpolation (RCP-66)")
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


def read_only_rbac_errors(objects):
    """RCP-308: the RBAC of a designed recipe only reads, and binds only roles the recipe renders."""
    rbac = [o for o in objects if o.get("kind") in compare.RBAC_KINDS]
    # A ClusterRole is cluster-scoped, so a namespace in its metadata does not count.
    roles = {(o["kind"], (o.get("metadata") or {}).get("namespace") if o["kind"] == "Role" else None,
              (o.get("metadata") or {}).get("name"))
             for o in rbac if o["kind"] in ("Role", "ClusterRole")}
    errors = []
    for o in rbac:
        meta = o.get("metadata") or {}
        if o["kind"] in ("Role", "ClusterRole"):
            if "aggregationRule" in o:
                errors.append(f"{compare.ident(o)}: aggregationRule, a designed recipe grants only the rules it lists (RCP-308)")
            for rule in o.get("rules") or []:
                if extra := sorted(set(rule.get("verbs") or []) - READ_VERBS):
                    errors.append(f"{compare.ident(o)}: verbs {', '.join(extra)}, a designed recipe only reads (RCP-308)")
                named = [*(rule.get("apiGroups") or []), *(rule.get("resources") or [])]
                if bad := sorted({n for n in named if n == "*" or n.split("/")[0] == "secrets"}):
                    errors.append(f"{compare.ident(o)}: {', '.join(bad)}, a designed recipe reads no Secret (RCP-308)")
                if rule.get("nonResourceURLs"):
                    errors.append(f"{compare.ident(o)}: nonResourceURLs, a designed recipe reads only resources (RCP-308)")
        else:
            ref = o.get("roleRef") or {}
            namespace = meta.get("namespace") if ref.get("kind") == "Role" else None
            if (ref.get("kind"), namespace, ref.get("name")) not in roles:
                errors.append(f"{compare.ident(o)}: binds {ref.get('kind')}/{ref.get('name')}, which the recipe does not render (RCP-308)")
    return errors


def lint_compose_output(objects, read_only_rbac=False):
    """RCP-38: what a compose recipe proves without a reference to compare with. A designed recipe
    may read the API (RCP-308)."""
    errors = read_only_rbac_errors(objects) if read_only_rbac else [
        f"{compare.ident(o)}: RBAC object, the source grants no API access (RCP-38)"
        for o in objects if o.get("kind") in compare.RBAC_KINDS
    ]
    selected, own = compare.selections(objects)
    errors += [f"{e} (RCP-38)" for e in own]
    errors += [f"{i}: selector selects no pods (RCP-38)" for i, s in sorted(selected.items()) if not s]
    return errors


def lint_design_output(objects, source):
    """RCP-44: a designed recipe is linted as a compose one (RCP-38), with read-only RBAC (RCP-308); RCP-23: it runs its Source image,
    in a container or, through an operator, as spec.image or spec.<part>.image of a custom resource (RCP-58)."""
    image = "{}:{}@{}".format(*source)
    errors = lint_compose_output(objects, read_only_rbac=True)
    images = {c.get("image") for o in objects for _, t in compare.pod_templates(o) for c in (t.get("spec") or {}).get("containers") or []}
    specs = [o.get("spec") or {} for o in objects]
    images |= {s.get("image") for s in specs} | {p.get("image") for s in specs for p in s.values() if isinstance(p, dict)}
    if image not in images:
        errors.append(f"no container runs the Source image {image} (RCP-23)")
    return errors
