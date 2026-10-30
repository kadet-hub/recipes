# Recipes

```text
Status: Draft. check 0.13.1 implements renders and deploys, for charts
        from OCI and HTTP repositories, for release manifests (RCP-59) and
        for compose sources and designed recipes (RCP-38, RCP-44, RCP-58),
        included recipes and prerequisites (RCP-47 to RCP-50, RCP-54,
        RCP-55), and renders from given outputs (RCP-34);
        migrates (RCP-14) and RCP-21 are not implemented;
        RCP-15 only up to publication.
Code: <name>/, check/, .github/, renovate.json, README.md
Verified against: #3, cert-manager at deploys; #10, valkey at deploys;
                  #14, mysql at deploys; #17, mongodb at deploys;
                  #19, powerdns at deploys; #29, strimzi at deploys;
                  #26, keycloak-operator at deploys;
                  #33, external-dns-powerdns at deploys;
                  #34, kafka at deploys; #35, postgresql at deploys;
                  #36, rabbitmq-cluster-operator and rabbitmq at deploys;
                  #38 and #42, keycloak at deploys;
                  #39, nextcloud and valkey at deploys
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

Some operators ship as one YAML file attached to a GitHub release, which
`kubectl apply` installs. The RabbitMQ Cluster Operator is one.

A recipe is that rebuilt application, maintained and proven in one place,
so that users include a recipe the way they would install a chart. This
repository holds the recipes, the one comparison script that proves them,
and the CI that runs it.

Some applications need other applications next to them. Nextcloud needs a
database and a cache in its namespace, which its chart brings as subcharts,
and the database needs an operator that runs once per cluster.

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

DEC-4: A chart's subchart becomes a recipe of its own, and the parent recipe
includes it through `classes:` (Included recipes). A subchart that several
charts share is then written once. Where the parent's chart can use an
external service in place of its subchart, as Nextcloud's chart uses an
external PostgreSQL, the parent includes the recipe for that service.
Revised in this change: the first version let the parent override the
included recipe's values, which RCP-18 rules out (DEC-12).

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
(RCP-23): `oci://` is a chart, a GitHub file URL a compose file, a GitHub
release download URL a release manifest, another `https://` URL that ends
in `<chart>:<version>` a chart from an HTTP repository, and an image
reference without a scheme the image of a designed recipe. A separate
`Source-Type:` line was considered. It would repeat what the line already
says, and the two could contradict each other. Revised in #23: the HTTP
repository was added.

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

DEC-12: The parent leaves an included recipe as it is. It writes nothing
below the included recipe's keys, which RCP-18 already enforces, and
depends only on names the included recipe renders, such as its Service and
the Secret with its credentials. What the included recipe requires, the
target sets, and the parent's README names it. A parent and its included
recipes come from one commit of this repository, so the commit fixes the
combination `check` proved, and the registry resolves it to published
versions (DEC-28 there). An included recipe includes no recipe itself,
which keeps the fetch inventory and the registry record flat. No recipe
needs a deeper chain yet.

Letting the parent override the included recipe's values was considered.
RCP-18 would then have to let one recipe write into another's keys, and the
included recipe's own proof would no longer cover what the parent compiles.
Copying the included recipe into the parent's directory was considered too.
A target that also included it through another recipe would get the same
keys twice. A range of versions per included recipe would let a fix in the
included recipe reach users without a parent release, but it would publish
combinations that no CI run compiled together.

DEC-13: What a recipe needs once per cluster, such as an operator with its
CRDs or a Gateway API implementation, is a prerequisite and not an included
recipe. The README names it on a `Requires:` line, the user installs it in
a target of its own, and `check` installs it on the kind cluster before the
proof (Included recipes). An operator included like a database would be
rendered by every target that uses it, and two operators would reconcile
the same objects.

DEC-14: A project that runs its application through its own operator, and
ships a chart for the operator but none for the application, gets two
recipes (Keycloak). The operator is a chart recipe and a prerequisite
(DEC-13). The application is a designed recipe that renders the operator's
custom resource with the project's image as its source (DEC-11, RCP-58).
Deploying the image with the `kubernetes` generator was considered. It
would replace the operator, whose upgrade and configuration logic the
project maintains, with a workload that nobody upstream maintains, and the
project's deployment guides for Kubernetes use the operator.
mongodb did not take this path because no kadet-hub generator renders
MongoDB's resources (Designed recipes).

DEC-15: A manifest that a project attaches to a GitHub release is a source
like a chart, pinned by the release's tag and the file's SHA-256 (Release
manifests). The file holds the objects as the project installs them, so
`renders` compares the recipe with them as with a rendered chart, and helm
does not run. The project's Kustomize base was considered as the source.
kustomize would be one more tool in `check` and in the registry gate, and
the RabbitMQ Cluster Operator's base does not name the operator image,
which its release build sets. A Kapitan `https` dependency that brings the
file into the target is ruled out by RCP-17, and it fetches without a
checksum. An application on such an operator follows DEC-14, as `rabbitmq`
does on the RabbitMQ Cluster Operator.

DEC-16: A recipe that rebuilds what a copyleft chart renders, without
copying its text, is not a derivative of the chart and is published under
this repository's Apache-2.0 (Nextcloud). The recipe takes from the chart
what the image and the Kubernetes API dictate: field names, ports, paths,
probe values. It carries no template, file or values text of the chart,
and neither the recipe nor the registry ships the chart; `check` fetches
it in CI only to compare. AGPL-3.0 section 13 concerns a modified program
run as a network service, and the chart is neither run nor modified. This
is the maintainer's reading, not legal advice. The remaining risk is that
the selection and arrangement of those values counts as expression; it is
accepted. Text that is copied falls under RCP-42.

DEC-17: `keycloak` renders a route to a Gateway the target names,
formerly OQ-16, only as its option `route`. The Gateway terminates TLS and
forwards plain HTTP to Keycloak's port 8080 (Keycloak). Keycloak's reverse
proxy guide calls this edge termination generally less secure than
re-encrypt (`docs/guides/server/reverseproxy.adoc` of keycloak/keycloak
26.8.1). Re-encrypt needs a BackendTLSPolicy towards port 8443, and
passthrough a TLSRoute on a `TLS` listener. cloud-provider-kind 0.12.0,
which provides `gateway-api` to `check`, installs both CRDs and implements
neither. It watches no BackendTLSPolicy or TLSRoute
(`pkg/gateway/controller.go`), builds every backend without TLS
(`translateBackendRefToCluster` in `pkg/gateway/gateway.go`) and accepts
only HTTP and HTTPS listeners, so `check` could not prove a route in either
mode. A target that needs TLS up to Keycloak leaves the option out and
exposes `<name>-service` on port 8443 itself.

DEC-18: `nextcloud` renders no backup, formerly OQ-11. Its README says in
a section "Backups" what a target backs up and how (RCP-64). Every part of
a backup needs something the cluster provides. The database needs an object
store with credentials and the Barman Cloud Plugin, which no recipe
installs. The claims need a CSI driver with a VolumeSnapshotClass or a
file-level tool such as Velero. `check` has none of these, so a backup the
recipe rendered could not be proven at `deploys`. Rendering the database
backup as an option of `postgresql` was considered. It would add the plugin
as a prerequisite (DEC-13) and the object store as Required parameters
(RCP-40) for a part that no check exercises.

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
  name or, from a chart or a release manifest, a name the source uses.

  `check lint` compiles `tests/target.yml` and renders the chart with
  `tests/values.yaml`, or reads the release manifest, to compare the names.
  A compose file or an image names no Kubernetes objects, so there every
  name starts with the recipe's.

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
  - Since: #12

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

- RCP-66: A class file MUST write each image reference as one literal
  `<registry>/<repository>:<tag>@sha256:<digest>`, or `<repository>:<tag>`
  where the source pins no digest. Its tag MUST NOT come from an
  interpolation such as `${applications.<name>.version}`.

  Until this change the recipes kept the tag in
  `applications.<name>.version` and the digest in the image line. A reader
  found the version in `init.yml` and the digest in another file, and
  Renovate could read neither. A target that raised the version without
  the digest got the new tag in its manifests, while the kubelet pulled
  the old image by digest.

  `check lint` fails on a string of a class file that holds `@sha256:` and
  `${`. A reference without a digest, such as Strimzi's
  `STRIMZI_DEFAULT_BUILDAH_IMAGE`, is not recognized as one, so the rule
  covers it only by review.

  - Test: `check lint`; `check/tests/test_lint.py` (`Lint.test_image_tag_from_interpolation`) (partial: references without a digest)
  - Since: #50

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
  `check lint` cannot tell copied text from written text. For a chart
  under a copyleft license the review compares the recipe's lines with the
  chart's templates, `files/` and `values.yaml` verbatim, as for nextcloud
  (DEC-16).

  - Test: manual: review; CI `check` job
  - Since: #10

## Proof

`check <name>` renders the source chart pinned by version and digest with
`tests/values.yaml`, compiles the recipe with the same values, and compares
the two. Helm hooks that only run inside `helm install` and test pods are
listed in the recipe's README and left out of the comparison.

`check` applies every object server-side. A client-side apply stores the
object as an annotation, and the API rejects that for CRDs above 256 KiB,
such as CloudNativePG's `clusters` and `poolers`. Null fields are dropped
before an apply, on both sides alike. A null leaves a field unset in a
manifest, and a server-side apply rejects it where the schema has no
`nullable`, as CloudNativePG's `cluster` chart renders
`bootstrap.initdb: null`.

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
  `<version>`. For a chart from an HTTP repository it is
  ``Source: `https://<repository>/<chart>:<version>@sha256:<digest>` ``,
  where `https://<repository>` is the URL `helm repo add` takes and
  `<digest>` the SHA-256 of the chart's archive. `check` reads the
  repository's `index.yaml`, downloads the archive its entry for `<chart>`
  and `<version>` names, and fails unless the archive's SHA-256 is
  `<digest>` and its `Chart.yaml` names `<chart>` and `<version>`. For a
  compose file it is
  ``Source: `https://github.com/<owner>/<repo>/blob/<commit>/<path>@sha256:<digest>` ``
  with the full commit SHA, and `check` fetches the file at that commit
  and fails unless its SHA-256 is `<digest>`. For a release manifest it is
  ``Source: `https://github.com/<owner>/<repo>/releases/download/<tag>/<file>@sha256:<digest>` ``,
  and `check` downloads the release asset and fails unless its SHA-256 is
  `<digest>`. For a designed recipe it is
  ``Source: `<registry>/<repository>:<tag>@sha256:<digest>` ``, the
  project's image with its registry host, and `check lint` fails unless a
  container of the compiled recipe runs exactly that image. The release
  name is the recipe's name, and the namespace is `parameters.namespace`
  of `tests/target.yml`.

  `tests/target.yml` is the recipe's side of `tests/values.yaml`: it
  includes the recipe and the options those values switch on. Compose
  files outside GitHub are not supported yet.

  An HTTP repository has no digest that a client checks. Its `index.yaml`
  maps a version to an archive URL, and the repository's owner can change
  both. helm 4.3.1 keys its download cache by the entry's `digest` but
  does not compare it with the archive (`pkg/downloader/chart_downloader.go`).
  It checks only a provenance file, with `--verify`, and external-dns
  publishes none. Kapitan 0.36.3's `helm` dependency takes `source`,
  `chart_name` and `version`, runs `helm pull --untar --repo`, keeps no
  archive and checks no digest (`dependency_manager/base.py`). `check`
  therefore downloads the archive itself and compares its SHA-256, which
  is also the `digest` that helm writes into the index entry. A recipe has
  no `helm` dependency (RCP-17), so neither a consumer's fetch inventory
  nor its compile fetches the chart. Only `check` and the registry gate
  (REC-7 there) do.

  - Test: `check lint`; `check/tests/test_lint.py`; release manifest
    download and HTTP repository: `check/tests/test_check.py`
  - Since: #2, #8, #14; release manifest: #22, #25; HTTP repository: #23

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

