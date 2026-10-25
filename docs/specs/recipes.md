# Recipes

```text
Status: Draft. check 0.3.0 implements renders and deploys, for compose
        sources and designed recipes deploys (RCP-38, RCP-44); migrates
        (RCP-14), RCP-21, RCP-22, RCP-31, RCP-32 and RCP-34 are not
        implemented; RCP-15 only up to publication.
Code: <name>/, check/, .github/, renovate.json, README.md
Verified against: #3, cert-manager at deploys; #10, valkey at deploys;
                  #14, mysql at deploys; this change, mongodb at deploys
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

Many self-hosted applications ship no chart, only a Docker Compose file in
their repository. Migrating one is the same mapping to generators, but the
source has no Kubernetes objects to compare the recipe with.

Some projects publish neither, only a container image. A recipe for such a
project is designed in kadet-hub, with no upstream artifact to derive it
from or to compare it with.

A recipe is that rebuilt application, maintained and proven in one place,
so that users include a recipe the way they would install a chart. This
repository holds the recipes, the one comparison script that proves them,
and the CI that runs it.

## Decisions

DEC-1: This repository holds the recipe sources, the comparison script
`check` and the CI. Publishing goes through kadet-hub/registry like a
generator: a tagged recipe is registered there, and the release workflow
publishes it as an OCI artifact with an attestation and an entry in the
index. The registry side is its spec
[`docs/specs/recipes.md`](https://github.com/kadet-hub/registry/blob/main/docs/specs/recipes.md)
(`REC-`).

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

DEC-8: A Docker Compose file is a source, and a recipe derived from one is
proven at `deploys` only (Compose sources). `renders` compares Kubernetes
objects, and a compose file has none. kompose would render some, but its
output is a heuristic translation itself, so agreeing with it proves
nothing about the compose file. `migrates` replaces a Helm release in the
cluster, and a compose stack runs outside it. The proof is therefore
behaviour: the recipe deploys and its smoke test exercises what the
compose file sets up.

DEC-9: The source type follows from the form of the README's `Source` line
(RCP-23): `oci://` is a chart, a GitHub file URL a compose file, and an
image reference without a scheme the image of a designed recipe. A separate
`Source-Type:` line was considered. It would repeat what the line already
says, and the two could contradict each other.

DEC-10: A recipe of kadet-hub/examples moves here with the project's own
Helm chart or Kustomize base as its source where the project ships one
(Recipes from kadet-hub/examples). It is then proven like any chart recipe,
and the examples recipe's behaviour becomes `tests/values.yaml` and its
check `tests/smoke`. Moving the examples recipe as it is was considered. It
has no upstream artifact to compare with, and users of the project's chart
could not move to it with a proof. A recipe designed in kadet-hub for a
project that ships no chart, base or compose file has the project's image
as its source (DEC-11).

DEC-11: A project that ships no chart, Kustomize base or compose file gets
a recipe designed in kadet-hub, with the project's container image as its
source, proven at `deploys` only (Designed recipes). The image is the one
artifact such a project maintains, so the recipe pins it and Renovate
follows it. With no objects to compare with, the proof is behaviour, as
for a compose source (DEC-8). A chart maintained by a third party was
rejected as a source. A proof against it would carry that party's choices
into the recipe and tie the recipe to a chart the project does not
maintain.

