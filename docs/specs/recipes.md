# Recipes

```text
Status: Draft. check 0.1.0 implements renders and deploys; migrates
        (RCP-14), RCP-21 and RCP-22 are not implemented.
Code: <name>/, check/, .github/, renovate.json, README.md
Verified against: #3, cert-manager at deploys
```

## Problem

A Helm chart or a Kustomize base is how most teams receive third-party
software for Kubernetes. Moving such an application to Kapitan means
rebuilding what the chart renders as inventory for kadet-hub generators,
then proving that nothing was lost. kadet-hub/examples did this by hand for
metrics-server, cert-manager and kube-prometheus-stack (`chart-vs-kapitan`).
Two test runs of the `to-recipe` agent skill on cert-manager v1.21.2 showed
that the migration can be done by an agent, but also that every run writes
its own comparison and that the result is only as good as that comparison.

A recipe is that rebuilt application, maintained and proven in one place,
so that users include a recipe the way they would install a chart. This
repository holds the recipes, the one comparison script that proves them,
and the CI that runs it.

## Decisions

DEC-1: This repository holds the recipe sources, the comparison script
`check` and the CI. Publishing goes through kadet-hub/registry like a
generator: a tagged recipe is registered there, and the release workflow
publishes it as an OCI artifact with an attestation and an entry in the
index. The registry side needs its own change (OQ-3).

DEC-2: A recipe is a class directory, split by component. The RBAC entries
of a component live in that component's file, because they bind its
ServiceAccount; splitting by resource kind would separate a workload from
the roles it needs. Optional parts of the chart, such as CRDs behind
`crds.enabled`, are separate classes that a target includes.

DEC-3: Recipes are written for the omegaconf inventory backend and use its
built-in resolvers to derive values instead of repeating them. Custom
resolvers are not used, because a consumer would have to install them.

DEC-4: A chart's subchart becomes a recipe of its own. The parent recipe
includes it through `classes:` and overrides only what the parent chart's
values change. A subchart that several charts share is then written once.

DEC-5: A recipe is proven at one of three levels, `renders`, `deploys` and
`migrates` (Proof). Every recipe reaches `renders`. Proving every recipe on
a running cluster does not scale to large charts and is not what a chart
catalog does either, so the higher levels are per recipe and shown in its
README.

DEC-6: Recipes are fetched before the inventory is loaded, through a
separate fetch inventory (Distribution). Kapitan 0.36.3 cannot fetch a
class that the same inventory uses. A Kapitan feature that reloads the
inventory after the fetch (OQ-2) would let the pins live where they are
used and reduce this to one command.

DEC-7: No Open Component Model (OCM) packaging for now (OQ-1).