For a compose source and a designed recipe, `renders`, also as part of
`deploys`, proves the recipe side only (RCP-38, RCP-44), and there is no
`migrates` level.

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
  `app.kubernetes.io/part-of`, `chart`, `release`, `heritage`, `component`),
  and image digests on the recipe side. Secrets the chart generates are
  compared by key.

  Keeping the identifying labels would force a recipe to copy the chart's
  label scheme. What selects on them is checked by RCP-10 instead. Every
  other label and annotation stays, because ingress controllers, meshes
  and monitoring read them.

  Strimzi's chart puts `chart`, `release` and `heritage` on every object,
  set from the chart's name and version, the release name and `Helm`, as
  charts scaffolded by older versions of `helm create` do. Its
  `component` label names the template, such as `deployment` or
  `service-account`, like `app.kubernetes.io/component`. The `kubernetes`
  generator renders only the `name` label on ServiceAccounts and
  ConfigMaps, so a recipe cannot carry these labels, and `heritage: Helm`
  would name a manager that does not manage the object.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2; `chart`, `release`, `heritage`, `component`: #29

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

  A RoleBinding without a namespace binds in the target namespace, where
  RCP-8 applies it. `helm template` leaves the namespace of an object out
  when the chart's template does, as the Keycloak Operator's chart does for
  its RoleBinding to `view`.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2; RoleBinding without a namespace: this change

- RCP-12: After normalization the object diff MUST be empty, except for
  differences of the classes below. `check` reports each remaining
  difference with its class.

  | Class | Example | Why it is accepted |
  |---|---|---|
  | Selector scheme | the generator selects on `name`, the chart on `app.kubernetes.io/*` | RCP-10 proves the same selection |
  | Explicit default | pod `automountServiceAccountToken: true` where the chart leaves it unset, a container's empty `securityContext`, a Certificate's `privateKey.rotationPolicy: Always` | same value as the ServiceAccount's, every field unset as on the other side, or cert-manager's default since 1.18 |
  | Port by name | `targetPort: http-metrics` against `9402` | resolves to the same container port |
  | Derived name | container named after the component, webhook configuration `<ns>-<component>`, sorted container ports | names the generator derives, no change in behaviour |

  The two cert-manager runs ended with exactly these differences. A class
  is added here only with the run that needs it.

  `check` accepts a difference only where its class holds: a selector
  difference where RCP-10 found the same selection, `true` where the other
  side is unset and the pod's ServiceAccount does not disable the token,
  `{}` as a container's `securityContext` where the other side has none,
  `Always` as a cert-manager Certificate's `privateKey.rotationPolicy`
  where the other side leaves it unset, a port name that resolves to the other side's number in the selected pods
  or the same pod, a first container named after its workload, container
  ports that are the same set sorted by name, and a webhook configuration
  named `<namespace>-...` with the same webhooks.

  The `kubernetes` generator renders `securityContext: {}` on a container
  that sets no `security_context`. The Keycloak Operator's chart sets none.

  The `certmanager` generator 1.0.2 renders `privateKey.rotationPolicy:
  Always` on every Certificate, and the RabbitMQ Cluster Operator's
  manifest sets no `privateKey`. cert-manager 1.18 made `Always` the
  default behind the feature gate `DefaultPrivateKeyRotationPolicyAlways`,
  which is on by default, and its release notes announce the gate as GA
  for 1.19. A recipe whose report shows this difference therefore requires
  cert-manager 1.18 or later with that gate on, and its README says so.

  - Test: `check/tests/test_compare.py`; CI `check` job
  - Since: #2; empty `securityContext`: #24; `rotationPolicy`: #30

- RCP-13: A recipe's README MUST state its proof level, and CI MUST run
  `check` at that level for every recipe a pull request changes and for
  every recipe once a week. A change below `check/` or `.github/` changes
  every recipe.

  - Test: CI `select` job
  - Since: #2

- RCP-65: A pull request MUST NOT merge unless the CI job `ci` passed. `ci`
  needs every other job of the run and fails when one of them failed or
  was cancelled. A skipped job passes, since a pull request that changes no
  recipe skips `lint` and `check`.

  The `lint` and `check` jobs are a matrix whose names carry the recipe, so
  no fixed job name could be a required check without `ci`. The `main`
  ruleset requires `ci`, so an approved pull request with a failed proof
  stays blocked.

  - Test: CI `ci` job; manual: `gh api repos/kadet-hub/recipes/rulesets`
  - Since: #47

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
  `check` MUST then apply the recipe on one fresh kind cluster as RCP-26
  describes for the level it runs at. At `deploys` that is for real, with
  the rollout of every workload and `tests/smoke`. At `renders` it
  compares nothing, as there is no reference.

  These are the parts of `renders` that need no reference. A compose file
  grants no Kubernetes API access, so a Role or binding in its recipe
  would grant something the source never had. The `next` compile
  (RCP-24) runs unchanged.

  `check --level renders` is for the registry gate, which proves every
  recipe at `renders` (REC-9 there). The README's level and the level CI
  runs (RCP-13) stay `deploys`.

  - Test: `check lint`; `check/tests/test_lint.py`; CI `check` job;
    `renders`: `check/tests/test_check.py`
  - Since: #8; `renders`: #45

- RCP-39: The `tests/smoke` of a compose recipe MUST check what the compose
  file sets up: every published port answers through its Service, every
  service with a `healthcheck` is ready, and one functional request needs
  the services together, such as a write through the application that
  its database stores.

  - Test: manual: review; CI `check` job
  - Since: #8

## Release manifests

A release manifest is a file of Kubernetes objects attached to a GitHub
release, the file a project's install guide applies with
`kubectl apply -f <url>`. The recipe rebuilds those objects with kadet-hub
generators, and its `Source` line pins the file by the release's tag and
SHA-256 (RCP-23). At `renders` the file's objects take the place of the
rendered chart. The file has no values and no release name, and its
objects name their own namespaces. The recipe therefore has no
`tests/values.yaml`, and `tests/target.yml` compiles it as the file
installs it.

A release asset can be replaced under its tag unless the release is
immutable, so `check` fails on a file with another SHA-256. GitHub's API
reports each asset's SHA-256 as `digest`.

The RabbitMQ Cluster Operator, MPL-2.0, is the first. rabbitmq/cluster-operator
publishes no chart, and its install guide applies `cluster-operator.yml`
from the latest release. The only chart for the operator is Bitnami's
`rabbitmq-cluster-operator`, a third-party chart (DEC-11). The release
build renders the Kustomize base `config/installation` and sets the
operator image with a ytt overlay (`generate-installation-manifest` in its
Makefile). Release v2.23.1 of 2026-10-13 is not immutable. It attaches
`cluster-operator.yml` and `cluster-operator-ghcr-io.yml` with the same
SHA-256, `ae35a547751656bc64bb734026249a845d226d96aba5a73783e05c5ec3444687`,
and `cluster-operator-quay-io.yml` with the image on quay.io. The file
holds the CRD `rabbitmqclusters.rabbitmq.com`, the operator's Deployment
and RBAC, a mutating and a validating webhook configuration, and two
cert-manager Certificates with their Issuer, so the recipe
`rabbitmq-cluster-operator` requires `cert-manager` (Prerequisites).

- RCP-59: At `renders`, `check` MUST compare a recipe from a release
  manifest with the manifest's objects as RCP-8 to RCP-12 compare a chart
  recipe with the rendered chart.

  helm does not render the file, so RCP-25 has no hooks to leave out.

  - Test: CI `check` job
  - Since: #22, this change

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

powerdns was the third, the PowerDNS part of the kadet-hub/examples recipe
`external-dns-powerdns` (Recipes from kadet-hub/examples). PowerDNS
publishes no chart and no Kustomize base. The compose file in PowerDNS/pdns
builds its three services from the repository's Dockerfiles, and a `build`
without a published `image` is a gap of Compose sources. The recipe runs
`docker.io/powerdns/pdns-auth-51`, which PowerDNS builds, on the 5.1
release line that the examples recipe followed. PowerDNS publishes one
repository per release line, such as `pdns-auth-50` and `pdns-auth-51`, and
on 2026-10-25 `pdns-auth-52` held only `5.2.0-alpha0`.

As in the examples recipe, PowerDNS keeps its zones in SQLite on the claim.
The claim hides the image's empty database, so an init container copies it
onto an empty claim, and a second one creates the zone
`applications.powerdns.zone` when the database lacks it. The examples
recipe's check read an A record that external-dns wrote. Without
external-dns, `tests/smoke` writes the record through the API and reads it
back over DNS.

- RCP-44: A designed recipe MUST be at level `deploys`. `check lint` and
  `check` MUST check it as RCP-38 describes for a compose recipe: no RBAC
  object, every selector selecting pods, then one fresh kind cluster, with
  a deploy and `tests/smoke` at `deploys` and the apply of RCP-26 without
  a comparison at `renders`.

  An image grants no Kubernetes API access, so a Role or binding in its
  recipe would grant something no upstream artifact asks for, and nothing
  would compare it. The `next` compile (RCP-24) runs unchanged.

  - Test: `check lint`; `check/tests/test_lint.py`; CI `check` job;
    `renders`: `check/tests/test_check.py`
  - Since: #14; `renders`: #45

- RCP-45: The `tests/smoke` of a designed recipe MUST reach every Service
  port through its Service and make one request that needs what the recipe
  sets up, such as a query as the user the recipe creates in its database.

  - Test: manual: review; CI `check` job
  - Since: #14

- RCP-58: A designed recipe whose image the project's operator runs MUST
  set the image of its `Source` line as `spec.image` of the custom resource
  it renders for that operator, or as `spec.<part>.image` where the
  resource names an image per part, and MUST require the operator's recipe
  (RCP-54). `check lint` MUST accept a compiled object's `spec.image` or
  `spec.<part>.image` as the image that RCP-23 asks a container to run.

  The operator creates the workload and its Services from the resource, so
  the compiled recipe has no container to lint. The resource is no RBAC
  object and selects no pods, so RCP-44 holds as it is. `check` waits only
  for the rollouts of compiled workloads, so `tests/smoke` waits for the
  resource to be ready and then reaches the Services the operator created
  (RCP-45).

  A Strimzi Kafka names the image of its brokers and controllers as
  `spec.kafka.image` (Kafka). `spec.<part>.image` is one level below
  `spec`, so the images of deeper parts, such as the Topic Operator's
  `spec.entityOperator.topicOperator.image`, do not count.

  - Test: `check lint`; `check/tests/test_lint.py`; CI `check` job
  - Since: #24; `spec.<part>.image`: #34

## Recipes from kadet-hub/examples

kadet-hub/examples carried recipes as single classes, written in kadet-hub
in place of Bitnami charts (EX-5 there). Each one moves here with its
project's chart as source (DEC-10), and the examples repository then points
to the recipe here. valkey was the first: valkey-io publishes the chart
`valkey` in valkey-io/valkey-helm, BSD-3-Clause, at
`oci://ghcr.io/valkey-io/valkey-helm/valkey`, whose standalone mode renders
a Deployment, a PersistentVolumeClaim and ACL authentication where the
examples recipe had a StatefulSet and `--requirepass`. mysql and mongodb
moved as designed recipes (Designed recipes). kafka moves as a designed
recipe on Strimzi's operator, which becomes the chart recipe `strimzi`
(Kafka).

`external-dns-powerdns` combines two projects and moved in two steps.
PowerDNS ships no chart and moved first, as the designed recipe `powerdns`.
external-dns ships its chart only in the HTTP repository
`https://kubernetes-sigs.github.io/external-dns/`, and it needs a
ClusterRole, which a designed recipe cannot have (RCP-44). An OCI chart is
asked for in kubernetes-sigs/external-dns#4630, open since 2024. external-dns
followed as the chart recipe `external-dns-powerdns` on the chart
`external-dns` 1.23.0 from that repository (RCP-23), with external-dns
0.23.0. It includes `powerdns` (RCP-47) and requires nothing.