Related: [kadet-hub authoring guide](https://github.com/kadet-hub/registry/blob/main/docs/authors.md),
[consumers guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md),
[chart-vs-kapitan](https://github.com/kadet-hub/examples/tree/main/chart-vs-kapitan)

## Layout

```text
<name>/
  init.yml          # generator pins, applications.<name>, classes of the components
  <component>.yml   # one per component, with its RBAC
  <option>.yml      # optional class, such as crds.yml
  vendor/           # vendored files, each with <file>.LICENSE (RCP-35)
  README.md
  tests/
    values.yaml     # chart source: the values the proof renders the chart with
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
  file per component, a `README.md` and `tests/target.yml`, from a chart
  source also `tests/values.yaml`, and above level `renders` also
  `tests/smoke`.

  `init.yml` sets no `components`, so each component lives in its own
  file. Vendored files, such as the CRDs, live below the recipe directory,
  so the class directory carries them.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2, #8

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
  name or, from a chart source, a name the chart uses.

  `check lint` compiles `tests/target.yml` and renders the chart with
  `tests/values.yaml` to compare the names. A compose file or an image
  names no Kubernetes objects, so there every name starts with the
  recipe's.

  Recipes share the `components` and `generators.kubernetes.rbac`
  namespaces of the inventory, so two recipes in one target must not
  collide.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2, #8, #14

## Writing a recipe

A recipe follows the authoring guide: each value is written once, values
the generator derives are left out, values equal to the generator's
default are left out, and a line that does not change the output does not
belong in the recipe.

- RCP-35: Every vendored file `vendor/<file>` MUST have the upstream license
  as `vendor/<file>.LICENSE`, and the upstream NOTICE as
  `vendor/<file>.NOTICE` when the upstream source has one. `check lint`
  MUST fail on a file a `copy` entry names without its `.LICENSE`.

  The registry publishes the recipe directory, so it redistributes the
  vendored files. Apache-2.0, the license of cert-manager's CRDs, requires
  the license and the NOTICE with each copy (section 4). The registry gate
  checks the same (REC-15). cert-manager's upstream source v1.21.2 has
  no NOTICE.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #7

- RCP-40: A recipe's README MUST have a section "Required parameters"
  directly after "Include", and `check lint` MUST fail when it is missing
  or empty. The section names every parameter the target must set, or
  says "No parameter has to be set."

  A value the recipe leaves unset, such as a ref of RCP-19, stops the
  compile until the target sets it. The include snippet alone does not
  say which values those are. The registry shows the section on the
  recipe's page next to the snippet (CAT-37c there).

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #9

- RCP-4: YAML in a recipe MUST use block style. Flow style is allowed only
  for a mapping or list that fits on one line of at most 80 characters,
  such as `{fieldPath: metadata.namespace}`.

  The cert-manager test runs wrote RBAC rules as long flow lines, which
  are hard to review in a diff.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2

- RCP-43: A recipe on the `kubernetes` generator 1.7.0 or later MUST
  write `args` as a mapping, in a component and in its
  `additional_containers` and `init_containers`. `check lint` MUST warn
  on an `args` list and MUST NOT fail on it.

  The keys name the arguments and do not render. A list value gives
  several arguments, such as `[--leader-election-namespace, kube-system]`,
  and `~` drops one. The values render in the mapping's order (K8S-4 of the
  generator's spec). A target changes or drops one argument the recipe
  sets by its key, as in `components.cert-manager.args.verbosity: --v=4`.
  With a list it cannot, because both backends merge a target's list into
  the class's: reclass appends, and the omegaconf backend of Kapitan 0.36.3
  extends with `EXTEND_UNIQUE`. Changing one argument then took a class
  that resets the list, included before the target. cert-manager switched
  to the mapping in #4.

  A list is still valid input for the generator and renders the same
  objects (K8S-3), so a recipe with a list compiles and is proven like any
  other. The warning asks for the mapping without stopping a proof.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: this change

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

- RCP-42: A class file that carries text a chart renders from its
  templates, such as a script in a ConfigMap, MUST name the chart file and
  version in a comment above it and have the upstream license next to it
  as `<file>.LICENSE`. Each `${` of that text MUST be written as
  `${escape:...}`.

  The registry publishes the class file, so it redistributes the text as
  RCP-35 describes for vendored files. The generator renders ConfigMaps, so
  the text stays in the class instead of a `copy` of the whole object
  (RCP-7). Kapitan 0.36.3 resolves the omegaconf inventory twice, so `\${`
  is resolved on the second pass. `${escape:...}` comes out as `${...}`. A
  value the chart computes from its templates, such as a `checksum/*` pod
  annotation, is written as the chart renders it with `tests/values.yaml`,
  and the README says that it does not follow a change of the recipe.
  `check lint` cannot tell copied text from written text.

  - Test: manual: review; CI `check` job
  - Since: #10

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

- RCP-23: A recipe's README MUST contain the line ``Level: `<level>` `` and
  one `Source` line. For a chart it is
  ``Source: `oci://<chart>:<version>@sha256:<digest>` ``, and `check`
  pulls the chart by that digest and fails unless the chart's version is
  `<version>`. For a compose file it is
  ``Source: `https://github.com/<owner>/<repo>/blob/<commit>/<path>@sha256:<digest>` ``
  with the full commit SHA, and `check` fetches the file at that commit
  and fails unless its SHA-256 is `<digest>`. For a designed recipe it is
  ``Source: `<registry>/<repository>:<tag>@sha256:<digest>` ``, the
  project's image with its registry host, and `check lint` fails unless a
  container of the compiled recipe runs exactly that image. The release
  name is the recipe's name, and the namespace is `parameters.namespace`
  of `tests/target.yml`.

  `tests/target.yml` is the recipe's side of `tests/values.yaml`: it
  includes the recipe and the options those values switch on. Charts from
  an HTTP repository and compose files outside GitHub are not supported
  yet.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #2, #8, #14

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
  The pin has no minimum release age: a digest update of a moving tag has
  no release timestamp, so the repository's `minimumReleaseAge` with
  `minimumReleaseAgeBehaviour: timestamp-required` would hold it forever.

  - Test: manual: Renovate dry run
  - Since: #3; release age exempted: this change

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

For a compose source and a designed recipe, `deploys` proves the recipe
side of `renders` only (RCP-38, RCP-44), and there is no `migrates` level.

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

## Compose sources

A compose recipe maps the services of one compose file, pinned by
repository, commit and SHA-256 (RCP-23), to components of the `kubernetes`
generator 1.7.0 or later. Variables in the file resolve to their defaults,
as `docker compose config` resolves them without an `.env` file, and
`extends` within the same file is resolved first. The main service becomes
the component `<name>`, every other service `<name>-<service>`, so RCP-3
holds. Every reference to a service name or `container_name` in
environment values, commands and configs is rewritten to the new name,
and the README lists the renames.

| Compose | Recipe | Decision |
|---|---|---|
| `services.<service>` | a component: a Deployment, or a StatefulSet if it mounts a named volume | |
| `image` | `image` as `tag@sha256:<digest>` | `latest` or a missing tag is pinned to the most specific version tag with the same digest at migration, which the README names. |
| `entrypoint`, `command` | `command`, `args` | Compose overrides ENTRYPOINT and CMD the same way. A string is split as `docker compose` splits it. `args` is a mapping (RCP-43). |
| `environment`, `env_file` | `env` | A credential, or a value that contains one such as a database URL, becomes a key of the component's `secrets`, referenced with `secretKeyRef`. Its value is a parameter under `applications.<name>` that the recipe leaves unset, so the compile fails until the target sets it (RCP-19). |
| `ports` | a port with `container_port` and `service_port`, `service.type: ClusterIP` | The published port becomes the Service port. A host IP is dropped, and exposing the Service outside the cluster is left to the target. |
| `expose`, and ports other services connect to | a port with `service_port` | Services on a compose network reach every port, so a port the others use is declared even without `expose`. |
| `healthcheck` | `healthcheck.readiness` of `type: command`, `CMD` as the command list, `CMD-SHELL` as `sh -c` | `interval`, `timeout` and `retries` become period, timeout and failure threshold. The compose defaults 30s, 30s and 3 are written where the generator's differ. Compose never restarts an unhealthy container, so there is no liveness probe. `start_period` and `start_interval` only delay failures and are dropped. `disable: true` renders no probe. |
| `depends_on` | nothing | The dependency's readiness probe keeps its Service without endpoints until it is ready, and the dependent restarts until it connects. An init container that waits was rejected, because it adds an image the compose file does not have. |
| `deploy.replicas` | `replicas` | |
| `deploy.resources` | `resources`: `limits` from `limits`, `requests` from `reservations` | `cpus` is in CPU units. Compose memory units are binary, so `512M` is `512Mi`. |
| named `volumes` of one service | `volume_claims` with `volume_mounts` | Compose sizes nothing. The claim is `ReadWriteOnce` with `1Gi`, which the README offers as a setting. |
| `configs`, `secrets` | `config_maps`, `secrets` with `mount` at the compose target | The default targets are `/<config>` and `/run/secrets/<secret>`. A config's content is written inline, with its source file and SHA-256 in the README. A secret's value is a parameter the target sets. |
| bind mount of a file in the pinned repository | as `configs`, read-only | It is the same file a config would name. |
| `restart` | nothing | Every policy becomes `restartPolicy: Always`. A service that exits by design becomes a Job, which the user confirms. |
| `user` | `security_context.runAsUser` and `runAsGroup` | The API takes numbers only, so a user name is resolved from the image's `/etc/passwd`. |
| `labels` | `pod_annotations` | Values such as Traefik rules are not valid Kubernetes label values. |
| `container_name`, `networks` that every service shares | nothing | Pods are named by their workload, and one namespace already reaches every Service. |

What the table does not map is a gap, and so is each of these:

| Compose | Why it stops |
|---|---|
| `build` without a published `image` | There is no image to pin |
| `network_mode` | `host` puts the pod on the node's network, `service:` and `container:` share a network namespace, which only containers of one pod can |
| bind mounts of directories or of paths outside the repository, the Docker socket among them | They carry host state that a recipe cannot, and a hostPath reaches the node (RCP-20) |
| `privileged`, `cap_add`, `devices`, `pid: host`, `ipc: host` | They widen what a container may do on the node and need a review a migration cannot replace |
| `networks` that separate services, `aliases`, fixed addresses, external networks | Services in one namespace reproduce only the DNS names. Nothing would prove the isolation. |
| `extends` or `include` of a file outside the pinned repository | The content is not pinned |
| a named volume of several services | `ReadWriteOnce` cannot be shared across nodes, and kind has no `ReadWriteMany` storage to prove it on |
| `working_dir` | The `kubernetes` generator 1.7.0 has no key for `workingDir`. It is a generator request. |

- RCP-37: A compose recipe MUST map every key of its compose file as the
  table above says. A key the table does not map, or one of the gaps,
  MUST stop the migration with a report, and no recipe is written.

  A gap is reported to kadet-hub/registry like a missing generator
  (RCP-7). A mapping is added to the table only with the migration that
  needs it.

  - Test: manual: review against the compose file
  - Since: #8

- RCP-38: A compose recipe MUST be at level `deploys`. `check lint` MUST
  fail on an RBAC object in the compiled recipe, on a workload whose
  selector does not select its own pods, and on a Service,
  PodDisruptionBudget or NetworkPolicy whose selector selects no pods.
  `check` MUST then apply the recipe for real on one fresh kind cluster,
  wait for the rollout of every workload and run `tests/smoke`, as RCP-26
  describes.

  These are the parts of `renders` that need no reference. A compose file
  grants no Kubernetes API access, so a Role or binding in its recipe
  would grant something the source never had. The `next` compile
  (RCP-24) runs unchanged.

  - Test: `check lint`; `check/tests/test_lint.py`; CI `check` job
  - Since: #8

- RCP-39: The `tests/smoke` of a compose recipe MUST check what the compose
  file sets up: every published port answers through its Service, every
  service with a `healthcheck` is ready, and one functional request needs
  the services together, such as a write through the application that
  its database stores.

  - Test: manual: review; CI `check` job
  - Since: #8

## Designed recipes

A designed recipe deploys the project's image with the `kubernetes`
generator 1.7.0 or later, configured as the image's documentation
describes: the environment variables its entrypoint reads, the ports it
opens, the user it runs as and the paths it writes. The image of the
`Source` line is the one the recipe runs (RCP-23). Credentials are
parameters under `applications.<name>` that the recipe leaves unset
(RCP-19), as for a compose source. What a chart would offer as values,
such as the volume size, the README lists under Settings. Once the project
ships a chart, a Kustomize base or a compose file, the recipe moves to that
source (DEC-10).

mysql was the first. Oracle publishes the charts `mysql-operator` and
`mysql-innodbcluster`, UPL-1.0, in the HTTP repository
`https://mysql.github.io/mysql-operator/`. They install the MySQL Operator
and an InnoDB Cluster it manages, and on 2026-10-25 the repository's index
listed only version 2.3.1 of each, for MySQL 26.10.0, an Innovation
release. The recipe runs `container-registry.oracle.com/mysql/community-server`,
which the MySQL team builds, on the 9.7 LTS line that the kadet-hub/examples
recipe followed. Oracle builds that image for linux/amd64 only. The arm64
build has its own tag, `<version>-aarch64`, so the digest the recipe pins
is that of the amd64 image. The examples recipe's check, `select 1` as the
user `app` in its database, is the recipe's `tests/smoke`.

mongodb was the second. The charts of mongodb/helm-charts, Apache-2.0,
install MongoDB's operators or resources those operators manage. One of
them, `enterprise-database`, renders a `MongoDB` resource for the
Enterprise Operator and needs Ops Manager or Cloud Manager. The chart of
MongoDB Controllers for Kubernetes, `mongodb-kubernetes`, is also published
at `oci://quay.io/mongodb/helm-charts/mongodb-kubernetes`. None of them
deploys a server on its own, and a recipe on the operator would need an
operator recipe and a generator for its resources (RCP-7). The recipe runs
`docker.io/mongodb/mongodb-community-server`, which MongoDB builds, on the
9.0 major release that the kadet-hub/examples recipe followed. The Docker
Official Image `mongo` is built by docker-library.

MongoDB rebuilds a release under the same tag: Docker Hub listed 14 builds
of `9.0.4-ubi9-slim` between 2026-10-14 and 2026-10-25, each also tagged
with its build time, such as `9.0.4-ubi9-slim-20261020T065348Z`. The
recipe pins the digest of that build, the one the examples recipe ran. The
examples recipe's check, `ping` after mongosh authenticates as `root`, is
the recipe's `tests/smoke`.

- RCP-44: A designed recipe MUST be at level `deploys`. `check lint` and
  `check` MUST check it as RCP-38 describes for a compose recipe: no RBAC
  object, every selector selecting pods, then a deploy on one fresh kind
  cluster and `tests/smoke`.

  An image grants no Kubernetes API access, so a Role or binding in its
  recipe would grant something no upstream artifact asks for, and nothing
  would compare it. The `next` compile (RCP-24) runs unchanged.

  - Test: `check lint`; `check/tests/test_lint.py`; CI `check` job
  - Since: #14

- RCP-45: The `tests/smoke` of a designed recipe MUST reach every Service
  port through its Service and make one request that needs what the recipe
  sets up, such as a query as the user the recipe creates in its database.

  - Test: manual: review; CI `check` job
  - Since: #14

## Recipes from kadet-hub/examples

kadet-hub/examples carried recipes as single classes, written in kadet-hub
in place of Bitnami charts (EX-5 there). Each one moves here with its
project's chart as source (DEC-10), and the examples repository then points
to the recipe here. valkey was the first: valkey-io publishes the chart
`valkey` in valkey-io/valkey-helm, BSD-3-Clause, at
`oci://ghcr.io/valkey-io/valkey-helm/valkey`, whose standalone mode renders
a Deployment, a PersistentVolumeClaim and ACL authentication where the
examples recipe had a StatefulSet and `--requirepass`. mysql and mongodb
moved as designed recipes (Designed recipes).

- RCP-41: The README of a recipe that replaces one of kadet-hub/examples
  MUST have a section `Replaces` that names that recipe and lists the
  objects, names and settings that change for a target moving from it.

  A target that included the examples recipe compiles different objects
  from the new one, such as another Secret key, so the move is a change
  its owner makes on purpose.

  - Test: manual: review
  - Since: #10

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

- RCP-15: Consumers MUST fetch recipes with a separate fetch inventory,
  pinned by digest once the recipe is published and by commit SHA before,
  and verify them as the consumers guide describes, until Kapitan fetches
  such classes itself (OQ-2).

  Until a recipe's first release (Releasing), the fetch inventory pins this
  repository by commit SHA as a `git` dependency, and the consumer verifies
  the generators the recipe pins. The steps are in the README's
  "Using a recipe".

  Once it is published, the fetch inventory pins
  `ghcr.io/kadet-hub/recipes/<name>` by digest instead. The registry's
  consumer workflow handles that when its policy names the fetch inventory
  (CON-4 there). It verifies the recipe against the `recipes` section of
  the index (CON-5), and then the generators the recipe pins as
  dependencies of the main inventory, like any generator.

  - Test: manual: the README's "Using a recipe" steps on a fresh clone;
    the digest path: the registry's `consumer-selftest` (not written)
  - Since: #5 (commit SHA); not implemented (digest)

- RCP-16: Renovate MUST open a pull request when the chart a recipe is
  derived from has a new release. The pull request runs `check` at
  `renders`, so the diff of the new chart against the recipe is visible.

  Renovate moves the README's `Source` line to the new version and its
  digest. The recipe's images, vendored files and values stay at the old
  version, so `check` fails and its report is the diff a maintainer
  works from. The images take their tag from
  `applications.<name>.version`, which Renovate cannot read, so it does
  not update them on its own.

  For a designed recipe Renovate moves the image of the `Source` line in
  the same way, and `check lint` fails until the recipe runs the new image
  (RCP-23). A package rule keeps the image on the release line the README
  names. For mysql that is MySQL's 9.7 LTS line: from 26.7 on, Oracle
  numbers the Innovation releases by calendar, so the rule allows versions
  below 10. For mongodb it is MongoDB's 9.0 major release. MongoDB supports
  a major release for five years and stops patching a minor release once
  the next one is out, so the rule allows versions below 9.1.

  Renovate gets no release timestamp for the mongodb image. Docker Hub
  refuses anonymous requests for tag list pages after the tenth, and the
  image has more than 1000 tags. With `minimumReleaseAgeBehaviour:
  timestamp-required`, every update of it stays pending (OQ-15).

  Compose sources are not covered yet (OQ-10).

  - Test: manual: Renovate dry run
  - Since: #3; designed recipes: #14; mongodb: this change

### Releasing

A recipe version is released by a tag in this repository and registered in
kadet-hub/registry as `recipes/<name>.yaml`, which pins the tag and its
commit. The first version is a maintainer pull request there; Renovate
proposes every later tag with the same prefix (REG-7). The registry gate
then checks the recipe itself, with a pinned `check` release, its own
sandbox and level `renders` (REC-4 to REC-10), and the release workflow
publishes the class directory without `tests/` (REC-11). What the gate
checks, formerly OQ-3, is decided there. Owners per recipe, formerly OQ-4,
are the `owners` of the registry entry, set by the maintainer (REC-3).

- RCP-31: A recipe version MUST be a tag `<name>-vX.Y.Z` on a commit of
  `main` where CI ran `check` at the README's level for that recipe and
  passed. Only the admin role MAY create such tags, and no one MAY move or
  delete them.

  The version is the recipe's own SemVer. The major version rises when a
  target that included the previous version needs a change to compile the
  same application, for example a renamed key or a removed option. A new
  chart version is a minor version unless it also does that. A `tags`
  ruleset enforces who creates tags. The registry's SEC-16 opens an issue
  when a registered tag moves.

  - Test: manual: `gh api repos/kadet-hub/recipes/rulesets`
  - Since: not implemented

- RCP-32: The first paragraph of a recipe's README, after the heading, MUST
  describe the recipe in at most 300 characters, without control or
  bidirectional formatting characters.

  The registry's index takes it as the recipe's description (REC-13), and
  the catalog shows it in lists and in `/llms.txt`. cert-manager's first
  paragraph currently runs into the `Source` line with a colon and needs
  splitting.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: not implemented

- RCP-33: A recipe's class files MUST be the files RCP-36 lints. No file of
  the recipe MAY end in `.py`.

  The omegaconf backend loads `vendor/x.yml` as `.vendor.x` for any class
  that includes it, so a nested YAML file is a class file unless it is
  vendored data that nothing includes. The registry gate checks the same
  (REC-4). Revised in #7: the first version banned every `.yml` file
  below the root, which RCP-36 replaces by linting those files.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #6, #7

- RCP-34: `check <name> --level renders` MUST accept the compiled output of
  the recipe and the rendered chart as input, and then run neither Kapitan
  nor helm.

  The registry gate compiles and renders in its gVisor sandbox and gives
  `check` only the two outputs (DEC-21 there), so a chart that attacks
  `helm template` (OQ-7) or a generator stays inside the sandbox. In this
  repository's CI `check` keeps compiling and rendering itself.

  - Test: `check/tests/` (not written); the registry's `gate-selftest`
  - Since: not implemented

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
merge, conversion and boolean resolvers. Kapitan's `escape` returns its
argument as a literal `${...}` and reads nothing.

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

- RCP-36: `check lint` MUST apply its class file rules, RCP-17 to RCP-19
  among them, to every file of a recipe that can act as a class: each
  `*.yml` and `*.yaml` below the recipe directory, except `tests/` and the
  files a `copy` entry of the recipe names as input. Every `classes` entry
  of a linted file MUST resolve to a linted file.

  The omegaconf backend loads any YAML file below the classes path that a
  class names, such as `vendor/x.yml` through `.vendor.x`, so a check of
  the root's `*.yml` files alone leaves nested files unchecked. `tests/`
  holds the proof's chart values and target. A `copy` input is vendored
  data, which `check lint` checks for its license (RCP-35) but not as a
  class. Neither is linted as a class, so a recipe must not include them. `check lint` resolves an entry as Kapitan
  0.36.3's omegaconf backend does: a relative entry against the including
  file's directory, an absolute `recipes.<name>.` entry against the
  repository root, `init` before the file of the same name and `.yml`
  before `.yaml`. An entry fails when the backend could try a path
  outside the repository before the linted file, because that path may
  exist in a consumer's inventory. Root files are always linted, even if
  a `copy` entry names them.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #7

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

- RCP-44: Every pull request MUST request a review from `neat-bot`. That
  review MUST NOT be a condition for merging.

  `.github/CODEOWNERS` names `@neat-bot` for every path. GitHub requests a
  code owner only when it has write access, and never the author of the
  pull request. With write access, an approval by `neat-bot` also counts
  toward the one approval the `main` ruleset requires. The ruleset leaves
  code owner review off, so a missing review from `neat-bot` does not
  block a merge.

  - Test: manual: `gh pr view <n> --json reviewRequests` on a new pull
    request; `gh api repos/kadet-hub/recipes/codeowners/errors` lists no
    errors; the `main` ruleset in `gh api repos/kadet-hub/recipes/rulesets`
    has `require_code_owner_review: false`
  - Since: #13

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
  injected extra object then shows up as a difference outside RCP-12. The
  registry gate pins a `check` release in the same way (REC-5, REC-9).

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
- AC-9 (RCP-33, RCP-36): `check lint` fails on a nested `vendor/x.yml`
  with an `external` entry and on one with `oc.env`, both included as
  `.vendor.x`, on an include of `tests/target.yml` and on a `.py` file,
  and passes on cert-manager.
- AC-6 (RCP-20, RCP-21): actionlint passes. A fixture pair of an old and a
  new recipe with an added image, an added ClusterRole verb and an added
  hostPath volume makes `check` list all three.
- AC-4 (RCP-15): a fresh clone of a consumer project fetches cert-manager
  by commit SHA and compiles it with the two commands above, and once
  cert-manager is published, by digest through the registry's consumer
  workflow.
- AC-8 (RCP-31, RCP-32, RCP-34, RCP-35, RCP-40): `check lint` fails on a
  README whose first paragraph exceeds 300 characters, on one without the
  section "Required parameters" and on a vendored file without `.LICENSE`;
  `check cert-manager --level renders` with a compiled output and a chart
  render given reports the same result as without them; a tag pushed by a
  non-admin is rejected.
- AC-10 (RCP-1, RCP-23, RCP-37 to RCP-39): `check lint` fails on a compose
  recipe at level `renders`, on a compose `Source` line without a full
  commit SHA, and on a fixture with a RoleBinding or a Service whose
  selector matches no pods; miniflux passes `check miniflux --level
  deploys` in CI.
- AC-11 (RCP-41, RCP-42): valkey passes `check valkey --level deploys` in
  CI, its README names the kadet-hub/examples recipe it replaces, and
  `valkey.yml` names the chart file of its init script and has
  `valkey.yml.LICENSE`.
- AC-13 (RCP-23, RCP-44, RCP-45): `check lint` fails on a designed recipe
  at level `renders` and on one whose `Source` image no container runs,
  and passes on mysql and mongodb; both pass `check <name> --level
  deploys` in CI.
- AC-12 (RCP-43): `check lint` warns on an `args` list of a component
  and of an `init_containers` entry and still passes, does not warn when
  the recipe pins the generator below 1.7.0, and passes without a warning
  on cert-manager and valkey.
- AC-7 (RCP-16, RCP-29, RCP-30): a local Renovate dry run on this
  repository extracts the chart of every chart recipe, the image of every
  designed recipe, the `next` pin, the kind node image, the generator
  pins, every tool and action pin and the `check` lock, and finds no
  update set to merge automatically. With mysql one patch release back, it
  proposes the next 9.7 release and no 26.x.

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
- OQ-10: Should Renovate propose the newest commit of a compose source's
  repository, so the SHA-256 check of RCP-23 shows when the file changed?
  RCP-16 covers charts only.
- OQ-15: How should Renovate follow the mongodb image, whose updates stay
  pending without a release timestamp (RCP-16)? With
  `timestamp-optional` for the image, as for registries without
  timestamps, or with no release age and a schedule window as in RCP-29,
  Renovate proposes each new build at once, a new digest almost every day.
  Docker Hub credentials for Renovate would give timestamps, but the
  newest patch tag is pushed again with each build, so it would reach the
  three days only once MongoDB stops rebuilding it. Until this is decided,
  a maintainer moves the pin.

## Implementation inventory

| Path | Purpose |
|---|---|
| `README.md` | Using a recipe (RCP-15) |
| `<name>/` | One recipe (RCP-1) |
| `check/check.py` | CLI, sources, kind clusters, report; pins the kind node and Kapitan `next` images |
| `check/lint.py` | `check lint` (RCP-1 to RCP-7, RCP-17 to RCP-19, RCP-23, RCP-33, RCP-35, RCP-36, RCP-38, RCP-40, RCP-43, RCP-44) |
| `check/compare.py` | Normalization, pairing, classes, selectors, can-i (RCP-9 to RCP-12) |
| `check/tests/` | AC-1, AC-2, AC-5, AC-9, AC-10, AC-13 without a cluster |
| `check/pyproject.toml`, `check/uv.lock` | Kapitan 0.36.3, omegaconf 2.4.0.dev4, PyYAML |
| `.github/workflows/ci.yml` | RCP-13, RCP-20, RCP-28 |
| `.github/CODEOWNERS` | `@neat-bot` for every path (RCP-44) |
| `.github/ruleset-tags.json` | RCP-31, applied with `gh api` |
| `.github/actions/tools/` | Pinned helm, kubectl, kind, oras, gh |
| `renovate.json` | RCP-16, RCP-29, RCP-30 |

| Value | Setting |
|---|---|
| Repository | `kadet-hub/recipes`, public, Apache-2.0 |
| Artifact | `ghcr.io/kadet-hub/recipes/<name>` |
| Tag | `<name>-vX.Y.Z`, created by the admin role only |
| Registry entry | kadet-hub/registry `recipes/<name>.yaml` |
| Inventory backend | omegaconf, Kapitan 0.36.3 |
| First recipe | cert-manager, chart v1.21.2, level `deploys`, target `migrates` |
| First recipe from kadet-hub/examples | valkey, chart `valkey` 0.12.0 of valkey-io/valkey-helm, level `deploys` |
| First compose recipe | miniflux, `contrib/docker-compose/basic.yml` of miniflux 2.3.4, level `deploys` |
| First designed recipe | mysql, `container-registry.oracle.com/mysql/community-server` 9.7.4, level `deploys` |
| Environment | `fork-pull-request`, required reviewer: a maintainer |
| Consumer path | `inventory/classes/recipes/<name>/` |
