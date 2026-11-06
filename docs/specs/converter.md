# Converter

```text
Status: Draft. check 0.16.0 implements CNV-1 to CNV-19.
Code: check/convert.py, check/tests/test_convert.py,
      check/tests/fixtures/convert/, check/pyproject.toml, check/uv.lock,
      .github/workflows/ci.yml (job convert), docs/convert.md, README.md
Verified against: main @ a723bd2
```

Related: [recipes.md](recipes.md) RCP-9 to RCP-12 (comparison), RCP-22
(release tags), RCP-25 (hooks), RCP-27 (generator verification).

## Problem

A Helm user who looks at Kapitan first wants to know whether the kadet-hub
generators can render what their own chart renders, with their own
values. Kapitan's `helm` input renders a chart unchanged, which answers a
different question: the objects stay chart-shaped and Helm runs at every
compile. The recipes in this repository answer it for 34 curated charts,
not for a private one. The `to-recipe` agent skill migrates any chart, but
each run is an agent session whose result varies and which text in the
chart can steer.

`kadet-convert` is one deterministic command: chart and values in, a
Kapitan project for the `kubernetes` generator out, proven against
`helm template` with the comparison of `check`, plus a list of what it
could not map. A spike on podinfo 6.17.0, oauth2-proxy 10.7.1 with the
redis-ha subchart, and cert-manager v1.21.2 found every mapped object equal
except one StatefulSet whose `serviceName` the generator cannot set. It
also measured that chart values turn into inventory parameters for only
21 % to 32 % of the probed values, which shaped DEC-181.

## Decisions

- DEC-180: The converter maps the objects `helm template` renders, not the
  chart's templates.

  Rendered objects are a closed set of kinds with an API schema, and
  `check` compares exactly these. Template logic (`tpl`, `include`,
  `lookup`, string building) has no counterpart in inventory and nothing
  could prove a translation of it.

- DEC-181: Values are frozen. The inventory holds the rendered values as
  literals, and the value map (CNV-12) says for each chart value where it
  landed. The converter writes no parameters.

  In the spike, a parameter was proven for 28 of podinfo's 132 probed
  values, 97 of 358 for oauth2-proxy with redis-ha and 59 of 186 for
  cert-manager. Switches such as `ingress.enabled` add or remove objects
  and cannot be an interpolation, and values below a switch that is off
  show no effect at all. Changing such a value means converting again.

- DEC-182: The proof is `check`'s, imported, not copied: `compare.py` for
  normalisation, pairing, selectors and the classes of RCP-12, and
  `check.prove_side` for the server-side dry run on fresh kind clusters and
  `kubectl auth can-i`.

  A converted chart gets the verdict a recipe gets, and a new accepted
  class reaches both at once.

- DEC-183: The converter is `check/convert.py` in the `check` project. It
  shares `check/pyproject.toml` and `check/uv.lock`, is released with the
  `check-vX.Y.Z` tags of RCP-22, and runs as `kadet-convert` with `uvx`
  from such a tag.

  `uvx` builds the project from its `pyproject.toml` and resolves its exact
  pins, not the lock, and it does not apply `[tool.uv]` overrides, so it
  installs Kapitan's capped `cryptography` (RCP-67). Only Kapitan's ref
  functions import it, and a conversion writes no refs. The locked
  environment is `uv run --locked --project check check/convert.py`.

- DEC-184: A conversion is a one-off migration. The output is a project the
  user takes over and edits; a later conversion writes a new one and does
  not merge with their edits.

- DEC-185: The output stays faithful to the chart. Services,
  ServiceAccounts, ConfigMaps, Secrets and RBAC roles are standalone
  entries with the chart's names and labels; only workloads are
  components.

  Folding them into components would give a recipe's shape but more
  accepted differences, and fails where a Service's port names differ from
  the container ports'. A faithful cert-manager conversion is about twice
  the lines of the hand-written recipe.

- DEC-186: The proof needs Docker and kind, as `check` does.

- DEC-187: Hooks are left out and listed in the report, as RCP-25 does for
  recipes.

- DEC-188: A field the `kubernetes` generator cannot set is reported as not
  mappable. Such gaps become generator features in kadet-hub/generators,
  and the converter maps them once a release has them.

## Rendering

The chart is pulled once and rendered from the archive. A chart reference
is anything `helm pull` takes: `oci://<repo>:<version>`,
`oci://<repo>@sha256:<digest>`, or a chart name with `--repo` and
`--version`. A local chart directory or archive is rendered as it is.

- CNV-1: The converter MUST render the chart with
  `helm template <release> <chart> -n <namespace> --include-crds` and the
  values files given, and the report MUST name the chart's name and
  version and the SHA-256 of the archive it rendered.

  - Test: CI `convert` job, report section `Source`
  - Since: #100