The chart names its objects after the release, which is the recipe's name,
so the Deployment, Service, ServiceAccount and ClusterRole are
`external-dns-powerdns`. The examples recipe named them `external-dns`, and
the ClusterRole and its binding `dns-external-dns`. Keeping `external-dns`
through `fullnameOverride` was considered. RCP-18 rules out the component
`external-dns`, and the generator names a workload after its component, as
with Kafka's `events`. The rename costs no data. external-dns keeps its
state in the zone, as TXT records with its owner ID, so a Deployment of the
new name with the same `--txt-owner-id`, `kadet-hub-recipe`, takes the
records over. The ClusterRole and its binding come from
`generators.kubernetes.rbac.external-dns-powerdns`. A component's
`cluster_role` would be named `<namespace>-external-dns-powerdns`, which
RCP-3 rejects.

The parent writes nothing below `applications.powerdns` (RCP-18). external-dns
filters on `applications.powerdns.zone`, so the target sets the zone once
for both recipes. It reads the API key from the Secret `powerdns`, key
`api-key`, which `powerdns` renders, and reaches the API through the Service
`powerdns`. Both recipes pin the `kubernetes` generator 1.9.0 (RCP-48), so
`powerdns` moved from 1.8.0 in the same change. The chart installs the CRDs
of DNSEndpoint and DNSRecord from its `crds/` directory with every release.
The recipe copies them from the chart's archive, and external-dns reads them
only with the source `crd`, which the recipe does not set. `tests/smoke` is
the examples recipe's check: PowerDNS answers an A record with the cluster
IP of a Service annotated with a hostname in the zone.

- RCP-41: The README of a recipe that replaces one of kadet-hub/examples
  MUST have a section `Replaces` that names that recipe and lists the
  objects, names and settings that change for a target moving from it.

  A target that included the examples recipe compiles different objects
  from the new one, such as another Secret key, so the move is a change
  its owner makes on purpose.

  - Test: manual: review
  - Since: #10

## Included recipes

A parent recipe includes another recipe of this repository with a
`classes` entry `recipes.<other>`, or `recipes.<other>.<option>` for one of
its options. `check lint` already resolves such an entry to the files of
`<other>/` (RCP-36). The included recipe renders its objects in the
target's namespace under its own names, and the parent connects to them by
those names. Nextcloud reaches its database through the Service
`postgresql-cluster-rw` and the Secret `postgresql-cluster-app`, and its
cache through the Service `valkey` and the Secret `valkey-auth`. These
names are literals in the parent, except the Cluster's name, which the
parent reads from `applications.postgresql.cluster` (RCP-60). A rename in
the included recipe breaks the parent, which CI shows (RCP-50) and which
raises the included recipe's major version (RCP-53).

Each recipe pins its own generators, so a parent and its included recipes
can pin the same generator twice. Kapitan merges the `kapitan.dependencies`
and `kapitan.compile` lists of all classes. Two equal pins fetch the same
artifact into `lib/<generator>` and write the same files. Two pins of
different versions conflict. The later fetch wins `lib/<generator>`, and
both compile entries run that version.

A consumer project fetches the generators into one `lib/` for all of its
targets, so recipes in separate targets conflict too. The consumer workflow
fails on two dependencies with the same `output_path` and different sources
(CON-1 in kadet-hub/registry). cert-manager 1.0.0 pins the `kubernetes`
generator 1.7.0 and cnpg 1.0.0 pins 1.9.0, so no project can use both.

- RCP-47: A recipe MAY include another recipe of this repository as
  `recipes.<other>` or `recipes.<other>.<option>`. `check lint` MUST fail
  when the included recipe includes a recipe itself.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #15; implemented: #31

- RCP-48: Every recipe of this repository MUST pin a generator it shares
  with another recipe of this repository at the same source. `check lint`
  MUST fail on two `kapitan.dependencies` entries of the recipe and its
  included recipes with the same `output_path` and different sources. It
  MUST also fail when another recipe pins the `output_path` of one of these
  entries at a different source.

  The other recipes are the directories next to the recipe that hold an
  `init.yml`, which leaves out `check/` and `docs/`. A recipe checked
  without such directories next to it has nothing to compare. The registry
  gate writes every recipe directory of the recipe's commit next to it
  (REC-4 there), so from `check` 0.12.0 on its REC-5 compares the same pins
  as this repository's CI.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #15; implemented: #31; every recipe: #48

- RCP-49: `check` MUST build the project from the parent and each recipe it
  includes, at the same commit, and verify the generators of each as RCP-27
  describes. An object belongs to an included recipe when the compile of
  that recipe's own `tests/target.yml` renders an object of the same kind
  and name, and to the parent otherwise. RCP-3 applies to the objects of
  each recipe. At `renders`, `check` MUST leave the objects of included recipes
  out of the comparison and list each as
  `` included <recipe>: `<Kind>/<name>` ``. At `deploys` it MUST apply them
  together with the parent's.

  The parent's `tests/values.yaml` switches the chart's subcharts off and
  points the chart at the included recipes' Services and Secrets, so the
  chart side renders the parent's objects only. Each included recipe is
  proven by its own `check`. At `deploys` the parent's `tests/smoke`
  exercises the whole stack. Ownership by name prefix was the first
  version of this rule. It fails for an included recipe that keeps a name
  its chart renders, such as a Cluster that keeps the name of the
  kadet-hub/examples recipe it replaces.

  - Test: `check/tests/test_check.py`; CI `check` job
  - Since: #15; implemented: #31; designed parents: #38

- RCP-50: CI MUST also run `check` for every recipe that includes a recipe
  a pull request changes, at the including recipe's level.

  - Test: CI `select` job
  - Since: #15; implemented: #31

- RCP-51: The section "Required parameters" of a parent MUST name the
  parameters its included recipes require as well.

  The include snippet of a parent names only the parent. A target that
  misses `applications.valkey.password` stops with the interpolation error
  of RCP-40, which names the key but not the recipe it belongs to.

  - Test: manual: review
  - Since: #15; implemented: #39

- RCP-52: A consumer MUST fetch each included recipe of a parent as RCP-15
  fetches the parent: before publication at the parent's commit SHA,
  afterwards by the digest that the parent's index record lists (CON-4 in
  kadet-hub/registry).

  - Test: manual: the README's "Using a recipe" steps for nextcloud on a
    fresh clone
  - Since: not implemented

- RCP-53: A parent version MUST be tagged on a commit where the directory
  of each included recipe, without `tests/`, equals a tagged version of
  that recipe. An included recipe's major version MUST also rise when a
  name or Secret key that a parent reads changes.

  The registry finds the included version by that tree (REC-16 there), so a
  parent tagged before the release of a changed included recipe fails its
  gate. The consumer gets a new version of an included recipe only with a
  parent release that includes it, because CON-4 pins exactly the versions
  of the parent's record. A fix in `valkey` therefore means a `valkey`
  release followed by a `nextcloud` release.

  - Test: the registry gate (REC-16); manual: release review for the
    major-version clause
  - Since: the registry gate, kadet-hub/registry#390

### Prerequisites

A prerequisite is named on the README's `Requires:` line (DEC-13). A parent
names its own prerequisites, and those of its included recipes apply too,
so `nextcloud` names `gateway-api` and gets `cnpg` through
`postgresql`.

A prerequisite's own prerequisites apply as well. `rabbitmq` names
`rabbitmq-cluster-operator`, whose README names `cert-manager`, so a target
that installs the operator needs cert-manager installed first. Each
`Requires:` line names only what its own recipe needs, so a change to the
operator's prerequisites changes one README.

`gateway-api` is the one entry that is not a recipe. `check` provides it
with cloud-provider-kind, the kind project's cloud provider, pinned like
the other tools (RCP-28). Version 0.12.0 installs the CRDs of the Gateway
API 1.6.1 standard channel, creates the GatewayClass `cloud-provider-kind`
and implements Gateway and HTTPRoute with one Envoy container per Gateway
on the runner's Docker (`pkg/gateway` of kubernetes-sigs/cloud-provider-kind).
At `deploys` `check` adds the Gateway `gateway` in the namespace `gateway`,
with a listener `http` on port 80 that admits routes from every namespace,
and the recipe's `tests/target.yml` attaches its route to it.
cloud-provider-kind runs outside kind with the runner's Docker socket. A
Gateway or LoadBalancer Service that a pull request applies at `deploys`
therefore starts containers on the runner, which the approval for forks of
RCP-20 covers. It also manages every other kind cluster on the same
Docker host, including clusters that have nothing to do with `check`, so a
proof that requires `gateway-api` runs only where no other kind cluster
runs, as on a CI runner. It does not advertise `HTTPRoutePathRedirect`, so a redirect
that changes the path is proven at `renders` only. Envoy Gateway supports
that feature and was considered, but it would add a chart install to every
proof that requires `gateway-api`.

- RCP-54: A recipe that needs something once per cluster MUST name it on
  one README line ``Requires: `<entry>`[, `<entry>`]``. An entry is a
  recipe of this repository or `gateway-api`. `check lint` MUST fail on any
  other entry and on a recipe that both includes and requires the same
  recipe. It MUST also fail on a recipe that requires itself, directly or
  through the `Requires:` lines of its prerequisites.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #15; implemented: #31

- RCP-55: Before the proof, `check` MUST install the prerequisites of the
  recipe, of its included recipes and, in turn, of those prerequisites on
  every kind cluster it creates. Each is installed once, after the
  prerequisites it requires. A prerequisite recipe is compiled from its
  own `tests/target.yml`. At `renders` only its Namespaces, CRDs,
  ServiceAccounts and RBAC objects are applied, as RCP-26 applies the
  recipe's. At `deploys` all of it is applied and its rollouts are waited
  for, and an apply the API server rejects is repeated for up to a minute,
  as is the recipe's own apply after them.

  The chart side needs the prerequisites too: a dry run of a CloudNativePG
  Cluster or an HTTPRoute fails without its CRD. The RabbitMQ operator's
  Certificates need cert-manager's CRDs at `renders` and its webhook at
  `deploys`. That webhook refused them for a few seconds after its rollout
  had reported done in kadet-hub/examples CI (EX-6 there), which the
  repeated apply covers.

  `check` waits for every CRD it applies to be Established before the next
  apply, for up to a minute. `kubectl wait --for condition=Established`
  fails instead of waiting while a new CRD's `status.conditions` is still
  null, which failed `check rabbitmq-cluster-operator --level deploys` once
  on `main`, so `check` reads the conditions itself.

  - Test: CI `check` job, report lines `requires`; `check/tests/test_check.py`
    (`Established`)
  - Since: #15; implemented: #31; CRD wait: #49

- RCP-56: The `tests/smoke` of a recipe that renders a route MUST reach the
  application through that route.

  - Test: manual: review; CI `check` job
  - Since: #15; implemented: #39

## Nextcloud

Nextcloud is the first parent. The stack is four recipes, written in this
order:

| Recipe | Source | Role |
|---|---|---|
| `cnpg` | `oci://ghcr.io/cloudnative-pg/charts/cloudnative-pg:0.29.1@sha256:3245fa051bb21d0dd9246272f57a2760b4234817a164a3167d2a1e7fb9f63fd9`, CloudNativePG 1.30.1, Apache-2.0 | prerequisite of `postgresql`: the operator, its webhooks and, as option `crds`, its CRDs |
| `postgresql` | `oci://ghcr.io/cloudnative-pg/charts/cluster:0.9.0@sha256:c8130c6573ab59e7629390ee5c468e5bc3d8536e6ec4ca8deea1aee792c4a9e5`, Apache-2.0 | included by `nextcloud`: one CloudNativePG Cluster |
| `valkey` | `oci://ghcr.io/valkey-io/valkey-helm/valkey:0.12.0`, on `main` since #10 | included by `nextcloud`: distributed cache and transactional file locking |
| `nextcloud` | `oci://ghcr.io/nextcloud/helm/nextcloud:9.4.1@sha256:90ffc4c8dd014e25343ecd37de7262f04d1c2cacb47a48315316d7798e7b35cb`, AGPL-3.0 | the parent: Nextcloud 35.0.2, its route and its background jobs |

The three new charts are published on ghcr.io by the projects' own GitHub
organizations, as RCP-23 requires. The nextcloud organization describes
its chart as community maintained. The chart's OCI package has
the SHA-256 of the GitHub release asset `nextcloud-9.4.1.tgz`,
`e3d768864800bcc23eb66e6f65cbf5f0545b1506cf8c65f55a91d21af3bad4bf`.
Nextcloud 35.0.2, released on 2026-10-15, is the newest stable release and
the chart's `appVersion`.