Related: [kadet-hub authoring guide](https://github.com/kadet-hub/registry/blob/main/docs/authors.md),
[consumers guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md),
[chart-vs-kapitan](https://github.com/kadet-hub/examples/tree/main/chart-vs-kapitan)

## Layout

```text
<name>/
  init.yml          # generator pins, applications.<name>, classes of the components
  <component>.yml   # one per component, with its RBAC
  <option>.yml      # optional class, such as crds.yml
  README.md
  tests/
    values.yaml     # the values the proof renders the chart with
    target.yml      # the target the proof compiles the recipe with
    smoke           # deploys level: proves the application works
check/              # the comparison script and its tests
```

In a consumer's project, a recipe lives at
`inventory/classes/recipes/<name>/`, so `recipes.<name>` includes it and
`recipes.<name>.<option>` adds an option. The omegaconf backend resolves a
class directory through its `init.yml` and resolves relative includes such
as `.controller` (Kapitan 0.36.3, `inventory/backends/omegaconf`).

- RCP-1: Every recipe MUST be a directory `<name>/` with an `init.yml`, one
  file per component, a `README.md`, `tests/values.yaml` and
  `tests/target.yml`, and above level `renders` also `tests/smoke`.

  `init.yml` sets no `components`, so each component lives in its own
  file. Vendored files, such as the CRDs, live below the recipe directory,
  so the class directory carries them.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-2: A recipe MUST NOT set `generators.manifest.default_config`. Settings
  shared by its components go into `applications.<name>.component_defaults`,
  and each component sets `application: <name>`.

  `default_config` is merged into every component of a target, so a
  recipe's defaults would change other applications compiled in the same
  target. The first cert-manager test run put `POD_NAMESPACE`, a
  `prometheus.io/port` annotation and `security_profile: restricted` there.
  The `kubernetes` generator merges application defaults only into the
  components that name the application.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-3: Every object name a recipe renders MUST start with the recipe's
  name or a name the chart uses.

  `check lint` compiles `tests/target.yml` and renders the chart with
  `tests/values.yaml` to compare the names.

  Recipes share the `components` and `generators.kubernetes.rbac`
  namespaces of the inventory, so two recipes in one target must not
  collide.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

## Writing a recipe

A recipe follows the authoring guide: each value is written once, values
the generator derives are left out, values equal to the generator's
default are left out, and a line that does not change the output does not
belong in the recipe.

- RCP-4: YAML in a recipe MUST use block style. Flow style is allowed only
  for a mapping or list that fits on one line of at most 80 characters,
  such as `{fieldPath: metadata.namespace}`.

  The cert-manager test runs wrote RBAC rules as long flow lines, which
  are hard to review in a diff.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-5: A value that is derivable from another inventory value MUST be
  written as an interpolation or with a built-in resolver, such as
  `${namespace}`, `${parentkey:}` or `${merge:...}`.

  - Test: manual: review
  - Since: #2

- RCP-6: Images MUST be pinned as `tag@sha256:digest`, also where an image
  is passed in a container argument.

  `check lint` reads the compiled output: every container image and every
  argument of the form `--<...>image<...>=<ref>`.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-7: A recipe MUST NOT copy a whole object through a pass-through
  section, such as the `kubernetes` generator's `manifests`.

  An object that only fits there is a gap in the generators. It is
  reported to kadet-hub/registry as a generator request instead.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

## Proof

`check <name>` renders the source chart pinned by version and digest with
`tests/values.yaml`, compiles the recipe with the same values, and compares
the two. Helm hooks that only run inside `helm install` and test pods are
listed in the recipe's README and left out of the comparison.

`check` is one Python CLI in `check/`, run with
`uv run --locked --project check check/check.py`. Its lock pins Kapitan
0.36.3 with omegaconf 2.4.0.dev4, the install the consumers guide gives
users, and PyYAML. The kind node image and the Kapitan `next` image are
pinned by digest in `check/check.py`. helm, kubectl, kind, oras and gh come
from `PATH`; CI installs them pinned (RCP-28).

- RCP-23: A recipe's README MUST contain the line
  ``Source: `oci://<chart>:<version>@sha256:<digest>` `` and the line
  ``Level: `<level>` ``. `check` pulls the chart by that digest and fails
  unless the chart's version is `<version>`. The release name is the
  recipe's name, and the namespace is `parameters.namespace` of
  `tests/target.yml`.

  `tests/target.yml` is the recipe's side of `tests/values.yaml`: it
  includes the recipe and the options those values switch on. Charts from
  an HTTP repository are not supported yet.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-24: `check` MUST compile every recipe with Kapitan 0.36.3 from its
  lock, and that compile alone decides the level. It MUST also compile the
  recipe with the image `ghcr.io/kadet-hub/kapitan:next@sha256:<digest>`,
  built by kadet-hub/kapitan from kapicorp/kapitan `master` plus open
  upstream pull requests, and report a failed compile or every output file
  that differs from 0.36.3, without changing its exit status.

  Users install 0.36.3. `next` shows early what the next Kapitan release
  changes for a recipe.

  - Test: CI `check` job, report line `kapitan next`
  - Since: #2, #3

- RCP-29: Renovate MUST move the `next` pin of RCP-24 to the current
  digest of the tag `next`, in one pull request at a time that it updates
  only in a daily schedule window and that does not merge automatically.

  kadet-hub/kapitan rebuilds `next` up to every 15 minutes and tags each
  build `next-<sha>` and `next`. Renovate cannot order the `next-<sha>`
  tags, so the pin names the moving tag `next` and Renovate updates its
  digest, as it does for `latest`. The pin's report line names the
  digest. The commit an image was built from is in its
  `org.opencontainers.image.revision` label and in kadet-hub/kapitan#1.
  The window, 00:00 to 06:00 Europe/Berlin, keeps a build every 15
  minutes from turning into a stream of pull requests.

  - Test: manual: Renovate dry run
  - Since: #3

- RCP-25: `check` MUST leave out every chart object with the annotation
  `helm.sh/hook`, and MUST fail unless the README names each of them as
  `` `<Kind>/<name>` ``.

  - Test: CI `check` job, report lines `hook left out`
  - Since: #2

- RCP-26: At level `renders`, `check` MUST apply for real only Namespaces,
  CRDs, ServiceAccounts and RBAC objects, and every other object only with
  a server-side dry run. At level `deploys` it MUST apply the recipe for
  real on the recipe's cluster, wait for the rollout of every Deployment,
  StatefulSet and DaemonSet, and run `tests/smoke` with `KUBECONFIG` set to
  that cluster. The smoke test's exit status decides.

  `renders` then starts no pod from a pull request, so it needs no
  approval on forks (RCP-20).

  - Test: CI `check` job
  - Since: #2

- RCP-27: `check` MUST pull each generator a recipe pins only after
  verifying it as the consumers guide describes: the attestation of the
  latest index, that index listing the digest under the pinned version and
  not yanked, and the attestation of the generator itself.

  - Test: CI `lint` and `check` jobs, report line `generator`
  - Since: #2

| Level | What is proven | Cluster |
|---|---|---|
| `renders` | Same objects after server-side dry run and normalization, selectors select the same objects, same permissions for every subject | kind, API server only |
| `deploys` | `renders`, and a fresh install becomes ready and passes `tests/smoke` | kind |
| `migrates` | `deploys`, and a running Helm release is replaced by the recipe while `tests/smoke` keeps passing | kind |

- RCP-8: Each side MUST be compared on its own fresh kind cluster. Every
  namespace either side names MUST exist before the dry run, and the
  target namespace MUST be the context's namespace.

  A dry run merges with objects that already exist, which can hide a
  missing field on both sides. `kubectl apply -n` rejects objects that name
  another namespace, such as cert-manager's leader election Roles in
  `kube-system`, so the namespace is set in the context instead.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2

- RCP-9: Normalization MUST drop exactly these fields and nothing else:
  `uid`, `resourceVersion`, `creationTimestamp`, `managedFields`,
  `generation`, `status`, the annotation
  `kubectl.kubernetes.io/last-applied-configuration`, labels and
  annotations whose key starts with `helm.sh/` or `meta.helm.sh/`, the labels
  `app.kubernetes.io/managed-by` and `app.kubernetes.io/version`, the labels
  that only identify an object (`app`, `name`, `app.kubernetes.io/name`,
  `app.kubernetes.io/instance`, `app.kubernetes.io/component`,
  `app.kubernetes.io/part-of`), and image digests on the recipe side. Secrets
  the chart generates are compared by key.

  Keeping the identifying labels would force a recipe to copy the chart's
  label scheme. What selects on them is checked by RCP-10 instead. Every
  other label and annotation stays, because ingress controllers, meshes
  and monitoring read them.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2

- RCP-10: Every selector on both sides MUST select the same objects, judged
  on the labels before normalization: a workload's selector its own pods, a
  Service's endpoints the pods of the same workload, and a NetworkPolicy,
  PodDisruptionBudget or ServiceMonitor the same pods or Services as on the
  chart side.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2

- RCP-11: RBAC MUST be compared by what it grants. `check` collects every
  subject a binding on either side names and diffs
  `kubectl auth can-i --list` for each one, in every namespace either side
  binds a Role in, with sorted verbs. ClusterRoles that aggregate into the
  built-in roles are covered by a test user bound to `view`, `edit` and
  `admin`.

  A group is listed as a test user in that group. `check` lists only once
  the built-in roles carry the rules aggregated into them. Labels that
  aggregate into roles kind does not have, such as OpenShift's
  `cluster-reader`, are reported as not tested.

  RBAC object names do not take part in the comparison. The `kubernetes`
  generator rejects `:` in names, so a recipe renames objects like
  `cert-manager-controller-approve:cert-manager-io` and lists the renames
  in its README.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2

- RCP-12: After normalization the object diff MUST be empty, except for
  differences of the classes below. `check` reports each remaining
  difference with its class.

  | Class | Example | Why it is accepted |
  |---|---|---|
  | Selector scheme | the generator selects on `name`, the chart on `app.kubernetes.io/*` | RCP-10 proves the same selection |
  | Explicit default | pod `automountServiceAccountToken: true` where the chart leaves it unset | same value as the ServiceAccount's |
  | Port by name | `targetPort: http-metrics` against `9402` | resolves to the same container port |
  | Derived name | container named after the component, webhook configuration `<ns>-<component>`, sorted container ports | names the generator derives, no change in behaviour |

  The two cert-manager runs ended with exactly these differences. A class
  is added here only with the run that needs it.

  `check` accepts a difference only where its class holds: a selector
  difference where RCP-10 found the same selection, `true` where the other
  side is unset and the pod's ServiceAccount does not disable the token, a
  port name that resolves to the other side's number in the selected pods
  or the same pod, a first container named after its workload, container
  ports that are the same set sorted by name, and a webhook configuration
  named `<namespace>-...` with the same webhooks.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2

- RCP-13: A recipe's README MUST state its proof level, and CI MUST run
  `check` at that level for every recipe a pull request changes and for
  every recipe once a week. A change below `check/` or `.github/` changes
  every recipe.

  - Test: CI `select` job
  - Since: #2

## Migration

Replacing a running Helm release cannot be a plain `kubectl apply`:
`Deployment.spec.selector` is immutable, objects the recipe names
differently stay behind, and Helm still owns the objects. The recipe's
README documents these steps and the `migrates` level runs them on kind.

1. Delete the release's Helm secrets (`sh.helm.release.v1.<release>.*`), so
   Helm forgets the release without deleting its objects.
2. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
3. For each Deployment whose selector changed, delete it with
   `--cascade=orphan` before step 2, so its pods keep serving until the
   recipe's pods are ready, then delete the orphaned ReplicaSets.
4. Delete the objects the chart rendered under a name the recipe does not
   use, from the list `check` prints.

- RCP-14: A recipe at level `migrates` MUST pass `tests/smoke` before, during
  and after the steps above, and after them no object may carry the label
  `app.kubernetes.io/managed-by: Helm`.

  The steps are a proposal. Whether step 3 keeps cert-manager's webhook
  available throughout is not measured yet.

  - Test: `check <name> --level migrates`
  - Since: not implemented

## Distribution

A recipe is published as `ghcr.io/kadet-hub/recipes/<name>`, one OCI
artifact per release, versioned with its own SemVer and tagged
`<name>-vX.Y.Z` in this repository. The chart version it was derived from
is metadata of the artifact and is shown in the README.

Kapitan resolves the inventory before it fetches dependencies, and it does
not reload it after the fetch. Probes on Kapitan 0.36.3 with both backends,
with the recipe's dependency in the same inventory:

| Case | Command | Result |
|---|---|---|
| Fresh clone, recipe missing | `kapitan compile --fetch` | stops with `Class recipes.demo not found`, nothing fetched |
| Recipe present, pin raised | `kapitan compile --fetch` | does not fetch, the file exists, compiles the old recipe |
| Recipe present, pin raised | `kapitan compile --force-fetch` | fetches the new recipe, compiles the old one |
| After that | `kapitan compile` | compiles the new recipe |

A fetch inventory that holds only the recipe dependencies works:

```sh
kapitan compile --inventory-path fetch --fetch --output-path .
kapitan compile --fetch
```

The first command exits with status 1 and
`No such file or directory: .../compiled`, because the fetch target
compiles nothing. The recipe is fetched all the same. After a pin is
raised, `--fetch` keeps the existing directory, and `--force-fetch` copies
the new recipe over it, so files the new version removed stay. The
consumer therefore deletes `inventory/classes/recipes/<name>` before the
first command.

- RCP-15: Consumers MUST fetch recipes with a separate fetch inventory, pinned
  by digest, and verify them as the consumers guide describes for
  generators, until Kapitan fetches such classes itself (OQ-2).

  Until recipes are published (OQ-3), the fetch inventory pins this
  repository by commit SHA as a `git` dependency, and the consumer verifies
  the generators the recipe pins. The steps are in the README's
  "Using a recipe".

  - Test: manual: the README's "Using a recipe" steps on a fresh clone
  - Since: #5

- RCP-16: Renovate MUST open a pull request when the chart a recipe is
  derived from has a new release. The pull request runs `check` at
  `renders`, so the diff of the new chart against the recipe is visible.

  Renovate moves the README's `Source` line to the new version and its
  digest. The recipe's images, vendored files and values stay at the old
  version, so `check` fails and its report is the diff a maintainer
  works from. The images take their tag from
  `applications.<name>.version`, which Renovate cannot read, so it does
  not update them on its own.

  - Test: manual: Renovate dry run
  - Since: #3

## Security

A recipe reaches users' machines and clusters through a pinned artifact,
so it is supply chain. The threats below were worked through against
Kapitan 0.36.3, and each requirement names the paths it closes.

An inventory class is not just data. It can add `kapitan.compile` entries:
`external` runs any binary through `subprocess`, `jinja2` renders in a
plain `jinja2.Environment` without sandbox, and `kadet` runs Python it
brings along. The omegaconf resolver `from_file` reads any path the
compiling user can read, and its value can land in compiled output or in a
dependency's source URL, which the consumer workflow fetches outside its
sandbox. Classes merge into shared parameters, so a recipe can change
another application's component, such as its image, without any output
rule noticing. The consumer workflow's sandbox contains much of this, but
the `to-recipe` skill and most users compile locally.

Besides `from_file`, the built-in resolvers of Kapitan 0.36.3 and omegaconf
2.4.0.dev4 were checked for what they read from the compiling host.
`oc.env` returns an environment variable, such as a token that the CI job
or the user's shell holds. `filename`, `parent_filename`, `path` and
`parent_path` return a node flag meant to carry the class file's name and
path on the host. Neither 0.36.3 nor kapicorp/kapitan `master` sets that
flag, so they resolve to `null` today, which also leaves a recipe no use
for them. No built-in resolver reads the clock. `oc.decode` only parses
its argument, and `${oc.decode:${oc.env:X}}` is caught through `oc.env`.
The remaining ones read only the inventory: `oc.create`, `oc.select`,
`oc.deprecated`, `oc.dict.keys`, `oc.dict.values` and Kapitan's key,
merge, conversion and boolean resolvers.

- RCP-17: A recipe MUST contain only parameters, `kadet` compile entries
  whose input is a kadet-hub generator pinned by digest in the same
  recipe, `copy` entries of vendored files with a SHA-256 comment, and
  `oci` dependencies on `ghcr.io/kadet-hub/` pinned by digest. It MUST NOT
  use the resolvers `from_file`, `write`, `oc.env`, `filename`,
  `parent_filename`, `path` or `parent_path`.

  This makes a recipe data: with it, a recipe can neither run code nor
  read files, environment variables or its own location on the host at
  compile time. `write` is listed because it writes to keys outside the
  recipe (RCP-18).

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2, #3

- RCP-18: A recipe MUST write parameters only below keys of its own name:
  `components.<name>*`, `applications.<name>`,
  `generators.<generator>.<section>.<name>*`, plus its own entries in
  `kapitan.dependencies` and `kapitan.compile`.

  RCP-3 keeps rendered object names apart. This keeps the inventory apart,
  so a recipe cannot reach into another application's components or bind
  its ServiceAccount through an RBAC entry named after something else.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-19: A recipe MUST NOT name a ref backend. A value the chart generates,
  such as a password, is a ref whose full tag the target sets, and
  `check lint` MUST reject `?{` in a recipe file.

  The examples' recipes use the `base64` backend so they run anywhere. In a
  user's repository that is a plaintext secret in git.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-20: CI MUST run pull requests with `pull_request`, never
  `pull_request_target`, with `permissions: {}` and no secrets, and MUST NOT
  write caches from pull request runs. The `deploys` and `migrates` levels
  MUST wait for a maintainer's approval on pull requests from forks.
  Releases run in a separate workflow on `main`.

  `deploys` applies the pull request's manifests to kind inside the runner.
  The kind node is a privileged container, so a hostPath pod reaches the
  runner's file system.

  On a pull request from a fork, the `check` job of a recipe above
  `renders` runs in the environment `fork-pull-request`, whose required
  reviewer is a maintainer. The jobs use only the run's `GITHUB_TOKEN`,
  read-only, which `gh attestation verify` needs.

  - Test: manual: workflow review; actionlint in the CI `test` job
  - Since: #2

- RCP-28: CI MUST run the unit tests of `check`, actionlint and
  `check lint` on every pull request. Every action MUST be pinned by commit
  SHA, and every tool CI downloads by version and SHA-256.

  The tools are installed by `.github/actions/tools`, uv by
  `astral-sh/setup-uv` with its cache off.

  - Test: CI `test` and `lint` jobs
  - Since: #2

- RCP-30: Renovate MUST propose updates for every pin of RCP-28, the
  packages in `check/uv.lock`, the kind node image and the generators a
  recipe pins, and MUST NOT merge any update automatically.

  `renovate.json` follows kadet-hub/examples. A tool pin carries a
  `# renovate:` comment, a release asset its SHA-256 and an image its
  digest. Renovate waits three days after a release whose registry
  reports a release date. kind and its node image move in one pull
  request. helm and kubectl are not GitHub release assets, so Renovate
  moves only their version, and the tools step fails until their SHA-256
  is set from the publisher's checksum file. Python stays on 3.13, which
  `requires-python` pins. omegaconf stays on 2.4.0.dev4, because later
  releases removed `ListMergeMode`, which Kapitan 0.36.3 needs
  (kapicorp/kapitan#1621).

  Renovate pushes only `renovate/` branches. The `branches` ruleset of
  this repository admits only the admin role to every branch but `main`.
  Until it excludes `renovate/**` and a `renovate branches` ruleset
  admits Renovate and the admin role there, as REV-3 does in
  kadet-hub/registry, Renovate cannot push.

  - Test: manual: Renovate dry run
  - Since: #3

- RCP-21: A pull request that moves a recipe to a new chart version MUST
  show, apart from the object diff, every image that changed, the `can-i`
  diff of each subject between the old and the new recipe, and any added
  webhook, hostPath volume, privileged container or host namespace.
  Such pull requests MUST NOT merge automatically.

  `renders` compares the recipe with the chart. A compromised chart
  release passes it. This diff is what a reviewer can still catch.

  - Test: `check` tests; Renovate configuration
  - Since: not implemented

- RCP-22: `check` MUST be released with its own version tag
  `check-vX.Y.Z`, and the `to-recipe` skill MUST run a pinned version
  instead of writing its own normalization.

  An agent reads chart templates, `NOTES.txt` and `values.yaml`, which the
  chart author controls. A comparison the agent writes itself can be
  steered by text in them. A diff against a pinned script cannot, and an
  injected extra object then shows up as a difference outside RCP-12.

  - Test: manual: the skill names a `check` version
  - Since: not implemented

Kapitan trusts its inventory: a class may run any binary through an
`external` entry. Recipes change that model, because their classes come
from a third party. RCP-17 and RCP-18 restore it for recipe content. What
Kapitan itself would need once it fetches classes (OQ-2), such as limits
on where a fetched class's dependencies may write, is part of that
feature's design (OQ-6).

## Verification

- AC-1 (RCP-1 to RCP-7): `check lint` fails on a recipe with
  `default_config`, with a `manifests` pass-through, with an image without
  digest, with a long flow-style line, and passes on cert-manager.
- AC-2 (RCP-8 to RCP-12): `check`'s tests run the comparison on fixtures
  that differ by a dropped label, an unchanged selector that no longer
  matches, a lost RoleBinding to a group, and an accepted difference of
  each class, and fail or pass accordingly.
- AC-3 (RCP-13, RCP-14): cert-manager v1.21.2 passes `check cert-manager
  --level migrates` in CI. Met so far up to `deploys`.
- AC-5 (RCP-17 to RCP-19): `check lint` fails on fixtures with an
  `external` entry, a `jinja2` entry, each resolver RCP-17 forbids, an
  unpinned or foreign dependency, a key under another application's component, and a
  literal `?{base64:` ref.
- AC-6 (RCP-20, RCP-21): actionlint passes. A fixture pair of an old and a
  new recipe with an added image, an added ClusterRole verb and an added
  hostPath volume makes `check` list all three.
- AC-4 (RCP-15): a fresh clone of a consumer project fetches cert-manager
  by commit SHA and compiles it with the two commands above.
- AC-7 (RCP-16, RCP-29, RCP-30): a local Renovate dry run on this
  repository extracts the chart of every recipe, the `next` pin, the kind
  node image, the generator pins, every tool and action pin and the
  `check` lock, and finds no update set to merge automatically.

## Open questions

- OQ-1: Should a recipe release also be an OCM component version that
  references the recipe, its generators, its images and its chart source,
  for transfer into an air-gapped registry? Not before someone needs
  air-gapped installs. Images pinned by digest (RCP-6) and the chart source
  as metadata keep that option open.
- OQ-2: Kapitan feature: `kapitan compile --fetch` loads the inventory
  ignoring missing classes, fetches, reloads, and repeats until no new
  dependency appears, so one command behaves like `helm dependency update`
  followed by `helm template`. The pins stay in the inventory as
  `kapitan.dependencies` of the class or target that uses the recipe, as
  charts are declared today. Repeating is needed because a parent recipe
  declares the dependency on its subchart recipes (DEC-4), which only
  appears after the parent is fetched. A dependency entry then must not
  interpolate values from a class it fetches. kapicorp/kapitan#436
  described remote inventories in 2021. Kapitan 0.36.3 loads the inventory
  with `ignore_class_not_found` during `--fetch` and has an unused
  `reset_inv()`, but neither takes effect.
- OQ-3: What does the registry gate check for a recipe? A recipe contains
  no generator code, so the sandboxed compile and the scans of a generator
  do not all apply. A first answer: the gate runs `check lint` and
  `renders`, and the release workflow publishes the class directory.
- OQ-4: Who owns a recipe? Owners per recipe as for generators, or the
  maintainers of this repository?
- OQ-5: Does Renovate's chart update only report the diff (RCP-16), or does
  an agent run `to-recipe` on the new chart and propose the changed recipe?

- OQ-6: Which limits does Kapitan need once classes can come from a third
  party, for example confining `from_file` and the `output_path` of a
  fetched class's dependencies to the project? To be settled with the
  Kapitan maintainers together with OQ-2.
- OQ-7: Not checked yet: how far the consumer workflow's gVisor sandbox
  contains a recipe that breaks RCP-17, and whether `helm template` itself
  can be attacked by a chart while `check` renders it. `template` has no
  cluster access, which limits functions like `lookup`, but that is not
  verified.

## Implementation inventory

| Path | Purpose |
|---|---|
| `README.md` | Using a recipe (RCP-15) |
| `<name>/` | One recipe (RCP-1) |
| `check/check.py` | CLI, sources, kind clusters, report; pins the kind node and Kapitan `next` images |
| `check/lint.py` | `check lint` (RCP-1 to RCP-7, RCP-17 to RCP-19, RCP-23) |
| `check/compare.py` | Normalization, pairing, classes, selectors, can-i (RCP-9 to RCP-12) |
| `check/tests/` | AC-1, AC-2, AC-5 without a cluster |
| `check/pyproject.toml`, `check/uv.lock` | Kapitan 0.36.3, omegaconf 2.4.0.dev4, PyYAML |
| `.github/workflows/ci.yml` | RCP-13, RCP-20, RCP-28 |
| `.github/actions/tools/` | Pinned helm, kubectl, kind, oras, gh |
| `renovate.json` | RCP-16, RCP-29, RCP-30 |

| Value | Setting |
|---|---|
| Repository | `kadet-hub/recipes`, public, Apache-2.0 |
| Artifact | `ghcr.io/kadet-hub/recipes/<name>` |
| Tag | `<name>-vX.Y.Z` |
| Inventory backend | omegaconf, Kapitan 0.36.3 |
| First recipe | cert-manager, chart v1.21.2, level `deploys`, target `migrates` |
| Environment | `fork-pull-request`, required reviewer: a maintainer |
| Consumer path | `inventory/classes/recipes/<name>/` |