- CNV-2: The converter MUST NOT run, fetch or open anything that a chart or
  its values name, except `helm pull` of the chart given and
  `helm template` on it.

  Chart text and values are written by the chart's author. Subcharts come
  from the chart's `charts/` directory; the converter runs no
  `helm dependency build`.

  - Test: manual: review of the subprocess calls in `check/convert.py`
  - Since: #100

- CNV-3: The converter MUST render twice and report every field outside
  hooks that differs between the two renders.

  Passwords from `randAlphaNum` or certificates from `genCA` change on each
  render. The conversion freezes the first render's value, so the user
  learns which values to replace.

  - Test: `check/tests/test_convert.py` (`Render.test_generated_fields`)
  - Since: #100

- CNV-20: The converter MUST NOT read the output directory as the chart. It
  MUST reject an `--out` that resolves to the same path as the chart
  argument, before it creates the directory or runs a command.

  check 0.16.0 created `--out` before it pulled the chart. With
  `oauth2-proxy --repo <url> --out oauth2-proxy`, it found the new empty
  directory, took it for a local chart and stopped with
  `Chart.yaml file is missing`. Pulling the chart before creating `--out`
  would still read an existing empty directory of that name as the chart.

  - Test: `check/tests/test_convert.py` (`Cli.test_out_named_like_the_chart`)
  - Since: #112

## Mapping

| Kind | Section |
|---|---|
| Deployment, StatefulSet, DaemonSet | `components.<name>`, pod template and containers included |
| Service | `generators.kubernetes.services.<name>` with the chart's selector |
| ConfigMap | `generators.kubernetes.configs.<name>` |
| Secret | `generators.kubernetes.secrets.<name>`, data from the secrets class (CNV-10) |
| ServiceAccount | `generators.kubernetes.service_accounts.<name>` |
| Role, ClusterRole, RoleBinding, ClusterRoleBinding | `generators.kubernetes.rbac.<role>`, one entry per role with the bindings that bind it |
| Ingress | `ingresses.<name>` |
| PersistentVolumeClaim | `generators.kubernetes.persistent_volume_claims.<name>` |
| MutatingWebhookConfiguration, ValidatingWebhookConfiguration | `webhooks` or `validating_webhooks` of the component whose pods the webhook's Service selects |
| CustomResourceDefinition | a `copy` compile entry of a vendored file |

- CNV-4: Every rendered object outside hooks MUST be mapped by the table
  above or reported as not mapped with its kind. The converter MUST NOT use
  the `manifests` section or another pass-through.

  An object copied through whole proves nothing about the generator
  (RCP-7). The generator renders more kinds than the table, such as
  NetworkPolicy, PodDisruptionBudget and APIService; the converter reports
  them as not mapped until it maps them.

  - Test: `check/tests/test_convert.py` (`Mapping.test_unmapped_kind`)
  - Since: #100

- CNV-5: The report MUST list every field of an object that the converter
  cannot map, with its path, as not mappable.

  With the `kubernetes` generator 1.14.0 these are, among others, a
  StatefulSet's `serviceName` other than its own name,
  `podManagementPolicy`, a container's `workingDir`, the pod's
  `shareProcessNamespace`, a Service's `ipFamilyPolicy`, a port without a
  name, an env `valueFrom` other than `fieldRef`, `secretKeyRef` and
  `configMapKeyRef`, and `revisionHistoryLimit`, `minReadySeconds` or
  `progressDeadlineSeconds` of 0, which the generator writes only when
  truthy (DEC-188).

  - Test: `check/tests/test_convert.py` (`Mapping.test_not_mappable_fields`)
  - Since: #100

- CNV-6: Where the generator writes a default that differs from the API
  default, the converter MUST write the chart's value, or the API default
  where the chart leaves the field unset.

  These are a probe's `timeoutSeconds` (generator 5, API 1),
  `automountServiceAccountToken` on pods and ServiceAccounts (generator
  `false`, API unset), `imagePullPolicy` (generator `IfNotPresent`, API
  `Always` for an untagged or `:latest` image), a Service port's
  `appProtocol`, which the generator derives from the port names `http`,
  `https`, `h2c`, `ws` and `wss`, and a webhook's `namespaceSelector`,
  which the generator sets to exclude its own namespace.

  - Test: `check/tests/test_convert.py` (`Mapping.test_api_defaults`)
  - Since: #100