The operator's recipe is named `cnpg`, after the release name it renders
the chart with (RCP-23). Then every object starts with `cnpg`: the
Deployment, ServiceAccount and ClusterRoles `cnpg-cloudnative-pg`, and the
webhook Service, the two ConfigMaps and the two webhook configurations,
which the chart names `cnpg-*` whatever the release. A recipe named
`cloudnative-pg` could not write keys for those objects (RCP-18). The
operator finds its own Deployment by the label
`app.kubernetes.io/name: cloudnative-pg` to own its webhook certificates,
so the recipe sets that label, which RCP-9 leaves out of the comparison.
The chart passes the operator image by tag in `OPERATOR_IMAGE_NAME`, which
the operator gives to the instance pods, and the recipe keeps the tag.

`postgresql` replaces the kadet-hub/examples recipe of the same name
(RCP-41). That recipe rendered the Cluster `app-db` with 10Gi per
instance and the Pooler `app-db-pooler-rw` in the namespace `databases`,
and installed the operator from its chart through a `helm` compile entry,
which RCP-17 rules out here. The operator becomes the recipe `cnpg`, and
the Cluster comes from CloudNativePG's own `cluster` chart (DEC-10),
rendered by the `cloudnative-pg` generator 1.1.0, whose `spec` key passes
the fields it has no flat key for. With the release name `postgresql` the
chart names the Cluster `postgresql-cluster`. The operator then writes
the Secret `<cluster>-app` with the keys `username`, `password`, `host` and
`dbname` (`pkg/specs/secrets.go` of CloudNativePG v1.30.1), and the
read-write Service is `<cluster>-rw`. The operator generates the database
password, so no target sets one. The chart's Helm test Job
`postgresql-cluster-ping-test` is left out (RCP-25). The recipe runs
PostgreSQL 18, which Nextcloud 35's system requirements recommend, as
`ghcr.io/cloudnative-pg/postgresql:18.6-system-trixie`.

- RCP-60: `postgresql` MUST take the Cluster's name, the database, its
  owner, the storage size and the number of instances from
  `applications.postgresql.cluster`, `.database`, `.owner`, `.storage`
  and `.instances`.

  The defaults are what the chart renders for the release name
  `postgresql`: `postgresql-cluster`, `app`, `app`, 8Gi and 3.
  CloudNativePG names the claims `<cluster>-<n>` and the Secret
  `<cluster>-app` after the Cluster, so a Cluster keeps its data only under
  its old name. A target moving from kadet-hub/examples sets
  `cluster: app-db` and `storage: 10Gi` and keeps the claims and the Secret
  `app-db-app`. The chart renders no Pooler by default, so a target that
  keeps `app-db-pooler-rw` sets it as an entry of its own. The generator
  entry keeps the key `postgresql` (RCP-18) and passes the name as `name`,
  which the `cloudnative-pg` generator reads since 1.1.0, as `kafka` keeps
  `events`. A parent reads these keys for the Service, the Secret and the
  database and sets none of them (DEC-12).

  - Test: `check postgresql`; manual: compile of the README's `Replaces`
    snippet
  - Since: #35

Nextcloud's admin manual for version 35 lists Valkey as a Redis-compatible
backend for the distributed cache and for transactional file locking
(`caching_configuration.rst` of nextcloud/documentation `stable35`). Formal
tests run against Redis with the `redis` PHP extension and against Valkey
with Nextcloud's own `KeyValueCache`, added in 34.0.2. For that cache the
manual supports Valkey 9 except numbered databases in cluster mode. The
image configures the `redis` extension from `REDIS_HOST`, so Valkey 9.1.2
of `valkey` in standalone mode runs on a combination that the manual
expects to work but does not test. Nextcloud server uses no RabbitMQ. The
manual names it only for the Euro-Office document server.

The chart runs `docker.io/library/nextcloud:35.0.2-apache`, the Docker
official image built from nextcloud/docker, which the recipe pins as
`35.0.2-apache@sha256:89af7ee7a96ff5e9668280566209268ae6b2d02327f6ef6d56f6d68228cf9431`.
Apache starts as root and serves as `www-data`, UID 33, so the target's
namespace needs the Pod Security level `baseline`. With an external
database the chart renders no init container that waits for it. The
image's entrypoint retries `occ maintenance:install` up to ten times
(`docker-entrypoint.sh` of nextcloud/docker), which has to outlast the
Cluster's start on kind. That is not measured yet.

The entrypoint installs only on the first start. It copies `version.php`
onto the claim before the install, and a later start that finds the file
skips the install, so a container restarted during the install never
installs. The chart's liveness probe restarts a container that has not
answered on `/status.php` after about 30 seconds. The recipe therefore
enables the chart's `startupProbe`, which holds the liveness probe back
for up to 330 seconds.

### Exposure

The chart renders an HTTPRoute that attaches to a Gateway the cluster
already runs (`httpRoute.parentRefs`). It has the host names, two
`RequestRedirect` rules from `/.well-known/carddav` and
`/.well-known/caldav` to `/remote.php/dav`, and one rule to the Service
`nextcloud` on port 8080. The recipe keeps that route. TLS, the certificate
and the listener belong to the Gateway, and the listener must admit routes
from the target's namespace. The target names the Gateway, optionally its
listener, and the host.

Behind the Gateway Nextcloud receives plain HTTP. The chart's
`phpClientHttpsFix` sets `OVERWRITEPROTOCOL=https`, so Nextcloud builds
`https://` links, and `nextcloud.host` and `trustedDomains` take the host.
The image writes `NEXTCLOUD_TRUSTED_DOMAINS` into `config.php` when it
installs Nextcloud (nextcloud/docker README), so a later change of the host
needs `occ config:system:set trusted_domains`. `TRUSTED_PROXIES` depends on
the addresses of the Gateway implementation's proxies and has no default.
Without it Nextcloud takes the proxy's address for the client's.

Gateway API's standard channel has no request body limit. A limit is a
policy of the Gateway implementation and is set on the Gateway's side. The
image caps PHP uploads at `PHP_UPLOAD_LIMIT`, 512M by default, which a
target raises in `components.nextcloud.env`. The route sets no timeouts,
as the chart's default values set none.

Four generator changes came first, in the `kubernetes` generator 1.8.0
(kadet-hub/generators#107) and 1.9.0 (#109):

- The `kubernetes` generator 1.7.0 renders a route only below a Gateway it
  renders itself (`gateways.<gateway>.routes`), and a redirect only with
  scheme, port and status code. The chart's route needs `parentRefs` to a
  Gateway outside the inventory and a redirect `path` of type
  `ReplaceFullPath`.
- The same generator fails the compile on a webhook with
  `failurePolicy: Fail` and no CA (`webhooks.py`). The CloudNativePG
  operator writes the CA into its webhook configurations itself, so its
  chart renders none, and `cnpg` does not compile until the inventory
  can declare that.
- The operator writes that CA only into the webhook configurations
  `cnpg-mutating-webhook-configuration` and
  `cnpg-validating-webhook-configuration` (`internal/configuration` of
  CloudNativePG 1.30.1), and the generator named both
  `<namespace>-<component>`. The operator crash-looped on kind until the
  names could be set.
- A container mounts each volume once, because `volume_mounts` is keyed by
  volume name. Nextcloud's chart mounts its claim `nextcloud-main` at six
  paths.

RCP-48 then moves `valkey` and `postgresql` to the `kubernetes` version
that `nextcloud` pins.

### First version

The first version is one Nextcloud replica with what it needs to hold real
files. The rest waits for later recipes or options (OQ-12):

| Part | First version | Why |
|---|---|---|
| Database | `postgresql` | Nextcloud's chart supports an external PostgreSQL with credentials from a Secret (`externalDatabase.existingSecret`) |
| Cache, file locking | `valkey` | `externalRedis.existingSecret` reads the password from `valkey-auth` |
| Background jobs | chart `cronjob`, `type: sidecar` | `/cron.sh` runs next to Apache in the same pod. The `cronjob` type runs a Kubernetes CronJob that needs the same ReadWriteOnce claim on the same node, which the chart leaves to a pod affinity the user writes. |
| Storage | chart `persistence` and `nextcloudData` | one claim for `/var/www/html`, one for the data directory, so the data can use another storage class and be backed up on its own; 8Gi each and the storage class are settings |
| Admin account | Secret `nextcloud`, as the chart renders it | the password is a ref the target sets (RCP-19) |
| Host and proxy | `phpClientHttpsFix`, `nextcloud.host`, `trustedDomains` | Exposure; `TRUSTED_PROXIES` is a setting |
| Upload size | on the Gateway's side | Exposure |
| SMTP | not rendered | the admin settings write the mail server into `config.php` on the claim; the chart's `nextcloud.mail` can become an option |
| notify_push | not rendered | the chart has no support; the Client Push app needs its own daemon (nextcloud/notify_push) behind a path of the route |
| Office | not rendered | Collabora publishes `oci://ghcr.io/collaboraonline/charts/collabora-online`; ONLYOFFICE-based servers such as Euro-Office also need RabbitMQ |
| imaginary | not rendered | the chart's `imaginary.enabled` can become an option; previews work without it |
| Metrics | not rendered | the chart's `metrics.enabled` can become an option |
| Backups | not rendered | the object store, the snapshot class and the backup tool belong to the cluster; the README says how (DEC-18, RCP-64) |
| More replicas | not rendered | the chart's `Recreate` strategy and ReadWriteOnce claims allow one pod |

The target sets `applications.nextcloud.host`,
`applications.nextcloud.gateway.name` and
`applications.nextcloud.gateway.namespace`, and as refs
`applications.nextcloud.admin.password` and `applications.valkey.password`
(RCP-51). `applications.nextcloud.gateway.section`, the listener's
`sectionName`, is optional.

### Backups

The recipe renders no backup (DEC-18). The admin manual's backup guide for
version 35 lists what to retain: the config, custom apps, theme and data
folders and the database (`admin_manual/maintenance/backup.rst` of
nextcloud/documentation `stable35`). In this recipe the config, custom apps
and themes are sub paths of the claim `nextcloud-nextcloud`, and the data
directory is the claim `nextcloud-nextcloud-data`.

The guide puts the instance into maintenance mode first, so that the
database and the files describe the same state. The Barman Cloud Plugin
archives WAL continuously, so the Cluster can be restored to a time inside
the maintenance window.

The `cloudnative-pg` generator 1.1.0 renders the database backup. A target
adds `object_stores`, `scheduled_backups` and
`clusters.postgresql.backup.object_store` to `generators.cloudnative-pg`.
The plugin and the Secret with the object store credentials are the
target's. The README's snippet compiles with `tests/target.yml` and renders
the ObjectStore, the ScheduledBackup and the plugin entry in the Cluster's
`plugins`.

Valkey needs no backup. The image configures it from `REDIS_HOST` as
`memcache.distributed` and `memcache.locking` and as the PHP session store
(`redis.config.php` and `entrypoint.sh` of nextcloud/docker `35/apache`).
Losing it empties the cache, drops the file locks and logs users out. The
recipe's claim and `appendonly yes` only carry that state across a restart.

- RCP-64: The README of `nextcloud` MUST have a section "Backups" that
  names what a target backs up and how: the database through the Barman
  Cloud Plugin, the two claims, and maintenance mode around the backup. It
  MUST say that Valkey needs no backup.

  The recipe renders none of it (DEC-18), so the README is the only place
  that tells a target which objects hold state.

  - Test: manual: review; compile of the README's snippet with
    `tests/target.yml`
  - Since: #43

### Proof

All four are at level `deploys`. `nextcloud`'s `tests/values.yaml` switches
off the chart's internal SQLite database and its subcharts. It sets
`externalDatabase` to type `postgresql` with the Secret
`postgresql-cluster-app` and `externalRedis` to the Service `valkey` with
the Secret `valkey-auth`, and enables `httpRoute` towards the Gateway of
`check`, `persistence`, `nextcloudData`, `cronjob`, `phpClientHttpsFix` and
`startupProbe`.
`tests/target.yml` sets the matching recipe values and the Valkey
password.

`tests/smoke` waits for the Cluster to be ready. Through the Gateway, with
the route's host name, `status.php` reports `"installed":true` and a file
written over WebDAV as the admin reads back, which needs the database, the
file locking and the data claim. In the pod,
`occ config:system:get memcache.locking` names the Redis backend. The two
well-known redirects are proven at `renders` only. cloud-provider-kind
0.12.0 translates a `RequestRedirect` with its host name and status code
and drops its `path` (`pkg/gateway/httproute.go`), so on kind the redirect
would keep the path.

The chart is AGPL-3.0. The first version copies no text from its
templates, so RCP-42 does not apply to it, and DEC-16 publishes it under
Apache-2.0. Of the recipe's 41 lines of 30 characters or more, one occurs
verbatim in the chart 9.4.1 (templates, `files/`, `values.yaml`): the label
`app.kubernetes.io/monitor: enabled`.

## Keycloak

The Keycloak project's guides deploy Keycloak on Kubernetes through the
Keycloak Operator. The one exception is the getting-started guide, which
applies an example manifest from the `main` branch of
keycloak/keycloak-quickstarts. The project ships no chart, Kustomize base or
compose file for a Keycloak server. With each release it ships the operator
three ways: an OLM bundle, which its installation guide recommends, a
Kustomize base in keycloak/keycloak-k8s-resources, and a Helm chart at
`oci://quay.io/keycloak/keycloak-operator-helm`, which the guide calls
experimental (`docs/guides/operator/installation.adoc` of keycloak/keycloak
26.8.1). The Quarkus Helm extension generates the chart from the same
manifests as the Kustomize base, and the chart names the Keycloak Team as
maintainer (`operator/README.md`). quay.io lists it from 26.8.0 on. The
`keycloak` generator 1.1.0, built for operator 26.8.1, renders Keycloak's
resources. Keycloak therefore moves from kadet-hub/examples as two recipes
(DEC-14):

| Recipe | Source | Role |
|---|---|---|
| `keycloak-operator` | `oci://quay.io/keycloak/keycloak-operator-helm:26.8.1@sha256:650f7e1021def78ff799aa5ada703818a1a7d0e3cb6ee7eba6d5e1b557656a17`, from keycloak/keycloak, Apache-2.0 | prerequisite of `keycloak`: the operator, its RBAC and, as option `crds`, its four CRDs |
| `keycloak` | `quay.io/keycloak/keycloak:26.8.1@sha256:a78d6b79572168cb25886b80a8b5b8d4ed4390743e3eecb810538683e209dd6b` | one `Keycloak` resource and its certificate and, as option `route`, an HTTPRoute; includes `postgresql`, requires `keycloak-operator`, `cert-manager` and `gateway-api` |

### The operator

The chart installs the operator cluster-wide. Its four controllers watch
every namespace (`JOSDK_ALL_NAMESPACES`) with ClusterRoles. The guide calls
that mode a preview. In it a `Keycloak` resource cannot set its own
ServiceAccount, and one operator supports only the Keycloak version it was
released with. The recipe keeps the chart's default, because a
prerequisite runs once per cluster in a target of its own (DEC-13). Its
`tests/target.yml` installs it in the namespace `keycloak-operator`, as the
guide does. A target narrows the watch through the four `*_NAMESPACES`
variables.

The Kustomize base was considered as the source. Its operator watches only
its own namespace, so it would have to run in the namespace of every
Keycloak it serves, and `check` takes no Kustomize source (RCP-23). OLM
would have to be installed on the cluster first.

The kadet-hub/examples recipe installed the operator from this chart through
a `helm` compile entry, which RCP-17 rules out here, and restricted its
controllers to their own namespace.

The recipe rebuilds the chart's objects with the `kubernetes` generator.
The four CRDs are vendored from keycloak/keycloak-k8s-resources at tag
26.8.1, whose files equal the chart's and which carries the Apache-2.0
license that RCP-35 asks for. The chart package has no license file. The
chart passes the default Keycloak image to the operator by tag, in
`RELATED_IMAGE_KEYCLOAK` and `kc.operator.keycloak.image`. The recipe pins
both by digest (RCP-6), and `tests/values.yaml` sets the same values. The
chart's Deployment, pod template, Service and ServiceAccount carry
`app.quarkus.io/*` annotations with the build's commit and time. RCP-9
compares them, so the recipe writes them as the chart renders them.

The project rebuilds a release from the same source revision and moves the
version tag to the new build. On 2026-10-25 the image tag `26.8.1` pointed
to the build of 2026-10-23, also tagged `26.8.1-1`. `26.8.1-0` is the build
of the release day, 2026-10-13. The chart's 26.8.1 was also created on
2026-10-23, so its digest and build annotations change with a rebuild.

### The Keycloak resource

`keycloak` renders one `Keycloak` resource in the target's namespace, named
`keycloak` unless the target sets another name (RCP-61). The operator
creates the StatefulSet `<name>`, the Services `<name>-service` and
`<name>-discovery`, and the Secret `<name>-initial-admin` with a generated
password for a temporary admin.
The resource sets the image of the `Source` line (RCP-58). With an image
set, the operator starts Keycloak with `--optimized`, which assumes an
image built for its configuration (`KeycloakDeploymentDependentResource.java`).
The project's image is not built for PostgreSQL, so the recipe sets
`startOptimized: false` and Keycloak builds at start, as in the examples
recipe.

The database is the included recipe `postgresql` (DEC-4, DEC-12). Keycloak
connects to the Service `<cluster>-rw` and the database
`applications.postgresql.database`, where `<cluster>` is
`applications.postgresql.cluster` (RCP-60). The user and password are the
keys `username` and `password` of the Secret `<cluster>-app`, the keys the
generator's `credentials_secret` reads. With `postgresql`'s defaults these
are `postgresql-cluster-rw`, `app` and `postgresql-cluster-app`.
Keycloak 26.8.1 is tested against PostgreSQL 18
(`postgresql.version` in its `pom.xml`), the version `postgresql` runs.

Keycloak serves HTTPS on port 8443 with the Secret `keycloak-tls`. The
cert-manager Certificate `keycloak-tls` issues it for the host and for
`<name>-service.<namespace>.svc`, from an issuer the target names. The
certificate's common name is the host. The examples recipe set it because
Keycloak rejected its self-signed certificate with an empty issuer DN.

The operator renders an Ingress unless `ingress.enabled` is false. The
recipe turns it off, as the examples recipe did. A route to a Gateway is
the option `route` (The route).

The target sets `applications.keycloak.host` and
`applications.keycloak.issuer`, the issuer's `name` and `kind`.
`postgresql` requires no parameter (RCP-51).

- RCP-61: `keycloak` MUST take the name of its `Keycloak` resource from
  `applications.keycloak.name`, `keycloak` by default, and its certificate
  MUST name `<name>-service.<namespace>.svc`.

  The generator entry keeps the key `keycloak` (RCP-18) and passes the
  name as `name`, which the `keycloak` generator reads since 1.1.0, as
  `kafka` keeps `events`. The Certificate and its Secret stay
  `keycloak-tls`.

  - Test: `check keycloak`; manual: compile of the README's `Replaces`
    snippet
  - Since: #38

### The route

The option `route`, which a target includes as `recipes.keycloak.route`,
renders the HTTPRoute `keycloak` for the host, with one rule to
`<name>-service` on port 8080 (DEC-17). The `kubernetes` generator 1.9.0
renders it, which the option pins at the source `postgresql` pins
(RCP-48). As for Nextcloud, TLS, the certificate and the listener belong to
the Gateway, and the listener must admit routes from the target's
namespace. The target names the Gateway in
`applications.keycloak.gateway.name` and `.namespace`, and optionally the
listener in `.section`, the route's `sectionName`.

The option sets `spec.http.httpEnabled`, on which the operator adds port
8080 to `<name>-service` (`KeycloakServiceDependentResource.java` of the
operator 26.8.1). HTTPS on port 8443 stays. It also sets
`spec.proxy.headers` to `xforwarded`, so Keycloak takes the client's
address from the `X-Forwarded-For` header that the Gateway sets. Keycloak
builds its links from `hostname`, which stays `https://<host>`.

Keycloak accepts these headers from every client that reaches port 8080.
Its reverse proxy guide limits them to the proxy's addresses with the
option `proxy-trusted-addresses`. Those addresses depend on the Gateway
implementation, as for Nextcloud's `TRUSTED_PROXIES`, so the recipe sets
none.

`check` installs a prerequisite only from the `Requires:` line (RCP-55),
and `tests/target.yml` includes the option, so keycloak's README names
`gateway-api`. A target without the option needs no Gateway API.

- RCP-62: With the option `route`, `keycloak` MUST render an HTTPRoute for
  `applications.keycloak.host` to port 8080 of `<name>-service`, attached
  to the Gateway `applications.keycloak.gateway.name` in
  `applications.keycloak.gateway.namespace`, and to the listener
  `applications.keycloak.gateway.section` when it is set. It MUST enable
  Keycloak's HTTP listener with the proxy headers `xforwarded`.

  - Test: `check keycloak`; CI `check` job, `tests/smoke` through the
    Gateway
  - Since: #42

- RCP-63: Without the option `route`, `keycloak` MUST compile to the same
  files as before the option existed.

  A target that leaves the option out keeps a Keycloak that serves HTTPS
  only, and its `Keycloak` resource does not change, so the operator does
  not restart Keycloak.

  - Test: manual: compile of `tests/target.yml` without the option,
    compared with its compile at #41
  - Since: #42

### Moving from kadet-hub/examples

The examples recipe rendered the Namespace `keycloak`, the three operators
from their charts, the CloudNativePG Cluster `keycloak-db`, the self-signed
Issuer `keycloak-selfsigned`, the Certificate `sso-tls` and the Keycloak
`sso`. The operators become the prerequisites `keycloak-operator`,
`cert-manager` and `cnpg`, each in a target of its own. The old
operator in the namespace `keycloak` has to be gone before
`keycloak-operator` starts, or both reconcile the same resource.

Keycloak keeps its realms, users and sessions in the database, so a target
moving from the examples recipe keeps the names that hold them. It sets
`name: sso` on `keycloak` (RCP-61). The operator then keeps the StatefulSet
`sso`, the Services `sso-service` and `sso-discovery` and the Secret
`sso-initial-admin`. On `postgresql` it sets `cluster: keycloak-db`,
`database: keycloak`, `owner: keycloak`, `storage: 10Gi` and
`instances: 2` (RCP-60), so the Cluster keeps its claims `keycloak-db-<n>`
and Keycloak its database. Nothing is renamed or imported. The certificate
moves from `sso-tls` to `keycloak-tls` for the same DNS names. The recipe
renders no Issuer, so a target that keeps `keycloak-selfsigned` renders it
as `tests/target.yml` does. The README's `Replaces` section gives the
values and the order. The move is not tested (RCP-14).

Renaming `sso` to `keycloak` and importing `keycloak-db` into
`postgresql-cluster` with CloudNativePG's import bootstrap was considered.
The import runs once, when the new Cluster is created, so Keycloak would
have to stay stopped from the import until it starts on the new Cluster,
and the move would depend on an untested step. A Cluster `keycloak-db`
rendered by `keycloak` itself was considered too. It would keep the data in
place, but repeat the Cluster that `postgresql` proves and pins, so
Keycloak and Nextcloud would run their databases two ways.

### Proof

Both are at level `deploys`. `keycloak-operator`'s `tests/smoke` creates a
`Keycloak` resource in another namespace than the operator's and waits for
its StatefulSet, which needs the CRDs, the cluster-wide watch and the
ClusterRoles.

For `keycloak`, `check` installs `keycloak-operator`, `cert-manager`,
`gateway-api` and, through `postgresql`, `cnpg` (RCP-55), and applies
`postgresql` with the recipe (RCP-49). `tests/target.yml` adds the
self-signed Issuer `keycloak-selfsigned` and sets it as the issuer, and it
includes the option `route` towards the Gateway of `check`. `tests/smoke`
waits for the Cluster and the `Keycloak` to be ready. Through
`keycloak-service`, with the host name and the CA of `keycloak-tls`, it
then gets `/realms/master` and a token for the temporary admin of
`keycloak-initial-admin`, which needs the database. Through the Gateway,
with the route's host name, it gets `/realms/master` and a token again
(RCP-56). The examples recipe checked the readiness and `/realms/master`
over TLS.

## Kafka

Strimzi runs Apache Kafka on Kubernetes through its Cluster Operator. It
publishes the operator's chart `strimzi-kafka-operator`, Apache-2.0, at
`oci://quay.io/strimzi-helm/strimzi-kafka-operator`. The package of 1.3.0
is the release asset `strimzi-kafka-operator-helm-3-chart-1.3.0.tgz`, SHA-256
`42677cec73d2122f4a395d9891bbccfae18ec16b3582174d49ca04695f351192`. For a
Kafka cluster Strimzi ships no chart. Its release archives carry example
resources in `examples/kafka/`, which show features such as a plain
listener without authentication. Strimzi 1.3.0 of 2026-10-12 is the newest
release. It supports Kubernetes 1.32 and later and Kafka 4.2.0 to 4.3.1,
with 4.3.1 as the default (`kafka-versions.yaml`). The `strimzi` generator
1.1.0, built for Strimzi 1.3.0, renders Kafka, KafkaNodePool, KafkaTopic and
KafkaUser resources. Kafka therefore moves from kadet-hub/examples as two
recipes (DEC-14):

| Recipe | Source | Role |
|---|---|---|
| `strimzi` | `oci://quay.io/strimzi-helm/strimzi-kafka-operator:1.3.0@sha256:08852fb5aca9782750ec1698616cad0efe15d5eef1a366d124373129ff9c29ea`, Apache-2.0 | prerequisite of `kafka`: the Cluster Operator, its RBAC and the CRDs |
| `kafka` | `quay.io/strimzi/kafka:1.3.0-kafka-4.3.1@sha256:1f189b1f0f32684302d8b018b1d21b411e2469a9c465fbdc18fa3599cb5bbdad` | one Kafka cluster with its node pool, requires `strimzi` |

The example resources were considered as the source of `kafka`. They would
need a source form of their own, and `check` would compare the recipe with
an example that it deviates from on purpose, such as the plain listener.

### The operator

`tests/values.yaml` sets `watchAnyNamespace: true`, as the examples class
did. The operator then watches every namespace and binds its ClusterRoles
with ClusterRoleBindings, so one installation serves a Kafka in any
namespace (DEC-13). The chart's default watches only the release
namespace. `tests/target.yml` installs the operator in the namespace
`strimzi`.

The chart keeps its CRDs in `crds/`, which helm installs with the first
release and never upgrades. The recipe copies the release asset
`strimzi-crds-1.3.0.yaml`, SHA-256
`09f6db7000e27d6121e02334e666a55f06f8d62a9124e66adee6c84ec010bf41`, with
Strimzi's LICENSE. strimzi/strimzi-kafka-operator has no NOTICE (RCP-35).
The asset holds the chart's ten CRDs without the chart's `component` label
(RCP-9). The chart has no value that leaves them out, so they belong to the
recipe and are no option (DEC-2).

The operator binds the ClusterRoles `strimzi-kafka-broker`,
`strimzi-entity-operator` and `strimzi-kafka-client` by name to the pods it
starts. Kubernetes lets it grant only what it holds, so the chart binds the
three to the operator as well. The recipe keeps their names. Its bindings
take the names of its `rbac` entries, which the README lists (RCP-11).

The Deployment passes the images the operator starts in environment
variables. The recipe pins the operator image by digest in the container
and in the three variables that run it as the Topic Operator, the User
Operator and the Kafka init container, as the examples class did.
`tests/values.yaml` sets the same references as the tags of those three, so
the chart renders them alike. The chart appends the Kafka version to the
tag of each Kafka image and drops it when the values set a tag. The
version maps `STRIMZI_KAFKA_IMAGES`, `STRIMZI_KAFKA_CONNECT_IMAGES` and
`STRIMZI_KAFKA_MIRROR_MAKER_2_IMAGES` therefore stay as the chart renders
them, by tag, and `kafka` names its image itself. The images of Kafka
Bridge, Kafka Exporter, Cruise Control, Buildah and the Maven builder stay
by tag too, because no recipe here starts them.

The ConfigMap `strimzi-cluster-operator` holds the chart's log
configuration, text of its templates (RCP-42).

### The Kafka cluster

`kafka` renders the Kafka `kafka` and the KafkaNodePool `kafka-dual` in the
target's namespace. The pool has three nodes with the roles controller and
broker and a 10Gi claim each, the sizes of the examples class. Kafka is
4.3.1 with the metadata version `4.3-IV0`. The `strimzi` generator adds one
internal listener `tls` on port 9093 with mutual TLS, simple authorization
and the Entity Operator, and derives the replication settings from the
three brokers.

The Kafka sets the image of the `Source` line as `spec.kafka.image`
(RCP-58). Strimzi then runs that image in place of the one its version map
names. The Topic and User Operator images come from the operator. The
Kafka init container runs only for rack awareness or a node port listener
(`KafkaCluster.java`), which the recipe does not render. Because Strimzi
builds its Kafka images per release, `kafka` moves together with `strimzi`
(RCP-16).

The recipe renders no KafkaTopic and no KafkaUser. A target sets its own
under `generators.strimzi.topics` and `users`, and the generator assigns
them to the only Kafka. `tests/target.yml` adds the examples class's topic
`orders` as the KafkaTopic `kafka-orders` and its user as
`kafka-orders-app`, because RCP-3 holds for the test target's objects too.

### Moving from kadet-hub/examples

The examples class rendered the Namespace `kafka`, the operator from its
chart in the namespace `strimzi`, the Kafka `events` with the node pool
`dual`, the topic `orders` and the user `orders-app`. The recipe renders no
Namespace, and the target sets `namespace`. The Namespace `kafka` has to
outlive the examples class, because deleting it deletes the claims. The
operator becomes the prerequisite `strimzi` in a target of its own. Its
Deployment `strimzi-cluster-operator` selects on `name` only, so the
examples Deployment is deleted first, and the bindings the README lists are
deleted by their chart names.

The recipe keeps the keys `kafka` and `kafka-dual` (RCP-3, RCP-18). A
target that moves from the examples class sets `name: events` on the Kafka
and `name: dual` on its node pool. The `strimzi` generator then names the
resources as the examples class did, and Strimzi derives the same objects
from them: the Service `events-kafka-bootstrap`, the Secret
`events-cluster-ca-cert` and the claims `data-0-events-dual-<n>`. The
Kafka keeps its claims and with them its messages. The topic `orders` and
the user `orders-app` become entries the target sets, so their clients
keep the bootstrap address, the CA and their certificates. The move is not
tested (RCP-14).

Renaming `events` to `kafka` and `dual` to `kafka-dual` was considered. The
new cluster would start empty, because the claims of `events` would not
carry over, and only a KafkaMirrorMaker2 from `events` would keep the
messages. An exception to RCP-3 and RCP-18 for the names of a replaced
examples recipe was considered too. `check lint` and the registry gate
check the names of every recipe, and `name` keeps the old names without
one.

### Proof

Both are at level `deploys`. `strimzi`'s `tests/smoke` creates a single-node
Kafka on ephemeral storage in another namespace than the operator's and
waits until it is Ready, which needs the CRDs, the cluster-wide watch and
the ClusterRoles.

For `kafka`, `check` installs `strimzi` first (RCP-55). `tests/smoke` is
the examples check: the Kafka, the topic and the user are Ready, and a
client with the user's certificate writes a message to the topic and reads
it back over mutual TLS through the bootstrap Service.

## RabbitMQ

The RabbitMQ Cluster Operator runs RabbitMQ from a RabbitmqCluster
resource. It ships as a release manifest and no chart (Release manifests).
The `rabbitmq` generator 1.1.0, built for the operator 2.23.1, renders its
resources. RabbitMQ therefore moves from kadet-hub/examples as two recipes
(DEC-14, DEC-15):

| Recipe | Source | Role |
|---|---|---|
| `rabbitmq-cluster-operator` | `https://github.com/rabbitmq/cluster-operator/releases/download/v2.23.1/cluster-operator.yml@sha256:ae35a547751656bc64bb734026249a845d226d96aba5a73783e05c5ec3444687`, MPL-2.0 | prerequisite of `rabbitmq`: the operator, its webhooks, RBAC and the CRD, requires `cert-manager` |
| `rabbitmq` | `docker.io/library/rabbitmq:4.3.6-management@sha256:54cb013d76cd1fd6c0a0708f34062ad61c452bb6f016b434c6c33f1a765d2b58` | one RabbitmqCluster of three nodes, requires `rabbitmq-cluster-operator` |

A target with `rabbitmq` needs `rabbitmq-cluster-operator` installed first,
and that one `cert-manager` (Prerequisites).

### The operator

The recipe renders the manifest's objects with the `kubernetes` generator
1.9.0, and its two Certificates and the Issuer with the `certmanager`
generator 1.0.2. That generator sets `privateKey.rotationPolicy: Always`,
which the manifest leaves to cert-manager (RCP-12). The recipe therefore
needs cert-manager 1.18 or later with the feature gate
`DefaultPrivateKeyRotationPolicyAlways` on, its default, and its README says
so. The `cert-manager` recipe installs 1.21.2.

`tests/target.yml` installs the operator in `rabbitmq-system`, the namespace
the manifest names, and the recipe renders that Namespace as the manifest
does. The CRD is `config/crd/bases/rabbitmq.com_rabbitmqclusters.yaml` of
v2.23.1, SHA-256
`6203b7216bbb76aa6eeedc8ee3d07e4750b8ed66c9498346e6098be9a89c309e`, the same
object as in the manifest, copied with the repository's `LICENSE.txt`.
rabbitmq/cluster-operator has no NOTICE (RCP-35).

The webhook configurations keep the manifest's names. The generator's
`<namespace>-<component>` would start with neither the recipe's name nor a
name of the manifest (RCP-3). The two bindings take the names of their
`rbac` entries, which the README lists (RCP-11).

The manifest's webhook Service has one port without a name. The
`kubernetes` generator names every Service port after its key, so the
recipe gives the port an empty key, which the API stores as no name. An
RCP-12 class for a port name the generator adds was considered. It would
need a new `check` release before the registry gate accepts the recipe
(REC-9 there).

### The RabbitMQ cluster

`rabbitmq` renders the RabbitmqCluster `rabbitmq` in the target's namespace
with three nodes and the requests and limits of the examples class. Each
node keeps the operator's default claim of 10Gi. The resource sets the
image of the `Source` line as `spec.image` (RCP-58), the `management`
variant the examples class ran. The operator creates the default user and
its Secret `rabbitmq-default-user`, so no parameter has to be set.

### Moving from kadet-hub/examples

The examples class rendered the Namespace `messaging` and the
RabbitmqCluster `production` and included cert-manager's class. The
operator was installed from its release manifest by hand. A target that
moves sets `name: production` on the entry `rabbitmq`. The `rabbitmq`
generator then names the resource as the examples class did, and the
operator derives the same StatefulSet `production-server`, Secret
`production-default-user` and claims `persistence-production-server-<n>`, so
the cluster keeps its queues and messages. The Namespace `messaging` has to
outlive the examples class, because deleting it deletes the claims.
cert-manager and the operator move to targets of their own. The move is not
tested (RCP-14).

Renaming `production` to `rabbitmq` was considered. As for Kafka, the new
cluster would start empty.

### Proof

Both are at level `deploys`. `rabbitmq-cluster-operator`'s `tests/smoke`
creates a RabbitmqCluster in another namespace. The webhooks admit it with
the CA that cert-manager injected, the mutating webhook sets its image, and
its replicas become ready.

For `rabbitmq`, `check` installs `cert-manager` and then
`rabbitmq-cluster-operator` (RCP-55). `tests/smoke` is the examples check,
all replicas ready and `rabbitmq-diagnostics check_running`. Through the
Service `rabbitmq` it then sends a message through a quorum queue over the
HTTP API and reaches the AMQP and Prometheus ports.

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
  works from. The images follow the chart, so Renovate moves none of them
  to a new tag; the maintainer moves each one in its single line (RCP-66).

  When upstream rebuilds a pinned image tag, Renovate proposes the tag's
  new digest for every image line of a class file. A package rule keeps
  those lines on their tag, which moves by hand with the chart or, for a
  designed recipe, with the `Source` line. Docker Hub gives no release
  timestamps for repositories with more than 1000 tags, such as
  `library/nextcloud` and `library/postgres`, so a digest update needs
  none. A dry run on 2026-10-29 proposed new digests for the nextcloud,
  postgresql and miniflux database images, and no new tag.

  Renovate opens and updates the pull requests for `Source` lines and class
  image lines only on Mondays from 00:00 to 06:00 Europe/Berlin, so a
  recipe's source moves at most once a week and a maintainer reviews the
  week's chart and image updates together. `updateNotScheduled: false`
  keeps Renovate from pushing to an open pull request outside that window.
  Where Renovate gets release timestamps, the repository's three days of
  release age apply as well. GitHub raises no vulnerability alerts for
  images or charts, so a security fix in one can wait up to a week plus
  three days. A maintainer who needs it sooner moves the pin by hand.

  For a designed recipe Renovate moves the image of the `Source` line in
  the same way. The class line that runs that image carries the comment
  `# renovate: Source` above it, and Renovate moves that line in the same
  pull request, because both name the same image. `check lint` fails when
  the two differ (RCP-23). kafka's `applications.kafka.version` and
  `metadata_version` are Kafka settings of the `Kafka` resource, not image
  tags, so they stay and are raised by hand. A package rule keeps the image on the release line the README
  names. For mysql that is MySQL's 9.7 LTS line: from 26.7 on, Oracle
  numbers the Innovation releases by calendar, so the rule allows versions
  below 10. For mongodb it is MongoDB's 9.0 major release. MongoDB supports
  a major release for five years and stops patching a minor release once
  the next one is out, so the rule allows only tags that start with `9.0.`.
  It is the regex `/^9\.0\./`, because Renovate falls back to npm semver
  for a range such as `<9.1`, reads `9.0.4-ubi9-slim` as a prerelease and
  then allows no tag at all.

  Renovate gets no release timestamp for the mongodb image. Docker Hub
  refuses anonymous requests for tag list pages after the tenth, and the
  image has more than 1000 tags. With `minimumReleaseAgeBehaviour:
  timestamp-required`, the repository's three days would hold every update
  of it, so the image has no minimum release age, as the `next` pin of
  RCP-29 has none. MongoDB pushes the newest patch tag again with almost
  every daily build, and the weekly window above keeps its digest to one
  move a week. Docker Hub credentials for Renovate were considered. They would give
  timestamps, but a tag pushed again with each build would reach the three
  days only once MongoDB stops rebuilding it, one release late.

  powerdns needs no package rule. `pdns-auth-51` holds the 5.1 releases and
  their prereleases, whose tags carry a suffix such as `5.1.0-beta1`, and
  Renovate's docker versioning proposes no suffixed tag for a pin without
  one. The next release line is another repository, which a maintainer
  moves to. Docker Hub lists the repository's 11 tags on one page, so
  Renovate gets their release timestamps.

  The rabbitmq image, a Docker Official Image, has more than 1000 tags too,
  so Renovate gets no release timestamp for it. A package rule makes the
  timestamp optional for the image. Without the rule a dry run held
  `4.4.0-management` as pending, and with it the dry run proposed it.
  docker-library rebuilds the image when RabbitMQ's entry in its
  official-images library changes or the Ubuntu base image does. Between
  2026-07-25 and 2026-10-25 the entry changed 13 times and Ubuntu's 7 times.
  That moves the digest at most about twice a week, and the weekly window
  above bundles those moves into one. Renovate's docker versioning
  proposes only tags with the suffix `-management`, which keeps the variant.

  A package rule groups the `Source` lines of `keycloak-operator` and
  `keycloak` into one pull request, because one operator supports only the
  Keycloak version it was released with (Keycloak). Keycloak has no
  long-term support line, so no rule holds the version. The rebuild tags
  such as `26.8.1-1` carry a suffix, which Renovate's docker versioning
  proposes for no pin without one, so a rebuild reaches the pins as a new
  digest of `26.8.1`.

  A package rule groups the `Source` lines of `strimzi` and `kafka` into
  one pull request, because Strimzi builds its Kafka images per release
  and runs the image a Kafka names (Kafka). The image's tags have the form
  `<strimzi>-kafka-<kafka>`. Renovate's docker versioning reads
  `kafka-4.3.1` as a compatibility suffix and proposes only tags with the
  same suffix, so the image moves to a newer Strimzi release of the same
  Kafka version. A move to another Kafka version is a maintainer's change,
  together with the Kafka's `version` and `metadata_version`.

  For a chart from an HTTP repository Renovate's `helm` datasource reads
  the repository's `index.yaml`. It proposes a new version with the
  `digest` of its index entry, which has no `sha256:` prefix, so the
  manager captures only the hex digits after `sha256:`. The entry's
  `created` is the release timestamp, so the three days apply. With the
  external-dns chart at 1.22.0, a dry run proposed 1.23.0 with the digest
  of its archive.

  Compose sources are not covered yet (OQ-10).

  For a release manifest Renovate moves the tag and the SHA-256 of the
  `Source` line with the datasource `github-release-attachments`, as it
  moves the tool pins of RCP-30. It downloads the assets of the pinned
  release until one has the pinned SHA-256, hashes the asset of the same
  name in the new release, and waits the three days from the release's
  date. Assets of equal size are tried in the order the API lists them, so
  for the RabbitMQ Cluster Operator it may take `cluster-operator-ghcr-io.yml`
  for `cluster-operator.yml` (Release manifests). Should the two differ in
  a later release, `check` fails on the proposed SHA-256 (RCP-23).

  - Test: manual: Renovate dry run
  - Since: #3; designed recipes: #14; mongodb: #17, #20; powerdns: #19;
    keycloak: #26; release manifests: #22, #25; kafka: #34; HTTP
    repository: #23; rabbitmq: #36; digests of rebuilt tags: #55

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
  chart version is a minor version unless it also does that. The
  registry's SEC-16 opens an issue when a registered tag moves.

  Two tag rulesets, the same as kadet-hub/generators has, enforce who
  creates, moves and deletes tags. `tag creation` restricts creating any
  tag, with the admin role as its only bypass. `release tags` forbids
  deleting, updating and force-pushing `refs/tags/*-v*`, without bypass,
  which also covers `check-vX.Y.Z` (RCP-22).

  - Test: manual: `gh api repos/kadet-hub/recipes/rulesets`
  - Since: #41; the rulesets exist since the repository was set up

- RCP-32: The first paragraph of a recipe's README, after the heading, MUST
  describe the recipe in at most 300 characters, without control or
  bidirectional formatting characters, and MUST NOT end with a colon.

  The paragraph is the first non-empty block of lines after the first line
  that starts with `#`, with whitespace collapsed to single spaces. The
  length counts that text. The registry's index takes it as the recipe's
  description (REC-13), and the catalog shows it in lists and in
  `/llms.txt`. A description that ends in a colon announces text the index
  does not carry.

  - Test: `check lint`; `check/tests/test_lint.py`
  - Since: #46

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
  the recipe and the rendered chart, or the release manifest, as input, and
  then run neither Kapitan nor helm. For a compose source or a designed
  recipe it MUST take the compiled output alone.

  The registry gate compiles and renders in its gVisor sandbox and gives
  `check` only the two outputs (DEC-21 there), so a chart that attacks
  `helm template` (OQ-7) or a generator stays inside the sandbox. In this
  repository's CI `check` keeps compiling and rendering itself.

  The gate runs the pinned `check` release (RCP-22) as:

  ```sh
  uv run --locked --project check check/check.py <recipes>/<name> \
    --level renders --compiled <out> --rendered <file>
  ```

  `<recipes>` holds the recipe's directory at the recipe's commit, and next
  to it the directory of each recipe it includes (RCP-49) and of each
  prerequisite (RCP-55), as in this repository. `check` reads their
  READMEs, class files and `tests/target.yml` there.

  `<out>` is a Kapitan output path. It holds `compiled/<recipe>/` for the
  recipe and for each of those recipes. Each is the compile of that
  recipe's own `tests/target.yml`, whose `kapitan.vars.target` is the
  recipe's name. `check` fails when one is missing.

  `<file>` is the unfiltered output of
  `helm template <name> <chart> -n <namespace> -f tests/values.yaml --include-crds`,
  with the release name and namespace of RCP-23, or the release manifest
  as downloaded. `check` leaves out the hooks itself (RCP-25).

  `check` rejects the flags at another level, `--compiled` alone for a
  chart or a release manifest, and `--rendered` for a compose source or a
  designed recipe, which have nothing to render. With the flags `check`
  pulls no generator, chart, manifest or compose file and does not compile
  with Kapitan `next` (RCP-24). The generator attestations (RCP-27) and
  the digest of the chart, manifest or compose file (RCP-23) are then the
  gate's to verify (REC-6, REC-7 there), and the report says the outputs
  were given. Linting the output, the comparison and the proof on kind run
  as without the flags.

  - Test: `check/tests/test_check.py`; the registry's `gate-selftest`
  - Since: #41; compose sources and designed recipes: #45

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

- RCP-68: CI MUST fail when pip-audit reports an advisory for a package in
  `check/uv.lock`, or zizmor a finding in `.github/`.

  The job `deps` runs on every pull request and in the weekly run of `ci`,
  so an advisory published after a merge fails the next Monday run. It
  exports the whole lock with hashes, and pip-audit looks up every pinned
  version in PyPI's vulnerability data. With `--strict` a package it cannot
  look up fails the job too. There is no ignore list, so an advisory
  without a fixed release fails every pull request until a fix is released.
  When an upstream cap holds the fix back, RCP-67 lifts it.

  pip-audit is the lock's group `audit`, pinned by version and hash, and
  Renovate moves it with the other packages (RCP-30). zizmor is a release
  asset pinned like actionlint. It runs with the job's read-only token, so
  its online audits also check that each pinned action commit belongs to
  the action's repository and that no pinned action has a known advisory.
  A finding that does not apply is ignored on its line with
  `# zizmor: ignore[<audit>]` and the reason.

  The images a recipe pins are not gated here. kadet-hub/registry is to
  show their advisories on each recipe's catalog page.

  - Test: CI `deps` job; manual: the job's commands on a copy of the lock
    with cryptography 48.0.1 fail
  - Since: #53

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

  Lock file maintenance refreshes `check/uv.lock` once a week, in
  Renovate's default window before 04:00 UTC on Monday. It is the only
  update for packages that `check/pyproject.toml` does not name, such as
  cryptography, which Kapitan and its dependencies require. It runs
  `uv lock --upgrade`, which takes the newest releases without the three
  days.

  A GitHub vulnerability alert gets its pull request at once, outside the
  weekly windows and without the release age. That is Renovate's default
  for `vulnerabilityAlerts`, which overrides the package rules, so
  `renovate.json` sets nothing for it. Renovate acts only on alerts for
  packages it extracts: the direct dependencies in `check/pyproject.toml`
  and the action pins. An alert for a transitive package such as
  cryptography waits for lock file maintenance or a maintainer.

  Renovate pushes only `renovate/` branches. The `branches` ruleset admits
  only the admin role to every branch but `main` and `renovate/**`, and
  the `renovate branches` ruleset admits Renovate and the admin role to
  `renovate/**`, as REV-3 does in kadet-hub/registry.

  - Test: manual: Renovate dry run; `gh api repos/kadet-hub/recipes/rulesets`
  - Since: #3; lock file maintenance: #55

- RCP-57: Every pull request MUST request a review from `neat-bot`. That
  review MUST NOT be a condition for merging.

  The `request review` workflow requests `neat-bot` with the repository's
  own token when a pull request is opened, reopened or marked ready. It skips
  drafts, pull requests opened by bots, and pull requests from forks, whose
  token is read-only; on a fork the bot is requested by hand after a look at
  the pull request. `neat-bot` has read access only (terraform-homezone
  GHO-6a), so CODEOWNERS, which requests a code owner only with write access,
  cannot do it, and an approval by `neat-bot` counts toward no approval a
  ruleset requires.

  - Test: manual: on a new pull request the `request review` run succeeds and
    `gh pr view <n> --json reviewRequests` lists `neat-bot`;
    `gh api repos/kadet-hub/recipes/collaborators/neat-bot/permission` reports
    `read`
  - Since: #13 (CODEOWNERS, as RCP-44, an ID it shared with the
    designed-recipe rule), #18 (workflow)