- CNV-7: A string from the chart that contains `${` MUST compile to itself.

  Shell scripts in ConfigMaps are full of `${VAR}`, which OmegaConf would
  interpolate. Kapitan's omegaconf backend resolves an escaped `\${...}`
  again in its second pass by design, and its `escape` resolver emits
  `${...}` literally. The converter writes each `${...}` as
  `${escape:'...'}`, with quotes and the backslashes before them escaped in
  the quoted argument, and doubles the backslashes in front of the `${`.

  Related: Kapitan's [omegaconf.md](https://github.com/kapicorp/kapitan/blob/master/docs/pages/inventory/omegaconf.md),
  section "Literal `${...}` Output with `${escape:...}`".

  The resolver cannot emit a nested `${A${B}}` or an unclosed `${`, such as
  redis-ha's `\${SENTINEL_ID_${INDEX}}`. Such a string is escaped with
  backslashes instead, once per time Kapitan 0.36.3 resolves a value:
  three times, in two `OmegaConf.resolve` passes and
  `OmegaConf.to_container(resolve=True)`.

  - Test: `check/tests/test_convert.py` (`Escape.test_resolver_or_backslashes`,
    `Escape.test_kapitan_reads_text_back`, with the Kapitan of the lock)
  - Since: #100

- CNV-8: The converter MUST write one `rbac` entry per Role or ClusterRole
  with the bindings that bind it, an entry of its own for a binding whose
  subjects differ or whose role the chart does not render, and MUST
  replace `:` in RBAC names with `-`, listing each rename.

  The generator rejects `:` in names. RBAC is proven by what each subject
  may do, so names take no part in the proof (RCP-11). cert-manager v1.21.2
  needs 15 renames.

  - Test: `check/tests/test_convert.py` (`Mapping.test_rbac`)
  - Since: #100

- CNV-9: The converter MUST write each CRD as rendered into a file of its
  own below `vendor/` of the converted class and compile it with a `copy`
  entry.

  No generator renders a chart's CRDs. The proof compares the copied CRDs
  with the chart's.

  - Test: `check/tests/test_convert.py` (`Output.test_crds`)
  - Since: #100

## Secrets

A Secret's data is the chart's, often a credential from the user's values,
such as oauth2-proxy's client secret. Written into the converted class, it
would be committed with it.

- CNV-10: The converter MUST NOT write Secret data into the converted
  class. It MUST write each value into the secrets class
  `inventory/classes/converted/<release>/secrets.yml` under
  `applications.<release>.secrets`, interpolate it from there, list that
  file in the output's `.gitignore`, and tell the user in the report to
  keep it out of git and replace the values with refs.

  The values stay base64 with `b64_encode: false`, so a ref that replaces
  one holds the base64 value, as the generator's README asks.

  - Test: `check/tests/test_convert.py` (`Output.test_secret_data`)
  - Since: #100

## Values

The effective values are the chart's `values.yaml`, each subchart's
`values.yaml` under its name or alias, and the user's files on top. For
the value map, the converter renders the chart once per scalar value with
that value changed, maps both renders, and diffs the two inventories. A
string gets a suffix, a number 7919 added, a boolean its opposite.

A value reaches an inventory field when the field holds the new value, the
old string with the value replaced, or its base64. A value that adds or
removes fields or objects is a switch. A value that changes nothing is
listed as below a switch that is off when an `enabled`, `create` or
`enable` above it is `false`.

- CNV-11: Without changes by the user, the converted project MUST render
  the same objects as `helm template` with the values given, judged by
  CNV-14.

  - Test: CI `convert` job
  - Since: #100

- CNV-12: The converter MUST write `value-map.json` with every scalar value
  of the effective values and its class: reached, with the inventory
  fields; switch; no effect, below a switch that is off; no effect; derived,
  with the fields it changes; or render error. The report MUST list the
  values that reached inventory fields, with those fields.

  The value map is the table of chart values and inventory paths that a
  recipe README writes by hand, such as `replicaCount` to
  `components.podinfo.replicas`.

  - Test: `check/tests/test_convert.py` (`ValueMap.test_classes`); CI
    `convert` job, report section `Values`
  - Since: #100

## Proof and report

- CNV-13: The converter MUST leave out every object with the annotation
  `helm.sh/hook` and list each as `<Kind>/<name>` (DEC-187).

  - Test: CI `convert` job, report section `Left out`
  - Since: #100

- CNV-14: The converter MUST prove the output as DEC-182 says, on two
  fresh kind clusters `<prefix>-<release>-chart` and
  `<prefix>-<release>-recipe`, and MUST delete them afterwards. With
  `--no-proof` it MUST say in the report that the proof did not run and
  MUST NOT call any object equal.

  The prefix defaults to `convert`. Compared offline, API defaults such as
  `sessionAffinity: None` show up as differences: in the spike 7 of
  cert-manager's 11 objects, all equal after the dry run.

  - Test: CI `convert` job
  - Since: #100

- CNV-15: The report MUST put each object into exactly one class: exact;
  equal up to accepted classes, naming them; mapped with differences,
  listing them; not mapped, with the reason; hook left out; CRD copied. It
  MUST state for each RBAC subject whether its permissions are equal.

  - Test: CI `convert` job, report sections `Objects` and `Permissions`
  - Since: #100