- RCP-69: `SECURITY.md` MUST say how to report a vulnerability privately,
  which versions get fixes and how a fix is published, and the README MUST
  link it.

  Reports go through GitHub private vulnerability reporting, which the
  organisation's code security configuration turns on for every public
  repository, or by mail. The newest release of each recipe and of `check`
  gets fixes, and a recipe without a release is fixed on `main`. A fix is
  published as a GitHub security advisory with the affected versions and a
  CVSS score.

  Handling is best effort, without a service level or a response time.
  kadet-hub is run by a private person and nothing is monetised, so the
  maintainer reads the EU Cyber Resilience Act as not applying (recital
  18).

  - Test: manual: `gh api repos/kadet-hub/recipes/private-vulnerability-reporting`
    returns `"enabled": true`
  - Since: #54

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

  The release is a tag on a commit of `main`, and `X.Y.Z` is `VERSION` in
  that commit's `check/check.py`. Nothing else is published. The gate pins
  the tag's commit SHA and runs `check` from that commit.

  - Test: manual: the `to-recipe` skill names a `check-vX.Y.Z` tag
  - Since: tags `check-v0.9.0` and `check-v0.10.0`; the skill pins
    `check-v0.10.0` since kapitan-recipes 0.3.0, Moep90/agent-skills#9