- CNV-16: The converter MUST exit 0 when every object is mapped and the
  proof found every object and permission equal or accepted, 1 when an
  object is not mapped or a difference or permission difference remains,
  and 2 when a command it runs fails.

  The same statuses as `check`. A not mappable field (CNV-5) counts through
  the proof: it fails only where the field differs from what the API
  stores without it, such as `podManagementPolicy: Parallel`, not
  `OrderedReady`. With `--no-proof` only unmapped objects give 1.

  - Test: CI `convert` job
  - Since: #100

- CNV-17: Where a workload's selector differs from the chart's, the report
  MUST say that `kubectl apply` over a running Helm release fails on it.

  The generator selects on its `name` label, so this holds for every
  converted Deployment and StatefulSet: the selector is immutable, and a
  running release is replaced by deleting its workloads with
  `--cascade=orphan` first, as the recipe READMEs describe.

  - Test: CI `convert` job, report section `Objects`
  - Since: #100

## Output

- CNV-18: The output MUST be a Kapitan project that `kapitan compile`
  compiles without `--fetch`: `.kapitan` with the omegaconf backend, the
  converted class `inventory/classes/converted/<release>/init.yml`, the
  secrets class, vendored CRDs, the target
  `inventory/targets/<release>.yml`, and the `kubernetes` generator in
  `lib/kubernetes`, pinned by version and digest and pulled after the
  verification of RCP-27.

  - Test: CI `convert` job
  - Since: #100

## Distribution and CI

- CNV-19: CI MUST convert podinfo 6.17.0, pinned by digest, with
  `check/tests/fixtures/convert/podinfo-values.yaml`, and prove it on
  kind, in every run that checks every recipe (RCP-13).

  podinfo renders a Deployment, a Service, a ServiceAccount, an Ingress and
  three test pods, so the job also covers hooks. Its unit tests run in the
  `test` job with the others.

  - Test: CI `convert` job
  - Since: #100

## Alternatives

| Alternative | Why not chosen |
|---|---|
| Kapitan's `helm` input | Reproduces the chart; it remains the answer for users who keep following upstream releases, not for those who move to the generator |
| Translating templates | No inventory counterpart for template logic, and no proof (DEC-180) |
| Parameters from probed values | A quarter of the values at most, never the switches (DEC-181) |
| A separate project with its own lock | A second lock to keep in step with `check`'s, and a second release line |
| A `kapitan` subcommand | Couples Kapitan to one generator's input; deferred (OQ-17) |
| A web page | Would receive private charts and values with secrets, and the proof needs an API server |
| A proof without a cluster | API defaults show up as differences (CNV-14) |
| Emitting a recipe directory for `check` | Recipe rules (README `Level`, `tests/`, key scopes) fail a user's conversion for reasons unrelated to equality |

## Verification

- AC-141 (CNV-1, CNV-11, CNV-13 to CNV-19): the CI `convert` job converts
  podinfo 6.17.0 and exits 0; its report shows 4 objects equal, the 3 test
  pods left out, the selector note, and the value map.
- AC-142 (CNV-3 to CNV-10, CNV-12, CNV-20): `check/tests/test_convert.py` passes in
  the `test` job.

## Open questions

- OQ-17: Should Kapitan get a `kapitan convert helm` subcommand that calls
  this command? Deferred.

## Implementation inventory

| Path | Purpose |
|---|---|
| `check/convert.py` | `kadet-convert`: render, map, write, compile, prove, report, value map |
| `check/tests/test_convert.py` | AC-142 |
| `check/tests/fixtures/convert/podinfo-values.yaml` | Values of the CI conversion (CNV-19) |
| `check/pyproject.toml`, `check/uv.lock` | Entry point `kadet-convert`, built with setuptools (DEC-183) |
| `.github/workflows/ci.yml` | Job `convert` (CNV-19); `deps` exports the lock without the project |
| `renovate.json` | Moves the generator pin in `check/convert.py` (RCP-30) |
| `docs/convert.md`, `README.md` | Usage |

| Value | Setting |
|---|---|
| `kubernetes` generator | `ghcr.io/kadet-hub/kubernetes:1.14.0@sha256:787129e1eaed6b9bc868fe4c4aec58d40de6a89fc3cc08424a4cb5822b855080` |
| podinfo | `oci://ghcr.io/stefanprodan/charts/podinfo@sha256:258d0da545724b4eea8de5d5e724cd9a75aab3de79a87ba8d82ec402745cea58`, version 6.17.0 |
| Kind clusters | `<prefix>-<release>-chart`, `<prefix>-<release>-recipe`, prefix `convert` |
| Output | `<out>/project/`, `<out>/report.md`, `<out>/value-map.json`, `<out>/render.yaml` |