- RCP-67: `check/pyproject.toml` MAY lift a dependency's version constraint
  only to reach a release that fixes a published advisory. The override is
  removed once upstream allows the fixed release.

  The override is an entry of `override-dependencies` under `[tool.uv]`: a
  lower bound on the fixed release, with a comment that names the upstream
  change. GI-16 does the same for the registry's sandbox. Kapitan 0.36.3
  requires `cryptography<49`, and `check` overrides it to 50.0.0 or later
  (PYSEC-2026-3552, PYSEC-2026-3553, PYSEC-2026-3554) until a Kapitan
  release contains kapicorp/kapitan#1632. In Kapitan only the ref functions
  import cryptography, and a recipe has no refs (RCP-19).

  The registry gate and the `to-recipe` skill run `check` from a release
  tag (RCP-22), so they get the fixed version with the next `check`
  release.

  - Test: CI `test` and `check` jobs install and compile with the
    overridden version (partial: no check calls Kapitan's ref functions)
  - Since: #52

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
  README whose first paragraph exceeds 300 characters or ends with a
  colon, on one without the section "Required parameters" and on a vendored
  file without `.LICENSE`;
  `check cert-manager --level renders` with a compiled output and a chart
  render given reports the same result as without them; a tag pushed by a
  non-admin is rejected.
- AC-10 (RCP-1, RCP-23, RCP-37 to RCP-39): `check lint` fails on a compose
  recipe at level `renders`, on a compose `Source` line without a full
  commit SHA, and on a fixture with a RoleBinding or a Service whose
  selector matches no pods; miniflux passes `check miniflux --level
  deploys` in CI.
- AC-14 (RCP-47, RCP-48, RCP-54): `check lint` fails on a parent whose
  included recipe includes a recipe, on a parent and an included recipe
  that pin `lib/kubernetes` at different sources, on a recipe next to one
  that pins `lib/kubernetes` at another source, on a `Requires:` entry
  that is neither a recipe nor `gateway-api`, and on a recipe that includes
  and requires the same recipe. It passes on nextcloud, and on a recipe
  alone or next to one with the same `lib/kubernetes` pin.
- AC-15 (RCP-49, RCP-55, RCP-56): `check nextcloud --level deploys` passes
  in CI, its report lists the objects of `postgresql` and `valkey` as
  included and `cnpg` and `gateway-api` as installed, and its
  smoke test reads `status.php` through the Gateway. `check postgresql
  --level deploys` passes with `cnpg` installed.
- AC-16 (RCP-50): a pull request that changes only `valkey/` runs `check`
  for `valkey` and `nextcloud`.
- AC-17 (RCP-51, RCP-52, RCP-53): nextcloud's README names
  `applications.valkey.password` under "Required parameters", a fresh
  consumer clone compiles nextcloud with the fetch inventory pinning
  nextcloud, postgresql and valkey at one commit, and the first nextcloud
  tag follows tags of postgresql and valkey whose trees it contains.
- AC-18 (RCP-55, RCP-58, RCP-61): `check lint` fails on a designed recipe
  whose `Source` image neither a container runs nor a `spec.image` sets,
  and passes on keycloak. `check keycloak-operator --level deploys` and
  `check keycloak --level deploys` pass in CI, and the latter's report
  lists `postgresql` as included and `keycloak-operator`, `cert-manager`
  and `cnpg` as installed. keycloak's README `Replaces` snippet compiles
  to the Keycloak `sso` on the Service `keycloak-db-rw`, and its
  certificate names `sso-service.keycloak.svc`.
- AC-11 (RCP-41, RCP-42): valkey passes `check valkey --level deploys` in
  CI, its README names the kadet-hub/examples recipe it replaces, and
  `valkey.yml` names the chart file of its init script and has
  `valkey.yml.LICENSE`.
- AC-21 (RCP-23): `check`'s tests serve a chart repository on localhost.
  `check` takes the archive whose SHA-256 the `Source` line names, and
  fails on an archive with another SHA-256, on a `Chart.yaml` with another
  version and on a version the index does not list. `check lint` reads the
  HTTP form and fails without `tests/values.yaml`.
- AC-13 (RCP-23, RCP-44, RCP-45): `check lint` fails on a designed recipe
  at level `renders` and on one whose `Source` image no container runs,
  and passes on mysql, mongodb and powerdns; each passes `check <name>
  --level deploys` in CI.
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
- AC-19 (RCP-16, RCP-23, RCP-34, RCP-59): `check`'s tests fail the
  download of a release manifest whose SHA-256 differs from the `Source`
  line and pass it when it matches. `rabbitmq-cluster-operator` passes
  `check` at its README's level in CI, and a local Renovate dry run
  extracts its `Source` line with `github-release-attachments`.
- AC-20 (RCP-54, RCP-55): `check lint` fails on a recipe that requires
  itself and on two recipes that require each other. The report of
  `check rabbitmq --level deploys` lists `cert-manager` as installed before
  `rabbitmq-cluster-operator`.
- AC-22 (RCP-9, RCP-16, RCP-55, RCP-58): `check`'s tests drop the labels
  `chart`, `release`, `heritage` and `component`. `check lint` accepts a
  Kafka whose `spec.kafka.image` is the `Source` image and fails on one
  that names it only as the Topic Operator's image. `check strimzi --level
  deploys` and `check kafka --level deploys` pass in CI, and the report of
  the latter lists `strimzi` as installed. A local Renovate dry run puts
  both `Source` lines into one update.
- AC-23 (RCP-56, RCP-62, RCP-63): `check keycloak --level deploys` passes
  in CI, its report lists `gateway-api` as installed, and its smoke test
  gets `/realms/master` and a token through the Gateway of `check` with
  the route's host name. keycloak's `tests/target.yml` without the option
  `route` compiles to the same files as at #41.
- AC-24 (RCP-34, RCP-38, RCP-44): `check`'s tests run miniflux and mysql
  at `renders` on a given compiled output: lint fails on an RBAC object,
  otherwise the apply of RCP-26 runs on one cluster and nothing is
  compared, and `--rendered` is rejected. `check miniflux --level renders`
  and `check mysql --level renders` pass.
- AC-25 (RCP-16, RCP-66): `check lint` fails on a class file whose image
  takes its tag from `${...}` and passes the literal reference. Every
  recipe compiles to the same files as at #49. A local Renovate dry run
  puts a designed recipe's `Source` line and its `# renovate: Source`
  class line into one branch, as it did for rabbitmq's
  `4.4.0-management`.

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
- OQ-12: Do notify_push, an office server and imaginary become recipes
  that `nextcloud` includes, options of `nextcloud`, or recipes of their
  own that the target combines with it?

## Implementation inventory

| Path | Purpose |
|---|---|
| `README.md` | Using a recipe (RCP-15) |
| `SECURITY.md` | Reporting a vulnerability (RCP-69) |
| `SECURITY.md` | Reporting a vulnerability (RCP-69) |
| `<name>/` | One recipe (RCP-1) |
| `check/check.py` | CLI, sources, kind clusters, report; pins the kind node and Kapitan `next` images |
| `check/lint.py` | `check lint` (RCP-1 to RCP-7, RCP-66, RCP-17 to RCP-19, RCP-23, RCP-32, RCP-33, RCP-35, RCP-36, RCP-38, RCP-40, RCP-43, RCP-44, RCP-58) |
| `check/compare.py` | Normalization, pairing, classes, selectors, can-i (RCP-9 to RCP-12) |
| `check/tests/` | AC-1, AC-2, AC-5, AC-9, AC-10, AC-13, AC-19, AC-21, AC-24 without a cluster |
| `check/pyproject.toml`, `check/uv.lock` | Kapitan 0.36.3, omegaconf 2.4.0.dev4, PyYAML; pip-audit in the group `audit` (RCP-68) |
| `.github/workflows/ci.yml` | RCP-13, RCP-20, RCP-28, RCP-68 |
| `.github/workflows/request-review.yml` | requests `neat-bot` (RCP-57) |
| Rulesets `tag creation`, `release tags` | RCP-31, applied with `gh api` |
| `.github/actions/tools/` | Pinned helm, kubectl, kind, oras, gh, cloud-provider-kind (RCP-55) |
| `renovate.json` | RCP-16, RCP-29, RCP-30 |
| `check/lint.py`, `check/check.py`, `.github/workflows/ci.yml` | Included recipes and prerequisites (RCP-47 to RCP-56) |

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
| First chart from an HTTP repository | external-dns-powerdns, chart `external-dns` 1.23.0 of kubernetes-sigs/external-dns, external-dns 0.23.0, includes powerdns, level `deploys` |
| First parent | nextcloud, chart `nextcloud` 9.4.1, Nextcloud 35.0.2, includes postgresql and valkey, requires `gateway-api`, level `deploys` |
| postgresql | chart `cluster` 0.9.0 of cloudnative-pg/charts, `cloudnative-pg` generator 1.1.0, `kubernetes` generator 1.9.0, PostgreSQL 18.6, requires `cnpg`, level `deploys` |
| cnpg | chart `cloudnative-pg` 0.29.1, CloudNativePG 1.30.1, `kubernetes` generator 1.9.0, level `deploys` |
| `gateway-api` | cloud-provider-kind 0.12.0, Gateway API 1.6.1 standard CRDs, Gateway `gateway/gateway`, listener `http` |
| keycloak-operator | chart `keycloak-operator-helm` 26.8.1 of keycloak/keycloak, Keycloak Operator 26.8.1, cluster-wide, CRDs of keycloak/keycloak-k8s-resources 26.8.1, level `deploys` |
| keycloak | `quay.io/keycloak/keycloak` 26.8.1, `keycloak` generator 1.1.0, `certmanager` generator 1.0.2, includes postgresql, requires `keycloak-operator`, `cert-manager` and `gateway-api`, level `deploys` |
| keycloak option `route` | `recipes.keycloak.route`, `kubernetes` generator 1.9.0, HTTPRoute `keycloak` to `<name>-service` port 8080, `applications.keycloak.gateway.name`, `.namespace` and `.section` (unset by default), `spec.http.httpEnabled: true`, `spec.proxy.headers: xforwarded` |
| strimzi | chart `strimzi-kafka-operator` 1.3.0 of strimzi/strimzi-kafka-operator, Strimzi 1.3.0, watches every namespace, CRDs of the 1.3.0 release, level `deploys` |
| kafka | `quay.io/strimzi/kafka` 1.3.0-kafka-4.3.1, Kafka 4.3.1, `strimzi` generator 1.1.0, requires `strimzi`, level `deploys` |
