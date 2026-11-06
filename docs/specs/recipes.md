# Recipes

```text
Status: Draft. check 0.16.0 implements renders and deploys, for charts
        from OCI and HTTP repositories, for release manifests (RCP-59) and
        for compose sources and designed recipes (RCP-38, RCP-44, RCP-58),
        included recipes and prerequisites (RCP-47 to RCP-50, RCP-54,
        RCP-55), and renders from given outputs (RCP-34);
        migrates (RCP-14) and RCP-21 are not implemented;
        RCP-15 only up to publication; RCP-30 not yet for the
        kubernetes-versions.json commit of RCP-70.
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

DEC-19: The Kubernetes minors `check` runs on come from
`kubernetes-versions.json` of kadet-hub/renovate-config, fetched at a
pinned commit (RCP-70). renovate-config computes the three minors upstream
supports from upstream sources, with the node images and the kind release
that built them, for every kadet-hub repository. Three `kindest/node` pins
in `check/check.py` were considered. Renovate would move each pin's patch
and digest, but it cannot add a new minor and drop the oldest, so that step
would be a manual edit that nothing prompts.

DEC-20: A compose service that runs a project this repository has a recipe
for becomes that included recipe (Compose sources). paperless-ngx's `db`
runs PostgreSQL and its `broker` Valkey, which `postgresql` and `valkey`
prove already. The database then runs on CloudNativePG with the operator's
generated password, and Valkey with the ACL password of `valkey`, where the
compose broker has none. A component per service, as miniflux keeps its
database, was considered. It would run PostgreSQL a third way next to
`postgresql` and miniflux, without the failover and the backup path that
`nextcloud` documents.

DEC-21: A relative bind mount of a directory that the pinned repository
does not contain becomes a volume claim, as a named volume does (Compose
sources). Docker creates such a source as an empty directory, so the
container starts with an empty directory either way. What the claim does
not give is access from the host, which in a cluster the storage behind
the claim takes over, without a hostPath. Directories the repository
contains carry content, and absolute paths and the Docker socket carry
host state, so they stay gaps. Leaving such a mount out was considered.
Kubernetes ignores the image's `VOLUME`, so paperless-ngx's `export`
directory, where its exporter writes backups, would be lost with the pod.

DEC-22: paperless-ai is the option `ai` of `paperless-ngx`, designed on its
image like a designed recipe (Paperless-ngx). It runs only against a
paperless-ngx API and needs a token of it. A recipe of its own was
considered. clusterzx/paperless-ai ships a compose file, which would be its
source (DEC-10), and that file sets `network_mode`, `cap_drop` and
`security_opt`, on which Compose sources stop. paperless-ai reads its
settings only from the file `/app/data/.env`, which its web setup writes.
The option renders that file from a Secret, so the target sets every
setting, and the web setup and the settings page cannot save.

DEC-23: A relative bind mount of a directory that the pinned repository
does not contain becomes a ConfigMap when the documentation has the user
write a settings file there and the image's entrypoint otherwise creates
it from a template the image carries (Compose sources). The ConfigMap holds
the template's settings. A secret that the entrypoint generates into the
file becomes a parameter the target sets. SearXNG's `./core-config/` is the
first such directory. A volume claim, as DEC-21 renders other such
directories, was considered. The settings would then live on the claim,
changed only from a shell in the pod, and a new claim would start with a
new random key.

DEC-24: `searxng` connects SearXNG to the included recipe `valkey`
(SearXNG). The image's settings template sets no Valkey URL, so with the
compose file as it is SearXNG leaves the compose service `valkey` unused.
The documentation names Valkey for the limiter, SearXNG's bot protection,
with `valkey` as the host of its URL. Leaving the connection out was
considered. `valkey` would then run without a client and still require
its password, and no request of the smoke test could need both services
(RCP-39).

DEC-28: `pihole` takes its compose file from the code block in `README.md`
of pi-hole/docker-pi-hole, and its `Source` line names that README
(Pi-hole). The repository ships no other compose file for Pi-hole alone.
`examples/docker-compose-caddy-proxy.yml` adds Caddy on a network of its
own with an external volume, and Compose sources stop on both. `check` and
the registry gate verify only the SHA-256 of the file a `Source` line
names, so a README pins the compose file as a compose file would. A
designed recipe on the image was considered. The project ships a compose
example, which DEC-10 puts first, and its documentation starts from it.

DEC-29: A compose recipe renders nothing for a `cap_add` whose
capabilities the project's documentation names as optional or as needed
only for a feature the recipe does not set up (Compose sources). Pi-hole's
compose example adds `NET_ADMIN`, `SYS_TIME` and `SYS_NICE`. `NET_ADMIN`
serves only DHCP and IPv6 router advertisements, and DHCP needs Pi-hole on
the LAN (Pi-hole). `SYS_TIME` lets FTL's NTP client set the clock, which in
a pod is the node's clock. `SYS_NICE` only raises FTL's priority. Without
them FTL logs one warning per capability and answers DNS. Rendering them
was considered. Pod Security `baseline` allows none of the three, so the
namespace would need `privileged`, and the pod could set the node's clock.
Stopping on the gap, as RCP-37 did before, would leave Pi-hole without a
recipe over capabilities that its DNS blocking does not use.

DEC-30: `pihole` renders one Service `pihole` of type `ClusterIP`, with DNS
on port 53 over both TCP and UDP (Pi-hole). Kubernetes allows both
protocols on one Service port, as `powerdns` renders it. A Service per
protocol was considered. Clients would get two names for one DNS server,
and two LoadBalancer Services get two addresses unless the implementation
shares one. Exposing the Service, such
as with `type: LoadBalancer`, is left to the target, because whether a
load balancer serves TCP and UDP on one address depends on its
implementation.

DEC-31: `n8n` runs n8n in queue mode, the default of n8n's chart, with the
included recipe `valkey` as the queue (n8n). n8n-main receives webhook
calls and the editor's requests and queues each execution, and the
Deployment `n8n-worker` runs them. Standalone mode, `queueMode.enabled:
false`, was considered. It would run one Deployment without Valkey, but
`tests/values.yaml` would then prove a configuration the chart does not
default to, and a release installed with the chart's defaults would change
how it runs its executions when the recipe replaces it.

Related: [kadet-hub authoring guide](https://github.com/kadet-hub/registry/blob/main/docs/authors.md),
[consumers guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md),
[chart-vs-kapitan](https://github.com/kadet-hub/examples/tree/main/chart-vs-kapitan)

## Layout

```text
<name>/
  init.yml          # generator pins, applications.<name>, classes of the components
  <component>.yml   # one per component, with its RBAC
  <option>.yml      # optional class, such as crds.yml
  recipe.yaml       # required parameters and backends (RCP-260)
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

- RCP-4a: YAML in a recipe MUST NOT use anchors (`&name`), aliases
  (`*name`) or merge keys (`<<`). Repeated values are written out. The
  rule covers the class files of RCP-36 and the files below `tests/`.

  A reader of an alias has to find its anchor to know the value, and a
  change to the anchor changes every place that uses it without showing
  up there in the diff. kadet-hub writes no anchors in any of its
  repositories.

  - Test: `check lint`; `check/tests/test_lint.py::test_anchor_and_alias`
  - Since: #65

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

## Required parameters and backends

A program that writes a target for a recipe, such as the quickstart, a
Backstage template or the Helm converter, needs two facts that the README
states only in prose: the parameters the target must set, and the
inventory backends the recipe resolves on. A Backstage prototype wrote a
target for immich without `applications.valkey.password`, and the target
did not compile until someone read the README.

DEC-190: Each recipe declares both facts in `<name>/recipe.yaml`, and
`check lint` proves the file against the README and against Kapitan. The
registry copies the two keys into the recipe's index record (REC-18
there), where a program reads them from the signed index.

```yaml
# immich/recipe.yaml
backends:
  - omegaconf
required:
  - path: applications.valkey.password
    description: Password of Valkey's user default, with which Immich connects to its job queue.
    secret: true
```

DEC-191: Every recipe declares `backends: [omegaconf]`, and its relative
class includes stay.

With the backends `reclass` and `reclass-rs`, `kapitan inventory` of
`tests/target.yml` stops for postgresql and for every recipe that
includes it with `Class recipes.cluster not found`. Both backends resolve
`.cluster` in `postgresql/init.yml` against the class name
`recipes.postgresql` and look for `recipes.cluster`. The omegaconf backend
resolves it against the file's directory (Layout). By the same rule,
`.valkey` in `valkey/init.yml` names `recipes.valkey` itself, and reclass
stops with a `RecursionError` while reclass-rs dies of a segmentation
fault.

Replacing every relative include of the 36 recipes with
`recipes.<name>.<class>` fixes the class lookup on both backends. 28
recipes then stop at their first interpolation. reclass separates the
keys of a reference with `:`, so it looks up
`${applications.postgresql.cluster}` as one key, and it has no `escape`
resolver. These interpolations are what DEC-3, RCP-5 and RCP-42 ask for.
omegaconf in turn reads `${applications:postgresql:cluster}` as a call of
a resolver named `applications` and fails with
`Unsupported interpolation type applications`.

The other eight recipes resolve. blackbox-exporter, cnpg, jellyfin,
memcached, ollama, rabbitmq and uptime-kuma resolve on both backends to
the same parameters as on omegaconf, rabbitmq-cluster-operator on
reclass-rs only. None of them derives a value from another yet. The
probes ran on 2026-11-05 with Kapitan 0.36.3, kapicorp-reclass 2.0.0 and
reclass-rs 0.10.1 from check's lock, on the recipes at `a723bd2`.

| Alternative | Why it was not taken |
|---|---|
| Lines in the README next to `Source:`, `Level:` and `Requires:` | Those lines hold one value each. A list of paths with a description and two flags would need a parser for prose. |
| Absolute includes, and all three backends for the seven recipes that resolve on them | The first value one of them derives (RCP-5) drops reclass and reclass-rs again, and a consumer on those backends breaks with that recipe's next version. The proof compiles on omegaconf only. |
| Interpolations in reclass syntax | omegaconf cannot read them, and `escape`, `merge` and `parentkey` have no reclass counterpart. |

- RCP-260: Every recipe MUST have a file `recipe.yaml` with the keys
  `backends` and `required` and no other. `backends` MUST list
  `omegaconf` and MAY list `reclass` and `reclass-rs`, each once.
  `required` MUST list each parameter a target must set, as a mapping
  with `path`, `description`, `secret` and, for a parameter that only an
  option needs, `option`.

  `path` is the dotted parameter path, such as
  `applications.valkey.password`. `description` is one line of at most
  300 characters, the limit of RCP-32. `secret` is `true` for a value the
  target sets as a ref (RCP-19). `option` names the option
  `recipes.<name>.<option>` that needs the parameter, such as `route` for
  the Gateway keycloak's route attaches to. A recipe that needs no
  parameter has `required: []`.

  The file is no class, and `check lint` does not lint it as one
  (RCP-36). RCP-4 and RCP-4a apply to it as to a class file.

  - Test: `check lint`; `check/tests/test_lint.py` (`Meta`)
  - Since: this change

- RCP-261: `check lint` MUST fail unless `recipe.yaml` matches the README.
  Each path MUST appear in backticks in the section "Required parameters"
  (RCP-40), and each backticked path there below `applications.`,
  `components.` or `generators.` MUST be a path of the file. The section
  MUST say "No parameter has to be set." exactly when `required` is
  empty. The Include snippet MUST set each path, to `<ref>` exactly when
  `secret` is `true`, and MUST include `recipes.<name>.<option>` for each
  `option`.

  The README is what a reader reads and the file what a program reads.
  The rule keeps the two from drifting apart, so the section names each
  path in full. authentik, netbox, semaphore and wordpress abbreviated
  paths such as `.email` until this change.

  - Test: `check lint`; `check/tests/test_lint.py` (`Meta`)
  - Since: this change

- RCP-262: `check lint` MUST prove each path of `required`. The Include
  snippet as the recipe's only target MUST resolve with
  `kapitan inventory` on omegaconf, and MUST fail with
  `Interpolation key '<path>` once the path is removed from it. For each
  `option`, the snippet without `recipes.<name>.<option>` and without the
  paths of that option MUST resolve.

  Kapitan resolves interpolations when it loads the inventory, before a
  generator runs, so `kapitan inventory` stops where a compile of the
  snippet would stop. It needs neither the generators nor the network.
  The snippet's placeholders, such as `<ref>`, resolve as strings. The
  included recipes lie next to the recipe as in the proof (RCP-49). An
  error that names a key below the path counts too: keycloak's target
  sets `applications.keycloak.issuer` as a whole mapping. With
  `--compiled`, `check` runs no Kapitan (RCP-34) and skips this rule and
  RCP-263.

  - Test: `check lint`; `check/tests/test_check.py` (`Meta`)
  - Since: this change

- RCP-263: `check lint` MUST run `kapitan inventory` on `tests/target.yml`
  with each backend of `backends`, and MUST fail when one of them does not
  resolve it.

  The proof compiles on omegaconf only. A further backend is checked to
  resolve the test target, not to resolve it to the same values; DEC-191
  compared the values once.

  - Test: `check lint`; `check/tests/test_check.py` (`Meta`)
  - Since: this change

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
users, and PyYAML. The Kapitan `next` image is pinned by digest in
`check/check.py`, and `--node-image` sets the kind node image (RCP-70).
helm, kubectl, kind, oras and gh come from `PATH`; CI installs them pinned
(RCP-28).

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

- RCP-29a: Before it runs the `next` image, `check` MUST verify the image's
  attestation with `gh attestation verify`, issued to the workflow
  `.github/workflows/next.yml` of kadet-hub/kapitan on `refs/heads/next`,
  and MUST fail when the verification fails.

  The digest pins what the image contains. The attestation shows where it
  was built: by that workflow, from the commit its provenance names. The
  image runs Kapitan on the recipe, so an image of unknown origin does not
  run, although its compile never decides (RCP-24). The workflow attests
  each build since kapicorp/kapitan#1637 added the step, and earlier
  builds have no attestation, so the pin moved to an attested build in
  this change. With the outputs given (RCP-34), `check` compiles nothing
  with `next` and verifies nothing.

  - Test: `check/tests/test_check.py` (`NextAttestation`); CI `check` job, report line `kapitan next`
  - Since: #84

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

- RCP-270: When a rollout at level `deploys` fails, `check` MUST add to
  its error the output of `kubectl describe` and the last 100 log lines of
  each container for every pod in the cluster that is neither ready nor
  completed.

  `check` deletes the cluster when the proof ends, so the error is all that
  remains of a pod that did not become ready. Up to check 0.15.0 a timeout
  printed only `timed out waiting for the condition`, as in the two
  failures DEC-195 explains. Pods of every namespace count, because a
  workload can wait for a prerequisite's pod. For a container that has not
  started, `kubectl logs` answers with the reason it waits, such as
  `ContainerCreating`, and the error carries that answer.

  - Test: `check/tests/test_check.py` (`RolloutFailure`)
  - Since: #104

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
  | Referenced Secret | a Secret only in the recipe that a pod of the chart side reads through a `secretKeyRef` | the chart reads a Secret that the user creates, RCP-243 |

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
  named `<namespace>-...` with the same webhooks. A Secret only in the
  recipe is accepted only as RCP-243 describes.

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
  - Since: #2; empty `securityContext`: #24; `rotationPolicy`: #30; Referenced Secret: #103

DEC-166: `check` accepts a Secret that only the recipe renders when pods
of the chart side read it by name (Referenced Secret, RCP-243). A chart
often takes credentials from a Secret that the user creates next to it,
through an `existingSecret` value or through extra environment variables
with a `secretKeyRef`. The chart renders no object for that Secret, and
the recipe, which takes the credentials as parameters, renders it. Until
this change a recipe could do this only where the chart could render the
same Secret itself from `tests/values.yaml`, as gitea does through
`extraDeploy` (DEC-38) and open-webui through `extraResources`.
stirling-pdf-chart 4.0.0 has no such value. Taking the credentials as
plain environment values was considered. A ref of the target would then
end up in the Deployment, which DEC-38 rejects. Requiring the chart to
render the Secret, through a change upstream, was considered as well. It
would hold the recipe back until the project releases the change. The
class checks the names and keys that the chart side reads, not the values,
as Secrets are compared by key (RCP-9).

- RCP-243: `check` MUST accept a Secret only in the recipe when a pod of
  the chart side in the Secret's namespace reads it by name, through
  `env[].valueFrom.secretKeyRef`, `envFrom[].secretRef` or a `secret`
  volume of a container or init container, and the Secret has exactly the
  keys those pods read. `envFrom` and a `secret` volume without `items`
  read every key. `check` MUST report each such Secret with the class
  Referenced Secret, and MUST fail on any other object only in the recipe.

  A reference on the recipe side alone does not count, because the recipe
  could otherwise add any Secret by reading it itself. A key that the
  chart side does not read is an extra value no source asked for, and a
  key it reads that the Secret lacks would stop the pod.

  - Test: `check/tests/test_compare.py` (`ReferencedSecret`); CI `check`
    job, report line `difference: Referenced Secret`
  - Since: #103

- AC-146 (RCP-243): `check/tests/test_compare.py` accepts a Secret that
  the chart side reads through `secretKeyRef`, `envFrom` and a `secret`
  volume with exactly its keys, and denies an unreferenced Secret, an
  extra key, a missing key, a reference on the recipe side only, a Secret
  in another namespace and an object of another kind. CI `check` passes
  for every recipe with the same verdict as before.

- RCP-13: A recipe's README MUST state its proof level, and CI MUST run
  `check` at that level for every recipe a pull request changes and for
  every recipe once a week. A change below `check/` or `.github/` changes
  every recipe.

  - Test: CI `select` job
  - Since: #2

- RCP-70: CI MUST run `check` for every recipe of RCP-13 once per
  Kubernetes minor in `kubernetes-versions.json` of
  kadet-hub/renovate-config, on that minor's node image and with the kind
  release the file names. `check` MUST name the node image in its report.

  The file lists the three minors upstream supports. Each has the newest
  patch that the latest kind release has a node image for, pinned by
  digest, and the file names that kind release with the SHA-256 of its
  binary (KV-1 to KV-6 in renovate-config's
  [spec](https://github.com/kadet-hub/renovate-config/blob/main/docs/specs/kubernetes-versions.md)).
  The `select` job fetches it at a commit of renovate-config, and the
  `check` job is a matrix of recipe and minor. Renovate moves the commit
  through the preset `github>kadet-hub/renovate-config`, which
  `renovate.json` extends, so a new minor replaces the oldest in one pull
  request.

  `renders` runs once per minor as well, because its dry run and the
  answers of `kubectl auth can-i` come from the node image's API server.
  `lint` starts no cluster and runs once.

  kind comes from the file, not from `.github/actions/tools`. kind's
  release notes bind a node image to the kind release that built it, and a
  kind pin of its own would let Renovate move kind without the images.
  Without `--node-image`, kind creates the clusters from its default image.

  kubectl stays on its pin of RCP-28, the newest minor. Against the oldest
  minor that is two minors apart, one more than the Kubernetes version skew
  policy supports for kubectl. The legs of the oldest minor show whether
  the kubectl commands of `check` and the smoke tests still work there.

  The URL in `select` names the commit followed by the comment
  `# kubernetes-versions-<date>`, the tag on that commit, which the preset
  matches.

  - Test: CI `check` job, one leg per minor, report line `node image`;
    `check/tests/test_check.py`; manual: Renovate dry run
  - Since: #59, #61

GitHub runs some `ubuntu-24.04` jobs on AWS, and the job log names the
cloud under `Runner Image Provisioner`. Those runners have a root
filesystem of 72 GB with 17 GB free. The runners on Azure have 91 to 92 GB
free. That held for all 116 jobs of three probes on a fork on 2026-11-05,
5 of them on AWS. Next to the images it pulls into the kind node, a proof
needs room for the node image (1.3 GB) and the Kapitan `next` image
(0.9 GB). Most recipes fit: in five CI runs of 2026-11-05, 19 legs of
other recipes ran on AWS and passed. paperless-ai of `paperless-ngx` does
not fit (DEC-195).

DEC-195: The `check` job removes the Android SDK, .NET, GHC and GHCup that
the runner image preinstalls when the root filesystem has less than 30 GB
free, before `check` runs. `paperless-ngx` failed twice in CI because
`rollout status` of `paperless-ngx-ai` timed out after 900 seconds (runs
41944637582 on 1.35 and 41971837975 on 1.37). Both legs ran on AWS. The
other 52 legs from 2026-11-04 to 2026-11-05 ran on Azure and passed. In
one of the probes, `check paperless-ngx --level deploys` on 1.37 failed
the same way on all 4 runners on AWS. The report of RCP-270 showed why:
containerd could not extract paperless-ai's PyTorch layer with
`no space left on device`, and the kubelet retried the pull until the wait
ended. After the removal, which left about 39 GB free, the check passed on
the same 4 runners. On Azure the removal frees 22 GB and took 32 to 196
seconds in 6 jobs, so the job skips it where the space is there. A longer
wait was considered. The pull fails, it is not slow. A larger runner was
considered too. It is billed per minute, while the standard runners are
free for this public repository.

- RCP-271: Before `check` runs, the CI `check` job MUST free disk space by
  removing preinstalled toolchains that `check` does not use, when the
  runner's root filesystem has less than 30 GB free.

  30 GB leaves room above what the proof of `paperless-ngx` needs. On kind
  1.36 the node held 16.6 GB while it pulled paperless-ai, sampled every 10
  seconds, and the node and Kapitan images add 2.2 GB.

  - Test: CI `check` job, the `df` output of the step; manual: the probe
    of DEC-195
  - Since: #104

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
| a service that runs a project this repository has a recipe for | the included recipe (RCP-47) | The parent connects through the Service and Secret that recipe renders (DEC-12, DEC-20). |
| relative bind mount of a directory the pinned repository does not contain | `volume_claims` with `volume_mounts`, as a named volume | Docker creates the directory empty (DEC-21). |
| the image's `HEALTHCHECK`, where the service sets no `healthcheck` | as `healthcheck` | Compose runs the image's check unless the service overrides it. |
| `name` at the top level | nothing | It names the compose project, whose name compose puts before its networks and volumes. RCP-3 names the objects. |
| `env_file` of a file that the pinned repository does not contain | `env` from the example file that the documentation copies to it | `docker compose config` fails without the file. |
| the SELinux option `z` or `Z` of a bind mount | nothing | It relabels the host directory for the container. On an SELinux node the container runtime labels a pod's volumes. |
| relative bind mount of a settings directory that the pinned repository does not contain and the image's entrypoint fills from its own template | `config_maps` with the template's settings, `mount` at the target | DEC-23. The README names the template with its SHA-256. |
| `cap_add` of capabilities that the documentation names as optional or as needed only for a feature the recipe does not set up | nothing | DEC-29. The README names each capability and what it would add. |
| `init: true` where the image's start script runs the server as PID 1 and the server ends on `SIGTERM` | nothing | DEC-120 |
| `depends_on` with `condition: service_healthy` on a service that becomes an included recipe, where the dependent exits while that service does not answer | an init container of the dependent's image that waits until the included recipe's Service accepts connections | DEC-121. It adds no image. |
| bind mount of a file that the pinned repository does not contain, which the documentation copies from a file the image carries byte for byte at the mount target | nothing | DEC-301. The README names the file and its SHA-256. |

What the table does not map is a gap, and so is each of these:

| Compose | Why it stops |
|---|---|
| `build` without a published `image` | There is no image to pin |
| `network_mode` | `host` puts the pod on the node's network, `service:` and `container:` share a network namespace, which only containers of one pod can |
| bind mounts of directories the pinned repository contains, of absolute paths or of paths outside the repository, the Docker socket among them | They carry content or host state that a recipe cannot, and a hostPath reaches the node (RCP-20) |
| `privileged`, `cap_add` other than above, `devices`, `pid: host`, `ipc: host` | They widen what a container may do on the node and need a review a migration cannot replace |
| `networks` that separate services, `aliases`, fixed addresses, external networks | Services in one namespace reproduce only the DNS names. Nothing would prove the isolation. |
| `extends` or `include` of a file outside the pinned repository | The content is not pinned |
| a named volume of several services | `ReadWriteOnce` cannot be shared across nodes, and kind has no `ReadWriteMany` storage to prove it on |
| `working_dir` | The `kubernetes` generator 1.7.0 has no key for `workingDir`. It is a generator request. |

- RCP-37: A compose recipe MUST map every key of its compose file as the
  table above says. A key the table does not map, or one of the gaps,
  MUST stop the migration with a report, and no recipe is written.

  A gap is reported to kadet-hub/registry like a missing generator
  (RCP-7). A mapping is added to the table only with the migration that
  needs it. Revised in #63: the included recipe, the bind mount
  of a directory the repository does not contain, which was a gap, and
  the image's `HEALTHCHECK`, all for paperless-ngx. Revised in #66: the
  project `name`, an `env_file` the repository does not contain, the
  SELinux option and the settings directory, all for searxng.
  Revised in #68: `cap_add` of optional capabilities, which was a gap,
  for pihole (DEC-29). Revised in #91: `init`, which was a gap,
  and the wait for an included recipe's database, both for umami
  (DEC-120, DEC-121). Revised in #118: the bind mount of a file
  the image carries, for ejabberd (DEC-301).

  - Test: manual: review against the compose file
  - Since: #8; included recipe, directory bind mount, `HEALTHCHECK`: #63;
    `name`, missing `env_file`, SELinux option, settings directory: #66;
    `cap_add`: #68; `init`, wait for the database: #91; file the image
    carries: #118

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

The readiness probe connects to the API's port 8081. pdns_server opens it
after port 53: in five starts of the pinned image, 53 accepted connections
after 0.08 to 0.13 seconds and 8081 about 0.03 seconds later. With the
probe on port 53, the CI run on main of 2026-11-04 marked the pod ready on
Kubernetes 1.37 before the API listened, and `tests/smoke` got `Connection
refused` from it. Changed in #83.

`pdnsutil zone create` writes the SOA from the setting
`default-soa-content`. Its default,
`a.misconfigured.dns.server.invalid hostmaster.@ 0 10800 3600 604800 3600`,
names a placeholder primary in the reserved top-level domain `.invalid`.
powerdns 1.0.0 and 1.0.1 and the kadet-hub/examples recipe created their
zones with that primary. The init container `zone` replaces it with
`ns1.<zone>.` through `pdnsutil rrset replace`, on the zone it has just
created and on a zone an earlier version created. TTL, hostmaster, serial
and timers stay. The serial does not rise, because the recipe sets up no
secondary that would need it to transfer the change. An SOA with another
primary was set by the operator and stays as it is. Changed in #92.

Setting `default-soa-content` to `ns1.@ hostmaster.@ ...` was considered.
pdnsutil 5.1 reads settings only from its configuration file, so the init
container would have to write one, and the setting does not change a zone
that exists.

The zone has no address record for `ns1.<zone>`. Clients reach PowerDNS at
an address the target decides, such as the cluster IP of the Service
`powerdns` or a load balancer, and a Service created anew gets another
cluster IP. The recipe has no address it could write, and its README names
this as a constraint.

- RCP-194: The init container `zone` of `powerdns` MUST create the zone
  `applications.powerdns.zone` with an SOA record whose primary is
  `ns1.<zone>.` and whose hostmaster is `hostmaster.<zone>.`.

  - Test: `powerdns/tests/smoke` reads the SOA through the Service
    `powerdns`; CI `check` job of `powerdns` and `external-dns-powerdns`
  - Since: #92

- RCP-195: When the SOA of the zone `applications.powerdns.zone` names the
  primary `a.misconfigured.dns.server.invalid.`, the init container `zone`
  MUST replace that primary with `ns1.<zone>.` and keep the rest of the
  record. It MUST NOT change an SOA with another primary.

  - Test: manual: on kind, the claim of powerdns 1.0.1 started with this
    version, then an SOA with another primary set through the API and the
    pod restarted (#92)
  - Since: #92

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
`powerdns`. Both recipes pin the same `kubernetes` generator (RCP-48), so
`powerdns` moved from 1.8.0 to 1.9.0 in the same change. The chart
installs the CRDs of DNSEndpoint and DNSRecord from its `crds/` directory
with every release.
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

Every recipe moved from the `kubernetes` generator 1.9.0 to 1.14.0 in one
change. 1.14.0 is the first version with the container keys `tty` and
`stdin` (K8S-16 in kadet-hub/generators), which `open-webui` needs for the
chart's `tty: true`. The changelogs from 1.9.1 to 1.14.0 state unchanged
output for inventories without their new keys, and no recipe sets one. A
compile of every recipe's `tests/target.yml` with Kapitan 0.36.3 gave the
same bytes with both versions.

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
  afterwards by the digest that the parent's index record lists, which the
  registry's consumer workflow adds itself (CON-7 in kadet-hub/registry).

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

## Miniflux

`miniflux` is the first compose recipe (Compose sources). It maps
`contrib/docker-compose/basic.yml` of miniflux/v2 at
`238c5614e584ebc87894e7d9f10bc91373a0b2c2`, the commit of the tag 2.3.4.
The file's health check of the service `miniflux` is commented out, so
version 1.0.0 rendered no probe for miniflux. Its pod was ready as soon as
the container ran.

At a start, miniflux pings PostgreSQL, runs its migrations with
`RUN_MIGRATIONS=1`, creates the admin account with `CREATE_ADMIN=1`, and
only then listens on port 8080. While the database does not answer, it
exits with status 1 and the kubelet restarts it (`internal/cli/cli.go`).
`rollout status` therefore returned while miniflux did not listen. In the
compose example of kadet-hub/examples#147 and in the job
`check miniflux --level deploys on 1.37` of #101, `kubectl port-forward`
in `tests/smoke` reached the pod in that state, got `connection refused`
and ended.

`/healthcheck` answers `OK` with status 200 once miniflux reaches its
database, and 503 while it does not (`internal/http/server/healthcheck.go`).
The commented check of the compose file, `miniflux -healthcheck auto`,
requests that path on the first address of `LISTEN_ADDR`, below the path
of `BASE_URL`, and fails after 3 seconds without an answer
(`internal/cli/health_check.go`). The Docker page of the Miniflux
documentation offers the same check for a compose file.

DEC-200: `miniflux` has one probe, a readiness probe that runs
`/usr/bin/miniflux -healthcheck auto` in the container, every 30 seconds
with a timeout of 30 seconds and 3 failures. It is the check that the
compose file comments out, mapped as Compose sources map a
`healthcheck`, with the compose defaults for interval, timeout and
retries, since the check sets none. The pod becomes ready once miniflux
has migrated its database and answers, so `rollout status` waits for both.
The check follows `LISTEN_ADDR` and `BASE_URL` of the container. An HTTP
probe on `/healthcheck` was considered. It would make the same request from
the kubelet without a second process, but a target that sets `BASE_URL`
with a path would have to move the probe as well. The compose component of
kadet-hub/examples#147, which turns the recipe's probes back into compose
health checks, takes only command probes. `/readiness` answers like
`/healthcheck` at the root regardless of `BASE_URL`, and the API
documentation names it for Kubernetes, but no compose file uses it. A
liveness probe on the check would restart miniflux whenever PostgreSQL
does not answer, and compose never restarts an unhealthy container.

DEC-201: `miniflux` keeps `RUN_MIGRATIONS=1` and `CREATE_ADMIN=1` on its
container. The README tells a target with more than one replica to start
with one, on an empty database and for an upgrade with new migrations.
miniflux 2.3.4 takes no lock for either. It reads the
schema version outside the transactions of its migrations
(`internal/database/database.go`), and it creates the admin account after
checking that it does not exist (`internal/cli/create_admin.go`). Several
pods that start on an empty database therefore run the same migrations or
create the same account. All but one fail, exit and restart, as the
multi-environment example of kadet-hub/examples#150 saw once or twice per
run. On kind 1.37, with the database ready before miniflux started, three
replicas started at once restarted in 5 of 5 runs. Two of the three pods
restarted each time, 12 restarts in all, each after a migration failed
with `duplicate key value` or `already exists`, and all three pods became
ready. One replica that was scaled to three once its pod was ready
restarted in none of 5 runs. The Miniflux documentation names `miniflux
-migrate` or `RUN_MIGRATIONS=1` as the step before the start
(`content/docs/upgrade.md` of miniflux/website), and nothing for several
instances. A Job that runs `miniflux -migrate` was considered. Pods
without `RUN_MIGRATIONS` exit while the schema is behind
(`IsSchemaUpToDate`), so they would restart until the Job finished, and
the admin account would still race. Pods cannot wait for the Job without
access to the API, which a compose recipe does not get (RCP-38). A
StatefulSet, whose pods start one after another, was considered too. The
Deployment of every installed version would keep running next to it, and
miniflux keeps no state of its own.

- RCP-280: `miniflux` MUST have the readiness probe of DEC-200 on the
  container `miniflux`, and no liveness or startup probe.

  - Test: RCP-281; CI `check` job, which waits for the rollout before
    `tests/smoke`
  - Since: #107

- RCP-281: Before its first request, the `tests/smoke` of `miniflux` MUST
  fail when the Deployment `miniflux` has no readiness probe that runs
  `/usr/bin/miniflux -healthcheck auto`.

  Without the probe the rest of the test passes whenever miniflux listens
  by the time it connects, so the race shows only in some runs. On kind
  1.37 with both images pulled, ten fresh namespaces per variant went
  through what `check` does after the apply: `rollout status` of
  `miniflux-db` and `miniflux`, then `tests/smoke` of version 1.0.0.
  Without the probe, `miniflux -healthcheck auto` in the pod failed right
  after the rollouts in 10 of 10 runs, and the smoke test failed in 1 with
  `connection refused`. With the probe the check passed in 10 of 10 runs,
  and so did the smoke test. The rollouts took 45 to 73 seconds with the
  probe and 15 to 43 seconds without it, because the probe runs every 30
  seconds.

  - Test: manual (#107): `tests/smoke` against miniflux 1.0.0 on kind fails at
    the probe; CI `check` job
  - Since: #107

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

## PostgreSQL with pgvector

pgvector adds the column type `vector` and nearest-neighbour indexes to
PostgreSQL. Immich stores the embeddings of its smart search and face
recognition in such columns and, as of v3.3.5, takes pgvector 0.5 or later
below 1.0 when VectorChord is not available (`VECTOR_VERSION_RANGE` in
`server/src/constants.ts` of immich-app/immich). `postgresql` has the option
`pgvector`, which a target or a parent includes as
`recipes.postgresql.pgvector`.

The image needs no change. `postgresql` pins
`ghcr.io/cloudnative-pg/postgresql:18.6-system-trixie`. CloudNativePG
builds its `system` images on the `standard` ones, which ship pgvector
(`README.md` of cloudnative-pg/postgres-containers). The pinned digest
carries the package `postgresql-18-pgvector` 0.8.7. pgvector's control file
does not mark the extension as trusted, so only a superuser can create it.
The owner `app` that CloudNativePG creates is no superuser.

DEC-46: The option creates the extension through the Cluster's
`bootstrap.initdb.postInitApplicationSQL`, which CloudNativePG runs as
superuser in the application database once, right after it has created
the Cluster. The chart renders the same statement from
`cluster.initdb.postInitApplicationSQL`. On a Cluster that exists already
the option has no effect, and a superuser runs the statement by hand, as
the README says. A `Database` object with `extensions` was considered.
The operator would reconcile it on a running Cluster as well, and both the
`cloudnative-pg` generator 1.1.0 and the chart's `databases` value render
it. Its `spec.template` is the name of a database template, a string,
and `check` reads every `spec.template` as a pod template. `lint_output`
in `check/lint.py` and `pod_templates` in `check/compare.py` stop on it
with `AttributeError`, so the object needs a `check` change first.

`tests/target.yml` of `postgresql` includes the option, so
`check postgresql` proves the Cluster with the statement. A parent that includes
`recipes.postgresql` alone compiles the same Cluster without it.

- RCP-100: With the option `pgvector`, `postgresql` MUST render its Cluster
  with `CREATE EXTENSION IF NOT EXISTS vector` in
  `bootstrap.initdb.postInitApplicationSQL`. Without the option it MUST
  NOT render that statement.

  - Test: `check postgresql`; manual: a compile of `tests/target.yml`
    without the option
  - Since: #71; "that statement": #73

- RCP-101: The `tests/smoke` of `postgresql` MUST, as the owner through
  `postgresql-cluster-rw`, require that `pg_extension` of the database
  lists `vector` and compute the distance between two vectors.

  The owner cannot create the extension, so a listed `vector` shows that
  the statement ran as superuser. The distance shows that the owner can use
  the type.

  - Test: CI `check` job, report line `smoke`
  - Since: #71

- AC-50 (RCP-100, RCP-101): `check postgresql --level deploys` passes in
  CI on each Kubernetes minor, and its smoke test reports the version of
  `vector`. On a cluster kept with `--keep`, `tests/smoke` fails after
  `DROP EXTENSION vector` as superuser.

### The option `earthdistance`

earthdistance computes great-circle distances on the surface of the
Earth, built on the type `cube`. Both are contrib modules of PostgreSQL in
the pinned image. Immich v3.3.5 creates both in its first migration
(`@Extensions` in `server/src/schema/index.ts`) and uses earthdistance for
reverse geocoding (`server/src/repositories/map.repository.ts`). `cube`
is a trusted extension, which the owner may create. `earthdistance` is
not, and Immich as `app` stopped on kind with `permission denied to create
extension "earthdistance"`.

The option `earthdistance`, included as `recipes.postgresql.earthdistance`,
adds `CREATE EXTENSION IF NOT EXISTS earthdistance CASCADE` to the
Cluster's `postInitApplicationSQL`, as DEC-46 does for `vector`. CASCADE
creates `cube` with it. The omegaconf backend extends the list with the
statements of each option in the order the target includes the classes.
`tests/target.yml` includes `pgvector` first, and `tests/values.yaml`
lists the two statements in the same order.

- RCP-102: With the option `earthdistance`, `postgresql` MUST render its
  Cluster with `CREATE EXTENSION IF NOT EXISTS earthdistance CASCADE` in
  `bootstrap.initdb.postInitApplicationSQL`, and without it MUST NOT. Its
  `tests/smoke` MUST, as the owner, require that `pg_extension` lists
  `cube` and `earthdistance` and compute a distance with `earth_distance`.

  - Test: `check postgresql`; CI `check` job, report line `smoke`;
    manual: a compile of `tests/target.yml` without the option
  - Since: #73

- AC-52 (RCP-102): `check postgresql --level deploys` passes in CI on each
  Kubernetes minor, and its smoke test reports `earthdistance`. On a
  cluster kept with `--keep`, `tests/smoke` fails after
  `DROP EXTENSION earthdistance` as superuser.

## Immich

Immich manages photos and videos. Clients upload them through its API, the
server keeps the files on its library volume and their metadata in
PostgreSQL, and background jobs create thumbnails and, through the machine
learning service, the embeddings of smart search and face recognition.
`immich` deploys it from the chart `immich` 0.13.4 of
immich-app/immich-charts, which Immich publishes at
`oci://ghcr.io/immich-app/immich-charts/immich`. It was the newest release
on 2026-11-03. The chart builds on the bjw-s common library 5.2.1, which
it carries as a subchart. Chart and Immich are AGPL-3.0. The recipe
carries no template, file or values text of the chart, so DEC-16 applies
as for nextcloud.

DEC-47: `immich` runs Immich v3.3.5 instead of the chart's v3.2.0.
GHSA-q89f-h332-8q2h, rated high, lets an authenticated user run code in
the server's container through an SVG upload that reaches ImageMagick. It
names v3.2.2 as affected and v3.2.4 as fixed and gives no lower bound, so
v3.2.0 is probably affected. v3.3.5 of 2026-10-21 was the newest release
on 2026-11-03, and v3.4.0-rc.1 is a release candidate. The chart's README
asks its users to set the image tag, because the chart does not follow
every Immich release. `tests/values.yaml` sets `v3.3.5` for the server and
machine learning, and the recipe pins both images to their indexes for
amd64 and arm64. The images do not follow the chart's version, so
Renovate moves them and the tag in `tests/values.yaml` together (RCP-16). The chart's v3.2.0 was considered. It would run a version with a
known path to code execution.

### Database and queue

The database is the included recipe `postgresql` with its options
`pgvector` and `earthdistance` (DEC-4, DEC-12, PostgreSQL with pgvector).
Immich creates its other extensions, `uuid-ossp`, `unaccent`, `cube` and
`pg_trgm`, itself, since they are trusted. The chart renders no
database and passes `DB_*` variables to the server, which
`tests/values.yaml` points at `postgresql-cluster-rw`, the database `app`
and the keys `username` and `password` of the Secret
`postgresql-cluster-app`. The recipe reads these names from
`applications.postgresql` (RCP-60).

DEC-48: `immich` stores its embeddings with pgvector and sets
`DB_VECTOR_EXTENSION=pgvector`. Immich v3.3.5 takes VectorChord or
pgvector. Without the variable it takes VectorChord when the server offers
it, and otherwise pgvector (`getVectorExtension` in
`server/src/repositories/database.repository.ts`). The image of
`postgresql` ships pgvector 0.8.7, inside the range `>=0.5 <1` that Immich
accepts. Neither extension is trusted, so a superuser creates it, which
the option `pgvector` does. The variable keeps Immich on that extension
when the image changes. VectorChord, which Immich's documentation and the
chart's example cluster use, was considered. It needs an image with
VectorChord, or an image volume, and `vchord.so` in
`shared_preload_libraries`, which `postgresql` does not render. Immich's
documentation describes VectorChord as faster and lighter on memory than
pgvecto.rs, but publishes no comparison with pgvector. Moving to
VectorChord later means installing it and letting Immich rebuild its
indexes `clip_index` and `face_index` ("Migrating from pgvector" in
`docs/docs/administration/postgres-standalone.md`).

Immich connects as `app`, the owner of the database, which is no
superuser, the setup that Immich's documentation calls "without superuser
permission". Its nightly database backup, on by default at 02:00, runs
`pg_dump` of the one database (`createDatabaseBackup` in
`server/src/services/database-backup.service.ts`) and works as `app`. On
kind a backup started through `POST /api/jobs` wrote
`immich-db-backup-...-v3.3.5-pg18.6.sql.gz` below `/data/backups` on the
library claim. The documentation still says that backups need a superuser
for `pg_dumpall`, which v3.3.5 does not run. A restore through Immich
replays the dump with `psql` as `app`. The dump starts with
`DROP EXTENSION IF EXISTS vector` and the same for `earthdistance`, which
`app` may not run on the extensions the superuser created, so the restore
is expected to fail. It is not tested. A backup of the Cluster itself
follows DEC-18.

Without `DB_SSL_MODE` Immich connects without TLS. CloudNativePG serves
TLS, and `tests/values.yaml` sets `require`, which postgres.js 3.4.9, the
driver of Immich v3.3.5, maps to TLS without verifying the server's
certificate (`secure` in `src/connection.js`), as `semaphore` does with
`sslmode=require`. On kind every connection of `app` used TLS by
`pg_stat_ssl`.

The queue is the included recipe `valkey`. The chart's own Valkey is off
by default, and its `REDIS_HOSTNAME` names `immich-valkey`.
`tests/values.yaml` sets `REDIS_HOSTNAME` to `valkey` for both components,
as the chart sets it, and `REDIS_PASSWORD` for the server from the key
`default-password` of `valkey-auth`, with which Immich authenticates as
Valkey's user `default`. Immich queues its background jobs there, the
thumbnails among them.

### Storage and machine learning

The chart mounts the library at `/data` from a claim that must exist and
renders none. Its README asks users to create one and name it in
`immich.persistence.library.existingClaim`, and the chart stops without
it. A claim that only the recipe rendered would fail `check` as an object
only in the recipe (RCP-12).

DEC-49: `immich` renders the PersistentVolumeClaim `immich-library`, 10Gi
with `ReadWriteOnce`, and `tests/values.yaml` creates the same claim
through the bjw-s library's `rawResources` under `server`, with
`existingClaim: immich-library`. `rawResources` renders a manifest as it
is given, with the library's labels, which RCP-9 leaves out of the
comparison. `check` then compares the claim like the chart's own objects,
as `gitea` creates its admin Secret through `extraDeploy` (DEC-38). A
required parameter that names an existing claim, as the chart has it, was
considered. `check` could not reach `deploys` with it, because the server
stays Pending until a claim exists. A `persistence` entry of the bjw-s
library, which renders claims, was considered as well. The chart always
adds the entry `data` with `existingClaim`, so a second entry would be a
second volume of the pod.

Machine learning is on by default and runs on the CPU. The server calls
it at `http://immich-machine-learning:3003` for smart search and face
recognition. Its image is 268 MB compressed for amd64 and 241 MB
for arm64, the server's 609 MB and 360 MB (sums of the layer sizes in the
registry manifests, MB = 10^6 bytes). It downloads its models from Hugging
Face into the emptyDir `/cache` when the first job needs them, so every
new pod downloads them again. Their size and the download in CI are not
measured. GPU images and hardware acceleration are not tested, because
kind has no GPU.

The chart's Ingress, its ServiceMonitors behind `immich.metrics.enabled`
and the configuration file behind `immich.configuration` are off by
default and not part of the recipe. The ServiceAccounts `immich-server`
and `immich-machine-learning` have no Role. The chart renders no hook.

### Proof

`immich` is at level `deploys`. `tests/target.yml` runs one PostgreSQL
instance.

- RCP-103: `immich` MUST point the server at the Service, the database and
  the Secret of `postgresql` with `DB_VECTOR_EXTENSION=pgvector` and
  `DB_SSL_MODE=require`, and at the Service `valkey` with the password of
  `valkey-auth`. It MUST include `recipes.postgresql.pgvector` and
  `recipes.postgresql.earthdistance`.

  - Test: `check immich`; `tests/smoke`
  - Since: #74

- RCP-104: The `tests/smoke` of `immich` MUST require `pong` from
  `/api/server/ping` of the server and `/ping` of machine learning through
  their Services, and that `/api/server/version` reports the version of
  the image tag the Deployment runs. It MUST sign up the admin through
  `/api/auth/admin-sign-up`, log in through `/api/auth/login`, upload a
  JPEG through `POST /api/assets`, and read back the asset's details with
  its SHA-1, the original byte for byte and a thumbnail. Every connection
  of `app` to PostgreSQL MUST use TLS.

  A login with a wrong password gets 401. The asset's details come from
  PostgreSQL and the original from the library claim. The server creates
  the thumbnail in a job that it queues in Valkey, so the thumbnail shows
  that the queue works. On kind with Valkey scaled to zero the upload
  itself failed with 500. The test does not wait for the machine learning
  jobs, which need the models from Hugging Face.

  - Test: CI `check` job, report line `smoke`
  - Since: #74

- AC-51 (RCP-103, RCP-104): `check immich --level deploys` passes in CI
  on each Kubernetes minor, its report lists the objects of `postgresql`
  and `valkey` as included and `cnpg` as installed, and its smoke test
  reads back the thumbnail of the asset it uploaded.

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
| `keycloak-operator` | `oci://quay.io/keycloak/keycloak-operator-helm:26.8.1@sha256:779b9309eb6fb3710110b2a92af2ca34b845c1f156fdbfef994efa7158e4fc71`, from keycloak/keycloak, Apache-2.0 | prerequisite of `keycloak`: the operator, its RBAC and, as option `crds`, its four CRDs |
| `keycloak` | `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332` | one `Keycloak` resource and its certificate and, as option `route`, an HTTPRoute; includes `postgresql`, requires `keycloak-operator`, `cert-manager` and `gateway-api` |

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
`<name>-service` on port 8080 (DEC-17). The `kubernetes` generator 1.14.0
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
1.14.0, and its two Certificates and the Issuer with the `certmanager`
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

## Paperless-ngx

Paperless-ngx is a document management system that runs OCR on scanned
documents and keeps them searchable. The project publishes no chart. Its
repository ships compose files in `docker/compose/`, one per database, each
also in a variant with Tika and Gotenberg for office documents.
`paperless-ngx` takes `docker-compose.postgres.yml` of v3.4.1, the newest
release on 2026-11-03, at commit `b67cfdf3fdfcde4883c4ac136c8545835f679d21`,
SHA-256 `85206b8ae6cd74db70998de6479b4c1f7b50c077772a1af2c026c9ecb35b689c`.
Its `env_file`, `docker-compose.env` in the same directory, sets only
`PAPERLESS_SECRET_KEY`, to `change-me`. Every compose file of the directory
also mounts the directories `./export` and `./consume`, which the
repository does not contain (DEC-21). The compose file and the image are
GPL-3.0. The recipe takes from them what the image dictates, such as
variable names, paths and the port, and copies no text, as DEC-16 reads it
for a copyleft chart.

| Service | Recipe |
|---|---|
| `webserver`, `ghcr.io/paperless-ngx/paperless-ngx:latest` | StatefulSet `paperless-ngx` on `3.4.1`, the tag `latest` pointed to, with the claims `data`, `media`, `consume` and `export` |
| `db`, `docker.io/library/postgres:18` | the included recipe `postgresql` (DEC-20) |
| `broker`, `docker.io/valkey/valkey:9-alpine` | the included recipe `valkey` (DEC-20) |

Paperless-ngx reads the database's host, name, user and password from the
Secret `<cluster>-app` of `postgresql`. The compose file sets the host `db`
and relies on the image's default `paperless` for the rest. It reaches
Valkey as `redis://:<password>@valkey:6379`, with the password from the
Secret `valkey-auth`, where the compose file has `redis://broker:6379`. The
password is part of a URL, so it must not contain characters a URL
reserves. The image's `HEALTHCHECK` requests port 8000 with `curl` and
becomes the readiness probe. The image starts as root and runs
paperless-ngx as the user `paperless`, UID 1000, so the target's namespace
needs the Pod Security level `baseline`. The compose file creates no
account. Paperless-ngx asks for a superuser on the first visit of its web
interface.

### The option `ai`

paperless-ai, MIT, analyzes the documents of a paperless-ngx instance with
an LLM and sets their title, tags and correspondent through the
paperless-ngx API. Its newest release is 3.0.9 of 2025-11-04, which the
option runs as
`docker.io/clusterzx/paperless-ai:3.0.9@sha256:2b65888163fd59716f1c8285b31c5bd0b30c9c3c192c42b516688e3887d4ba60`.
Its amd64 image is 4.3 GiB compressed, as it carries PyTorch next to
Node.js, and 8.2 GiB unpacked. containerd keeps a compressed layer until
it has unpacked it, so the pull needs about 12 GiB on the node at once.
The arm64 image is 0.6 GiB. On start its search service downloads two
models from Hugging Face.

The option, which a target includes as `recipes.paperless-ngx.ai`, renders
the StatefulSet `paperless-ngx-ai` with the claim `data` at `/app/data`, its
Service on port 3000 and the Secret `paperless-ngx-ai`, mounted as
`/app/data/.env` (DEC-22). The file points paperless-ai at
`http://paperless-ngx:8000/api` with the provider `custom`, which takes any
OpenAI-compatible endpoint, Ollama's among them. The target sets the rest:
the paperless-ngx user and its API token, the endpoint, the model, its API
key, and `JWT_SECRET`, which signs the logins of paperless-ai's web
interface and is a fixed string when unset (`routes/auth.js` of
clusterzx/paperless-ai 3.0.9).

paperless-ai checks the file at start: the token against `/api/documents/`
and one chat completion at the endpoint. It repeats the check every 5
seconds, up to 60 times, and then stays unconfigured until it restarts.
Once configured, it analyzes the documents at start and every 30 minutes.
Its `HEALTHCHECK`, `/health`, becomes the readiness probe and checks only
paperless-ai's own database. The route that `routes/setup.js` serves has
the configuration check commented out.

`/setup` answers without a login. A `POST` to it points paperless-ai's API
client at the URL it names until the pod restarts, before writing the file
fails. The web setup creates the login user only after it has written the
file, so with the option the web interface has no user. The tagging runs
without one. The image sets no `USER`. The option drops every capability
and privilege escalation, as paperless-ai's own compose file does.

- RCP-72: With the option `ai`, `paperless-ngx` MUST render paperless-ai
  with `/app/data/.env` from a Secret, whose values come from
  `applications.paperless-ngx.ai.user`, `.token`, `.url`, `.model`,
  `.api_key` and `.jwt_secret`, which the target sets. Without the option
  it MUST render no object of paperless-ai.

  - Test: `check paperless-ngx`; manual: compile of `tests/target.yml`
    without the option
  - Since: #63

### Proof

`paperless-ngx` is at level `deploys`, with `cnpg` installed through
`postgresql`. `tests/target.yml` sets a secret key other than the compose
file's `change-me`, which paperless-ngx 3.4.1 refuses at start
(`src/paperless/settings/__init__.py`), runs one PostgreSQL instance and
includes the option `ai`. It adds two
components that only the proof uses. `paperless-ngx-llm` runs busybox's
`httpd` with a script that answers every chat completion with the same
reply, the title `tagged by paperless-ai`. The Job `paperless-ngx-token` waits until paperless-ngx has migrated
its database, then creates the superuser `admin` and its API token with
the value the option's settings name, through `manage.py shell`. A real
LLM is not tested.

- RCP-73: The `tests/smoke` of `paperless-ngx` MUST copy a PDF into the
  claim `consume` and find the document by its text through
  `/api/documents/` on the Service port as the superuser. With the option
  `ai` it MUST restart `paperless-ngx-ai` once the document exists, reach
  `/health` through its Service, and then find the document under the
  title of the endpoint's reply through the API.

  Consuming the file needs the consumer, the task queue in Valkey, the
  database and the claim `media`. The title needs paperless-ai to read the
  document with the token, call the endpoint and write the title back.
  paperless-ai gives up on the API after its 60 tries and analyzes at
  start, and on kind its pod can start minutes before paperless-ngx
  answers, so the restart makes the check independent of that order.

  - Test: CI `check` job
  - Since: #63

## SearXNG

SearXNG is a metasearch engine. It sends a query to other search engines
and merges their results without tracking its users. The project publishes
no chart and no releases. Every commit on `master` is published as the
image `docker.io/searxng/searxng`, tagged `<date>-<commit>` and `latest`.
Its compose file is `container/docker-compose.yml` of searxng/searxng. That
file replaced searxng/searxng-docker, now archived with a notice of
2026-03-28 that points to it, whose compose file also ran Caddy as a
reverse proxy.
`searxng` takes the file at commit `cccbc9e158b0ac3bb2158e9841a647a5bec57b57`
of 2026-11-02, SHA-256
`0e56d5fa968a06e441353261f3134e7cea620c8a81d45a890842aef6c4d3ee11`. The
commit is the `org.opencontainers.image.revision` of the image
`2026.11.2-cccbc9e15`, which `latest` pointed to on 2026-11-03. The compose
file and the image are AGPL-3.0-or-later.

| Service | Recipe |
|---|---|
| `core`, `docker.io/searxng/searxng:latest` | StatefulSet `searxng` on `2026.11.2-cccbc9e15`, with the claim `core-data` and `/etc/searxng` from the ConfigMap `searxng` (DEC-23) |
| `valkey`, `docker.io/valkey/valkey:9-alpine` | the included recipe `valkey` (DEC-20), which SearXNG connects to (DEC-24) |

The current compose file has no proxy service. The documentation leaves a
reverse proxy to the operator of a public instance. The recipe leaves
exposure to the target, as the `ports` row of Compose sources says.

The compose file bind-mounts `./core-config/` at `/etc/searxng`. The
documentation creates the directory empty and has the user write
`settings.yml` there. On a start without that file the entrypoint copies
the image's `settings.template.yml` and replaces its `secret_key` with a
random string. The recipe's ConfigMap holds the template's two settings,
`use_default_settings: true` and `server.image_proxy: true`. They are
values the image dictates, not text under RCP-42. The template enables only
the format `html`, so `/search?format=json` answers 403 until the target's
settings add `json`.

The secret key signs the URLs of the image proxy and hashes the names of
the keys SearXNG writes to Valkey. It is `applications.searxng.secret_key`,
which the target sets. It reaches SearXNG as `SEARXNG_SECRET`, which
overrides `server.secret_key` of the file (`searx/settings_defaults.py`).

SearXNG reaches Valkey through `SEARXNG_VALKEY_URL`,
`valkey://:<password>@valkey:6379/0`, with the password from the Secret
`valkey-auth`. The password is part of a URL, so it must not contain
characters a URL reserves. With the limiter off, as in the template,
SearXNG stores only the token of its link-token check there, whenever it
renders an HTML page (`searx/botdetection/link_token.py`). It checks the
connection once at start. If Valkey does not answer then, SearXNG runs
without it until it restarts (`searx/valkeydb.py`). The compose service's
arguments `--save 300 1 --save 60 1000 --loglevel warning` are not
rendered, because `valkey` keeps its own configuration (DEC-12).

- RCP-74: `searxng` MUST mount `settings.yml` from the ConfigMap `searxng`
  at `/etc/searxng` and set `SEARXNG_SECRET` from
  `applications.searxng.secret_key`, which the recipe leaves unset.

  Without the key the compile stops with
  `Interpolation key 'applications.searxng.secret_key' not found` (RCP-19,
  RCP-40).

  - Test: `check searxng`; manual: compile of `tests/target.yml` without
    the key
  - Since: #66

- RCP-185: `searxng` MUST have a readiness probe on `/healthz` of the
  port `http`, and no liveness probe.

  The compose file and the image define no health check. Without a
  readiness probe `rollout status` returned before SearXNG answered, which
  the open-webui-searxng example in kadet-hub/examples ran into. `/healthz`
  answers `OK` once the web app serves requests and does not depend on
  Valkey or on the search engines. A liveness probe on it would restart a
  pod that is only slow, which nothing upstream asks for.

  - Test: `check searxng` (`rollout status`, then RCP-75)
  - Since: #87

### Proof

`searxng` is at level `deploys`. `tests/target.yml` sets the secret key and
the Valkey password, and replaces the settings with the recipe's plus the
format `json`.

- RCP-75: The `tests/smoke` of `searxng` MUST get `OK` from `/healthz`
  through the Service and search for `kubernetes` with `format=json`
  through the Service, requiring the query and a list of results in the
  response. After it loads the start page, it MUST find the link token
  `SearXNG_limiter.token` in Valkey.

  The search engines may not answer from a CI runner, so the results may
  be empty and are not counted. The token needs SearXNG to reach Valkey
  with the password from `valkey-auth`. SearXNG checks that connection only
  at start, and on kind its pod can start before Valkey answers, so the
  smoke test restarts it first.

  - Test: CI `check` job
  - Since: #66

## Blackbox exporter

The Prometheus blackbox exporter probes a target that a request names,
such as `/probe?target=<url>&module=http_2xx`, and answers with metrics
like `probe_success`. Prometheus scrapes it once per target.
`blackbox-exporter` deploys it from the chart `prometheus-blackbox-exporter`
11.20.2 of prometheus-community/helm-charts, Apache-2.0, which runs
blackbox_exporter 0.29.1.

prometheus-community publishes the chart in the HTTP repository
`https://prometheus-community.github.io/helm-charts` and at
`oci://ghcr.io/prometheus-community/charts/prometheus-blackbox-exporter`.
Both serve the same archive. The `Source` line takes the OCI form, because
`check` pulls an OCI chart by its digest, and an HTTP repository has no
digest a client checks (RCP-23).

`tests/values.yaml` keeps the chart's defaults, except the pod's seccomp
profile (DEC-205). The chart then renders a Deployment, its Service and
ServiceAccount, and a ConfigMap with the module `http_2xx`, all named
`<release>-prometheus-blackbox-exporter`. With the release name
`blackbox-exporter` that is
`blackbox-exporter-prometheus-blackbox-exporter`, which the recipe keeps as
its component's name. A release of that name installed with the chart's
defaults then keeps its object names when the recipe replaces it.
`fullnameOverride` in `tests/values.yaml` was considered. It would shorten
the names, but such a release would get new ones.

The chart's ServiceMonitor, PodMonitoring, PrometheusRule, Ingress, route,
NetworkPolicy, PodDisruptionBudget and config reloader are off by default
and are not part of the recipe. A ServiceMonitor needs the CRDs of the
Prometheus Operator, which no recipe of this repository installs and
`check` does not provide. The module configuration is the chart's `config`
value as its template renders it, carried with the chart's license
(RCP-42).

DEC-205: The pod of `blackbox-exporter` sets `seccompProfile.type:
RuntimeDefault` through the generator's `workload_security_context`, and
`tests/values.yaml` sets the chart's `podSecurityContext` to the same. The
chart's defaults give the container `runAsNonRoot`,
`allowPrivilegeEscalation: false` and `capabilities.drop: [ALL]`, but no
seccomp profile on the pod or the container. 11.20.2 is still the newest
chart on 2026-11-05. Pod Security `restricted` requires the profile
`RuntimeDefault` or `Localhost` on the pod or on every container. A
namespace that enforces it therefore rejected the pods of
blackbox-exporter 1.0.0, which the Argo CD example of
kadet-hub/examples#144 ran into. `RuntimeDefault` is the seccomp filter of
the container runtime. The pod level follows the chart, whose
`podSecurityContext` value is empty by default and meant for such
settings. The generator's `security_profile: restricted` was considered.
It also sets the pod's `runAsNonRoot`, which the chart sets only on the
container, so `tests/values.yaml` would have to differ from the chart's
defaults in a second field.

The recipe is at level `deploys`. check 0.14.0 fails every recipe at
`migrates` (RCP-14).

- RCP-71: The `tests/smoke` of `blackbox-exporter` MUST call `/probe` with
  the module `http_2xx` through the exporter's Service against an HTTP
  endpoint in the cluster that the recipe does not render, and require
  `probe_success 1`. It MUST also require `probe_success 0` for a target
  that answers with a status outside 2xx.

  The target is CoreDNS's metrics endpoint, port 9153 of the Service
  `kube-dns` in `kube-system`, which kubeadm sets up in every kind cluster. A
  probe of another Service shows that the exporter reaches the cluster
  network, not only its own pod. The failing probe of a path CoreDNS does
  not serve shows that `probe_success` follows the target's answer.

  - Test: CI `check` job, report line `smoke`
  - Since: #62

- RCP-285: The pod of `blackbox-exporter` MUST set `seccompProfile.type:
  RuntimeDefault`, and `tests/values.yaml` MUST set the chart's
  `podSecurityContext` to the same (DEC-205).

  - Test: `check blackbox-exporter`, which compares the Deployment with the
    chart's; RCP-286
  - Since: #106

- RCP-286: The `tests/smoke` of `blackbox-exporter` MUST require no Pod
  Security warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace.

  PodSecurity admission checks the running pods of a namespace on that dry
  run and warns about each violation, as for `memcached` (RCP-232). With
  blackbox-exporter 1.0.0 on kind 1.37 it warned about the pod's
  `seccompProfile` and nothing else.

  - Test: CI `check` job, report line `smoke`
  - Since: #106

## Jellyfin

Jellyfin is a media server. It indexes the files below `/media` and serves
a web client and an HTTP API on port 8096. `jellyfin` deploys it from the
chart `jellyfin` 3.7.0 of jellyfin/jellyfin-helm, which runs Jellyfin 12.4,
the newest stable release, as `docker.io/jellyfin/jellyfin:12.4`. The
recipe pins that tag to its multi-arch index for amd64 and arm64.

The Jellyfin organization maintains the chart in jellyfin/jellyfin-helm.
Its release workflow publishes each version with chart-releaser as a
GitHub release asset and in the HTTP repository
`https://jellyfin.github.io/jellyfin-helm`. It pushes no OCI artifact, so
the `Source` line takes the HTTP form of RCP-23. The archive's SHA-256 is
also the `digest` of its entry in the repository's `index.yaml`.

The chart and Jellyfin are GPL-2.0. The recipe carries no template, file
or values text of the chart, so DEC-16 applies as for nextcloud, and no
class file has a `.LICENSE` (RCP-42).

`tests/values.yaml` keeps the chart's defaults. The release name
`jellyfin` equals the chart's name, so the chart names its Deployment,
Service and ServiceAccount `jellyfin` and its claims `jellyfin-config` and
`jellyfin-media`. The claims ask for 5Gi and 25Gi with ReadWriteOnce and
name no StorageClass, so the cluster's default class provisions them,
`standard` on kind. `/media` is mounted read-only, and `/cache` is an
`emptyDir`. The chart's Service names its port `service` and targets the
container port `http`. A component's Service names each port after its
container port, so the recipe renders the Service as an entry of
`generators.kubernetes.services`.

The chart's Ingress, HTTPRoute, NetworkPolicy, ServiceMonitor with its
metrics hook, and DLNA on the host network are off by default and not part
of the recipe. Hardware transcoding is not tested, because it needs a GPU
in the pod and kind has none. The chart's README enables it with the
capability `SYS_ADMIN` and the host's `/dev/dri` as a `hostPath` volume,
which a target sets on the component.

The recipe is at level `deploys`. check 0.14.0 fails every recipe at
`migrates` (RCP-14).

- RCP-76: The `tests/smoke` of `jellyfin` MUST call `/health` and
  `/System/Info/Public` through the Service `jellyfin`. It MUST require
  `Healthy` from the first, and from the second JSON whose `Version` is the
  Deployment's image tag.

  `/System/Info/Public` answers without a login, also before the startup
  wizard has run. Its `Version` comes from the running server, so the test
  fails when the pod runs another release than the tag names, as when tag
  and digest disagree. Jellyfin reports the tag `12.4` as `12.4.0`, and the
  test accepts both forms. The test reads the tag from the Deployment, so
  it follows a Renovate update of the pin.

  - Test: CI `check` job, report line `smoke`
  - Since: #64

## Semaphore

Semaphore UI runs Ansible playbooks, Terraform and OpenTofu plans and shell
scripts from a web UI and an API. `semaphore` deploys it from the chart
`semaphore` 16.2.2 of semaphoreui/charts, Apache-2.0, which Semaphore's
installation guide names for Kubernetes
(`docs/admin-guide/installation/k8s.md` of semaphoreui/semaphore-docs). The
project publishes the chart at `oci://ghcr.io/semaphoreui/charts/semaphore`
and in the HTTP repository `https://semaphoreui.github.io/charts`. Both
serve the same archive, and the `Source` line takes the OCI form, as for
blackbox-exporter.

The chart's `appVersion` is Semaphore 2.18.3. That release is affected by
two advisories of semaphoreui/semaphore: GHSA-8cj9-r88m-8945, a CSRF on the
password change endpoint fixed in 2.18.21, and GHSA-cxvf-gvfq-36w2, a
privilege escalation up to 2.18.12. `tests/values.yaml` therefore sets the
image `docker.io/semaphoreui/semaphore:v2.19.17`, which the project builds
for amd64 and arm64 under the MIT license. It was the newest release with
an image on 2026-11-03. 2.19.18 was released on GitHub the day before, and
Docker Hub had no image for it. The image does not follow the chart's
version, so Renovate moves it on its own (RCP-16).

Semaphore 2.19 has no BoltDB, the chart's default `database.type`. Its
configuration rejects the dialect with `BoltDB not supported`
(`util/config.go` of v2.19.17), and the image's `server-wrapper` stops on
it. Besides `bolt` the chart takes `mysql` and `postgres`. The database is
therefore the included recipe `postgresql` (DEC-4, DEC-12). The chart's
`database.existingSecret` reads the keys `username` and `password`, the
keys of the Secret `<cluster>-app` that CloudNativePG writes.
`tests/values.yaml` points the chart at `postgresql-cluster-rw`, the
database `app` and the Secret `postgresql-cluster-app`, and the recipe
reads these names from `applications.postgresql` (RCP-60). The chart's
MariaDB and PostgreSQL subcharts are Bitnami's and stay off.

For PostgreSQL the chart passes `sslmode=disable` unless
`database.options` sets one, so the database password would cross the
cluster network in clear text. CloudNativePG serves TLS, and
`tests/values.yaml` sets `sslmode: require`, which encrypts the connection
without verifying the server's certificate.

The chart generates three Secrets at render time with random values:
`semaphore-general` with the cookie hash, the cookie encryption key and the
access key encryption key, `semaphore-runner` with the runner registration
token, and `semaphore-admin` with the admin account, which `admin.create`
adds.
The recipe renders the same Secrets from parameters the target sets
(RCP-77). The pod template carries the chart's `checksum/*` annotations of
its ConfigMap and these Secrets, written as `tests/values.yaml` renders
them (RCP-42). They do not change with the target's values.

`admin.create` adds the init container `admin`, which creates the admin
account with `semaphore user add` unless the login exists. Without it a new
Semaphore has no account to log in with. The init container gets the
server's environment plus the admin account and `SEMAPHORE_SSH_PATH`, in
the chart's order, and the recipe interpolates each shared variable from
the server's.

Remote runners stay off, the chart's default `general.useRemoteRunner:
false`. Semaphore still registers a new runner for any client that presents
the global registration token (`RegisterRunner` in `api/runners/runners.go`
of v2.19.17), so the token is a required parameter like the keys. An empty
token, which switches that off, was considered. The chart always sets one,
and a token nobody knows keeps runners out as well.

The `kubernetes` generator renders a `securityContext` on every container,
`{}` where the inventory sets none. `check` accepts the empty context on
containers but not on init containers (RCP-12), and the chart renders none
on its init container. `tests/values.yaml` sets
`podSecurityContext.runAsNonRoot: true`, which the chart puts on both
containers, and so does the recipe. The image runs as UID 1001, so nothing
changes for it. An RCP-12 class for init containers was considered. It
would need a new `check` release before the registry gate accepts the
recipe (REC-9 there).

The chart's Ingress, LDAP, OIDC, the mail, Telegram and Slack alerts, extra
Python packages and a custom CA bundle are off by default and not part of
the recipe. The chart's Helm test `semaphore-test-connection` is left out
(RCP-25). The recipe is at level `deploys`.

- RCP-77: `semaphore` MUST take the admin account's login and password,
  the cookie hash, the cookie encryption key, the access key encryption key
  and the runner registration token from `applications.semaphore.admin.username`,
  `.admin.password`, `.cookie_hash`, `.cookie_encryption`,
  `.access_key_encryption` and `.runner_token`, and MUST leave them unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, as refs for all but the login (RCP-19).
  Semaphore decodes the three keys from base64. The access key encryption
  key must decode to 16, 24 or 32 bytes (`validateAccessKeyEncryption` in
  `util/config.go`), and Semaphore encrypts the stored keys and secrets of
  its projects with it. The init container creates the account only once,
  so a later change of the password does not reach it.

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    each of the six parameters stops with `Interpolation key` and its name
  - Since: #67

- RCP-78: The `tests/smoke` of `semaphore` MUST log in as the admin account
  through `/api/auth/login`, read `/api/user` and `/api/projects` with the
  session, and require that `/api/info` reports the version of the image
  tag the Deployment runs and remote runners off. It MUST also get
  `/api/ping` through the endpoints of the Service `semaphore`.

  The login needs the account that the init container wrote into
  PostgreSQL, and `/api/user` must name it as admin. A wrong password and
  a request without the session cookie get 401. The smoke test runs no
  task, because a task needs a repository, an inventory and a key that the
  recipe does not render.

  - Test: CI `check` job, report line `smoke`
  - Since: #67

## Pi-hole

Pi-hole is a DNS server for a home or office network. It answers queries
for domains on its blocklists with an unroutable address, so ads and
trackers fail to load on every device that uses it as its resolver. Its
DNS core FTL also serves the web interface and the API that manage the
lists. The project publishes no chart. pi-hole/docker-pi-hole, EUPL-1.2,
builds the image `docker.io/pihole/pihole` and carries its compose example
as a code block in `README.md` (DEC-28). `pihole` takes the README at
commit `ffd0a489a633d0f2512818c46fd651ac50789175` of 2026-10-30, the tag
of release `2026.10.1`, the newest on 2026-11-03, SHA-256
`003d42d4097951284d6334af39399076490c696711b21f70081953ca3dd5596d`. The
commit is the `org.opencontainers.image.revision` of the image
`2026.10.1`, which `latest` pointed to on 2026-11-03, with Pi-hole Core
v6.5, Web v6.6.1 and FTL v6.8. The recipe takes from the image what it
dictates, such as variable names, ports, paths and its `HEALTHCHECK`
command, and copies no other text, as DEC-16 reads it for a copyleft chart.

The example's one service becomes the StatefulSet `pihole`. Its relative
bind mount `./etc-pihole`, which the repository does not contain, becomes
the claim `etc-pihole` at `/etc/pihole` (DEC-21). The published ports, DNS
on 53 over TCP and UDP, HTTP on 80 and HTTPS on 443, become the Service
`pihole` (DEC-30). FTL serves HTTPS with a self-signed certificate it
generates. `FTLCONF_dns_listeningMode: ALL`, which the example sets for
Docker's bridge network, lets FTL answer clients outside the pod's own
subnet, such as pods on other nodes.

The image starts as root and runs FTL as the user `pihole`, UID 1000. Its
start script gives FTL each capability FTL uses that the container has.
Without `cap_add` these are `CHOWN`, `NET_BIND_SERVICE` and `NET_RAW` of
the runtime's defaults (DEC-29). The target's namespace needs the Pod
Security level `baseline`. At its first start the image downloads its
default blocklist, the hosts file of StevenBlack/hosts on
raw.githubusercontent.com, into the claim, and a cron job in the container
updates it weekly.

Pi-hole's DHCP server is not set up. The example leaves its port 67/udp
commented out, and the server needs `NET_ADMIN`. DHCP broadcasts do not
cross into a container's network, so Pi-hole's documentation runs DHCP
with host networking, a macvlan network or a DHCP relay
(`docs/docker/DHCP.md` of pi-hole/docs). Host networking is `network_mode`,
a gap of Compose sources. The NTP server that FTL starts on port 123/udp is
not published either, as in the example.

- RCP-80: The `Source` line of `pihole` MUST name `README.md` of
  pi-hole/docker-pi-hole at the commit the image's tag was built from, with
  the README's SHA-256.

  `check` fetches the README at that commit and fails on another SHA-256
  (RCP-23). The commit is the image's `org.opencontainers.image.revision`.

  - Test: `check lint`; CI `check` job, report line `compose`; manual:
    the image's label
  - Since: #68

- RCP-81: `pihole` MUST set `FTLCONF_webserver_api_password` from the
  Secret `pihole`, whose value is `applications.pihole.password`, which the
  recipe leaves unset.

  Without the password the compile stops with
  `Interpolation key 'applications.pihole.password' not found` (RCP-19,
  RCP-40). Unset, the image would assign a random password and print it to
  the log.

  - Test: `check pihole`; manual: compile of `tests/target.yml` without
    the password
  - Since: #68

### Proof

`pihole` is at level `deploys`. `tests/target.yml` sets the example's
password and points Pi-hole's upstream at the cluster's DNS,
`kube-dns.kube-system.svc.cluster.local`. The image's default upstreams
are Google's resolvers `8.8.8.8` and `8.8.4.4`, which a network may not
let a pod reach.

- RCP-82: The `tests/smoke` of `pihole` MUST, from a pod of its own and
  through the Service `pihole`, resolve `example.com` over UDP and over
  TCP, log in at `/api/auth` on port 80 with the password of the Secret
  `pihole`, get 401 there with another password, get an answer on port
  443, deny a domain through the API, and then get `0.0.0.0` for that
  domain over UDP and over TCP.

  The test pod runs Pi-hole's image, which carries `dig` and `curl`.
  `0.0.0.0` is the answer of FTL's default blocking mode `NULL`. The domain
  lies under the reserved TLD `.example`, so it is NXDOMAIN until it is
  denied, and the check does not depend on the blocklist download. FTL
  answers the API before it reloads its lists (`src/api/list.c` of FTL
  v6.8), so the smoke test asks again for up to 20 seconds.

  - Test: CI `check` job, report line `smoke`
  - Since: #68

## n8n

n8n is a workflow automation tool. A workflow starts from a trigger, such
as a webhook call or a schedule, and runs nodes that call web services,
databases and scripts. `n8n` deploys it from the chart `n8n` 1.18.0 of
n8n-io/n8n-hosting, which n8n publishes at
`oci://ghcr.io/n8n-io/n8n-helm-chart/n8n` and describes as its official
chart. On 2026-11-03 the repository's newest release was 1.18.0 of
2026-10-28. Next to it was the release candidate 2.0.0-rc.1 of 2026-10-27,
which the recipe does not take.

The chart is MIT. n8n is under the Sustainable Use License 1.0, which
allows use and changes of n8n only for internal business purposes and for
non-commercial or personal use. Files with `.ee.` in their name need an n8n
Enterprise License (`LICENSE.md` of n8n-io/n8n). The OSI does not approve
the license as open source. This spec and the registry do not restrict the
license of an upstream image: `mongodb` runs MongoDB's SSPL-1.0 image, and
the registry matches `policy/licenses.txt` only against the `LICENSE` of
the repository a recipe comes from (REC-4 there). The recipe ships no n8n
code and names the image only, so it is Apache-2.0 like every recipe here.
Its README names n8n's license for the user who runs the image.

### The image

The chart's `appVersion` is n8n 2.45.5, and its default image
`docker.n8n.io/n8nio/n8n`. docker.n8n.io sends clients to Docker Hub for
their tokens and serves Docker Hub's repository `n8nio/n8n`. On 2026-11-03
it answered every anonymous request with 429 and `ratelimit-remaining: 0`,
while Docker Hub served the same tag to the same client with 99 of 100
pulls left. This suggests, without confirmation from n8n, that all
clients of docker.n8n.io share one anonymous quota. `tests/values.yaml`
therefore sets `image.repository: docker.io/n8nio/n8n`, and the recipe
pins that tag's index for amd64 and arm64. Keeping docker.n8n.io was
considered. Every
proof of `check` would then depend on a quota that other users of
docker.n8n.io use up.

Every advisory of n8n-io/n8n published by 2026-11-03 that reaches the 2.x
line names 2.45.5 or an earlier 2.x release as fixed, except
GHSA-365g-vjw2-grx8. That one covers every release: the Execute Command
node runs commands in the container for any user who may edit workflows.
n8n 2.45.5 does not load the node unless `NODES_EXCLUDE` is changed
(`packages/@n8n/config/src/configs/nodes.config.ts`), and the chart leaves
it alone. The recipe therefore runs the chart's version.

### Database and queue

The database is the included recipe `postgresql` (DEC-4, DEC-12). The
chart takes the host, the database and the user as values, and the
password from `database.passwordSecret`. `tests/values.yaml` points them at
`postgresql-cluster-rw`, `app`, `app` and the key `password` of the Secret
`postgresql-cluster-app` that CloudNativePG writes, and the recipe reads
these names from `applications.postgresql` (RCP-60). Without
`database.ssl.enabled` n8n connects without TLS. With it alone, n8n checks
the server's certificate against the CAs of Node.js, which do not include
CloudNativePG's own CA. `tests/values.yaml` sets `ssl.enabled: true` and
`ssl.rejectUnauthorized: false`, which encrypts the connection without
verifying the certificate, as `semaphore` does with `sslmode=require`.
Verifying against the CA in the Secret `postgresql-cluster-ca` was
considered. That Secret is the operator's, and `postgresql` does not name
it as a Secret its users read (DEC-12).

The queue is the included recipe `valkey` (DEC-31). `tests/values.yaml`
points `redis.host` at the Service `valkey` and `redis.passwordSecret` at
the key `default-password` of the Secret `valkey-auth`, with which n8n
authenticates as Valkey's user `default`. Two workers with a concurrency of
10, the chart's `queueMode.workerReplicaCount` and `workerConcurrency`,
stay as the chart sets them. Webhook processors, multi-main and task
runners are off by default and not part of the recipe. Multi-main needs an
n8n Enterprise license.

### Secrets and the rest of the chart

The chart renders the Secret `n8n` with `N8N_ENCRYPTION_KEY`, `N8N_HOST`,
`N8N_PORT` and `N8N_PROTOCOL`, and stops on the placeholder key of its
`values.yaml`. n8n encrypts the credentials that workflows use with the
key before it stores them in PostgreSQL. The chart also renders the Secret
`n8n-task-runners` with a token it generates at render time, also when
task runners are off and no container reads it. `tests/values.yaml` names
that Secret in `taskRunners.authToken.existingSecret`, so the chart renders
none, and neither does the recipe. Rendering it from a parameter was
considered. Every target would then set a token that nothing reads.

The chart binds its Role `n8n`, which reads every ConfigMap and Secret of
the namespace, to the ServiceAccount `n8n` of both Deployments, and the
recipe grants the same (RCP-11). The home directory of n8n-main is an
emptyDir, the chart's default without `persistence.enabled`. The pod
templates carry the chart's `checksum/config` and `checksum/secret` as
`tests/values.yaml` renders them (RCP-42). The ConfigMap `n8n` sets
`N8N_DEPLOYMENT_ARTIFACT` to `helm-chart/1.18.0`, which n8n reports to its
telemetry, as the chart renders it. The chart's Helm test
`n8n-test-connection` is left out (RCP-25). The recipe is at level
`deploys`.

- RCP-85: `n8n` MUST take `N8N_ENCRYPTION_KEY` from
  `applications.n8n.encryption_key` and MUST leave it unset.

  The compile then stops with
  `Interpolation key 'applications.n8n.encryption_key' not found` until
  the target sets it, as a ref (RCP-19, RCP-40). With another key n8n
  cannot decrypt the credentials it stored before.

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    the key stops with `Interpolation key` and its name
  - Since: #69

- RCP-86: The `tests/smoke` of `n8n` MUST get `ok` from `/healthz` and
  `/healthz/readiness` of n8n-main through its Service and from
  `/healthz/readiness` of each worker pod. It MUST set up the owner account
  through `/rest/owner/setup` and log in through `/rest/login`, then
  activate a workflow with a production webhook and require that the
  webhook answers with the query it was called with. After a restart of
  n8n-main it MUST log in and get the webhook's answer again.

  A worker reports ready only with its connections to PostgreSQL and to
  Valkey (`readiness` in `packages/cli/src/scaling/worker-server.ts` of
  n8n 2.45.5). In queue mode n8n-main queues every execution in Valkey
  instead of running it (`packages/cli/src/workflow-runner.ts`), so the
  webhook's answer comes from a worker. The restarted n8n-main starts on an
  empty home directory, so the owner and the active workflow come from
  PostgreSQL.

  - Test: CI `check` job, report line `smoke`
  - Since: #69

## Gitea

Gitea is a self-hosted Git service with a web UI and an API. `gitea`
deploys it from the chart `gitea` 12.7.0 of gitea/helm-gitea, MIT, which
the project publishes in the HTTP repository `https://dl.gitea.com/charts/`
and at `oci://docker.gitea.com/charts/gitea`. Both serve the same archive,
and the `Source` line takes the OCI form, as for semaphore. 12.7.0 was the
newest release on 2026-11-03. The chart's `main` has moved on with breaking
changes, such as CloudNativePG in place of its PostgreSQL HA subchart, that
no release carries yet.

The chart's `appVersion` is Gitea 1.27.0. `tests/values.yaml` sets the
image tag `28.3.0`, so the chart renders
`docker.gitea.com/gitea:28.3.0-rootless`, built for amd64, arm64 and
riscv64 (DEC-37). The image does not follow the chart's version, so
Renovate moves it on its own (RCP-16), together with the chart's label
`version: "28.3.0"`. That label is not one of the identifying labels of
RCP-9, so the recipe renders it on every object the chart puts it on, from
`applications.gitea.labels`. On the pod template it becomes part of the
Services' selectors, which select the same pods as the chart's (RCP-10).

The chart's subcharts are Bitnami's PostgreSQL, PostgreSQL HA, Valkey and
Valkey Cluster. `tests/values.yaml` switches PostgreSQL HA and Valkey
Cluster off, the two on by default. The database is the included recipe
`postgresql` (DEC-4, DEC-12). `gitea.config.database` points Gitea at
`postgresql-cluster-rw`, the database `app` and `SSL_MODE=require`, which
encrypts the connection without verifying the server's certificate.
`gitea.additionalConfigFromEnvs` takes the user and the password from the
Secret `postgresql-cluster-app`, as the chart's README shows for a database
password. The recipe reads these names from
`applications.postgresql` (RCP-60). Cache, sessions and queues are the
included recipe `valkey` (DEC-36).

The chart configures Gitea in the init container `init-app-ini`. It writes
`app.ini` on the claim `gitea-shared-storage` on every start, from the
Secret `gitea-inline-config`, which holds `gitea.config` one section per
key, and then from the `GITEA__<SECTION>__<KEY>` variables of its
environment, which win. The init container `configure-gitea` then migrates
the database and creates the admin account. The scripts both run come from
the Secrets `gitea` and `gitea-init`, which the recipe renders with the
chart's text (RCP-42). The pod template carries the chart's
`checksum/config` of these Secrets, written as `tests/values.yaml` renders
it.

The chart writes `SECRET_KEY` and `INTERNAL_TOKEN` from
`gitea.config.security` into `gitea-inline-config`. Without them
`init-app-ini` generates both, as it generates `JWT_SECRET` of `[oauth2]`
and `LFS_JWT_SECRET` of `[server]`. It keeps whatever an existing `app.ini`
holds for these four. The recipe takes the first two from parameters
(RCP-90). The admin account comes from the Secret
`gitea-admin` that `gitea.admin.existingSecret` names (DEC-38).

The chart renders the Services `gitea-http` on port 3000 and `gitea-ssh` on
port 22, both headless and of type `ClusterIP`. The recipe keeps both.
Gitea's built-in SSH server listens on 2222 in the rootless image. The
chart's `ROOT_URL` is `http://git.example.com`, from the default host of
its Ingress, also with the Ingress off. A target sets the address users
reach Gitea at as `GITEA__SERVER__ROOT_URL` and its neighbours in the
environment of `init-app-ini`.

The `kubernetes` generator renders a `securityContext` on every container,
`{}` where the inventory sets none, which `check` does not accept on init
containers (RCP-12). `tests/values.yaml` sets the chart's
`containerSecurityContext` to `runAsNonRoot: true`, which the chart puts on
all four containers, as semaphore does with its `podSecurityContext`. The
image runs as UID 1000.

The chart 12.7.0 renders no Actions runner. act_runner, which needs Docker
in Docker, has moved to the chart gitea/helm-actions, and the recipe
renders none. The chart's Ingress, Gateway API routes, OpenShift Route,
LDAP and OAuth sources, GPG signing and metrics are off by default and not
part of the recipe. Its Helm test `gitea-test-connection` is left out
(RCP-25).

DEC-36: `gitea` puts Gitea's cache, sessions and queues on the included
recipe `valkey`. The chart has no value for an external Redis. It sets
`[cache]`, `[session]` and `[queue]` to Redis only for its own Valkey
subcharts, and otherwise to Gitea's defaults: memory for cache and
sessions and a LevelDB queue on the claim. Its README advises against
these defaults in production, because the one pod holds cache and
sessions in its memory. `tests/values.yaml` sets the adapters to `redis`
in `gitea.config`, and `gitea.additionalConfigFromEnvs` gives each its URL
`redis://:$(VALKEY_PASSWORD)@valkey:6379/0` with the chart's pool options.
The kubelet puts in the password from `valkey-auth`, the Secret the
included recipe renders, as `nextcloud` builds its `REDIS_URL`. The URL
carries the password unencoded, so the README asks for a password of
letters and digits. The defaults were considered. They need no second
service, but sessions end with every restart of the pod, and `valkey` is
proven already.

DEC-37: `gitea` runs Gitea 28.3.0 instead of the chart's 1.27.0. Gitea
publishes security fixes only for its most recent major release
(`SECURITY.md` of go-gitea/gitea v28.3.0), and 1.27.3 of 2026-08-29 is the
last 1.27 release. Advisories rated high that affect 1.27, such as
GHSA-9v6p-xpcp-7488 and GHSA-8hhh-mqpg-jpxc, are fixed in 28.3.0 and 28.1.0
only. 28.3.0, released on 2026-11-01, was the newest release on
2026-11-03. The chart's `main` moved to 28.0.0 by its `appVersion` alone,
without a change to its templates. 1.27.3, the newest release of the line
the chart was released for, was considered. It stays without the fixes of
28.

DEC-38: `gitea` renders the admin account's Secret `gitea-admin` from
`applications.gitea.admin`, and `tests/values.yaml` sets
`gitea.admin.existingSecret` to it. The chart has two ways to set the
account: `gitea.admin.username` and `.password`, which it writes as plain
values into the environment of `configure-gitea`, or a Secret the user
creates. With the first, a ref of the target would end up in the
Deployment. The chart renders no Secret for `existingSecret`, so
`tests/values.yaml` creates the same Secret through the chart's
`extraDeploy`, as a user would next to the chart. `check` then compares it
like the chart's own objects.

- RCP-90: `gitea` MUST take the admin account's login and password,
  `SECRET_KEY` and `INTERNAL_TOKEN` from
  `applications.gitea.admin.username`, `.admin.password`, `.secret_key` and
  `.internal_token`, and MUST leave them unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, as refs for all but the login (RCP-19). The
  parent's README names `applications.valkey.password` as well (RCP-51).
  `configure-gitea` sets the admin password on every start, the chart's
  default `gitea.admin.passwordMode: keepUpdated`. `init-app-ini` writes
  the key and the token only into a new `app.ini`, so a later change in
  the target does not reach Gitea. Gitea encrypts stored secrets, such as
  two-factor keys, with `SECRET_KEY`.

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    each of the four parameters stops with `Interpolation key` and its name
  - Since: #70

### Proof

`gitea` is at level `deploys`. `tests/target.yml` runs one PostgreSQL
instance and sets the values `tests/values.yaml` gives the chart.

- RCP-91: The `tests/smoke` of `gitea` MUST require that `/api/healthz`
  reports `pass` for `database:ping` and `cache:ping` through the endpoints
  of the Service `gitea-http` and that `/api/v1/version` reports the
  version of the image tag the Deployment runs. As the admin account it
  MUST create a repository through
  `POST /api/v1/user/repos`, clone it over HTTP through `gitea-http` from a
  pod of its own, push one commit, and read the commit and the file back
  through the API. Valkey MUST then hold keys.

  Gitea runs the two checks only with `INSTALL_LOCK` set, and the overall
  `pass` alone would also hold without them. The push runs Gitea's
  hooks, which call its internal API with `INTERNAL_TOKEN`. The test pod
  runs Gitea's image, which carries `git`. Nothing but Gitea writes into
  the test's Valkey, so a key there shows that Gitea uses it. On kind with
  1.36.4 the keys were two cache entries `git-last-commit:...` of the
  pushed commit and the hash `MacaronCache` next to them.

  - Test: CI `check` job, report line `smoke`
  - Since: #70

- AC-40 (RCP-90, RCP-91): `check gitea --level deploys` passes in CI on
  each Kubernetes minor, its report lists the objects of `postgresql` and
  `valkey` as included and `cnpg` as installed, and its smoke test reads
  back the commit it pushed. `tests/target.yml` without
  `applications.gitea.secret_key` stops the compile with
  `Interpolation key 'applications.gitea.secret_key' not found`.

## Forgejo

Forgejo is a self-hosted Git forge with a web UI and an API, a fork of
Gitea. `forgejo` deploys it from the chart `forgejo` 17.3.2 of
forgejo-helm/forgejo-helm, MIT, which the project publishes at
`oci://code.forgejo.org/forgejo-helm/forgejo`. 17.3.2 was the newest
release on 2026-11-05. The chart started as a fork of Gitea's chart and
keeps its names: the values below `gitea`, the claim
`gitea-shared-storage`, the init container `configure-gitea` and the
`GITEA_*` variables of the containers. Settings of `app.ini` in the
environment take the prefix `FORGEJO__`.

The chart runs its `appVersion`, Forgejo 15.0.11, as
`code.forgejo.org/forgejo/forgejo:15.0.11-rootless`, built for amd64,
arm64 and arm/v6 (DEC-140). Forgejo is GPL-3.0-or-later. The image follows
the chart, so Renovate moves neither the image's tag nor the chart's label
`version: "15.0.11"`. The recipe renders that label from
`applications.forgejo.labels` on every object the chart puts it on, and on
the pod template it becomes part of the Services' selectors, as for gitea.

The chart has no subchart besides Bitnami's library chart `common`, which
renders nothing. Without a database setting Forgejo runs SQLite on the
claim. `tests/values.yaml` points `gitea.config.database` at the included
recipe `postgresql` (DEC-141): `postgresql-cluster-rw`, the database `app`
and `SSL_MODE=require`, which encrypts the connection without verifying
the server's certificate. `gitea.additionalConfigFromEnvs` takes the user
and the password from the Secret `postgresql-cluster-app` as
`FORGEJO__DATABASE__USER` and `FORGEJO__DATABASE__PASSWD`. The recipe reads
these names from `applications.postgresql` (RCP-60). Cache, sessions and
queues stay on the chart's defaults (DEC-142).

The chart configures Forgejo as Gitea's chart configures Gitea. The init
container `init-app-ini` writes `app.ini` on the claim on every start,
from the Secret `forgejo-inline-config` and then from the
`FORGEJO__<SECTION>__<KEY>` variables of its environment, which win.
`configure-gitea` then migrates the database and creates the admin
account, or sets its password (`gitea.admin.passwordMode: keepUpdated`).
The scripts both run come from the Secrets `forgejo` and `forgejo-init`,
which the recipe renders with the chart's text (RCP-42). The pod template
carries the chart's `checksum/config` of these Secrets, written as
`tests/values.yaml` renders it.

The chart renders the admin account's Secret `forgejo-admin` itself from
`gitea.admin.username` and `.password`. Without a password it generates
one and keeps it through a `lookup` of the existing Secret, which a
compile cannot do. The recipe renders the same Secret from parameters
(RCP-220), so `tests/values.yaml` sets both values and, unlike gitea's
(DEC-38), needs no `extraDeploy`. `init-app-ini` generates `SECRET_KEY`,
`INTERNAL_TOKEN`, `JWT_SECRET` and `LFS_JWT_SECRET` into a new `app.ini`
and keeps what an existing one holds. The recipe takes only `SECRET_KEY`
from a parameter (DEC-143).

The Services `forgejo-http` on port 3000 and `forgejo-ssh` on port 22 are
of type `ClusterIP` with a cluster IP, where Gitea's chart renders them
headless. Forgejo's built-in SSH server listens on 2222 in the rootless
image. The chart's `ROOT_URL` is `http://git.example.com`, from the default
host of its Ingress, also with the Ingress off. A target sets the address
users reach Forgejo at as `FORGEJO__SERVER__ROOT_URL` and its neighbours in
the environment of `init-app-ini`. The Deployment has the chart's strategy
`Recreate`, its readiness probe `GET /api/healthz` and its liveness probe
on the TCP port. The chart renders `securityContext: {}` on every container
without one, as the generator does, and `runAsUser: 1000` on
`configure-gitea`.

The chart's Ingress, Gateway API routes, OpenShift Route, ServiceAccount,
PodDisruptionBudget, ServiceMonitor, LDAP and OAuth sources and commit
signing are off by default and not part of the recipe. The chart renders
no Forgejo Actions runner. Its Helm test `forgejo-test-connection` is left
out (RCP-25).

DEC-140: `forgejo` runs Forgejo 15.0.11 of the 15.0 LTS line, the chart's
`appVersion`, and not 17.0.1, the newest release on 2026-11-05. Forgejo's
release schedule ends 15.0 on 15 July 2027 and 17.0 on 28 January 2027
(https://forgejo.org/docs/latest/admin/release-schedule/). 15.0.11, 16.0.7
and 17.0.1 were released on the same day, 2026-10-26. The chart's
maintainers closed Renovate's pull requests to Forgejo 16 and 17 without
merging them (forgejo-helm/forgejo-helm#1638, #1800), so its templates are
released for 15.0. Running 17.0.1 by `image.tag`, as gitea runs ahead of
its chart (DEC-37), was considered. Its line ends six months earlier, and
the chart was not released for it.

DEC-141: `forgejo` runs Forgejo on the included recipe `postgresql` and
not on the chart's default SQLite. The chart's README recommends PostgreSQL
or MySQL for long-term use with five or more active users and names
CloudNativePG first among the operators for it. SQLite was considered. It
needs no second service, but the database would then live on the claim
with the repositories, without the backup path that `postgresql` has
(DEC-18).

DEC-142: `forgejo` keeps the chart's defaults for cache, sessions and
queues: memory for the first two and a LevelDB queue on the claim. The
chart has no Redis subchart and no value for one. Its README calls
external Valkey a choice for medium to large instances that needs no data
migration later, and advises against the defaults in production because
one pod holds cache and sessions in its memory. Including `valkey`, as
gitea does (DEC-36), was considered. Sessions would then outlive a
restart of the pod, but the recipe would run a service that the chart
does not deploy and its maintainers recommend only for larger instances. A
target that wants Valkey includes `recipes.valkey` and sets the
`FORGEJO__CACHE__*`, `FORGEJO__SESSION__*` and `FORGEJO__QUEUE__*`
variables of `init-app-ini`.

DEC-143: `forgejo` takes `SECRET_KEY` from `applications.forgejo.secret_key`
and leaves `INTERNAL_TOKEN` to `init-app-ini`. Forgejo encrypts stored
secrets, such as two-factor keys, with `SECRET_KEY`, and the database
lives apart from the claim, so a new claim with a new key could not
decrypt them. `INTERNAL_TOKEN` authenticates Forgejo's own commands, such
as its Git hooks, against its internal API, and they read it from the same
`app.ini`, so a new one breaks nothing. Forgejo 18 removes it
(codeberg.org/forgejo/forgejo#14148, named in the chart's
`scripts/config_environment.sh`). Taking both, as gitea does
(RCP-90), was considered. It would add a required parameter that the next
LTS line drops.

- RCP-220: `forgejo` MUST take the admin account's login and password and
  `SECRET_KEY` from `applications.forgejo.admin.username`,
  `.admin.password` and `.secret_key`, and MUST leave them unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, as refs for all but the login (RCP-19).
  `configure-gitea` sets the admin password on every start. `init-app-ini`
  writes the key only into a new `app.ini`, so a later change in the target
  does not reach Forgejo.

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    each of the three parameters stops with `Interpolation key` and its
    name
  - Since: #93

- RCP-221: The `tests/smoke` of `forgejo` MUST require that `/api/healthz`
  reports `pass` for `database:ping` and that the web UI answers, both
  through the endpoints of the Service `forgejo-http`, and that
  `/api/v1/version` reports the version of the image tag the Deployment
  runs. The login of `forgejo-admin` MUST be an admin. As that account it
  MUST create a repository through `POST /api/v1/user/repos`, push one
  commit over HTTP through `forgejo-http` from a pod of its own, and read
  the commit and the file back through the API. It MUST delete the Forgejo
  pod and read both back again from the pod that replaces it.

  The push runs Forgejo's hooks, which call its internal API. The test pod
  runs Forgejo's image, which carries `git`. Forgejo reports its version
  with the Gitea version it is compatible with, such as
  `15.0.11+gitea-1.22.0`, so the test compares the part before `+`. The
  repository lives on the claim and its metadata in PostgreSQL, so the
  read after the deletion shows that both outlive the pod.

  - Test: CI `check` job, report line `smoke`
  - Since: #93

- AC-135 (RCP-220, RCP-221): `check forgejo --level deploys` passes in CI
  on each Kubernetes minor, its report lists the objects of `postgresql` as
  included and `cnpg` as installed, and its smoke test reads back the
  commit it pushed after the pod's deletion. `tests/target.yml` without
  `applications.forgejo.secret_key` stops the compile with
  `Interpolation key 'applications.forgejo.secret_key' not found`.

## authentik

authentik is an identity provider. Applications sign their users in
through it with OAuth2 and OpenID Connect, SAML, LDAP or RADIUS, and
authentik keeps the users and groups and runs the flows that log them in.
`authentik` deploys it from the chart `authentik` 2026.8.5 of
goauthentik/helm, which authentik's installation guide for Kubernetes uses
(`website/docs/install-config/install/kubernetes.mdx` of
goauthentik/authentik). The project publishes the chart in the HTTP
repository `https://charts.goauthentik.io` and at
`oci://ghcr.io/goauthentik/helm-charts/authentik`. Both serve the same
archive, and the `Source` line takes the OCI form, as for semaphore.

On 2026-11-03 the chart's newest release was 2026.8.5 of 2026-10-21. Its
`appVersion` is authentik 2026.8.5, the newest stable release, and the
recipe pins the image `ghcr.io/goauthentik/server:2026.8.5` to its index
for amd64 and arm64. Every advisory of goauthentik/authentik published by
2026-11-03 names 2026.8.2 or an earlier release as fixed. The chart is
GPL-3.0. The recipe carries no template, file or values text of the chart,
so DEC-16 applies as for nextcloud, and no class file has a `.LICENSE`
(RCP-42). authentik is MIT outside `authentik/enterprise/`, which has a
license of its own (`LICENSE` of goauthentik/authentik).

### Database without Redis

authentik needs no Redis since 2025.10. Its tasks moved to PostgreSQL in
2025.8, and 2025.10 moved the cache, the embedded outpost's sessions and
the WebSocket connections there too
([release notes](https://docs.goauthentik.io/releases/2025.10/)). The
chart 2026.8.5 has no Redis subchart, and the recipe includes no `valkey`.

The database is the included recipe `postgresql` (DEC-4, DEC-12). The
chart writes the host, the database and the user from
`authentik.postgresql` into its Secret `authentik`. `tests/values.yaml`
points them at `postgresql-cluster-rw`, `app` and `app`, and passes the key
`password` of the Secret `postgresql-cluster-app` to both containers as
`AUTHENTIK_POSTGRESQL__PASSWORD` through `global.env`, so the chart's
Secret holds no password. The recipe reads these names from
`applications.postgresql` (RCP-60). authentik connects without TLS by
default (`postgresql.sslmode: disable` in `authentik/lib/default.yml` of
2026.8.5). `tests/values.yaml` sets `sslmode: require`, which encrypts the
connection without verifying CloudNativePG's certificate, as `semaphore`
does. Since 2025.10 authentik needs TLS 1.3 or the Extended Master Secret
extension for that. On kind its connections used TLS 1.3 (`pg_stat_ssl`).
The chart's Bitnami PostgreSQL subchart is off by default and stays off.

### Keys and the admin account

The chart writes every key below `authentik` in its values into the Secret
`authentik` as an `AUTHENTIK_` variable, with `__` between nested keys,
and both Deployments read the whole Secret. The recipe renders the same
Secret. `AUTHENTIK_SECRET_KEY` signs authentik's cookies, so another key
ends every session (`website/docs/install-config/configuration/configuration.mdx`).

The worker creates the admin account `akadmin` from the blueprint
`blueprints/system/bootstrap.yaml`. It sets the password from
`AUTHENTIK_BOOTSTRAP_PASSWORD` and creates the API token
`authentik-bootstrap-token` from `AUTHENTIK_BOOTSTRAP_TOKEN`, each only
when it creates the object. It applies the blueprint when it first finds
it and again when its file changes, which a new authentik release can do
(`check_blueprint_v1_file` in `authentik/blueprints/v1/tasks.py`). A
deleted token then comes back. Without a usable password of `akadmin` the
initial setup flow lets the first visitor set one
(`blueprints/default/flow-oobe.yaml`). The chart has no values for either
variable. `tests/values.yaml` sets them as `authentik.bootstrap_password`
and `authentik.bootstrap_token`, which the chart writes into its Secret.

DEC-41: `authentik` requires the admin password and the bootstrap token as
parameters (RCP-95). With both unset, as the chart leaves them, the admin
account belongs to whoever reaches the initial setup flow first after the
rollout, and nothing outside authentik can call its API until someone
creates a token in the web UI. A required password with an optional token
was considered. The token is then a value the target sets or not, and
`tests/smoke` needs it to reach the API. A target that has no use for the
token sets a random value that nobody keeps and deletes the token in
authentik.

- RCP-95: `authentik` MUST take `AUTHENTIK_SECRET_KEY`,
  `AUTHENTIK_BOOTSTRAP_PASSWORD` and `AUTHENTIK_BOOTSTRAP_TOKEN` from
  `applications.authentik.secret_key`, `.bootstrap_password` and
  `.bootstrap_token`, and MUST leave them unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, as refs (RCP-19, RCP-40). A later change of
  the password or the token does not reach the account, which the worker
  created before.

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    each of the three parameters stops with `Interpolation key` and its
    name
  - Since: #72

### Server, worker and outposts

The chart renders the Deployments `authentik-server` and
`authentik-worker`, which run the same image as `server` and `worker`, and
the Service `authentik-server` with HTTP on port 80 and HTTPS on port 443.
Each Deployment prefers its pods on different nodes through an
anti-affinity that selects on the chart's labels `app.kubernetes.io/name`,
`instance` and `component`. The recipe renders the same anti-affinity and
puts these labels on the pods as `pod_labels`, so it selects the recipe's
pods. RCP-9 drops the labels before the comparison, and the Service, which
selects on every pod label, selects the same pods (RCP-10). The pod
templates carry the chart's `checksum/secret` as `tests/values.yaml`
renders it (RCP-42).

The chart's default `serviceAccount.create` renders its subchart
`authentik-remote-cluster` under the alias `serviceAccount`. It holds the
ServiceAccount `authentik` of the worker, a Role that lets it manage
Secrets, Services, ConfigMaps, Deployments, Ingresses, HTTPRoutes, Traefik
middlewares and ServiceMonitors in the namespace, and a ClusterRole that
lists CRDs. authentik detects the ServiceAccount and deploys the outposts it
manages, the components that serve its LDAP, RADIUS, proxy and remote
access providers, into the namespace. On kind the worker registered the
cluster as the outpost integration `Local Kubernetes Cluster`, which
reported itself healthy. The server runs as the namespace's `default`
ServiceAccount.

DEC-42: `authentik` renders the objects of the subchart
`authentik-remote-cluster` itself, as RBAC of its worker component
(Server, worker and outposts). The subchart grants only the parent's
worker. On its own it connects a second cluster to an authentik elsewhere
with a ServiceAccount token Secret, which the parent switches off. A recipe
of its own, as DEC-4 asks for a subchart, would be included only by
`authentik`. DEC-12 forbids the parent to override it, so it would have to
default to the parent's values, which differ from the subchart's own.
Switching `serviceAccount.create` off was considered. A release installed
with the chart's defaults would then lose its managed outposts when the
recipe replaces it.

GeoIP, email, the Ingress, the HTTPRoute, the metrics Services,
ServiceMonitors, the PrometheusRule, HPAs, PodDisruptionBudgets and
mounted blueprints are off by default and not part of the recipe. The
chart has no hooks. The recipe is at level `deploys`.

- RCP-96: The `tests/smoke` of `authentik` MUST get `/-/health/live/` and
  `/-/health/ready/` of the server through the Service `authentik-server`.
  With the token of `AUTHENTIK_BOOTSTRAP_TOKEN` it MUST require that
  `/api/v3/core/users/me/` names `akadmin` as a superuser and that
  `/api/v3/admin/version/` reports the Deployment's image tag, and with
  another token it MUST get 403. It MUST create an OAuth2 provider and an
  application through the API and get the application's
  `/.well-known/openid-configuration` with an `issuer` that names it.

  The worker applies the blueprints that create `akadmin`, its token and
  the default flows the provider needs, so the requests with the token
  need the server, the worker and PostgreSQL. The worker applies the
  blueprints one by one after its rollout. In a first run on kind the
  token already worked and the request for the provider still got 400,
  most likely because a flow it names did not exist yet. The smoke test
  therefore waits up to five minutes for the token and again for the
  flows. It reads the tag from the Deployment, so it follows a Renovate
  update of the pin.

  - Test: CI `check` job, report line `smoke`
  - Since: #72

## Vaultwarden

Vaultwarden is a password server for the Bitwarden clients, in place of
Bitwarden's own server. It keeps the users' encrypted vaults, their
attachments and Sends, and serves Bitwarden's web vault next to the API.
The project publishes no chart. dani-garcia/vaultwarden, AGPL-3.0, builds
the image `docker.io/vaultwarden/server` and carries its compose example as
the code block under "Docker Compose" in `README.md`. `vaultwarden` takes
the README at commit `6ed6921cc2b0e03b4d74189574d2a5e71c512e97`, the tag of
release 1.37.5 of 2026-11-01, the newest on 2026-11-03, SHA-256
`5c7e29e287f600fe1979d196d53f94cd8f87f9c0de1acf6481fde510fbfdd4fc`, as
`pihole` takes the README of docker-pi-hole (DEC-28). The commit is the
`org.opencontainers.image.revision` of the image `1.37.5`, which `latest`
pointed to on 2026-11-03, an index for amd64, arm64, arm/v7 and arm/v6.
Every advisory of dani-garcia/vaultwarden published by 2026-11-03 names
1.37.4 or an earlier release as fixed.

The repository's only compose file, `playwright/docker-compose.yml`, builds
Vaultwarden for its end-to-end tests. The compose pages of the project's
wiki live in the wiki's own repository, which no release commit pins. The
recipe takes from the image what it dictates, such as variable names,
ports, paths and its `HEALTHCHECK` command, and copies no other text, as
DEC-16 reads it for a copyleft chart.

The example's one service becomes the StatefulSet `vaultwarden`. Its
relative bind mount `./vw-data/`, which the repository does not contain,
becomes the claim `vw-data` at `/data` (DEC-21). The published port
`127.0.0.1:8000:80` becomes port 8000 of the Service `vaultwarden`, to the
container's port 80. The image's `HEALTHCHECK` runs `/healthcheck.sh`, which
gets `/alive`, every 60 seconds with a timeout of 10 seconds. It becomes
the readiness probe with compose's 3 retries. The image runs as root, so
the target's namespace needs the Pod Security level `baseline`.

DEC-55: `vaultwarden` sets `SIGNUPS_ALLOWED` to `false`, which the compose
example leaves at Vaultwarden's default `true` (Vaultwarden). With signups
on, anyone who reaches the Service can create an account. The wiki's
compose page tells its reader to switch them off once their own account
exists (`Using-Docker-Compose.md`). With signups off the admin page invites
users, and an invited address still registers in the web vault
(`register` in `src/api/core/accounts.rs` of 1.37.5). Keeping the default
was considered. A target would then serve open signups unless it set the
variable itself.

DEC-56: `vaultwarden` requires the admin token as a parameter and renders
`ADMIN_TOKEN`, which the compose example does not set (Vaultwarden).
Without the token Vaultwarden serves no admin page (`routes` in
`src/api/admin.rs`), and with signups off (DEC-55) nobody could create the
first account. An optional token was considered. A target that left it
unset would get a server without a way to create an account, and
`tests/smoke` needs the admin API to create a user.

DEC-57: `vaultwarden` keeps the vault in SQLite at `/data/db.sqlite3` on
the claim `vw-data`, Vaultwarden's default without `DATABASE_URL`
(Vaultwarden). The compose example runs no database service, and the row
of Compose sources for an included recipe maps a service of the compose
file. The claim also holds what Vaultwarden keeps outside the database:
attachments, Sends, the RSA key that signs its sessions and
`config.json`. The included recipe `postgresql`, with a `DATABASE_URL`
built from the Secret `postgresql-cluster-app` and `sslmode=require`, was
considered. It would add a database and the prerequisite `cnpg` that the
source does not have, and the files would still need the claim. SQLite
runs one replica, as the example does.

- RCP-110: The `Source` line of `vaultwarden` MUST name `README.md` of
  dani-garcia/vaultwarden at the commit the image's tag was built from,
  with the README's SHA-256.

  `check` fetches the README at that commit and fails on another SHA-256
  (RCP-23). The commit is the image's `org.opencontainers.image.revision`.

  - Test: `check lint`; CI `check` job, report line `compose`; manual:
    the image's label
  - Since: #75

- RCP-111: `vaultwarden` MUST set `DOMAIN` from
  `applications.vaultwarden.domain` and `ADMIN_TOKEN` from the Secret
  `vaultwarden`, whose value is `applications.vaultwarden.admin_token`, and
  MUST leave both parameters unset. It MUST set `SIGNUPS_ALLOWED` to
  `false`.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, the token as a ref (RCP-19, RCP-40). The
  example's `https://vw.domain.tld` stands for the user's address.
  Vaultwarden builds the links of its emails and the addresses that
  `/api/config` gives clients from `DOMAIN`, and checks the issuer of its
  session tokens against the domain's origin, so a new domain ends every
  session (`decode_jwt` in `src/auth.rs`). Vaultwarden takes the token as
  an Argon2id PHC string, which `vaultwarden hash` prints, or as plain
  text, for which it prints a notice at every start.

  - Test: CI `check` job; manual: a compile of `tests/target.yml` without
    each of the two parameters stops with `Interpolation key` and its name
  - Since: #75

- RCP-112: The `tests/smoke` of `vaultwarden` MUST, from a pod of its own
  and through the Service `vaultwarden` on port 8000, get `/alive`,
  require that `/api/version` names the image tag the StatefulSet runs and
  that `/api/config` names the domain, get 401 from `/admin` with a wrong
  token, log in there with the token whose PHC string `tests/target.yml`
  sets, require `signups_allowed: false` from `/admin/diagnostics/config`,
  invite a user through `/admin/invite`, and find that user in
  `/admin/users` once the pod `vaultwarden-0` was deleted and its
  successor is ready.

  `/api/config` reports the Bitwarden server version its clients expect,
  2026.6.0 in 1.37.5, and Vaultwarden's own version is `/api/version`. Its
  `settings.disableUserRegistration` stays `false` with signups off while
  invitations work without mail (`is_signup_disabled` in `src/config.rs`),
  so the smoke test reads the setting from the admin API. Without SMTP
  settings an invitation is a row in the database, so the user is found
  after the restart only if the new pod reads `db.sqlite3` from the claim.
  The Service refuses connections for a moment after the new pod is
  ready, until its endpoints follow, so the smoke test retries `/alive`
  for up to a minute.

  - Test: CI `check` job, report line `smoke`
  - Since: #75

- AC-60 (RCP-110 to RCP-112): `check vaultwarden --level deploys` passes
  in CI on each Kubernetes minor, and its smoke test finds the invited user
  after the restart. `tests/target.yml` without
  `applications.vaultwarden.domain` or `admin_token` stops the compile
  with `Interpolation key` and that key.

## NetBox

NetBox is a source of truth for network infrastructure. It models sites,
racks, devices, cables, IP prefixes and addresses, and serves them through
a web UI, a REST API and GraphQL. `netbox` deploys it from the chart
`netbox` 8.3.99 of netbox-community/netbox-chart, which the project calls
its official chart. The project publishes the chart at
`oci://ghcr.io/netbox-community/netbox-chart/netbox` and in the HTTP
repository `https://charts.netbox.oss.netboxlabs.com/`. Both serve the same
archive, SHA-256
`681766d72479ac9018c544a3c3fa1798f2f3363260192b7bc200e7d306c63103`, and the
`Source` line takes the OCI form, as for semaphore. 8.3.99 of 2026-11-03
was the newest release on that day. The chart released six patch versions
between 2026-10-23 and 2026-11-03, most of them for updates of its
dependencies, and Renovate moves the `Source` line once a week (RCP-16).

The chart's `appVersion` is NetBox v4.7.4 of 2026-10-27, the newest
release on 2026-11-03. The chart runs the image
`ghcr.io/netbox-community/netbox:v4.7.4`, which netbox-community/netbox-docker
builds. On 2026-11-03 the tag was the same index for amd64 and arm64 as
`v4.7.4-5.1.1`, netbox-docker's release 5.1.1, and the recipe pins that
index. Chart, NetBox and
netbox-docker are Apache-2.0. The ConfigMap `netbox` carries the chart's
`files/configuration.py` and the `netbox.yaml` its template renders, so
`netbox.yml` names both and has `netbox.yml.LICENSE` (RCP-42).

### Database, tasks and cache

The chart's subcharts are Bitnami's PostgreSQL and Valkey, both on by
default. `tests/values.yaml` switches them off. The database is the
included recipe `postgresql` (DEC-4, DEC-12). `externalDatabase` points
NetBox at `postgresql-cluster-rw`, the database `app` and the user `app`,
and its `existingSecretName` at the key `password` of the Secret
`postgresql-cluster-app`, so the chart renders no Secret of its own for the
password. The recipe reads these names from `applications.postgresql`
(RCP-60). The chart's `sslmode` is `prefer`, which falls back to a plain
connection when TLS fails. CloudNativePG serves TLS, and
`tests/values.yaml` sets `require`, which encrypts without verifying the
server's certificate, as `semaphore` does.

NetBox keeps its task queue and its cache in Redis, each as a database of
its own. Both point at the included recipe `valkey`: `tasksDatabase` at
database 0 and `cachingDatabase` at database 1 of the Service `valkey`, each
with the key `default-password` of the Secret `valkey-auth`, with which
NetBox authenticates as Valkey's user `default`. The chart then renders no
Secret `netbox-kv`.

### Secrets and the superuser

The chart renders the Secret `netbox-config` with `secret_key`,
`api_token_peppers` and `email_password`, and the Secret `netbox-superuser`
of type `kubernetes.io/basic-auth` with `username`, `password`, `email` and
`api_token`. It generates the key, a pepper, the password and the token at
render time when the values leave them empty. `configuration.py` reads
every secret from a file below `/run/secrets/netbox`, which a projected
volume of both Secrets and those of the included recipes provides.

The entrypoint of the image runs NetBox's migrations and then
`super_user.py` on every start of the container `netbox`
(`docker/docker-entrypoint.sh` of netbox-docker 5.1.1). The script creates
the superuser from `SUPERUSER_NAME`, `SUPERUSER_EMAIL` and the file
`/run/secrets/superuser_password` only when no user of that name exists.
It creates an API token only from `superuser_api_token` together with
`superuser_api_key`, which the chart does not mount, so the chart's
generated token is never read.

`API_TOKEN_PEPPERS` maps a pepper ID to a string of at least 50
characters, with which NetBox hashes v2 API tokens. NetBox runs without
it, but then creates no v2 token (`docs/configuration/required-parameters.md`
of NetBox v4.7.4). v1 tokens are deprecated since v4.6. The chart writes
the peppers as a JSON object, and `configuration.py` converts its keys to
integers.

DEC-85: `netbox` requires the superuser's name, address and password,
`SECRET_KEY` and the pepper as parameters (RCP-140). The chart generates
the password, the key and the pepper at render time, which a recipe turns
into parameters the target sets as refs (RCP-19). The chart's defaults
`admin` and `admin@example.com` for the name and the address were
considered. The address is a placeholder that no mail reaches. The name
of the only account NetBox creates belongs in the target next to its
password.

DEC-86: `netbox` takes one pepper, ID 1, from
`applications.netbox.api_token_pepper` and renders it as
`{"1": "<pepper>"}` into `api_token_peppers`, the object the chart
generates. A parameter for the whole JSON object was considered. A target
would then write JSON around a ref, and the omegaconf backend has no
built-in resolver that turns a mapping into JSON. A second pepper, to
rotate the hashes, is a change of the Secret's value in the target, which
the README shows.

DEC-87: `netbox` renders the key `api_token` of `netbox-superuser` with an
empty value. The projected volume names the key, so the Secret needs it.
Rendering it from a parameter was considered. Every target would then set
a token that netbox-docker 5.1.1 does not read. `n8n` leaves out its task
runners' token for the same reason. `email_password` keeps the chart's
empty default.

### Workloads

The Deployment `netbox` runs NetBox under granian on port 8080, behind the
Service `netbox` on port 80. Its init container `init-dirs` runs busybox
1.38.0 and creates two directories on an emptyDir, and NetBox keeps
uploaded images and attachments on the claim `netbox-media`, 1Gi with
`ReadWriteOnce`. The chart's probes get `/login/` and connect to port 8080,
and its `resourcesPreset` `medium` and `nano` become the containers'
resources.

The Deployment `netbox-worker` runs `manage.py rqworker`, which schedules
NetBox's system jobs and runs the jobs of the queues `high`, `default` and
`low` (`netbox/core/management/commands/rqworker.py` of v4.7.4). Its init
container `wait-for-backend` runs `rancher/kubectl` v1.36.2 and waits for
the rollout of `netbox`, so the worker starts on a migrated database. It
reads the Deployment through the Role `netbox`, which the chart binds to
the ServiceAccount `netbox` of both Deployments, and only the worker's pod
mounts the token. The recipe grants the same (RCP-11). The worker mounts
the media claim as well, so with `ReadWriteOnce` it runs on NetBox's node.

The chart's housekeeping CronJob is off by default. Its `values.yaml`
calls it useful only before NetBox v4.6, which runs housekeeping as a
system job of the worker. The Ingress, the HTTPRoute, LDAP, metrics with
their ServiceMonitors, PodDisruptionBudgets, autoscalers, `extraConfig`
and the claims for reports and scripts are off by default and not part of
the recipe either. The pod templates carry the chart's `checksum/config`
and `checksum/secret` as `tests/values.yaml` renders them (RCP-42). The
chart's only hook is its Helm test `netbox-test-connection`, which is left
out (RCP-25).

### Proof

`netbox` is at level `deploys`. `tests/target.yml` runs one PostgreSQL
instance.

NetBox migrates its empty database on its first start before it answers
`/login/`. On kind with Kubernetes 1.37.0 the migrations ran for five and
a half minutes, and the Deployment became available about 470 seconds
after the apply. The container used 343 CPU seconds, and the chart's CPU
limit of 750m throttled it for 54 seconds. check 0.14.0 waited 300 seconds
for each rollout and failed there. Two more runs, on 1.37.0 and 1.35.8
while other `check` runs used the same host, took about 550 and 570
seconds. The chart's own startup probe allows 1005 seconds, 5 seconds of
initial delay and 100 failures 10 seconds apart.

DEC-88: check 0.14.1 waits up to 900 seconds for the rollout of each
workload at `deploys` (RCP-26). It gives every other command it runs the
same 900 seconds. The CPU limit makes the start slower on a slower core,
and a runner's core speed is not measured, so the wait leaves room above
the 570 seconds. A longer wait delays only a proof that fails, and the CI
job keeps its limit of 30 minutes. 600 seconds, the
`progressDeadlineSeconds` that Kubernetes gives a Deployment that sets
none, was considered and leaves 30 seconds above the slowest run. Level
`renders` for `netbox` was considered too. It would prove no request
against NetBox. A higher CPU limit would render other resources than the
chart, and without the 54 seconds of throttling the start would still have
taken about seven minutes.

- RCP-140: `netbox` MUST take the superuser's name, address and password,
  `SECRET_KEY` and the pepper with ID 1 from
  `applications.netbox.superuser.name`, `.superuser.email`,
  `.superuser.password`, `.secret_key` and `.api_token_pepper`, and MUST
  leave them unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, as refs for the password, the key and the
  pepper (RCP-19, RCP-40). The parent's README names
  `applications.valkey.password` as well (RCP-51). A later change of the
  address or the password does not reach the superuser, which exists
  already, and a new name creates a second superuser. Another key ends
  every session, and another pepper invalidates the v2 tokens hashed with
  the old one.

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    each of the five parameters stops with `Interpolation key` and its name
  - Since: #79

- RCP-141: `netbox` MUST point NetBox at the Service, the database and the
  Secret of `postgresql` with `sslmode=require`, and its tasks and cache at
  databases 0 and 1 of the Service `valkey` with the password of
  `valkey-auth`.

  - Test: `check netbox`; `tests/smoke`
  - Since: #79

- RCP-142: The `tests/smoke` of `netbox` MUST get `/login/` and
  `/api/status/` through the Service `netbox`, and the status MUST report
  the version of the image tag the Deployment runs and at least one
  running worker. It MUST provision a token through
  `/api/users/tokens/provision/` with the superuser's login, get 403 with
  another token, create a site and a prefix through the API with the token
  and read both back. It MUST sync a data source through
  `/api/core/data-sources/<id>/sync/` and require that the job completes
  and that `/api/core/background-tasks/` reports its task as finished by a
  worker. Every connection of `app` to PostgreSQL MUST use TLS.

  The status counts the workers registered in Valkey. The token's
  plaintext is hashed with the pepper, so the token works only with the
  pepper the target set. The sync runs as a job that NetBox queues in
  Valkey's database 0 and the worker runs, so the finished task needs the
  API, Valkey, the worker and PostgreSQL. On kind with the worker scaled
  to zero the status reported no running worker, and the smoke test
  failed.

  - Test: CI `check` job, report line `smoke`
  - Since: #79

- AC-90 (RCP-140 to RCP-142): `check netbox --level deploys` passes in CI
  on each Kubernetes minor, its report lists the objects of `postgresql`
  and `valkey` as included and `cnpg` as installed, the permissions of the
  ServiceAccount `netbox` are equal on both sides, and its smoke test
  reads back the prefix it created and finds the sync finished.
  `tests/target.yml` without one of the five parameters of RCP-140 stops
  the compile with `Interpolation key` and that key.

## Ollama

Ollama runs language models and serves them through an HTTP API on port
11434, its own and an OpenAI-compatible one below `/v1`. The project
publishes no chart. Open WebUI's chart `open-webui` 17.5.0 renders Ollama
through its subchart `ollama` 1.79.0 of otwld/ollama-helm, which OTWLD
maintains, and turns it on by default. otwld/ollama-helm publishes the
chart with chart-releaser in the HTTP repository
`https://otwld.github.io/ollama-helm` and as a GitHub release asset, and
pushes no OCI artifact, so the `Source` line takes the HTTP form of
RCP-23. The archive is the one Open WebUI's chart carries in `charts/`,
file by file. Chart and Ollama are MIT.

DEC-75: `ollama` is a recipe of its own on the chart `ollama` 1.79.0, the
version that `open-webui` 17.5.0 pins in its `Chart.lock`, and
`open-webui` includes it (DEC-4). otwld/ollama-helm had released 1.94.0 by
2026-11-03. Its newest version was considered. The chart that Open WebUI's
chart renders would then differ from the recipe that replaces it, and the
recipe would move ahead of the parent it serves. DEC-11 rejects a
third-party chart as the source of a designed recipe, which this is not:
the parent's own chart brings it as a subchart, the case of DEC-4.

DEC-76: `ollama` runs Ollama 0.33.2, the chart's `appVersion`. No advisory
in the GitHub Advisory Database for `github.com/ollama/ollama` on
2026-11-03 names 0.33.2 or a release after 0.20.2 as affected. Ollama
0.40.14, the newest release on 2026-11-03, was considered. It would move
the image ahead of the chart without a fix that an advisory names.

`tests/values.yaml` keeps the chart's defaults and sets
`image.repository: docker.io/ollama/ollama`, the chart's image with its
registry host (RCP-66). The release name `ollama` equals the chart's name,
so the Deployment, Service and ServiceAccount are all `ollama`. Models live
in the `emptyDir` `ollama-data` at `/root/.ollama`, the chart's default
without `persistentVolume.enabled`, so a new pod pulls them again. The
image carries the CUDA and ROCm libraries and is 3383 MB compressed for
amd64 and 2780 MB for arm64 (sums of the layer sizes in the registry
manifests, MB = 10^6 bytes). The recipe requests no GPU, and GPUs are not
tested, because kind has none.

Ollama's API has no authentication, so every pod that reaches the Service
`ollama` can pull, delete and run models. The chart's Ingress, HTTPRoute,
Gateway, Knative service, autoscaler and model pulls at start are off by
default and not part of the recipe. The ServiceAccount `ollama` has no
Role. The chart's Helm test `ollama-test-connection` is left out (RCP-25).

- RCP-130: `ollama` MUST render the chart's Deployment, Service and
  ServiceAccount `ollama` with `docker.io/ollama/ollama:0.33.2` pinned to
  its index, models in the `emptyDir` `ollama-data` and no GPU.

  - Test: `check ollama`
  - Since: #78

- RCP-131: The `tests/smoke` of `ollama` MUST require `Ollama is running`
  from `/` through the Service and the version of the image tag from
  `/api/version`. It MUST pull `smollm:135m` through `/api/pull`, find it
  in `/api/tags` with the digest of its manifest, and get a reply from
  `/api/generate` with `done: true`. It MUST print how long the pull and
  the generation took.

  `smollm:135m` is 92 MB and Apache-2.0, the smallest of the chat models
  compared on 2026-11-03: `smollm2:135m` has 271 MB, `gemma3:270m` 292 MB
  and `qwen2.5:0.5b` 398 MB (layer sizes in registry.ollama.ai). Ollama
  pulls by name only, so the digest in `/api/tags` shows that the test ran
  the model it names.

  - Test: CI `check` job, report line `smoke`
  - Since: #78

- AC-80 (RCP-130, RCP-131): `check ollama --level deploys` passes in CI on
  each Kubernetes minor, and its smoke test reports the time of the pull
  and of the generation.

## Uptime Kuma

Uptime Kuma checks HTTP endpoints, ports, DNS records and other services at
an interval, notifies when one goes down, and serves status pages. The
project publishes no chart. louislam/uptime-kuma, MIT, carries
`compose.yaml` at the root of the repository and builds the image
`docker.io/louislam/uptime-kuma`. `uptime-kuma` takes the file at commit
`df601c58d9205562f34cfe5ef35264b341019d19`, the tag of release 2.5.9 of
2026-10-31, the newest on 2026-11-03, SHA-256
`f62a065cabc4671225ec4e58575dd9cca364b0d0b5087b57451278791672a54b`. The
file runs `louislam/uptime-kuma:2`, which on 2026-11-03 was the same index
as `2.5.9`, for amd64, arm64 and arm/v7. The image carries no
`org.opencontainers.image.revision` label.

Every advisory of louislam/uptime-kuma published by 2026-11-03 names 2.5.9
or an earlier release as fixed, except GHSA-qjxc-h5jf-c7rj. That one
names no fixed release. A logged-in user's HTTP monitor reaches whatever
the pod reaches, a cloud's metadata endpoint among them, and upstream
leaves the protection to the platform.

The file's one service becomes the StatefulSet `uptime-kuma`. Its relative
bind mount `./data`, which the repository does not contain, becomes the
claim `data` at `/app/data` (DEC-21). The published port `3001:3001`
becomes port 3001 of the Service `uptime-kuma`. The image's `HEALTHCHECK`
runs `extra/healthcheck` in shell form every 60 seconds with a timeout of
30 seconds and 5 retries. It becomes the readiness probe
`sh -c extra/healthcheck` with these values. The check is a Go binary that
gets `/` on port 3001 and fails only when no answer arrives
(`extra/healthcheck.go`). The image runs as root, so the target's
namespace needs the Pod Security level `baseline`.

DEC-65: `uptime-kuma` sets `UPTIME_KUMA_DB_TYPE` to `sqlite`, which the
compose file leaves unset (Uptime Kuma). Without it Uptime Kuma 2 starts
a database setup page on port 3001, which asks for no login, and waits
until a visitor chooses SQLite, the MariaDB the image embeds or an external
MariaDB (`server/setup-database.js` of 2.5.9). With the variable it writes
`db-config.json` from the environment at every start and serves its web UI
right away. SQLite keeps the database in `kuma.db` on the claim and runs
one replica, as the compose file does. Leaving the choice to the setup page
was considered. The first visitor would choose the database, could point
Uptime Kuma at a MariaDB of their own, and the choice would not follow the
inventory. The embedded MariaDB was considered too. It starts a MariaDB
server inside the container, and SQLite needs none.

DEC-66: `uptime-kuma` renders no admin account. The first visitor of the
web UI creates it, as with the compose file (Uptime Kuma). Uptime Kuma
2.5.9 reads no account from the environment and has no HTTP API that
creates one. Its only path is the socket.io event `setup`, which takes a
username and a password while the `user` table is empty and needs no login
(`server/server.js`). A Job that sends the event with a credential
parameter was considered. It would add a workload and a client that the
compose file does not have. The event also fails once an account exists,
so a changed parameter would never reach the account. The Service is
`ClusterIP`, so until the target exposes it only the cluster reaches the
setup, and the README asks for the account before the exposure.

- RCP-120: The `Source` line of `uptime-kuma` MUST name `compose.yaml` of
  louislam/uptime-kuma at the commit of the release tag that the image's
  tag names, with the file's SHA-256.

  `check` fetches the file at that commit and fails on another SHA-256
  (RCP-23). Without a revision label on the image, the release tag is what
  ties the file to the image. Renovate moves only the image's digest
  (RCP-16), so a new release changes tag, commit and SHA-256 together by
  hand.

  - Test: `check lint`; CI `check` job, report line `compose`; manual:
    `gh api repos/louislam/uptime-kuma/git/ref/tags/<tag>`
  - Since: #76

- RCP-121: `uptime-kuma` MUST set `UPTIME_KUMA_DB_TYPE` to `sqlite`
  (DEC-65) and MUST mount the claim `data` at `/app/data`.

  `/app/data` holds `kuma.db`, `db-config.json` and uploaded files. Uptime
  Kuma rewrites `db-config.json` from the variable at every start, so the
  database type follows the inventory.

  - Test: CI `check` job, report line `smoke`
  - Since: #76

- RCP-122: The `tests/smoke` of `uptime-kuma` MUST, from a pod of its own
  and through the Service `uptime-kuma` on port 3001, require `entryPage`
  from `/api/entry-page` and the web UI from `/`, and get 401 from
  `/metrics`. Over socket.io on the WebSocket transport it MUST create the
  admin account with the event `setup`, log in, add an HTTP monitor
  against `http://kube-dns.kube-system:9153/metrics` and wait for a
  heartbeat UP. It MUST then require the monitor UP from `/metrics` with
  the account. Once the pod `uptime-kuma-0` was deleted and its successor
  is ready, it MUST log in again, find the monitor and wait for a new
  heartbeat UP.

  The setup page of DEC-65 answers `/api/entry-page` with
  `setup-database`, so `entryPage` shows that RCP-121 took effect. The
  server depends on socket.io-client 4.8, so the image carries it below
  `/app/node_modules`, and the test speaks the web UI's protocol with
  `node` in a pod of the same image. A WebSocket without an `Origin`
  header passes Uptime Kuma's origin check. The server attaches the
  handlers of a new connection only after it sent the event `info`, and
  drops what arrives before, so the client waits for `info` before it
  sends anything. kubeadm's Service `kube-dns`
  serves CoreDNS' metrics on port 9153 without a login, on every kind
  cluster. A heartbeat is sent only while the monitor runs, so the one
  after the restart shows that the new pod started the monitor from
  `kuma.db` on the claim.

  - Test: CI `check` job, report line `smoke`
  - Since: #76

- AC-70 (RCP-120 to RCP-122): `check uptime-kuma --level deploys` passes
  in CI on each Kubernetes minor, and its smoke test sees the monitor UP
  after the restart.

## Open WebUI

Open WebUI is a web interface and an API for chatting with language
models. It keeps users, chats and settings in a database and sends the
chats to Ollama or to OpenAI-compatible endpoints. `open-webui` deploys it
from the chart `open-webui` 17.5.0 of open-webui/helm-charts, the newest
stable release on 2026-11-03. The project publishes the chart at
`oci://ghcr.io/open-webui/helm-charts/open-webui` and in the HTTP
repository `https://helm.openwebui.com`. Both serve the same archive, and
the `Source` line takes the OCI form, as for gitea. The chart is MIT. Open
WebUI is under the Open WebUI License, BSD-3-Clause with a fourth clause
that forbids changing its branding in deployments with more than 50 users
in 30 days without the copyright holder's permission. The recipe ships no
Open WebUI code and names the image only, as `n8n` does.

The chart runs Open WebUI 0.12.5 as `ghcr.io/open-webui/open-webui:0.12.5`,
which the recipe pins to its index for amd64 and arm64. It is 1643 MB
compressed for amd64 and 1481 MB for arm64 (sums of the layer sizes in the
registry manifests, MB = 10^6 bytes). No advisory of open-webui/open-webui
published by 2026-11-03 names 0.12.5 as affected. 0.13.0 came out on
2026-11-03 and is not in a chart release yet.

By default the chart also turns on its subcharts `ollama` and `pipelines`
and its own Redis for the websocket manager, and sets the OpenAI API to
Pipelines and `https://api.openai.com/v1`. It sets no `WEBUI_SECRET_KEY`
and no database URL. Open WebUI then keeps its data in SQLite on the claim
`open-webui`, 2Gi with ReadWriteOnce, which the StatefulSet `open-webui`
mounts at `/app/backend/data`. The init container `copy-app-data` copies
what the image has at that path onto the claim without overwriting. The
chart's main container sets `tty: true`, which the `kubernetes` generator
renders from 1.14.0 on (K8S-16 in kadet-hub/generators).

DEC-77: `open-webui` renders no Pipelines. Pipelines runs Python code that
admins upload as plugins, in a container of its own, and the chart runs it
as `ghcr.io/open-webui/pipelines:main`, a tag that moves with every commit
of open-webui/pipelines. Rendering it was considered. It is the chart's
default, but the recipe would pin a moving tag to one digest, and Renovate
would have no version to follow. `tests/values.yaml` sets
`pipelines.enabled: false`.

DEC-78: `open-webui` uses the included recipe `valkey` for Redis, as
DEC-20 does for a service this repository has a recipe for. The chart's
`websocket.existingSecret` names a Secret whose key `redis-url` the chart
sets as `REDIS_URL` and `WEBSOCKET_REDIS_URL`. The recipe renders the
Secret `open-webui` with `redis://:<password>@valkey:6379/0` there, the
password from `applications.valkey.password`, with which Open WebUI
authenticates as Valkey's user `default`. The URL carries the password
unencoded, so it must consist of letters and digits, as for gitea
(DEC-36). The chart's own Redis was considered. It runs
`redis:7.4.2-alpine3.21`, a Docker Official Image, without a password, a
second way to run Redis next to `valkey`. A Kubernetes variable
`$(VALKEY_PASSWORD)` in the URL, as gitea builds it, was considered too.
The chart puts its own variables before `extraEnvVars`, and Kubernetes
expands only variables defined earlier in the list.

DEC-79: The backends are the options `ollama` and `openai` of
`open-webui`. Without them the recipe sets `ENABLE_OLLAMA_API` and
`ENABLE_OPENAI_API` to `False`, so Open WebUI calls neither
`api.openai.com` nor its built-in Ollama URL, and an admin adds
connections in its settings. `recipes.open-webui.ollama` includes the
recipe `ollama` (DEC-75), sets `ENABLE_OLLAMA_API` to `True` and
`OLLAMA_BASE_URLS` to `http://ollama:11434`. `recipes.open-webui.openai`
sets `ENABLE_OPENAI_API` to `True`, `OPENAI_API_BASE_URL` from
`applications.open-webui.openai.url` and `OPENAI_API_KEY` from the key
`openai-api-key` of the Secret `open-webui`. vLLM and SGLang serve such an
endpoint and are reached through `openai`. No recipe renders them, since
they need a GPU and images of several GB that `check` cannot run on kind.

The chart's values `ollamaUrls` and `openaiBaseApiUrl` were considered as
the values of the proof. The chart renders their variables first in the
container's environment. An option class can only add keys after the ones
the recipe sets, because omegaconf appends new keys of a mapping, and
cannot remove one, because the generator renders `null` as the string
`None`. `tests/values.yaml` therefore sets `ollamaUrlsFromExtraEnv: true`
and an empty `openaiBaseApiUrl`, with which the chart renders neither, and
gives all variables of the options through `extraEnvVars` in the order the
options add them. Open WebUI reads its environment by name, so the order
changes nothing.

DEC-80: `open-webui` takes `WEBUI_SECRET_KEY` from
`applications.open-webui.secret_key`, which Open WebUI signs its logins
with. Without the variable the image's `backend/start.sh` of 0.12.5
generates a key into `/app/backend/.webui_secret_key`, outside the claim,
so every new container signs with a new key and every restart signs every
user out. `tests/values.yaml` sets it through `extraEnvVars` from the same
Secret.

The chart's `databaseUrl` would put a PostgreSQL URL with its password as
a plain value into the StatefulSet, so the recipe stays on the chart's
SQLite and does not include `postgresql`. Open WebUI copies its settings,
such as the backend URLs and `ENABLE_SIGNUP`, into the database on the
first start and keeps the database's values on later starts
(`seed_defaults` in `backend/open_webui/models/config.py` of 0.12.5), so a
changed URL in the target reaches a running instance only through the
admin settings. Signup is open until the first account signs up, Open
WebUI's default, which the chart does not change. That account becomes
admin, and Open WebUI then turns signup off in its settings
(`signup_handler` in `backend/open_webui/routers/auths.py` of 0.12.5), so
whoever reaches the Service first owns the instance. The README says so.
An admin who turns signup back on gets later accounts as `pending`
(`DEFAULT_USER_ROLE`).

The generator renders an empty `securityContext` on an init container,
which `check` does not accept where the chart has none (RCP-12).
`tests/values.yaml` sets the chart's `containerSecurityContext` to
`allowPrivilegeEscalation: false`, which the chart puts on both
containers, as gitea does. The image runs as root. The chart's Tika,
Terminals, Ingress, HTTPRoute, GKE ManagedCertificate and object storage
are off by default and not part of the recipe. The ServiceAccount
`open-webui-sa` has no Role, and the chart renders no hook.

- RCP-132: `open-webui` MUST take `WEBUI_SECRET_KEY` from
  `applications.open-webui.secret_key` and the password of the Redis URL
  from `applications.valkey.password`, and MUST leave the first unset.

  The compile then stops with `Interpolation key` and the key's name until
  the target sets it, as a ref (RCP-19, RCP-40). The README names
  `applications.valkey.password` as well (RCP-51).

  - Test: CI `lint` job; manual: a compile of `tests/target.yml` without
    `applications.open-webui.secret_key` stops with `Interpolation key`
    and its name
  - Since: #80

- RCP-133: Without an option `open-webui` MUST set `ENABLE_OLLAMA_API` and
  `ENABLE_OPENAI_API` to `False` and render no object of `ollama`. The
  option `ollama` MUST include `recipes.ollama` and point
  `OLLAMA_BASE_URLS` at `http://ollama:11434`. The option `openai` MUST
  take the URL and the key from `applications.open-webui.openai.url` and
  `.api_key` and leave both unset.

  - Test: `check open-webui`; manual: compiles of `tests/target.yml`
    without the options and with each one
  - Since: #80

- RCP-134: The `tests/smoke` of `open-webui` MUST require `/health`
  through the Service. It MUST sign up the first account through
  `/api/v1/auths/signup` and require the role `admin`, and require 403
  for a second signup. It MUST start an OpenAI-compatible stub, pull
  `smollm:135m` through `/ollama/api/pull`, find that model owned by
  `ollama` and the stub's owned by `openai` in `/api/models`, and get a
  chat completion from each through `/api/chat/completions`. Valkey MUST
  hold keys with Open WebUI's prefix, and the admin's token MUST still
  work after the pod `open-webui-0` restarted. It MUST print how long the
  pull and the completion took.

  The test waits up to five minutes for `/health`, which with the
  readiness probe of RCP-287 answers at once after the rollout. The
  completion from `smollm:135m` runs through Open WebUI and Ollama on
  the CPU. The stub is busybox's `httpd` with a script that lists one
  model and gives every completion the same reply, so the reply shows
  that the request went to the endpoint of the option `openai`. Open WebUI
  keeps state with the prefix `open-webui` in Redis (`REDIS_KEY_PREFIX`).
  A token signed with the key of the old pod is valid in the new one only
  with `WEBUI_SECRET_KEY` set (DEC-80).

  - Test: CI `check` job, report line `smoke`
  - Since: #80

- RCP-287: `open-webui` MUST have a readiness probe on `/ready` of the
  port `http`, and no liveness or startup probe. `tests/values.yaml` MUST
  set the same probe as the chart's `readinessProbe`.

  The chart renders a probe only from its values `readinessProbe`,
  `livenessProbe` and `startupProbe`, which default to `{}`. Without a
  probe `rollout status` returned before Open WebUI listened, and a
  port-forward started then ended at the first refused connection, which
  the open-webui-searxng example in kadet-hub/examples ran into. Open
  WebUI 0.12.5 answers `/ready` once its startup is complete and its
  database and Redis answer a ping (`readiness_check` in
  `backend/open_webui/main.py`). The chart's commented example uses
  `/health/db`, which pings the database only. A liveness probe would
  restart a pod that is only slow, as in RCP-185. The timeout is 3
  seconds, as for searxng.

  - Test: `check open-webui` (renders: the probe compared with the
    chart's; deploys: `rollout status`, then RCP-134)
  - Since: #109

- AC-81 (RCP-132 to RCP-134): `check open-webui --level deploys` passes in
  CI on each Kubernetes minor, its report lists the objects of `ollama`
  and `valkey` as included, and its smoke test gets a completion from
  `smollm:135m` and from the stub.

## MariaDB

MariaDB Server is a relational database that speaks the MySQL protocol.
Bitnami's `mariadb` chart was a common way to run it on Kubernetes. The
MariaDB Foundation publishes no chart and no Kustomize base. It maintains
the Docker Official Image `mariadb` in MariaDB/mariadb-docker, GPL-2.0,
whose README names the MariaDB Foundation and Community as maintainers.
docker-library builds the image from that repository, as `library/mariadb`
in docker-library/official-images records. The packaging is therefore the
project's own. The `mongo` image, which mongodb left aside (Designed
recipes), is packaged by docker-library itself in docker-library/mongo.

The repository's compose files are examples below `examples/`.
`compose-debug.yml` runs a debug build of 11.2 under gdb.
`replication-async/compose-replication.yml` and its semi-synchronous
variant start a primary and two replicas from `mariadb:lts` without a
volume. The files below `migration-5.7/` and `migration-8/` move a MySQL
database into MariaDB.

DEC-95: `mariadb` is a designed recipe on `docker.io/library/mariadb`
(DEC-11). The compose examples were considered as sources (DEC-10). None
runs a single server that keeps its data: the replication examples run
three servers whose data lives in the containers, and the others debug a
server or migrate from MySQL. mariadb-operator/mariadb-operator, MIT, was
considered as well. It is a project outside the MariaDB Foundation, and no
kadet-hub generator renders its resources (RCP-7). Bitnami's chart is a
third-party chart, which DEC-11 rules out.

The recipe follows the 12.3 LTS release line. The downloads REST API of
mariadb.org listed 12.3 on 2026-11-04 as the newest series with support
type "Long Term Support", GA on 2026-05-28 and supported until 2029-06-12.
13.0 is a rolling release. 12.3.3 of 2026-08-22 was the newest 12.3
release. Docker Hub's tag `12.3.3` is the index
`sha256:d46e102fa8b9b72bfcdeb56f9dd538742092119dc8b11f31fe662605cd234cd9`
for amd64, arm64/v8, ppc64le and s390x, built from mariadb-docker at
`bdfe641466a5312bb97d06a1a4e1fb411c49e6b6`, and on 2026-11-04 it was also
the tag `lts`.

The image runs `mariadbd` as the user `mysql`, UID 999 in its
`/etc/passwd`, and its entrypoint skips the switch from root when the
container starts as that user. The entrypoint initializes an empty data
directory with networking off. It creates the database `MARIADB_DATABASE`,
the user `MARIADB_USER` with `ALL` on that database, and `root` for
`localhost` and `%` (`12.3/docker-entrypoint.sh`). It also creates the
user `healthcheck` and its client file `.my-healthcheck.cnf` in the data
directory, which the image's `healthcheck.sh` reads.

With a `lost+found` directory at the root of the data directory, as an
ext4 volume has, MariaDB 12.3.3 listed the database `#mysql50#lost+found`,
and `mariadb-dump --all-databases` stopped on it with errno 13 while the
directory belonged to root. This was a local run of the pinned image with
Docker. The claim therefore holds the data in its subdirectory `mariadb`,
as `mysql` keeps its data below the subdirectory `mysql`.

DEC-96: `mariadb` has one probe, the readiness probe
`healthcheck.sh --connect --innodb_initialized` every 10 seconds with a
timeout of 5 seconds and 3 failures. These are the test and the values of
the compose example on the image's documentation page "Using
Healthcheck.sh" at mariadb.com, and the generator's defaults. The image
has no `HEALTHCHECK`. `--connect` fails while the server has networking
off, so the pod is not ready during the initialization. The TCP probes of
`mysql` were considered. They test only that the port is open, where the
documentation gives a check of InnoDB. A liveness probe was considered.
MariaDB opens its port only after its storage engines started, InnoDB's
crash recovery included (`mysqld_main` in `sql/mysqld.cc` of 12.3.3). A
liveness probe would restart a recovery that outlasts its threshold, and
the next start would recover again. Without a liveness probe no startup
probe is needed either.

Pod Security is as for `mysql`: `security_profile: restricted` with
`runAsUser`, `runAsGroup` and `fsGroup` 999. `tests/smoke` also checks
that the running pod passes the level `restricted`.

DEC-97: `mariadb` configures no TLS and leaves the server's zero
configuration TLS in place. MariaDB from 11.4 on generates a self-signed
certificate when none is configured, and its clients verify the
certificate by default through the account's password with
`mysql_native_password`, `ed25519` or `parsec` (MariaDB documentation
"Zero-Configuration SSL"). The entrypoint creates `app` with
`mysql_native_password`. `tests/smoke` connects with
`--ssl-verify-server-cert` and requires TLS on the session. `mysql`
neither sets nor checks TLS. A certificate from cert-manager was
considered. It would add cert-manager as a prerequisite (DEC-13) for a
verification that clients of 11.4 and later get without a CA.
`--require-secure-transport=ON` was considered. It refuses a client that
does not ask for TLS, which the image's default accepts, so the README
names the option as a setting.

Renovate moves the `Source` line and the class line marked
`# renovate: Source` together (RCP-16). A package rule keeps both on the
12.3 line. Docker Hub listed 957 tags of `library/mariadb` on 2026-11-04.
It serves the tag list 100 tags a page and refused the eleventh page of
`library/rabbitmq` to an anonymous request on the same day, so past 1000
tags Renovate gets no release timestamps, as for `rabbitmq`. The same rule
therefore makes the timestamp optional for the image.

- RCP-160: `mariadb` MUST run `docker.io/library/mariadb` of the 12.3 LTS
  line, pinned to its index, as the StatefulSet `mariadb` with the user
  `mysql`, UID 999, and `security_profile: restricted`. It MUST mount the
  claim `data` at `/var/lib/mysql` from the claim's subdirectory
  `mariadb`, and MUST create `applications.mariadb.database` and
  `applications.mariadb.user` with the passwords of the Secret `mariadb`.

  - Test: `check lint`; CI `check` job, report lines `image` and `smoke`
  - Since: #86

- RCP-161: `mariadb` MUST have the readiness probe of DEC-96 and no
  liveness or startup probe.

  - Test: manual: review; CI `check` job, which waits for the rollout
  - Since: #86

- RCP-162: The `tests/smoke` of `mariadb` MUST connect as the user `app`
  to its database through the Service `mariadb` on port 3306 with
  `--ssl-verify-server-cert`, require TLS on the session, create a table,
  write a row and read it back, and require a server version that starts
  with the image's tag. It MUST require no Pod Security warning from a
  server-side dry run of the label `pod-security.kubernetes.io/enforce:
  restricted` on its namespace. Once the pod `mariadb-0` was deleted and
  its successor is ready, it MUST read the row again through the Service.

  The admission plugin PodSecurity answers a change of a namespace's
  `enforce` label with a warning that names each running pod that would
  violate the new level, also on a dry run, so the label is never set.
  The tag is read from the StatefulSet, so the test follows a new image.
  The row after the restart shows that the data lives on the claim.

  - Test: CI `check` job, report line `smoke`
  - Since: #86

- RCP-163: Renovate MUST keep the image of `mariadb` on the 12.3 line and
  MUST NOT need a release timestamp for it.

  - Test: manual: Renovate dry run
  - Since: #86

- AC-95 (RCP-160 to RCP-162): `check mariadb --level deploys` passes in CI
  on each Kubernetes minor, and its smoke test reads the row after the
  restart.

## WordPress

WordPress is a PHP application for websites. It keeps posts, users and
settings in MySQL or MariaDB, and uploads, plugins and themes in its
directory `wp-content`. Bitnami's `wordpress` chart was the most installed
way to run it on Kubernetes, and Bitnami stopped publishing its free
images.

The WordPress project publishes no chart, no Kustomize base and no image
for a site. WordPress/wordpress-develop carries `docker-compose.yml` for
the development environment of WordPress core. It serves the repository's
own checkout through the bind mount `./:/var/www`, on which Compose sources
stop, and runs no WordPress release. WordPress/wpdev-docker-images builds
that environment's images `wordpressdevelop/php` and `wordpressdevelop/cli`,
which contain PHP and WP-CLI without WordPress.

The Docker Official Image `wordpress` packages every WordPress release. Its
Dockerfile downloads the release from wordpress.org and checks the SHA-1
that the build pins. docker-library/wordpress, GPL-2.0, holds the
Dockerfiles, and `library/wordpress` in docker-library/official-images
names Tianon Gravi and Joseph Ferguson of docker-library as maintainers,
the same as `library/rabbitmq`. The packaging is therefore docker-library's
and not the project's, unlike that of `mariadb` (MariaDB).

DEC-110: `wordpress` is a designed recipe on `docker.io/library/wordpress`
(DEC-11). DEC-11 names the project's image, and WordPress publishes none
for a site, so the Docker Official Image takes its place, as
`docker.io/library/rabbitmq` does for `rabbitmq`. The compose file of
wordpress-develop was considered as the source (DEC-10). It stops on its
bind mounts and runs a development checkout. Bitnami's chart is a
third-party chart, which DEC-11 rules out.

WordPress 7.1.4 was the newest release on 2026-11-04, by the version check
API of api.wordpress.org. docker-library builds it for PHP 8.2 to 8.5, each
as `apache`, `fpm` and `fpm-alpine`, and the tag `7.1.4-apache` without a
PHP version is PHP 8.3. The tag `7.1.4-php8.5-apache` is the index
`sha256:41666f6d61dd038f87ceacd6323685bd9818a3a9b3d80d98af3ce9797c403dce`
for amd64, arm/v5, arm/v7, arm64/v8, 386, ppc64le, riscv64 and s390x,
built from docker-library/wordpress at
`ef1166e08e869848d1633c0ae2078a486a305b68`. It runs PHP 8.5.12 and Apache
2.4.69 on Debian 13.

DEC-111: `wordpress` runs the tag `7.1.4-php8.5-apache`. php.net gives PHP
8.5 active support until 2027-12-31, 8.4 until 2026-12-31, and 8.3 none
since 2025-12-31. The PHP compatibility table of the WordPress core
handbook lists WordPress 7.1 as compatible with PHP 7.4 to 8.5, and
wordpress.org recommends PHP 8.3 or later. Renovate's docker versioning
proposes only tags with the pinned suffix, here `-php8.5-apache`, so the
PHP version changes only by hand. The variant `apache` serves PHP from one
container, where `fpm` needs a web server next to it. The image's default
`7.1.4-apache` was considered. It runs PHP 8.3, which gets security fixes
only, and its PHP version would change whenever docker-library moves the
default. A plugin that does not run on PHP 8.5 yet needs another tag,
which the README names as a setting.

### Files, database and keys

At its start the image's entrypoint copies WordPress from
`/usr/src/wordpress` to `/var/www/html` when that directory holds neither
`index.php` nor `wp-includes/version.php`. It skips every directory
`wp-content/<type>/<name>` that already exists, and writes `wp-config.php`
from `wp-config-docker.php` when the file is missing and a `WORDPRESS_*`
variable is set (`docker-entrypoint.sh`). `wp-config-docker.php` reads the
database settings and the eight keys and salts from `WORDPRESS_*`
variables.

`wordpress` mounts the claim `data` only at `/var/www/html/wp-content`,
from the claim's subdirectory `wp-content` (DEC-113), so uploads, plugins
and themes outlive the pod. The core files and `wp-config.php` are written
anew at every start, from the image and the inventory. The image tag is
then the WordPress version. WordPress's own automatic core update writes
into the container and is lost with the pod, whose successor runs the
image's version again. The claim is 8Gi, as `mariadb`'s, and the README
names the size as a setting. The whole `/var/www/html` on the claim, as
the image's documentation mounts it, was considered. The entrypoint copies
WordPress only onto an empty directory, so WordPress would update itself
on the claim and a new image tag would change nothing.

The database is the included recipe `mariadb` (DEC-4, DEC-12).
`WORDPRESS_DB_HOST` is its Service `mariadb`, `WORDPRESS_DB_NAME` and
`WORDPRESS_DB_USER` come from `applications.mariadb.database` and `.user`,
and `WORDPRESS_DB_PASSWORD` from the key `password` of its Secret
`mariadb`.

DEC-112: WordPress connects to MariaDB without TLS. WordPress 7.1.4 passes
the constant `MYSQL_CLIENT_FLAGS`, 0 when `wp-config.php` does not define
it, to `mysqli_real_connect` (`wp-includes/class-wpdb.php`), and MariaDB
accepts a client without TLS (DEC-97). On kind, mysqli of the pinned image
connected without TLS with the flags 0, and over TLSv1.3 with
`MYSQLI_CLIENT_SSL` alone, although no CA was given for the certificate
that MariaDB generates. Defining the constant with `MYSQLI_CLIENT_SSL`
through `WORDPRESS_CONFIG_EXTRA` was considered. It encrypts without
verifying the server, and the variable is the one place where a target
adds its own settings.

Without the eight variables `WORDPRESS_AUTH_KEY` to `WORDPRESS_NONCE_SALT`
the entrypoint replaces each placeholder with a random value when it
writes `wp-config.php`. Since `wp-config.php` is written at every start,
every new pod would sign cookies with new keys and log every user out, and
two replicas would reject each other's cookies. The keys are therefore
parameters under `applications.wordpress` that the target sets (RCP-19),
in the Secret `wordpress`.

### Pod Security

The image starts as root. The entrypoint then copies WordPress and Apache
binds port 80 as root, and Apache's workers switch to `www-data`, UID 33.
Started as another user, the entrypoint copies as that user and Apache runs
as it. In the image, Apache's lock, PID and log directories and
`/var/www/html` belong to `www-data` with mode 1777. For another user the
image's documentation refers to that of the `php` image, which names two
ways for its Apache variants: the sysctl
`net.ipv4.ip_unprivileged_port_start` at 0, or an Apache configuration on
a port above 1024. On kind with the node image of Kubernetes 1.37, a pod
of the pinned image as UID and GID 33, with every capability dropped,
served WordPress. With the pod's sysctl at 1024, the kernel's default,
Apache stopped with `(13)Permission denied: AH00072: make_sock: could not
bind to address 0.0.0.0:80`, also with `NET_BIND_SERVICE` added. A
process that does not run as root keeps none of the container's
capabilities in its effective set. The node's containerd 2.3.4 sets the
sysctl to 0 for every pod (`enable_unprivileged_ports`), which a runtime
need not do.

Run as another user than root, the entrypoint's `tar` stops with
`./wp-content: Cannot change mode to rwxrwxrwx: Operation not permitted`
when a volume mounted at `wp-content` belongs to another user, and the
container exits. The root directory of a new volume belongs to root.
kind's local-path provisioner creates it with mode 0777, and the kubelet
gives a volume that supports `fsGroup` the group 33 and mode 2775. With
Docker and UID 33 the copy stopped in both modes, also with the volume at
`/var/www/html`, and passed only on a directory that UID 33 owns. On kind,
with the claim's root at `wp-content`, the container exited on this error
at every start.

DEC-113: `wordpress` runs as `www-data`, UID, GID and `fsGroup` 33, under
`security_profile: restricted`, and sets the pod's sysctl
`net.ipv4.ip_unprivileged_port_start` to 0, so Apache binds port 80
without a capability on any runtime. Pod Security `baseline` and
`restricted` allow this sysctl, and it applies to the pod's network
namespace only. The init container `wp-content`, of the same image and
user, creates the directory `wp-content` on the claim, which the
container mounts as its subdirectory. UID 33 then owns the mount point
wherever the claim's root is writable for the group 33 or for everyone.
Root under Pod Security `baseline`, as the image's default, was
considered. Apache's parent process would run as root. Apache on port 8080
was considered as well. It would take `/etc/apache2/ports.conf` and the
site `000-default.conf` of the image as ConfigMaps, which the recipe would
have to keep in step with the image, and the claim would still need the
init container. `tests/smoke` checks that the pods pass the level
`restricted`.

### Probe and installation

DEC-114: `wordpress` has one probe, the readiness probe `GET /wp-login.php`
on port `http` at the generator's period of 10 seconds, timeout of 5
seconds and 3 failures. The image has no `HEALTHCHECK`, and its
documentation names no check. `wp-login.php` loads WordPress with its
options from the database. It answers 302 to `wp-admin/install.php`
before the installation, 200 after it, and 500 while the database is
unreachable, so the pod leaves the Service while it cannot serve pages. On
kind, with MariaDB scaled to zero, the pod became unready without a
restart and ready again once MariaDB was back. A liveness probe was
considered. Through WordPress it would restart every WordPress pod while
MariaDB is down, and on a static file it would test Apache alone.

DEC-115: `wordpress` renders no installation and no admin account. The
first visitor of `wp-admin/install.php` names the site and creates the
admin, as with the image alone. A Job with WP-CLI from the image tag
`cli`, with the admin's credentials as parameters, was considered. It
needs WordPress's files and `wp-config.php`, which only the WordPress pod
writes, and the claim is `ReadWriteOnce`. It would install only once, so a
changed parameter would not reach the account. The Service is `ClusterIP`,
so until the target exposes it only the cluster reaches the installation,
and the README asks for it before the exposure.

- RCP-180: `wordpress` MUST run `docker.io/library/wordpress` with the tag
  of DEC-111, pinned to its index, as the StatefulSet `wordpress` with the
  user `www-data`, UID 33, the sysctl and the profile of DEC-113. It MUST
  mount the claim `data` at `/var/www/html/wp-content` from the
  subdirectory that the init container `wp-content` creates, and MUST set
  the keys and salts from the parameters of `applications.wordpress` through
  the Secret `wordpress`.

  - Test: `check lint`; CI `check` job, report lines `image` and `smoke`
  - Since: #88

- RCP-181: `wordpress` MUST include `recipes.mariadb` and connect to the
  Service `mariadb` with the database and user of `applications.mariadb`
  and the key `password` of the Secret `mariadb`.

  - Test: CI `check` job, report line `smoke`
  - Since: #88

- RCP-182: `wordpress` MUST have the readiness probe of DEC-114 and no
  liveness or startup probe.

  - Test: manual: review; CI `check` job, which waits for the rollout
  - Since: #88

- RCP-183: The `tests/smoke` of `wordpress` MUST require no Pod Security
  warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace before
  it starts a pod of its own. From that pod, through the Service
  `wordpress` on port 80, it MUST get the redirect to
  `wp-admin/install.php`, install WordPress with a POST to
  `wp-admin/install.php?step=2`, and require the version of the image tag
  in the front page's generator tag. It MUST get no session for a wrong
  password, log in through `wp-login.php`, publish a post through
  `/wp/v2/posts` of the REST API and read it without the session on its
  permalink. It MUST upload a PNG through `/wp/v2/media` and fetch it byte
  for byte from its `source_url`. Once the pod `wordpress-0` was deleted
  and its successor is ready, it MUST read the post and the PNG again and
  reach `/wp/v2/users/me` with the session of the login.

  The installation goes through the Service as a visitor's would, so the
  test needs no image besides WordPress's and no access to the claim
  (DEC-115). Application passwords need HTTPS unless the environment type
  is `local` (`wp_is_application_passwords_supported`), so the REST calls
  use the login's cookie with the nonce of
  `wp-admin/admin-ajax.php?action=rest-nonce`. The post comes back from
  MariaDB and the PNG from the claim. The session after the restart shows
  that the keys come from the Secret. On kind, with the eight variables
  removed, a session got 400 from `admin-ajax.php` after the restart, where
  the entrypoint had written new random keys.

  - Test: CI `check` job, report line `smoke`
  - Since: #88

- RCP-184: Renovate MUST NOT need a release timestamp for the image of
  `wordpress`.

  Docker Hub listed 5982 tags of `library/wordpress` on 2026-11-04, so
  Renovate gets no release timestamps for it, as for `rabbitmq` (RCP-16).

  - Test: manual: Renovate dry run
  - Since: #88

- AC-110 (RCP-180 to RCP-183): `check wordpress --level deploys` passes in
  CI on each Kubernetes minor, its report lists the objects of `mariadb`
  as included, and its smoke test reads the post and the PNG after the
  restart.

## Ghost

Ghost is a publishing platform for blogs and newsletters. It keeps posts,
staff users, members and settings in MySQL, and uploaded images, themes
and its log files in its content directory. Staff work in the admin app
below `/ghost/`, which talks to the Admin API, and readers get the pages
that the active theme renders. Ghost is MIT. Release v6.75.0 of
2026-11-04 was the newest of TryGhost/Ghost on 2026-11-05.

Ghost publishes no chart and no Kustomize base. Its install guide for
Docker (docs.ghost.org/install/docker) clones TryGhost/ghost-docker, MIT,
and runs its `compose.yml`. On 2026-11-05 the file at
`af0fcad04ef1e4c6b7582ddc36696be5138820b2` ran Caddy, Ghost and MySQL by
default, and further services in the profiles `analytics` and
`activitypub`. Compose sources stop on that file. `caddy` mounts the
directory `./caddy` and `db` the directory `./mysql-init`, both of which
the repository contains. `tinybird-login` and `tinybird-deploy` `build`
without a published `image`. `working_dir`, `tty` and `profiles` are keys
that the mapping of Compose sources does not name.

The file runs Ghost as `ghost:6-alpine`, the Docker Official Image `ghost`.
`library/ghost` in docker-library/official-images names Austin Burdine of
Ghost, with a ghost.org address, as its maintainer and builds it from
TryGhost/docker-library-ghost, MIT. The packaging is therefore Ghost's
own, as `mariadb`'s is MariaDB's (MariaDB). Docker Hub's tag
`6.75.0-alpine`, also `6-alpine` on 2026-11-05, is the index
`sha256:bea7100f19d83b23c234fd8ad94a90505552f7b0f5f307b079907c1fd03dbdf7`
for amd64 and arm64, built from TryGhost/docker-library-ghost at
`1742107e163584e436b1f155d3751400a58384f0`. It runs Ghost on Node 22 and
Alpine 3.23.

DEC-210: `ghost` is a designed recipe on
`docker.io/library/ghost:6.75.0-alpine` (DEC-11). The compose file of
TryGhost/ghost-docker was considered as the source (DEC-10). It stops on
the directories it mounts and on its `build` services, as above. The
variant `alpine` is the one that file runs. The Debian variant, the tag
`6.75.0` without a suffix, was considered. It is the image's default, and
Ghost's own compose file does not use it.

The image's entrypoint copies the default content, the themes Casper and
Source among it, from `/var/lib/ghost/content.orig` into each directory of
`/var/lib/ghost/content` that does not exist yet, and starts
`node current/index.js` (`docker-entrypoint.sh`). Started as root, it
first gives the content directory to the user `node`, UID and GID 1000 in
the image's `/etc/passwd`, and switches to it. Started as that user, it
skips both steps. `ghost` runs as `node` with `fsGroup` 1000 under
`security_profile: restricted`, and mounts the claim `content` at
`/var/lib/ghost/content`. On kind the entrypoint filled the claim and Ghost
wrote uploads to it. The claim is 8Gi, as `mysql`'s, and the README names
the size as a setting.

The image's configuration, `config.production.json`, listens on port 2368
and sets the URL `http://localhost:2368`. Ghost reads further settings from
environment variables whose `__` separates the levels of its
configuration. `url` is the address readers and staff reach the site at.
Ghost builds every link from it, and with an `https` URL it redirects a
request that does not arrive over HTTPS, as a proxy reports it in
`X-Forwarded-Proto`. The recipe sets `url` from
`applications.ghost.url`, which the target sets (RCP-19).

DEC-211: The database is the included recipe `mysql` (DEC-4, DEC-12),
MySQL 9.7.4 of the 9.7 LTS line. Ghost connects to the Service `mysql`
with `applications.mysql.database` and `.user` and the key `password` of
the Secret `mysql`. `database__client` stays `mysql`, the default of
Ghost's production configuration. Ghost's compose file runs MySQL 8.0.46,
and Ghost's CI runs its tests against MySQL 8.0 only
(`.github/workflows/ci.yml` of v6.75.0). The install guide names no MySQL
version. endoflife.date lists the end of life of MySQL 8.0 as 2026-04-30.
On kind with the pinned images, Ghost created its schema on MySQL 9.7.4,
and the smoke test writes and reads posts. Nothing upstream tests Ghost's
later migrations on 9.7. A MySQL 8.0 component inside `ghost`, as the
compose file runs it, was considered. It would run a release line past its
end of life, and run MySQL a second way next to `mysql`, as DEC-20 argues
for paperless-ngx. Ghost connects without TLS, because its knex
configuration sets no `ssl` for `mysql2` (`configure-knex.ts` of v6.75.0).

Ghost exits when its database does not answer at start. On kind, with
`mysql` scaled to zero, the pod restarted twice in 45 seconds with
`ECONNREFUSED` on port 3306. Ghost's compose file starts it once `db` is
healthy. The init container `wait-for-database` of Ghost's image waits
until the Service `mysql` accepts connections on port 3306, as DEC-121
does for umami. The Service has an endpoint only once MySQL is ready, and
the image's BusyBox carries `nc`.

DEC-212: `ghost` has one probe, the readiness probe `GET /` on port `http`
with the header `X-Forwarded-Proto: https`, at the generator's period of 10
seconds, timeout of 5 seconds and 3 failures. The image has no
`HEALTHCHECK`, and the install guide names no check. Ghost opens its port
about a second after start and answers 503 while it boots. Its first boot
on kind spent 28 seconds creating the schema. Without the probe the Service
would send requests to it during that time. The front page reads posts from
the database. On kind it answered 503 during the boot, 200 afterwards and
500 while `mysql` was scaled to zero, with an `http` and with an `https`
URL. Without the header, Ghost answers the front page under an `https` URL
with 301 to HTTPS on the host the request named. The kubelet follows a
redirect to the same host (`pkg/probe/http/http.go` of Kubernetes). On
kind, under an `https` URL and without the header, the pod never became
ready, and the kubelet reported
`server gave HTTP response to HTTPS client`. The header marks the probe's
request as HTTPS, so Ghost renders the page under either scheme. A probe of `/ghost/api/admin/site/` was
considered. It answered 200 while `mysql` was down. A liveness probe was
considered. A database migration of a new Ghost version runs in the booting
process, and a restart in the middle of it would start it again.

DEC-213: `ghost` renders no owner account. The first visitor of
`/ghost/#/setup` names the site and creates the owner, as with Ghost's
compose file. Ghost 6.75.0 reads no account from its configuration. The
Admin API's `POST /authentication/setup/` creates the owner without a
login while none exists, and answers 403 afterwards
(`api/endpoints/authentication.js`). A Job that posts the setup with a
credential parameter was considered. It would add a workload that no
Ghost artifact has, and as the setup fails once an owner exists, a
changed parameter would never reach the account. The Service is
`ClusterIP`, so until the target exposes it only the cluster reaches the
setup, and the README asks for the setup before the exposure. Members, the
readers who subscribe to a site, sign up through Ghost's Portal by a link
that Ghost mails. Who may sign up is a setting of the site in the
database, which the recipe leaves at Ghost's default.

DEC-214: `ghost` configures no mail. The image's configuration sets
Ghost's transport `Direct`, which delivers to the recipient's mail server
from the pod. Ghost mails staff invitations, password resets and members'
sign-in links, and with `security.staffDeviceVerification`, `true` by
default, a code for each login from a browser without a verified session.
The first login of a user that never logged in skips the code
(`api/endpoints/session.js`). On kind, the owner's first login after the
setup got a session, and a second login answered 500 with
`Failed to send email`. The recipe keeps the verification on. Mail needs
an account at a mail provider, which only the target can name, so the
README names the settings and says that logins after the first need them.
Turning the verification off by default was considered. It would remove
the check of a new device for every installation, also once mail works.

- RCP-290: `ghost` MUST run `docker.io/library/ghost` in the variant
  `alpine` of DEC-210, pinned to its index, as the StatefulSet `ghost`
  with UID, GID and `fsGroup` 1000 and `security_profile: restricted`. It
  MUST mount the claim `content` at `/var/lib/ghost/content` and set `url`
  from `applications.ghost.url`.

  - Test: `check lint`; CI `check` job, report lines `image` and `smoke`
  - Since: #119

- RCP-291: `ghost` MUST include `recipes.mysql` and connect to the
  Service `mysql` with the database and user of `applications.mysql` and
  the key `password` of the Secret `mysql`. Its init container
  `wait-for-database` MUST wait until the Service `mysql` accepts
  connections on port 3306.

  - Test: CI `check` job, report line `smoke`
  - Since: #119

- RCP-292: `ghost` MUST have the readiness probe of DEC-212 and no
  liveness or startup probe.

  - Test: manual: review; CI `check` job, which waits for the rollout
  - Since: #119

- RCP-293: The `tests/smoke` of `ghost` MUST require no Pod Security
  warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace before
  it starts a pod of its own, and no restart of the pod `ghost-0`. From
  that pod, through the Service `ghost` on port 2368, it MUST get the
  setup status `false`, and a front page whose generator tag names the
  major and minor version of the image tag. It MUST create the owner
  through `POST /ghost/api/admin/authentication/setup/`, get 403 for a
  second setup, get no session for a wrong password and log in. With the
  session it MUST publish a post through `/ghost/api/admin/posts/` and
  read it without the session on its URL, and upload a PNG through
  `/ghost/api/admin/images/upload/` and fetch it byte for byte. Once the
  pod `ghost-0` was deleted and its successor is ready, it MUST read the
  post and the PNG again and reach `/ghost/api/admin/users/me/` with the
  session of the login.

  The setup goes through the Service as a visitor's would (DEC-213). The
  image brings Node.js 22, whose `fetch` makes the requests, so the test
  needs no image besides Ghost's. The post comes back from
  MySQL, the PNG from the claim, and the session from the table
  `sessions` in MySQL.

  - Test: CI `check` job, report line `smoke`
  - Since: #119

- RCP-294: Renovate MUST NOT need a release timestamp for the image of
  `ghost`.

  Docker Hub listed 2571 tags of `library/ghost` on 2026-11-05, so
  Renovate gets no release timestamps for it, as for `wordpress`
  (RCP-184). Renovate's docker versioning proposes only tags with the
  suffix `-alpine`, which keeps the variant.

  - Test: manual: Renovate dry run
  - Since: #119

- AC-290 (RCP-290 to RCP-293): `check ghost --level deploys` passes in CI
  on each Kubernetes minor, its report lists the objects of `mysql` as
  included, and its smoke test reads the post and the PNG after the
  restart.

Not proven: Ghost's migrations of later releases on MySQL 9.7, mail with
any transport, the members' sign-up and newsletters, the admin app in a
browser, and a route or Ingress in front of the Service.

## Umami

Umami is web analytics without cookies. A tracker script on each website
sends page views and events to Umami's public endpoint `/api/send`, and
Umami keeps them in PostgreSQL, from where its web UI and API report
visitors and page views per website. The project publishes no chart.
umami-software/umami, MIT, carries `docker-compose.yml` with Umami and
PostgreSQL at the root of the repository and builds the image
`ghcr.io/umami-software/umami`. `umami` takes the file at commit
`559e3c607c23d2c72d9bd4f6481bda428255323c`, the tag of release v3.4.1 of
2026-10-23, the newest on 2026-11-05, SHA-256
`fb542a641c14fc2b1ff0d59558a197ed4f607b6608bf812afd20dad662ae0e8c`. The
file runs `ghcr.io/umami-software/umami:latest`, which on 2026-11-05 was
the same index as `3.4.1`, for amd64 and arm64. The image carries no
`org.opencontainers.image.revision` label. Its SLSA provenance names the
commit as `vcs:revision`.

umami-software/umami lists two advisories on 2026-11-05.
GHSA-8www-cffh-4q98 is fixed in 2.3.1. GHSA-3xx8-742v-m4mq, rated high,
names no fixed release: `/api/send` returned a token that the share
check accepted, which gave read access to a website's analytics. Commit
`8bc49a2` of 2026-06-02, before v3.2.0, made `parseShareToken` accept only
tokens of the type `share`, and v3.4.1 has that check (`src/lib/auth.ts`).

| Service | Recipe |
|---|---|
| `umami` | Deployment `umami`, Service `umami` on port 3000, Secret `umami` |
| `db`, `postgres:15-alpine` with the volume `umami-db-data` | the included recipe `postgresql` (DEC-20) |

The compose service `umami` mounts no volume, so it becomes a Deployment.
Its healthcheck runs `curl http://localhost:3000/api/heartbeat` in shell
form every 5 seconds with a timeout of 5 seconds and 5 retries, and
becomes the readiness probe with these values. Without `-f`, curl fails
only when nothing answers. Umami reaches the database through
`DATABASE_URL`, which the compose file sets to
`postgresql://umami:umami@db:5432/umami`. The recipe takes the key `uri`
of the Secret `<cluster>-app`, which the operator writes with the user,
the generated password, the read-write Service and the database of
`postgresql` (`pkg/specs/secrets.go` of CloudNativePG v1.30.1). The
database and its owner are `app`, the defaults of `postgresql`.

At every start the image runs `scripts/start-docker.sh`. It checks the
connection and the server version, applies the Prisma migrations, and
then replaces itself with `node server.js`. The first migration creates
the user `admin` with the password `umami`.

DEC-120: `umami` renders nothing for the compose key `init: true`
(Umami). The key makes Docker start an init process as PID 1 that passes
signals on and reaps orphaned processes. umami-software/umami added it in
2024 against zombie processes of the start script of the time, which ran
`npm-run-all` (commit `995458d`). Since commit `d13085f` of 2026-06-20 the
script ends with `exec node server.js`, so the server is PID 1 without the
key. On kind the pod ran one process, `next-server` as PID 1, and its
deletion took 2 seconds, so the server ends on `SIGTERM` before the grace
period of 30 seconds. `shareProcessNamespace`, which makes the pod's pause
process PID 1, was considered. The `kubernetes` generator 1.14.0 has no
key for it, so it would be a gap of Compose sources and no recipe.

DEC-121: `umami` has the init container `wait-for-database`, which runs
the umami image and waits until the Service `<cluster>-rw` of
`postgresql` accepts connections on port 5432 (Umami). The compose file
starts Umami once `db` is healthy (`depends_on` with
`condition: service_healthy`). CloudNativePG puts the primary into the
Service's endpoints once it is ready, and until then a connection is
refused. The start script exits with status 1 when the database does not
answer. On kind without the init container, Umami exited four times while
the Cluster bootstrapped, and the kubelet's back-off held the fifth start
until Umami was ready 65 seconds after the Cluster. The back-off doubles up
to five minutes. The image's busybox carries `nc`. Leaving the restarts to the
kubelet, as the `depends_on` row of Compose sources does, was considered.
It would delay Umami by up to five minutes after the database is ready,
on every start that finds the database down. A startup probe was
considered too. It cannot hold a container that exits on its own. An
image of its own for the wait, which that row rejects, is not needed.

DEC-122: `umami` runs as the image's user `nextjs`, UID 1001 and GID 65533
in its `/etc/passwd`, under `security_profile: restricted` (Umami). The
compose file sets no `user`, and the image's `USER` is the name `nextjs`.
The kubelet verifies `runAsNonRoot` only for a numeric user, so the recipe
names the numbers. `tests/smoke` checks that the pods pass the level
`restricted`.
`baseline` was considered. It would leave the capabilities and privilege
escalation that the server does not use.

DEC-123: `umami` requires `TWO_FACTOR_ENCRYPTION_KEY` as a parameter, like
`APP_SECRET` (Umami). The compose file sets both to placeholders. Umami
takes the key only as 64 hexadecimal digits and offers no two-factor
authentication without a valid one (`src/lib/two-factor/crypto.ts`), so
the placeholder leaves it off. The `environment` row of Compose sources
makes a credential a parameter that the recipe leaves unset. The key
encrypts each user's TOTP secret, so it has to stay the same once a user
enabled two-factor authentication. Leaving the key out was considered.
Two-factor authentication would then be unavailable until a target added
the variable itself.

DEC-124: `umami` renders no admin account and does not change the default
password (Umami). The first migration creates `admin` with the password
`umami`, as with the compose file, and the README asks the target to
change it before exposing the Service, in the web UI's profile or through
`POST /api/me/password`. A Job that changes the password from a parameter
was considered. It would need the old password, so it works only once,
and it adds a workload that the compose file does not have. The Service
is `ClusterIP`, so until the target exposes it only the cluster reaches
the login.

DEC-125: Umami connects to PostgreSQL without TLS, as the compose file's
URL does (Umami). The key `uri` sets no `sslmode`. CloudNativePG serves
TLS and accepts a connection without it, and on kind the server's
connections showed `ssl` false in `pg_stat_ssl`. `sslmode=require` was
considered. pg-connection-string 2.14, which node-postgres reads the URL
with in the image, treats `require` as `verify-full` unless the URL also
sets `uselibpqcompat=true`, and verifying needs the Cluster's CA from the
Secret `<cluster>-ca` in the pod.

- RCP-190: The `Source` line of `umami` MUST name `docker-compose.yml` of
  umami-software/umami at the commit of the release tag that the image's
  tag names, with the file's SHA-256.

  `check` fetches the file at that commit and fails on another SHA-256
  (RCP-23). The commit is the image's `vcs:revision`. Renovate moves the
  tag, the commit and the image in one pull request (RCP-16).

  - Test: `check lint`; CI `check` job, report line `compose`; manual:
    `gh api repos/umami-software/umami/git/ref/tags/<tag>`
  - Since: #91

- RCP-191: `umami` MUST include `recipes.postgresql` and set
  `DATABASE_URL` from the key `uri` of the Secret `<cluster>-app`. It MUST
  set `APP_SECRET` and `TWO_FACTOR_ENCRYPTION_KEY` from the Secret
  `umami`, whose values are `applications.umami.app_secret` and
  `.two_factor_encryption_key`, and MUST leave both parameters unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them (RCP-19, RCP-40). `APP_SECRET` signs the login
  sessions and the tokens of `/api/send`. Without it Umami derives the
  secret from `DATABASE_URL` (`secret` in `src/lib/crypto.ts`).

  - Test: CI `check` job, report line `smoke`; manual: a compile of
    `tests/target.yml` without each of the two parameters stops with
    `Interpolation key` and its name
  - Since: #91

- RCP-192: `umami` MUST run as UID 1001 and GID 65533 under
  `security_profile: restricted` (DEC-122), with the init container of
  DEC-121, the readiness probe of the compose healthcheck and no liveness
  or startup probe.

  - Test: `check lint`; CI `check` job, report line `smoke`
  - Since: #91

- RCP-193: The `tests/smoke` of `umami` MUST require no Pod Security
  warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace and
  no restart of the umami container. From a pod of the umami image and
  through the Service `umami` on port 3000 it MUST get `/api/heartbeat`,
  get 401 for a wrong password, log in as `admin` with `umami`, require
  `isConfigured` from `/api/2fa/status`, and create a website. It MUST
  send a page view to `/api/send` as the tracker script does, with a
  browser's `User-Agent`, and require one page view from
  `/api/websites/<id>/stats`. It MUST change the password through
  `/api/me/password` and log in with the new one. Once the umami pod was
  deleted and its successor is ready, it MUST read the page view again
  with the session of that login and get 401 for `umami`.

  Umami drops a request whose `User-Agent` the package `isbot` matches,
  such as curl's, and answers it with `{"beep":"boop"}`
  (`src/app/api/send/route.ts`). The page view comes back from
  PostgreSQL. The session is a token signed with `APP_SECRET`, so the new
  pod accepts it only when the secret comes from the Secret. A password
  change ends the sessions signed before it, so the test logs in again
  before the restart. The old pod is gone before its successor is ready,
  so no request after the restart reaches it. With
  `kubectl rollout restart`, which starts the successor first, a request
  right after the old pod was gone waited 133 seconds for a connection to
  the Service, on kind with 1.35 and in CI with 1.36. On kind with 1.37,
  ten requests after each of five deletions passed. With rollout
  restarts, the first request after the third one hung.

  - Test: CI `check` job, report line `smoke`
  - Since: #91

- AC-120 (RCP-190 to RCP-193): `check umami --level deploys` passes in CI
  on each Kubernetes minor, its report lists the objects of `postgresql`
  as included and `cnpg` as installed, and its smoke test reads the page
  view after the restart.

## Memcached

memcached is an in-memory key-value cache. Clients store and read values
over TCP port 11211 in its text or binary protocol, and a value lives only
as long as the server's memory holds it. Bitnami's `memcached` chart was a
common way to run it on Kubernetes.

Bitnami's chart 8.8.7, the newest in
`oci://registry-1.docker.io/bitnamicharts/memcached` on 2026-11-05, runs
memcached 1.6.45 in Bitnami's image `bitnami/memcached:latest`. `helm
pull` printed the chart's digest
`sha256:a5b77e13f77f5aefba1e3a18951a55ec3fda68f8f70676edd26cf4a83d7a6be8`.
With its defaults, `architecture: standalone`, it renders five objects. The
Deployment `memcached` runs one replica as UID 1001 with a read-only root
filesystem. Its readiness probe connects to port 11211 every 5 seconds,
and its liveness probe runs `pgrep memcached` every 10 seconds. Its
resources are the preset `nano`: requests of 100m CPU, 128Mi memory and
50Mi ephemeral storage, and limits of 150m CPU, 192Mi memory and 2Gi
ephemeral storage. The Service `memcached` of type `ClusterIP` exposes
the port `memcache`, 11211, with `publishNotReadyAddresses: true`. The
ServiceAccount `memcached` mounts no token. The NetworkPolicy `memcached`
admits port 11211 from every source and allows all egress. The
PodDisruptionBudget `memcached` sets `maxUnavailable: 1`. Authentication,
TLS, persistence and the metrics exporter are off. The architecture
`high-availability` renders a StatefulSet in place of the Deployment.

The memcached project publishes no chart, no Kustomize base and no image.
memcached/memcached, BSD-3-Clause, carries `docker-compose.yml`. Its five
services build test images from the Dockerfiles in `devtools/`, one per
Linux distribution, which run `make test`. Docker Hub's namespace
`memcached` held no repository on 2026-11-05. The Docker Official Image
`memcached` downloads each release from memcached.org, checks the SHA-1
that its Dockerfile pins, and runs the test suite during the build.
docker-library/memcached, BSD-3-Clause, holds the Dockerfiles, and
`library/memcached` in docker-library/official-images names Tianon Gravi
and Joseph Ferguson of docker-library as maintainers, as for `wordpress`
(WordPress).

DEC-150: `memcached` is a designed recipe on `docker.io/library/memcached`
(DEC-11). DEC-11 names the project's image, and memcached publishes none,
so the Docker Official Image takes its place, as for `wordpress`
(DEC-110). The compose file was considered as the source (DEC-10). Its
services run the test suite and no server, and Compose sources stop on a
`build` without a published `image`. Bitnami's chart is a third-party
chart, which DEC-11 rules out.

memcached 1.6.45, tagged on 2026-07-10, was the newest release of
memcached/memcached on 2026-11-05. Docker Hub's tag `1.6.45`, also `1.6`,
`1` and `latest`, is the index
`sha256:aea0d81d101a9b64fe30cf2cf2f96144e284f8e9552bb084a03f4e12e9043bab`
for amd64, arm/v5, arm/v7, arm64/v8, 386, ppc64le, riscv64 and s390x,
built on 2026-10-28 from docker-library/memcached at
`53ac0ecb0bf88b471a0110f8996ce791baf1a667` on Debian 13. The recipe runs
this default variant. The variant `1.6.45-alpine` builds the same release
on Alpine Linux, and the recipe has no reason to leave the default.
Docker Hub listed 306 tags of `library/memcached` on 2026-11-05, so
Renovate gets release timestamps for the image, and RCP-16 applies
without a package rule.

DEC-151: `memcached` renders the chart's default architecture as two
objects, the Deployment `memcached` with one replica and the Service
`memcached` of type `ClusterIP` with the port `memcache`, 11211. The
chart's other three objects change nothing about how memcached is
reached, so the recipe leaves them out. The NetworkPolicy admits from
every source the only port memcached listens on. The PodDisruptionBudget
allows every eviction, since `maxUnavailable: 1` of one replica is the
whole Deployment. The ServiceAccount is bound to no role. The generator
sets `automountServiceAccountToken: false` on the pod, so the pod runs as
`default` without a token, as the chart's pod runs without one. The
Deployment also leaves out the chart's preferred pod anti-affinity, which
has no second replica to spread. The Service leaves out
`publishNotReadyAddresses`, so the readiness probe of DEC-152 decides when
clients reach the pod. Rendering the three objects was considered. A
target that restricts its clients with a NetworkPolicy has to name them,
which the chart's policy does not. The architecture `high-availability` is
not the chart's default.

The recipe takes the requests and the memory limit of the preset `nano`.
memcached keeps at most 64 megabytes of items by default
(`--memory-limit`). On kind, 300 values of 500 kB filled that cache with
174 evictions, and memcached's resident memory was 70 MiB, below the
limit of 192Mi. The CPU limit is left out, as `mariadb` and `valkey` set
none. The ephemeral-storage request and limit are left out, because
memcached writes no file.

The image's `USER` is the name `memcache`, UID and GID 11211 in its
`/etc/passwd`. The kubelet verifies `runAsNonRoot` only for a numeric
user, so the recipe names the numbers under `security_profile:
restricted`, as `umami` does (DEC-122). `read_only_root_filesystem: true`
keeps the chart's read-only root filesystem. memcached writes no file
without extstore or a PID file, and on kind a write to `/` in the pod
failed with `Read-only file system` while memcached served.

DEC-152: `memcached` has one probe, a TCP readiness probe on the port
`memcache` at the generator's period of 10 seconds, timeout of 5 seconds
and 3 failures. The image has no `HEALTHCHECK`, and its documentation
names no check. A connection to port 11211 succeeds once memcached
listens, which is what the chart's readiness probe tests as well. The
chart's liveness probe cannot run in the pinned image, which has no
`pgrep`. The entrypoint `exec`s memcached, so memcached is the
container's PID 1, and the kubelet restarts the container when memcached
exits, without a probe. A TCP
liveness probe was considered. Every restart empties the cache, and a
probe that times out under load would restart a memcached that still
serves.

DEC-153: `memcached` configures no authentication and no TLS, the chart's
defaults. Every client that reaches the Service reads and writes every
key, and the Service is `ClusterIP`. Clients of a release of the chart
with its defaults connect the same way. SASL, which the image is built
with, was considered. memcached 1.6.45 refuses the text protocol with
`-S` (`ERROR: You cannot allow the ASCII protocol while using SASL.`),
so clients of the text protocol would stop working, and SASL needs a
password database in the pod. `memcached -h` marks the authentication of
the text protocol, `--auth-file`, as experimental. TLS (`--enable-ssl`)
was considered too. It needs a certificate, which would add cert-manager
as a prerequisite (DEC-13).

- RCP-230: `memcached` MUST run `docker.io/library/memcached` pinned to
  its index as the Deployment `memcached` with one replica, as UID and GID
  11211 under `security_profile: restricted` with a read-only root
  filesystem, behind the Service `memcached` of type `ClusterIP` with the
  port `memcache`, 11211. It MUST render no other object.

  - Test: `check lint`; CI `check` job, report lines `image` and `smoke`;
    manual: the compile of `tests/target.yml` writes
    `memcached-deploy.yml` and `memcached-svc.yml` only
  - Since: #94

- RCP-231: `memcached` MUST have the readiness probe of DEC-152 and no
  liveness or startup probe.

  - Test: manual: review; CI `check` job, which waits for the rollout
  - Since: #94

- RCP-232: The `tests/smoke` of `memcached` MUST, through the Service
  `memcached` on port 11211 in the text protocol, store a value on one
  connection and read it on a second, and require that `stats` reports the
  version of the image tag as `STAT version`. It MUST require no Pod
  Security warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace.

  The image has no `nc`, so bash's `/dev/tcp` in the memcached pod is the
  client, as `mariadb` connects from its own pod. `quit` makes memcached
  close the connection. The value read on the second connection comes
  from the server. The tag is read from the Deployment, so the test
  follows a new image. On kind the test failed with the Service's
  selector on no pod, with the tag `1.6.44` on the digest of `1.6.45`, and
  with a pod running as root in the namespace.

  - Test: CI `check` job, report line `smoke`
  - Since: #94

- AC-140 (RCP-230 to RCP-232): `check memcached --level deploys` passes in
  CI on each Kubernetes minor, and its smoke test reads the value on a
  second connection through the Service.

## Stirling-PDF

Stirling-PDF is a web UI and HTTP API that merges, splits, converts and
edits PDF files. One Java process does the work, with LibreOffice,
Tesseract, qpdf and other tools from its image. It keeps `settings.yml`,
an H2 database with its users and its keys in `/configs`.
Stirling-Tools/Stirling-PDF is MIT except the directories its `LICENSE`
names, such as `app/proprietary/`, which holds the login.

DEC-160: `stirling-pdf` is a chart recipe on the chart
`stirling-pdf-chart` 4.0.0 of Stirling-Tools/Stirling-PDF-chart, MIT. The
project keeps the chart in its own GitHub organization. Its release
workflow publishes each version with chart-releaser as a GitHub release
asset and in the HTTP repository `https://docs.stirlingpdf.com/Stirling-PDF-chart`,
the URL the chart's README gives to `helm repo add`. It pushes no OCI
artifact, so the `Source` line takes the HTTP form of RCP-23. The compose
files below `docker/compose/` of Stirling-PDF were considered as the
source. DEC-10 puts the project's chart first. The chart lags behind the
application: from 2026-02-19 to 2026-10-21 it stayed at Stirling-PDF
2.5.1, while the project released 2.5.2 to 3.2.0. Version 4.0.0 of
2026-10-21 moved it to 3.2.0.

DEC-161: `stirling-pdf` runs Stirling-PDF 3.2.0, the chart's
`appVersion`, pinned to its index for amd64 and arm64. 3.2.2 of 2026-10-24
was the newest release on 2026-11-05. No advisory of
Stirling-Tools/Stirling-PDF on 2026-11-05 names a release after 3.0.0 as
affected. Running the image ahead of the chart, as gitea does for an
advisory, was considered. Without an advisory it would run a version that
the chart's release was not made for.

DEC-162: `tests/values.yaml` sets `image.registry: docker.io`, so the
recipe runs `docker.io/stirlingtools/stirling-pdf`. The chart's default
registry `docker.stirlingpdf.com` forwards to Docker Hub. It answered three
anonymous manifest requests for `3.2.0` on 2026-11-05 with 429 Too Many
Requests, and its responses name one address as Docker Hub's rate limit
source, so all anonymous clients of the proxy share one limit. The
installation guide on docs.stirlingpdf.com names Docker Hub and
`ghcr.io/stirling-tools/stirling-pdf` for when `docker.stirlingpdf.com` is
unreachable. Both served the same index as the proxy's tag. GHCR was
considered. Docker Hub keeps the chart's `image.repository`, so only the
registry changes.

DEC-163: `tests/values.yaml` turns on the chart's claim with
`persistence.enabled`, as the chart's `examples/single-node.yaml` does.
With the chart's default, an `emptyDir` at `/configs`, every new pod starts
with new keys, the default settings and the default admin password again.
The claim `stirling-pdf-stirling-pdf-chart` asks for 8Gi with
ReadWriteOnce. With it the chart sets the Deployment's strategy to
`maxSurge: 0`, so one pod at a time opens the database, and
`STORAGE_LOCAL_BASEPATH` to `/configs/storage`. The example's `resources`,
2Gi of memory, were considered as well. The chart's default sets none, and
the README names them as a setting.

DEC-164: `stirling-pdf` runs as `stirlingpdfuser`, UID, GID and `fsGroup`
1001, under `security_profile: restricted`, by `securityContext` and
`containerSecurityContext` in `tests/values.yaml`. The chart then renders
its init container `prepare-non-root`. It copies `/usr/local/bin` into an
`emptyDir` that the container mounts there, because the image's start
script links into that directory, which belongs to root. The chart's
default `fsGroup` 1000 and its comment name UID 1000 as the image's user.
In the 3.2.0 image UID 1000 is `ubuntu` and `stirlingpdfuser` is 1001. On
kind with Kubernetes 1.37, the container as UID 1000 could not write
`/logs` or create `/tmp/stirling-pdf` and restarted. As 1001 it became
ready after 47 seconds. Started as root, the chart's default, the start
script switches to `stirlingpdfuser` with `setpriv` and runs LibreOffice as
a second user, `stirlingofficeuser`. As 1001 it cannot switch, so
LibreOffice runs as `stirlingpdfuser`, and its log reports the image's
LibreOffice sandbox with Landlock and seccomp as active. The chart's
default was considered. It needs Pod Security `baseline`, and the start
script runs as root with the runtime's default capabilities until it
switches users.

DEC-165: `stirling-pdf` creates the first admin from the required
parameters `applications.stirling-pdf.admin.username` and `.password`,
through the Secret `stirling-pdf-admin` that the recipe renders.
`tests/values.yaml` sets the chart's `envs` `SECURITY_INITIALLOGIN_USERNAME`
and `SECURITY_INITIALLOGIN_PASSWORD` from its keys `username` and
`password`, so `check` accepts the Secret as a Referenced Secret
(DEC-166). Stirling-PDF 3.2.0 turns the login on by default
(`security.enableLogin` in `settings.yml.template`), and every API call
needs a session or an API key. On its first start, while the database
holds no user, it creates an admin from both variables when both are set,
and otherwise the user `admin` with the password `stirling`
(`initializeAdminUser` in `InitialSecuritySetup.java`). On kind with the
variables set, the log named only the configured admin, and a login as
`admin` with `stirling` got 401. Stirling-PDF does not write the variables
into `settings.yml`. A later change of the parameters does not reach the
account, which the README says.

Stirling-PDF has no self-registration to switch off. `/api/v1/user/register`
creates a disabled user, and it is not among the endpoints that
`RequestUriUtils.isPublicAuthEndpoint` opens without a login, so it
answered 401 without one. The default account, as the chart leaves it, was
the first version of this recipe. A known password would hold every
installation until its first login, also on a Service exposed before that.
Plain `envs` values were considered. The target's ref would then end up in
the Deployment, which DEC-38 rejects for gitea.

The chart's Ingress, HTTPRoute, ServiceMonitor, PodDisruptionBudget,
HorizontalPodAutoscaler and cluster mode, which needs PostgreSQL, Valkey,
S3 and a licence, are off by default and not part of the recipe. The chart
renders no hook. The ServiceAccount has no role. The init container's
command is text of the chart's `templates/deployment.yaml`, so
`stirling-pdf.yml.LICENSE` carries the chart's license (RCP-42). Renovate
moves the `Source` line through the `helm` datasource (RCP-16).

- RCP-240: `stirling-pdf` MUST render the chart's Deployment, Service,
  ServiceAccount and claim `stirling-pdf-stirling-pdf-chart` with the
  values of DEC-162 to DEC-165, and
  `docker.io/stirlingtools/stirling-pdf:3.2.0` pinned to its index.

  - Test: `check stirling-pdf`; CI `check` job
  - Since: #98; DEC-165: #105

- RCP-241: `stirling-pdf` MUST run as UID, GID and `fsGroup` 1001 under
  `security_profile: restricted`, with the init container
  `prepare-non-root` of DEC-164.

  - Test: `check lint`; CI `check` job, report line `smoke`
  - Since: #98

- RCP-242: The `tests/smoke` of `stirling-pdf` MUST require no Pod
  Security warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace, and
  `status: UP` with the version of the image tag from
  `/api/v1/info/status` through the Service. It MUST get 401 from
  `/api/v1/general/merge-pdfs` and from `/api/v1/user/register` without a
  login, and from a login as `admin` with `stirling`. It MUST log in with
  the username and password of the Secret `stirling-pdf-admin`, and as
  that admin it MUST merge two one-page PDFs that it writes itself, and require from `qpdf --check`
  and `pdftotext` in the image a valid file of two pages with the first
  file's text on the first. It MUST change `ui.appNameNavbar` through
  `/api/v1/admin/settings`. Once the pod was deleted and its successor is
  ready, it MUST log in as that admin again and read the new value from
  `/api/v1/admin/settings/key/ui.appNameNavbar`.

  Stirling-PDF applies a changed setting only at its next start
  (`AdminSettingsController.java`), from `settings.yml` on the claim, so
  the value after the restart shows that the claim keeps the settings. On
  kind the key still read as unset before the restart. The test
  writes the PDFs with a correct cross-reference table, so the merge gets
  well-formed input. qpdf and pdftotext come from the image, so the runner
  needs no PDF tool.

  - Test: CI `check` job, report line `smoke`
  - Since: #98; admin of the Secret and sign-up: #105

- RCP-244: `stirling-pdf` MUST put `applications.stirling-pdf.admin.username`
  and `.admin.password` into the keys `username` and `password` of the
  Secret `stirling-pdf-admin`, MUST set `SECURITY_INITIALLOGIN_USERNAME`
  and `SECURITY_INITIALLOGIN_PASSWORD` from them, and MUST leave both
  parameters unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets each of them, the password as a ref (RCP-19, RCP-40).

  - Test: CI `check` job, report lines `difference: Referenced Secret` and
    `smoke`; manual: a compile of `tests/target.yml` without each
    parameter stops with `Interpolation key` and its name
  - Since: #105

- AC-145 (RCP-240 to RCP-242, RCP-244): `check stirling-pdf --level
  deploys` passes in CI on each Kubernetes minor, with differences of the
  classes Selector scheme, Derived name, Explicit default and Referenced
  Secret only, and its smoke test logs in as the admin of the Secret and
  reads the setting after the restart.

## Zulip

Zulip is a team chat whose messages are organized by channel and topic.
One container of `ghcr.io/zulip/zulip-server` runs nginx, the Django
application, the Tornado event server and the queue workers under
supervisord. It keeps its data in PostgreSQL, queues events in RabbitMQ,
caches in memcached and counts rate limits in Redis, and stores uploads
and generated secrets on its claim at `/data`. Zulip and its chart are
Apache-2.0.

DEC-313: `zulip` is a chart recipe on the chart `zulip` 2.3.0 of
zulip/docker-zulip, tag `helm-2.3.0`, which Zulip publishes at
`oci://ghcr.io/zulip/helm-charts/zulip`. It runs
`ghcr.io/zulip/zulip-server:12.3-0`, the chart's `appVersion`, pinned to
its index for amd64 and arm64. On 2026-11-05 2.3.0 was the newest chart
and 12.3-0 the newest image tag. The repository's `compose.yaml` was
considered as the source. DEC-10 puts the chart first, and Zulip's
documentation for Kubernetes starts from the chart.

DEC-314: The chart's Bitnami subcharts give way to the included recipes
`postgresql`, `rabbitmq`, `memcached` and `valkey` (DEC-20).
`tests/values.yaml` switches the four subcharts off and points
`externalPostgresql`, `externalRabbitmq`, `externalMemcached` and
`externalRedis` at their Services, with each password as a `valueFrom` of
the included recipe's Secret, which the chart takes for these values. The
subcharts run images of `bitnamilegacy`, and the PostgreSQL subchart runs
`zulip/zulip-postgresql` 14. Keeping them was considered. They would run a
second PostgreSQL, RabbitMQ and Redis next to the recipes that this
repository proves, and the legacy images get no updates.

Zulip's own PostgreSQL image adds hunspell dictionaries and a stop word
list for its full-text search. The first migration of 12.3
(`zerver/migrations/0001_squashed_0569.py`) falls back to PostgreSQL's
`pg_catalog.english` when the server lacks them and `REMOTE_POSTGRES_HOST`
is set, and logs a warning, as it did on kind. The CloudNativePG image
lacks them, so search on `zulip` stems words less well than on Zulip's
image. Zulip's documentation names the same trade-off for managed
databases. The
migration creates the schema `zulip` and sets the owner's `search_path`,
which the owner of the database `app` may do.

The RabbitMQ Cluster Operator generates the default user's name as well as
its password, in the Secret `rabbitmq-default-user`. The chart's
`externalRabbitmq.user` takes only a string, so `tests/values.yaml` leaves
it empty and sets `SETTING_RABBITMQ_USERNAME` in `zulip.environment` from
the Secret's key `username`. The user reaches the vhost `/`, Zulip's
default.

The included recipe `memcached` has no authentication (DEC-153). The
chart's schema requires a memcached password, so `tests/values.yaml` sets
`externalMemcached.password` to the empty string. Zulip then sets
`MEMCACHED_USERNAME`, but the python-binary-memcached client authenticates
only when a password is set as well. On kind memcached reported
`auth_cmds 0` and items written by Zulip.

DEC-315: `zulip` creates the organization and its owner on the first start
from the required parameters `applications.zulip.administrator` and
`applications.zulip.owner_password`. The chart runs every script of
`postSetup.scripts` on each start, after the migrations, from the ConfigMap
`zulip-post-setup-scripts`. The script `create-organization.sh` of
`tests/values.yaml` runs `manage.py create_realm` when `manage.py
list_realms` shows no organization at the root domain, and passes the
password through `--password-file`, so it does not appear in a process
list. The file belongs to the user `zulip`, because the command runs as
that user and could not open `/dev/stdin` of the root shell. The owner's
login is the server administrator's address, which Zulip requires as
`SETTING_ZULIP_ADMINISTRATOR`. A second address parameter was considered.
One organization on its own server has one person who answers both.

`create_realm` commits the organization in a durable transaction before
`do_create_user` sets the owner's password (`zerver/actions/create_realm.py`
of 12.3), and Zulip rejects a password that is shorter than 8 characters
or that zxcvbn guesses in fewer than 10000 attempts
(`check_password_strength` in `zproject/backends.py`). On kind a password
of twelve `a` left the organization `Zulip` without an owner, and the
script skipped it on every later start. The script therefore runs Zulip's
strength check first and stops before `create_realm` on a weak password,
so the next start tries again. Wrapping both steps in one transaction was
considered. The durable transaction of `do_create_realm` cannot be nested.

A new organization requires an invitation to join (`invite_required`
defaults to true in `zerver/models/realms.py` of 12.3), and
`OPEN_REALM_CREATION` stays at its default, off, so a new organization
needs a link from `manage.py generate_realm_creation_link`. The chart's
documented way, a creation link opened in a browser after the install, was
considered. Until someone opens it the server has no organization and no
admin, and the defaults for applications with accounts ask for the first
admin from parameters (DEC-165).

DEC-316: `applications.zulip.secret_key` is required and sets
`SECRETS_secret_key` from the Secret `zulip`. Zulip's chart documentation
lists it among the settings a values file must set. Without it the image
generates one into `zulip-secrets.conf` on the claim. Leaving it to the
image was considered. A restored or replaced claim would then log every
user out, and the key would not be in the target's refs.

DEC-317: Zulip serves plain HTTP on port 80, the chart's default with
`CERTIFICATES` unset, and the recipe renders no Ingress or route, as the
chart's `ingress.enabled` defaults to false. TLS ends at a proxy the target
sets up, whose addresses go into `LOADBALANCER_IPS`. Zulip answers a
request without proxy headers only from the loopback. On kind a request
through the Service from another pod got 500, with or without
`X-Forwarded-For`, and `errors.log` named `ProxyMisconfigurationError`.
`tests/smoke` therefore reaches the Service through `kubectl
port-forward`, as the chart's CI does. A proxy that `LOADBALANCER_IPS`
names is not proven.

The chart renders no hook and no Role. The ServiceAccount `zulip` keeps
the API default `automountServiceAccountToken: true`, as on the chart side.
`tests/target.yml` runs one PostgreSQL instance and one RabbitMQ node, so
the proof fits a CI runner. The recipe is at level `deploys`.

- RCP-393: `zulip` MUST render the chart's StatefulSet, Service,
  ServiceAccount, claim `zulip-data` and ConfigMap
  `zulip-post-setup-scripts` with the values of DEC-314 to DEC-316, and the
  Secret `zulip` with the keys `secret-key` and `owner-password`.

  - Test: `check zulip`; CI `check` job
  - Since: #123

- RCP-394: `create-organization.sh` MUST create the organization at the
  root domain with the owner `applications.zulip.administrator` and the
  password `applications.zulip.owner_password` when none exists, and MUST
  leave an existing organization unchanged. It MUST create nothing when
  Zulip's strength check rejects the password.

  - Test: `zulip/tests/smoke`, the owner's login before and after the pod
    is replaced; manual: on kind, a password of twelve `a` left no
    organization and the log line `ZULIP_OWNER_PASSWORD is too weak for
    Zulip.`, and after the Secret got a strong password the next start
    created the organization with the owner (#123)
  - Since: #123

- RCP-395: The `tests/smoke` of `zulip` MUST reach Zulip through the
  Service `zulip`, log in as the owner, and have a member created with
  `manage.py create_user` and the owner each read the other's message in
  the channel `general`. It MUST require that a signup without an
  invitation and a new organization without a creation link are refused.
  After it deletes the Zulip pod and the PostgreSQL primary, it MUST log
  in as the owner again and read both messages. It MUST also require that
  Zulip's queue workers consume RabbitMQ, that memcached holds items
  without a SASL authentication, and that `manage.py check_redis` passes.

  - Test: CI `check` job, report line `smoke`
  - Since: #123

## Actual

Actual is a personal finance app. Its sync server serves the web UI, keeps
the budget files that clients upload and passes their changes between
devices. actualbudget/actual, MIT, carries the server's compose file at
`packages/sync-server/docker-compose.yml` and builds the image
`docker.io/actualbudget/actual-server`. The project publishes no chart, and
its Docker guide starts from that file (`packages/docs/docs/install/docker.md`).
`actual` takes the file at commit `1766241e3f4b3c578e424c4fa15f1eb83c0da17d`,
the tag `v26.11.0` of release 26.11.0 of 2026-11-02, the newest on
2026-11-05, SHA-256
`bdf050bf6247938005c871b20d2c27647e09843a21631ef5ca430dfc4e5982a6`. The file
runs `docker.io/actualbudget/actual-server:latest`, which on 2026-11-05 was
the same index as `26.11.0`, for amd64 and arm64. The image carries no
`org.opencontainers.image.revision` label. Every advisory of
actualbudget/actual published by 2026-11-05 names 26.11.0 or an earlier
release as fixed.

The file's one service, `actual_server`, becomes the StatefulSet `actual`.
Its relative bind mount `./actual-data`, which the repository does not
contain, becomes the claim `actual-data` at `/data` (DEC-21). The server
keeps the password hash, its sessions and the list of budget files in
`server-files/account.sqlite` there, and the files themselves in
`user-files`. The published port `5006:5006` becomes port 5006 of the
Service `actual`. The service's health check runs
`node scripts/health-check.js` every 60 seconds with a timeout of 10 seconds
and 3 retries. It becomes the readiness probe
`sh -c 'node scripts/health-check.js'`. The script gets `/health` on the
server's port and fails unless the answer is `UP`
(`src/scripts/health-check.ts`). The image runs as root, so the target's
namespace needs the Pod Security level `baseline`.

Every line below the file's `environment` is a comment, so the recipe
renders no variable. The file asks its reader to remove the key when no
option is set. Docker Compose 5.6.1 refuses the file as it is, with
`services.actual_server.environment must be a mapping`.

DEC-220: `actual` renders no server password. The first visitor of the web
UI sets it, as with the compose file (Actual). Actual 26.11.0 takes the
password through `POST /account/bootstrap`, which needs no login while no
password is set (`src/app-account.js`), or from the script
`reset-password.js`, which reads it from a terminal (`src/util/prompt.ts`).
Its configuration reads no password from the environment or a file. Its
only `_FILE` variables are those of the OpenID client secret and a GitHub
token (`src/load-config.js`). A Job or init container that sets the
password from a parameter was considered. It would call the bootstrap
endpoint or Actual's internal modules, which the compose file does not, and
a changed parameter would not reach a server whose password is set. The
Service is `ClusterIP`, so until the target exposes it only the cluster
reaches the bootstrap, and the README asks for the password before the
exposure. Actual has no self-registration. Further users exist only with
OpenID, and with its default `ACTUAL_USER_CREATION_MODE` of `manual` an
OpenID login creates a user only while the server has none
(`src/accounts/openid.ts`).

- RCP-300: The `Source` line of `actual` MUST name
  `packages/sync-server/docker-compose.yml` of actualbudget/actual at the
  commit of the release tag that the image's tag names, with the file's
  SHA-256.

  `check` fetches the file at that commit and fails on another SHA-256
  (RCP-23). Without a revision label on the image, the release tag ties
  the file to the image, as for `uptime-kuma` (RCP-120). Renovate moves tag
  and commit of the `Source` line and the image in one pull request
  (RCP-16), and the SHA-256 by hand.

  - Test: `check lint`; CI `check` job, report line `compose`; manual:
    `gh api repos/actualbudget/actual/git/ref/tags/<tag>`
  - Since: #111

- RCP-301: `actual` MUST mount the claim `actual-data` at `/data` and MUST
  have the readiness probe `sh -c 'node scripts/health-check.js'` every 60
  seconds with a timeout of 10 seconds and 3 failures, and no liveness
  probe.

  - Test: RCP-302; CI `check` job, which waits for the rollout before
    `tests/smoke`
  - Since: #111

- RCP-302: The `tests/smoke` of `actual` MUST, from a pod of its own and
  through the Service `actual` on port 5006, require `UP` from `/health`
  and the image tag from `/info`, find the server without a password and
  get 401 from `/sync/list-user-files` without a login. It MUST set the
  password through `/account/bootstrap`, get `already-bootstrapped` from a
  second call and `invalid-password` from a login with another password,
  log in, upload a budget file through `/sync/upload-user-file`, and find
  it in `/sync/list-user-files` and unchanged from
  `/sync/download-user-file`. Once the pod `actual-0` was deleted and its
  successor is ready, it MUST log in with the same password and download
  the same file.

  The server writes an upload to `user-files` as it is
  (`upload-user-file` in `src/app-sync.ts`) and reads none of it, so a
  fixed byte string stands in for the zip of `db.sqlite` and
  `metadata.json` that the web UI uploads. The test runs `node` in a pod
  of the same image, because the image has neither curl nor wget. After
  the restart, the login needs the hash in `account.sqlite` and the
  download the file in `user-files`, both on the claim.

  - Test: CI `check` job, report line `smoke`
  - Since: #111

## Qdrant

Qdrant is a vector database. Clients store points, each a vector with a
JSON payload, in collections and search them for the nearest vectors,
through a REST API on port 6333 and a gRPC API on port 6334. It is meant
as the vector store of a retrieval stack with Ollama, LiteLLM and Open
WebUI. `qdrant` deploys it from the chart `qdrant` of qdrant/qdrant-helm.
The project publishes the chart with chart-releaser as a GitHub release
asset and in the HTTP repository `https://qdrant.github.io/qdrant-helm`,
the URL its README gives to `helm repo add`. It pushes no OCI artifact, so
the `Source` line takes the HTTP form of RCP-23. Chart and Qdrant are
Apache-2.0.

With its defaults the chart runs one replica as the StatefulSet `qdrant`
in Qdrant's distributed mode (`config.cluster.enabled`), where the peers
talk over an internal gRPC API on port 6335. The data lives on the claim
template `qdrant-storage`, 10Gi with ReadWriteOnce, and snapshots in an
`emptyDir`. The Services `qdrant` and `qdrant-headless` expose the ports
`http`, `grpc` and `p2p`, the ConfigMap `qdrant` holds the start script
`initialize.sh` and `production.yaml`, and the ServiceAccount `qdrant` has
no role. The pod is ready once `/readyz` answers. The chart sets no API
key, and the init container `ensure-dir-ownership` runs `chown -R` on the
volumes as root.

DEC-230: `qdrant` is a chart recipe on the chart `qdrant` 1.20.0, the
newest release on 2026-11-05, and runs Qdrant 1.20.0, its `appVersion` and
the newest release of qdrant/qdrant. The advisories of qdrant/qdrant on
2026-11-05 name no release from 1.20.0 on. GHSA-frc7-44gm-99qq, fixed in
1.20.0, is the reason not to run an older one: before 1.20.0 the internal
port of distributed mode answered without authentication, so a pod that
reached port 6335 could add a peer and receive the stored data.

DEC-231: `qdrant` runs one node. The chart's StatefulSet sets
`podManagementPolicy: Parallel`, which the `kubernetes` generator cannot
render, in 1.14.0 or in 1.15.0. `tests/values.yaml` sets `OrderedReady`,
the API default that the recipe gets. With one replica both policies
start the same pod. The chart's values warn that with `OrderedReady` the
nodes of a cluster wait for each other's readiness forever, so the README
does not offer the number of replicas as a setting. The recipe keeps the
chart's distributed mode, which runs on one node as well. Stopping on the gap,
as Compose sources stop on one, was considered. The chart's default is one
node, and one node is what the recipe proves.

DEC-232: `qdrant` runs `docker.io/qdrant/qdrant:v1.20.0-unprivileged`
under Pod Security `restricted`. Qdrant builds this variant of every
release with the user 1000:1000, and the chart switches to it with
`image.useUnprivilegedImage`, which also leaves out the init container
`ensure-dir-ownership`. `tests/values.yaml` adds `capabilities.drop: [ALL]`
on the container and the seccomp profile `RuntimeDefault` on the pod,
which `restricted` requires beyond the chart's defaults: UID 1000, GID
2000, `fsGroup` 3000 and a read-only root filesystem. The default image
with `updateVolumeFsOwnership: false` was considered. It runs the same
binary as UID 1000, but its files belong to root, and the unprivileged
variant is the one Qdrant builds for a container without root.

DEC-233: `qdrant` requires the API key `applications.qdrant.api_key`. The
recipe renders it into the Secret `qdrant-apikey`, key `api-key`, and
`tests/values.yaml` sets the chart's `env` `QDRANT__SERVICE__API_KEY`
from it, so `check` accepts the Secret as a Referenced Secret (DEC-166).
Without a key Qdrant answers every request of every pod that reaches the
Service. From 1.20.0 the internal port needs the same key, because
`service.enforce_internal_auth` is on by default, but only once a key is
set (GHSA-frc7-44gm-99qq). The chart's value `apiKey` with a string was
considered. The chart then renders the Secret with a second key
`local.yaml`, mounts it as a configuration file and puts a hash of the
Secret on the pod, and the recipe would carry the hash of the test key.
`apiKey: true` generates a key with `lookup`, which neither
`helm template` nor Kapitan can run. The read-only key and JWT access,
which Qdrant also offers, are not rendered.

The generator puts the label `name` on each claim template, and the chart
puts `app: qdrant` there. The recipe adds `app`, and `tests/values.yaml`
adds `name` through `persistence.additionalLabels`, so the templates are
equal. With the chart's defaults Qdrant sends anonymous usage statistics to
Qdrant, which the recipe keeps and the README says how to turn off. The
chart's Ingress, ServiceMonitor, PodDisruptionBudget, snapshot claim and
snapshot restoration are off by default and not part of the recipe. Its
Helm test, a ConfigMap and a Pod, is left out (RCP-25). The start script
in the ConfigMap is text of the chart's `templates/configmap.yaml`, so
`qdrant.yml.LICENSE` carries the chart's license (RCP-42).

- RCP-310: `qdrant` MUST render the chart's StatefulSet, Services, ConfigMap
  and ServiceAccount, with `docker.io/qdrant/qdrant:v1.20.0-unprivileged`
  pinned to its index, one replica and the claim template
  `qdrant-storage` of 10Gi.

  - Test: `check qdrant`; CI `check` job
  - Since: #110

- RCP-311: `qdrant` MUST put `applications.qdrant.api_key` into the key
  `api-key` of the Secret `qdrant-apikey`, MUST set
  `QDRANT__SERVICE__API_KEY` from it, and MUST leave the parameter unset.

  The compile then stops with `Interpolation key ... not found` until the
  target sets it, as a ref (RCP-19, RCP-40).

  - Test: `check lint` (RCP-262); CI `check` job, report lines
    `difference: Referenced Secret` and `smoke`
  - Since: #110

- RCP-312: `qdrant` MUST run as UID 1000, GID 2000 and `fsGroup` 3000
  under Pod Security `restricted`, without an init container.

  - Test: CI `check` job, report line `smoke`
  - Since: #110

- RCP-313: The `tests/smoke` of `qdrant` MUST require no Pod Security
  warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace, and
  the version of the image tag from `/` through the Service with the key
  of the Secret `qdrant-apikey`. It MUST get 401 from `/collections`
  without a key and with a wrong one. With the key it MUST create a
  collection, write three points with vectors and payload, and get the
  nearest one with its payload from a query. Once the pod `qdrant-0` was
  deleted and its successor is ready, it MUST find the three points and
  get the same answer to the query.

  The successor mounts the claim of the deleted pod, so the points after
  the restart show that the claim keeps the data.

  - Test: CI `check` job, report line `smoke`
  - Since: #110

- AC-310 (RCP-310 to RCP-313): `check qdrant --level deploys` passes in CI
  on each Kubernetes minor, with differences of the classes Selector
  scheme, Port by name, Derived name, Explicit default and Referenced
  Secret only, and its smoke test finds the points after the pod was
  replaced.

## ejabberd

ejabberd is an XMPP server. Clients log in to accounts of its domain, chat
directly and in group rooms, and the server archives their messages. It
also federates with other XMPP servers. ProcessOne publishes no chart.
processone/ejabberd, GPL-2.0, builds the image `ghcr.io/processone/ejabberd`
for amd64 and arm64 and documents it in `CONTAINER.md`, which carries three
compose examples as code blocks. `ejabberd` takes `CONTAINER.md` at commit
`5ef8f25445204ebc0633242aecc1ba0473e3901d`, the tag of release 26.09 of
2026-09-30, the newest on 2026-11-05, SHA-256
`c13e76ebc376b36cd088ed91facd15ec3fe1d253cc5620bc93e4f7f023ce29f4`. The
image `26.09.1`, which `latest` pointed to on 2026-11-05, is ProcessOne's
rebuild of that tag of 2026-10-23, and its
`org.opencontainers.image.revision` is `26.09`. The image
`docker.io/ejabberd/ecs` comes from processone/docker-ejabberd, for amd64
only, and does not read `REGISTER_ADMIN_PASSWORD` ("Images Comparison" in
`CONTAINER.md`).

DEC-300: `ejabberd` maps the compose example under "Customized Example" in
`CONTAINER.md` (ejabberd), as `pihole` takes the code block of its README
(DEC-28). It is the one example that registers an admin account from a
variable, `REGISTER_ADMIN_PASSWORD`, and keeps the Mnesia database in a
directory outside the container. "Minimal Example" stores nothing outside
the container and registers no account, so nobody could log in and a new
pod would start empty. "Clustering Example" runs two nodes without storage
and with a fixed Erlang cookie. The repository's own compose file,
`test/docker/docker-compose.yml`, runs the databases of ejabberd's test
suite and no ejabberd. A designed recipe on the image was considered.
DEC-10 puts the project's compose example first.

The example's service `main` becomes the StatefulSet `ejabberd`. Its
relative bind mount `./database`, which the repository does not contain,
becomes the claim `database` at `/opt/ejabberd/database` (DEC-21). The
published ports 5222 for clients, 5269 for other servers, 5280 for the web
admin and 5443 for TLS become the Service `ejabberd`. On 5443 ejabberd
serves BOSH, WebSocket, its HTTP API, the web admin and HTTP upload. The
image's `HEALTHCHECK` runs `ejabberdctl status` every minute with a timeout
of 5 seconds and 10 retries, which becomes the readiness probe. The image
sets the Erlang node name to `ejabberd@localhost`, so Mnesia finds its
tables on the claim in every new pod.

DEC-301: A bind mount of a file that the pinned repository does not
contain, which the documentation copies from a file that the image carries
byte for byte at the mount target, renders nothing (Compose sources). The
example mounts `./conf/ejabberd.yml` at `/opt/ejabberd/conf/ejabberd.yml`,
and `CONTAINER.md` has the user copy it from `ejabberd.yml.example`. The
image's build moves `.github/container/ejabberd.yml.example` into the
release (`.github/container/Dockerfile`), and the image's file at the
mount target has its SHA-256,
`12e320cde9dcb0b8f73cab84a33a3abe90a8aaf4e9295f087346d354385ad8fa`. That
file defines the macros `HOST` and `ADMIN` that the example's
`EJABBERD_MACRO_HOST` and `EJABBERD_MACRO_ADMIN` set. The repository's root
`ejabberd.yml.example` defines neither, so with it the two variables would
change nothing. A ConfigMap with the file's text was considered. It would
copy 289 lines of GPL-2.0 text into the recipe, which DEC-16 avoids, and
mount the same bytes the container already has.

DEC-302: `ejabberd` runs under the Pod Security level `restricted` and adds
the capability `NET_BIND_SERVICE` to its container (ejabberd). The image
gives `beam.smp` the file capability `cap_net_bind_service+ep`
(`setcap` in `.github/container/Dockerfile`). With every capability
dropped, the kernel refuses to execute a file whose capabilities it cannot
grant, and the container exits with
`erlexec: Error 1 executing '.../beam.smp'`. `restricted` allows adding
`NET_BIND_SERVICE` and no other capability. The capability stays out of the
running process, because `allowPrivilegeEscalation: false` keeps
`beam.smp` from gaining it, and ejabberd binds only ports above 1024.
Docker's default capabilities include `NET_BIND_SERVICE`, so the compose
container has it too. The level `baseline` with the runtime's default
capabilities was considered. It would keep a dozen more capabilities that
ejabberd does not use.

DEC-303: `ejabberd` requires the admin password as a parameter and keeps
the registration rules of the image's `ejabberd.yml` (ejabberd). The
example sets `REGISTER_ADMIN_PASSWORD=somePassw0rd`, a placeholder in
documentation. The image registers `admin@<host>` with it when the
database is empty, and the macro `ADMIN` makes that account the only one
in the ACL `admin`. `mod_register` accepts in-band registration only from
the access rule `trusted_network`, which allows the loopback network, and
the HTTP API admits only the admin on the loopback network. A client that
reaches the Service therefore cannot create an account, and the admin
creates accounts in the pod or in the web admin. The example's password as
the recipe's default was considered. Every target that kept it would run
an admin account with a password published in `CONTAINER.md`.

DEC-304: `ejabberd` stops ejabberd in a preStop hook with
`ejabberdctl stop && ejabberdctl stopped`, which the compose example does
not have (ejabberd). The image's entrypoint is `tini -- ejabberdctl
foreground`, and `ejabberdctl` starts the Erlang VM as its child without
`exec`. tini hands SIGTERM to that shell, which exits, and tini then exits
too, which kills the VM before Mnesia writes its log to the claim. In CI on
Kubernetes 1.36 the account registered last was missing after the pod was
deleted (run 42110904623), and `docker stop` of the image lost every account
registered since the start. With the hook the node stops in 2 to 3 seconds
and the accounts are there after the restart. Keeping the image's stop was
considered. Every rollout, eviction and node drain would lose recent
accounts and messages.

DEC-305: `ejabberd` requires the Erlang cookie as a parameter and sets it
as `ERLANG_COOKIE`, which the compose example does not set (ejabberd).
`ejabberdctl` writes the variable to `~/.erlang.cookie` before it starts
an Erlang node. Without it, the server node and the node of `ejabberdctl
started`, which the image forks at every start, both start without a
cookie file. ejabberd names the provisional file of its ctl socket after a
hash of the cookie (`get_provisional_udsocket_path` in
`src/ejabberd_listener.erl`). In 2 of 15 fresh starts of the image on
Docker the listener then failed with `enoent` and the container exited, and
on kind it restarted. The image runs `CTL_ON_CREATE` only while
`database/schema.DAT` is missing, and the failed start had already written
it, so the admin account was never registered. With the variable set, 25
of 25 fresh starts registered the admin. The node accepts Erlang
distribution on the pod's address, and the cookie is its only
authentication, so it is a ref like the password. Retrying the
registration at every start was considered. It would put the password into
`CTL_ON_START`, which the container logs, and would not keep ejabberd from
exiting on its first start.

- RCP-380: The `Source` line of `ejabberd` MUST name `CONTAINER.md` of
  processone/ejabberd at the commit of the release tag that the image's
  `org.opencontainers.image.revision` names, with the file's SHA-256.

  `check` fetches the file at that commit and fails on another SHA-256
  (RCP-23).

  - Test: `check lint`; CI `check` job, report line `compose`; manual:
    the image's label
  - Since: #118

- RCP-381: `ejabberd` MUST set `REGISTER_ADMIN_PASSWORD` from the Secret
  `ejabberd`, whose value is `applications.ejabberd.admin_password`, which
  the recipe leaves unset, and `ERLANG_COOKIE` from the same Secret, whose
  value is `applications.ejabberd.erlang_cookie`, which the recipe leaves
  unset too. It MUST set `EJABBERD_MACRO_HOST` to
  `applications.ejabberd.host` and `EJABBERD_MACRO_ADMIN` to
  `admin@<host>`.

  Without either parameter the compile stops with `Interpolation key` and
  its name (RCP-19, RCP-40). The host defaults to the example's
  `example.com`.

  - Test: CI `check` job; manual: a compile of `tests/target.yml` without
    the parameter stops with `Interpolation key` and its name
  - Since: #118

- RCP-382: The container of `ejabberd` MUST run as UID and GID 9000 under
  `restricted` and MUST add no capability other than `NET_BIND_SERVICE`.

  - Test: CI `check` job, the rollout of `ejabberd`; manual: review
  - Since: #118

- RCP-383: The `tests/smoke` of `ejabberd` MUST, from a pod of its own and
  through the Service `ejabberd`, get stream features on 5222 that require
  STARTTLS and on 5269, get 401 from `/admin/` on 5280, and get `forbidden`
  for an in-band registration in a BOSH session on 5443. As the admin
  through the API in the pod it MUST create two accounts and a persistent
  room with its archive. Over BOSH the two accounts MUST exchange a room
  message and a direct message, which the admin MUST read through the
  room's history. Once the pod `ejabberd-0` was deleted and its successor
  is ready, the API MUST list both accounts, and the second account MUST
  find both messages in its archives.

  The test pod runs the ejabberd image, which carries `curl` and `nc`. It
  connects from outside the loopback network, from which `ejabberd.yml`
  would accept a registration. A room's history lives in memory and
  starts empty in the new pod, so after the restart the archives prove that
  the messages are on the claim.

  - Test: CI `check` job, report line `smoke`
  - Since: #118

- RCP-384: `ejabberd` MUST stop ejabberd in a preStop hook and wait until
  the node has stopped.

  - Test: `tests/smoke`, which requires every account after the pod's
    deletion; CI `check` job
  - Since: #118

- AC-380 (RCP-37, RCP-380 to RCP-384): `check ejabberd --level deploys`
  passes in CI on each Kubernetes minor, and its smoke test finds both
  messages in the archives after the restart. `tests/target.yml` without
  `applications.ejabberd.admin_password` or `erlang_cookie` stops the
  compile with `Interpolation key` and that key.

## Mattermost

Mattermost is a team chat server with channels, direct messages, file
sharing and a REST API. Its free edition is Team Edition, which Mattermost
builds from the open source part of mattermost/mattermost and publishes as
the image `docker.io/mattermost/mattermost-team-edition`. Team Edition has
no OpenID Connect. Mattermost's documentation offers OpenID Connect only on
its commercial plans, and the open source part carries GitLab as its only
SSO provider (`server/channels/app/oauthproviders/` of v12.0.2). The recipe
therefore has no OIDC parameters.

DEC-290: `mattermost` is a chart recipe on the chart
`mattermost-team-edition` 6.6.111 of mattermost/mattermost-helm,
Apache-2.0, from the HTTP repository `https://helm.mattermost.com`. The
chart's README marks it as no longer supported and points new deployments
to the Mattermost Operator. Mattermost's release automation still
publishes a chart version with every server release. 6.6.111 of
2026-11-05 moved its `appVersion` to 12.0.2, as the commits before it did
for each release since 11.9.0. The repository publishes no OCI artifact,
so the `Source` line takes the HTTP form of RCP-23.

| Alternative | Why it was not taken |
|---|---|
| The Mattermost Operator, chart `mattermost-operator` 1.0.5 | It runs Mattermost from the custom resource `Mattermost` of `installation.mattermost.com/v1beta1`. No kadet-hub generator renders that kind, so the application recipe would stop on a gap (RCP-7) until one exists. |
| The chart `mattermost` 2.8.1 of the same repository, without the operator | It runs Enterprise Edition, follows the ESR releases (11.7) and renders no claim for files, which it expects in S3. |
| The image as a designed recipe | DEC-10 puts the project's chart first. |

DEC-291: `mattermost` runs Mattermost 12.0.2, the chart's `appVersion`.
The chart writes the image as `mattermost/mattermost-team-edition` with
the tag `12.0.2@sha256:<digest>`. `check` drops the digest only on the
recipe's side (RCP-9), and a class file names the registry (RCP-66), so
`tests/values.yaml` sets `image.repository` to
`docker.io/mattermost/mattermost-team-edition` and `image.tag` to `12.0.2`.
The recipe pins the digest the chart pins, an index with an image for
amd64 only. 12.1.0 was a pre-release on 2026-11-05. Renovate moves the
image and the tag in `tests/values.yaml` with Mattermost's releases
(RCP-16), as for semaphore, because the chart only follows the image.

DEC-292: The database is the included recipe `postgresql` (DEC-4,
DEC-12). The chart passes Mattermost the connection string in `MM_CONFIG`
from its Secret `<fullname>-mattermost-dbsecret`, which it builds from
`externalDB.externalConnectionString`. CloudNativePG generates the
password and keeps it only in the Secret `postgresql-cluster-app`. The
connection string in `tests/values.yaml` leaves the password out,
`app@postgresql-cluster-rw:5432/app?sslmode=require&connect_timeout=10`,
and `extraEnvVars` sets `PGPASSWORD` from that Secret. lib/pq 1.12.3,
Mattermost's PostgreSQL driver (`server/go.mod` of v12.0.2), reads the
variable for a password the string does not name. `sslmode=require`
encrypts the connection without verifying the server's certificate,
because CloudNativePG signs it with its own CA. The recipe reads the
names from `applications.postgresql` (RCP-60). The key `uri` of
`postgresql-cluster-app` as `MM_CONFIG` was considered. The chart reads
`MM_CONFIG` only from its own Secret.

With a connection string in `MM_CONFIG`, Mattermost keeps its
configuration in the database. The chart's Secret `<fullname>-config`
adds `MM_<SECTION>_<SETTING>` variables, which override that configuration
and lock the setting in the System Console.

DEC-293: `mattermost` runs as the image's user `mattermost`, UID, GID and
`fsGroup` 2000 in its `/etc/passwd`, with `allowPrivilegeEscalation: false`
and all capabilities dropped, by `securityContext` and
`containerSecurityContext` in `tests/values.yaml`. That passes Pod
Security `restricted`. The image has no shell. Mattermost writes its logs
and server plugins below `/mattermost` in the container, so the root
filesystem stays writable. The chart's default sets no security context
and was considered. The image would still run as 2000, but the namespace
would need `baseline`.

DEC-294: `tests/values.yaml` sets `MM_TEAMSETTINGS_ENABLEOPENSERVER` to
`"false"` in the chart's `config`. Mattermost's default is the same. The
variable locks the setting, so a System Console change cannot open
sign-up while the target says otherwise. Without open sign-up, accounts
come from the admin or from an invitation.

DEC-295: `mattermost` creates no admin account, and its README says how
to create the first one with `mmctl` in local mode, which the image turns
on with `MM_SERVICESETTINGS_ENABLELOCALMODE`. Mattermost has no setting
for an initial account. Until the first account exists, Mattermost makes
the first account created through sign-up a system admin, also with open
sign-up off (`CreateUserFromSignup` in `server/channels/app/user.go` of
v12.0.2). The Service is of type `ClusterIP`, and the README asks for the
admin before the target exposes it.

| Alternative | Why it was not taken |
|---|---|
| An init container through `extraInitContainers` that runs `mattermost import bulk` with the admin as a user line of a Secret | On an empty database the import first runs Mattermost's app migrations, and the first of them saves the configuration. The import opens the configuration store read-only (`InitDBCommandContextCobra` in `server/cmd/mattermost/commands/init.go`), so it stopped on kind with `configuration store is read-only`, and the pod never started. |
| A Job through the chart's `extraDeploy` that creates the admin through the API | The API server generates a Job's selector and pod labels from the Job's UID, `batch.kubernetes.io/controller-uid`. The two sides of `check` would never compare equal unless RCP-9 dropped those labels. |
| `MM_TEAMSETTINGS_ENABLEUSERCREATION: "false"` against the first sign-up | It also refuses every invitation (`CreateUserWithInviteId`, `CreateUserWithToken`). |

The chart renders the claims `mattermost-mattermost-team-edition` for
files, 10Gi, and `mattermost-mattermost-team-edition-plugins` for the web
app's plugins, 1Gi, with ReadWriteOnce. The recipe keeps the chart's names
for a release named `mattermost`, so a release replaced by the recipe
keeps its claims. The Service is `mattermost-team-edition` on port 8065.
The chart's Ingress, its HTTPRoute and its MySQL subchart are off by
default or by `tests/values.yaml` and not part of the recipe. Its Helm
test `Pod/mattermost-mattermost-team-edition-test` is left out (RCP-25).
The ConfigMap with the test's script is no hook, so the recipe renders it
with the chart's text and `mattermost.yml.LICENSE` (RCP-42).

- RCP-370: `mattermost` MUST render the chart's Deployment, Service,
  Secrets, claims and test ConfigMap with the values of DEC-291 to DEC-294
  and `docker.io/mattermost/mattermost-team-edition:12.0.2` pinned to its
  index.

  - Test: `check mattermost`; CI `check` job
  - Since: #122

- RCP-371: `mattermost` MUST connect to the Cluster of `postgresql` with a
  connection string without a password and `sslmode=require`, and MUST set
  `PGPASSWORD` from the key `password` of `<cluster>-app`.

  - Test: CI `check` job, report line `smoke`
  - Since: #122

- RCP-372: The `tests/smoke` of `mattermost` MUST require no Pod Security
  warning from a server-side dry run of the label
  `pod-security.kubernetes.io/enforce: restricted` on its namespace, and
  `status: OK` from `/api/v4/system/ping` through the Service. It MUST
  create the admin with `mmctl --local` as the README says. Through the
  API it MUST read the image tag as `Version` with `BuildEnterpriseReady`
  `false` from the client configuration, and get 403 for a sign-up without
  an invitation. As the admin it MUST create a team, a channel and a
  second user, and post a message with a file. The second user MUST read
  the message and the file, and read both again once the pod was deleted
  and its successor is ready.

  The message comes from PostgreSQL and the file from the claim, so the
  read after the restart needs both. On kind the smoke test ran in 28
  seconds.

  - Test: CI `check` job, report line `smoke`
  - Since: #122

- RCP-373: The README of `mattermost` MUST say how to create the first
  admin with `mmctl --local`, and that until then the first sign-up
  becomes a system admin.

  - Test: manual: review
  - Since: #122

- AC-370 (RCP-370 to RCP-372): `check mattermost --level deploys` passes
  in CI on each Kubernetes minor, with differences of the classes Selector
  scheme, Explicit default and Derived name only, and its smoke test reads
  the message and the file after the restart.

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

## Recipe requests

A recipe that nobody has written yet is requested with the issue form
`.github/ISSUE_TEMPLATE/recipe-request.yml`. It asks for the application,
the Helm chart or Docker Compose file a recipe would rebuild, and why the
requester needs it, and labels the issue `recipe-request`. kadet-hub.org
lists the open requests on `/wanted/`, most 👍 first (CAT-41 in
kadet-hub/registry), so a second reader adds a 👍 instead of a duplicate.
GitHub applies the label only when it exists in this repository.

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
  the generators the recipe pins. The README's "Using a recipe" shows the
  digest path and names the commit path.

  Once it is published, the fetch inventory pins
  `ghcr.io/kadet-hub/recipes/<name>` by digest instead. The registry's
  consumer workflow handles that when its policy names the fetch inventory
  (CON-4 there). It verifies the recipe against the `recipes` section of
  the index (CON-5), and then the generators the recipe pins as
  dependencies of the main inventory, like any generator. It adds the
  recipes a pinned recipe includes from that recipe's record (CON-7), so
  the fetch inventory pins only the recipes the consumer's targets
  include. Kapitan's own fetch reads no index, so a local compile pulls
  the included recipes by digest. The Include sections of the recipes with
  included recipes say both.

  - Test: manual: the README's "Using a recipe" steps on a fresh clone;
    the digest path: the registry's `consumer/test_consumer.py`
    (`FetchInventory`, `Includes`) and kadet-hub/examples
    `open-webui-searxng/check` (EX-17 there), which verifies and pulls four
    published recipes by digest and deploys them on kind
  - Since: #5 (commit SHA); digest: registry #397, README on the digest
    path: #89; the Include sections of the recipes
    with included recipes: #90; included recipes from the index: registry
    #536, the Include sections: #95; forgejo: #102

- RCP-16: Renovate MUST open a pull request when the chart a recipe is
  derived from has a new release. The pull request runs `check` at
  `renders`, so the diff of the new chart against the recipe is visible.

  Renovate moves the README's `Source` line to the new version and its
  digest. The recipe's images, vendored files and values stay at the old
  version, so `check` fails and its report is the diff a maintainer
  works from. The images follow the chart, so Renovate moves none of them
  to a new tag; the maintainer moves each one in its single line (RCP-66).
  Images a recipe runs ahead of the chart are the exception below.

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

  For a compose source Renovate moves the `Source` line to the project's
  next release (formerly OQ-10). An HTML comment directly above the line
  names the release tag of the pinned commit, such as
  `<!-- renovate: tag=2.5.9 -->` for uptime-kuma. Renovate's `github-tags`
  datasource then moves the tag and the commit of the URL together. The
  SHA-256 stays, so `check` fails on it when the release changed the file,
  and the maintainer maps the change from the new file. An unchanged file
  passes with the new commit.

  The image of the compose file's main service comes from the same
  release, such as `louislam/uptime-kuma:2.5.9`. Its class line carries the
  comment `# renovate: upstream` above it, and Renovate moves its tag and
  digest with the `docker` datasource. A package rule per compose recipe
  groups that image with the `Source` line into one pull request. The
  images of the other services stay on their tags, as the compose file
  pins them.

  SearXNG publishes no releases (SearXNG). Its comment names the branch,
  `<!-- renovate: branch=master -->`, and the `git-refs` datasource moves
  the commit to the branch's newest. `git-refs` gives no release
  timestamps, so a package rule makes the timestamp optional for it. A
  regex versioning reads the image tags `<date>-<commit>` by their date
  alone, so of several images of one day Renovate may propose any. A dry
  run with the image at `2026.11.1-10db664f1` proposed `2026.11.2-d138f443b`
  and the commit of `2026.11.2-cccbc9e15`. Before merging, the maintainer
  sets the image and the `Source` commit to the same commit, the image's
  `org.opencontainers.image.revision`.

  gitea, semaphore and immich run an image ahead of the chart's
  `appVersion`, because the chart's version is affected by an advisory
  (Gitea, Semaphore, Immich). Every line that names that version carries
  `# renovate: upstream`. Above the class image line the marker stands
  alone. Above the tag in `tests/values.yaml` and gitea's `version` label
  it names the image, as in `# renovate: upstream docker.gitea.com/gitea`.
  Renovate moves them all to the newest image in one pull request, which
  waits for a reviewer like a `Source` line. The README's prose keeps the
  old version until the maintainer updates it in that pull request. A
  package rule groups immich's server and machine learning images, which
  run the same release.

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
    repository: #23; rabbitmq: #36; digests of rebuilt tags: #55;
    compose sources and images ahead of the chart: #82

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
  `*.yml` and `*.yaml` below the recipe directory, except `tests/`,
  `recipe.yaml` (RCP-260) and the files a `copy` entry of the recipe names
  as input. Every `classes` entry
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

  The tools are installed by `.github/actions/tools`, kind by the `check`
  job (RCP-70), uv by `astral-sh/setup-uv` with its cache off.

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
  packages in `check/uv.lock`, the `kubernetes-versions.json` commit of
  RCP-70 and the generators a recipe pins.

- RCP-30a: Renovate MUST merge its own pull request once every check on it
  passed, unless it is a major update, lock file maintenance, a digest
  update of a GitHub Action, the `next` pin (RCP-29), the
  `kubernetes-versions.json` commit (RCP-70), or moves a `Source` line or a
  `# renovate: Source` class line (RCP-16, RCP-21).

  Renovate merges without GitHub's auto-merge (`platformAutomerge: false`),
  so it waits for every check, and through a bypass of the `main` ruleset in
  `pull_request` mode, which allows no direct push. Lock file maintenance
  takes the newest releases without the three days of release age. A digest
  update of an action under an unchanged version is a moved tag, the
  pattern of a hijacked action. A source update is a new chart or image
  that RCP-21 leaves to a reviewer. A new `kubernetes-versions.json` can add a
  Kubernetes minor and drop the oldest, which decides what the recipes
  support.

  - Test: manual: `renovate.json` `automerge` rules; `gh api repos/kadet-hub/recipes/rulesets` lists Integration 2740 with `bypass_mode: pull_request` on `main`
  - Since: #56, #59

  `renovate.json` follows kadet-hub/examples. A tool pin carries a
  `# renovate:` comment, a release asset its SHA-256 and an image its
  digest. Renovate waits three days after a release whose registry
  reports a release date.
  helm and kubectl are not GitHub release assets, so Renovate
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
  - Since: #3; lock file maintenance: #55; `kubernetes-versions.json` commit: #59

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
- AC-7 (RCP-16, RCP-29, RCP-30, RCP-30a): a local Renovate dry run on this
  repository extracts the chart of every chart recipe, the image of every
  designed recipe, the `next` pin, the generator
  pins, every tool and action pin and the `check` lock, and sets none of
  the updates RCP-30a excludes to merge automatically. With mysql one patch release back, it
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
- AC-26 (RCP-65, RCP-70): on a pull request that changes `.github/`, the
  `check` job runs every recipe once per minor of
  `kubernetes-versions.json`, each report names that minor's node image,
  and `ci` stays the one required check. `check`'s tests pass
  `--node-image` to `kind create cluster` and no `--image` without it.
- AC-27 (RCP-37, RCP-72, RCP-73): `check paperless-ngx --level deploys`
  passes in CI, its report lists the objects of `postgresql` and `valkey`
  as included and `cnpg` as installed, and its smoke test finds the PDF
  copied into `consume` through the API, and then under the title that
  paperless-ai set from the stub's reply. `tests/target.yml` without the
  option `ai` compiles
  without the objects of `paperless-ngx-ai`.
- AC-28 (RCP-37, RCP-74, RCP-75): `check searxng --level deploys` passes
  in CI, its report lists the objects of `valkey` as included, and its
  smoke test finds the link token in Valkey. `tests/target.yml` without
  `applications.searxng.secret_key` stops the compile with
  `Interpolation key 'applications.searxng.secret_key' not found`.
- AC-32 (RCP-37, RCP-80 to RCP-82): `check pihole --level deploys` passes
  in CI on each Kubernetes minor, and its smoke test gets `0.0.0.0` for
  the denied domain over UDP and over TCP. `tests/target.yml` without
  `applications.pihole.password` stops the compile with
  `Interpolation key 'applications.pihole.password' not found`.
- AC-35 (RCP-85, RCP-86): `check n8n --level deploys` passes in CI on each
  Kubernetes minor, its report lists the objects of `postgresql` and
  `valkey` as included and `cnpg` as installed, and its smoke test gets the
  webhook's answer before and after the restart of n8n-main.
  `tests/target.yml` without `applications.n8n.encryption_key` stops the
  compile with `Interpolation key 'applications.n8n.encryption_key' not
  found`.
- AC-45 (RCP-95, RCP-96): `check authentik --level deploys` passes in CI on
  each Kubernetes minor, its report lists the objects of `postgresql` as
  included and `cnpg` as installed, the permissions of the ServiceAccount
  `authentik` are equal on both sides, and its smoke test gets the OpenID
  configuration of the application it created. `tests/target.yml` without
  `applications.authentik.secret_key`, `bootstrap_password` or
  `bootstrap_token` stops the compile with `Interpolation key` and that
  key.

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
| `check/check.py` | CLI, sources, kind clusters, report; pins the Kapitan `next` image |
| `check/lint.py` | `check lint` (RCP-1 to RCP-7, RCP-66, RCP-17 to RCP-19, RCP-23, RCP-32, RCP-33, RCP-35, RCP-36, RCP-38, RCP-40, RCP-43, RCP-44, RCP-58) |
| `check/compare.py` | Normalization, pairing, classes, selectors, can-i (RCP-9 to RCP-12, RCP-243) |
| `check/tests/` | AC-1, AC-2, AC-5, AC-9, AC-10, AC-13, AC-19, AC-21, AC-24, AC-26 without a cluster |
| `check/pyproject.toml`, `check/uv.lock` | Kapitan 0.36.3, omegaconf 2.4.0.dev4, PyYAML; pip-audit in the group `audit` (RCP-68); the entry point `kadet-convert` ([converter.md](converter.md)) |
| `.github/workflows/ci.yml` | RCP-13, RCP-20, RCP-28, RCP-68, RCP-70, RCP-271 |
| `.github/workflows/request-review.yml` | requests `neat-bot` (RCP-57) |
| `.github/ISSUE_TEMPLATE/recipe-request.yml` | Recipe requests, listed on kadet-hub.org/wanted/ (CAT-41 in kadet-hub/registry) |
| Rulesets `tag creation`, `release tags` | RCP-31, applied with `gh api` |
| `.github/actions/tools/` | Pinned helm, kubectl, oras, gh, cloud-provider-kind (RCP-55) |
| `renovate.json` | RCP-16, RCP-29, RCP-30 |
| `check/lint.py`, `check/check.py`, `.github/workflows/ci.yml` | Included recipes and prerequisites (RCP-47 to RCP-56) |
| `<name>/recipe.yaml`, `check/lint.py`, `check/check.py` | Required parameters and backends (RCP-260 to RCP-263) |

| Value | Setting |
|---|---|
| Repository | `kadet-hub/recipes`, public, Apache-2.0 |
| Artifact | `ghcr.io/kadet-hub/recipes/<name>` |
| Tag | `<name>-vX.Y.Z`, created by the admin role only |
| Registry entry | kadet-hub/registry `recipes/<name>.yaml` |
| Inventory backend | omegaconf, Kapitan 0.36.3 |
| First recipe | cert-manager, chart v1.21.2, level `deploys`, target `migrates` |
| First recipe from kadet-hub/examples | valkey, chart `valkey` 0.12.0 of valkey-io/valkey-helm, level `deploys` |
| First compose recipe | miniflux, `contrib/docker-compose/basic.yml` of miniflux 2.3.4, readiness probe `miniflux -healthcheck auto` (DEC-200, RCP-280), migrations without a lock (DEC-201), level `deploys` |
| First designed recipe | mysql, `container-registry.oracle.com/mysql/community-server` 9.7.4, level `deploys` |
| Environment | `fork-pull-request`, required reviewer: a maintainer |
| Kubernetes minors (RCP-70) | `kubernetes-versions.json` of kadet-hub/renovate-config at `843255e` (`kubernetes-versions-2026-11-02`): 1.37.0, 1.36.4, 1.35.8, kind v0.33.0 |
| Consumer path | `inventory/classes/recipes/<name>/` |
| First chart from an HTTP repository | external-dns-powerdns, chart `external-dns` 1.23.0 of kubernetes-sigs/external-dns, external-dns 0.23.0, includes powerdns, level `deploys` |
| powerdns | `docker.io/powerdns/pdns-auth-51` 5.1.5, SQLite on the claim `data`, zone `applications.powerdns.zone` with the SOA primary `ns1.<zone>.` set by the init container `zone` (RCP-194, RCP-195), `kubernetes` generator 1.14.0, level `deploys` |
| First parent | nextcloud, chart `nextcloud` 9.4.1, Nextcloud 35.0.2, includes postgresql and valkey, requires `gateway-api`, level `deploys` |
| postgresql | chart `cluster` 0.9.0 of cloudnative-pg/charts, `cloudnative-pg` generator 1.1.0, `kubernetes` generator 1.14.0, PostgreSQL 18.6, requires `cnpg`, level `deploys` |
| cnpg | chart `cloudnative-pg` 0.29.1, CloudNativePG 1.30.1, `kubernetes` generator 1.14.0, level `deploys` |
| postgresql option `pgvector` | `recipes.postgresql.pgvector`, `CREATE EXTENSION IF NOT EXISTS vector` in `bootstrap.initdb.postInitApplicationSQL`, pgvector 0.8.7 of the pinned image (RCP-100, RCP-101) |
| postgresql option `earthdistance` | `recipes.postgresql.earthdistance`, `CREATE EXTENSION IF NOT EXISTS earthdistance CASCADE` in the same list, with `cube` (RCP-102) |
| `gateway-api` | cloud-provider-kind 0.12.0, Gateway API 1.6.1 standard CRDs, Gateway `gateway/gateway`, listener `http` |
| keycloak-operator | chart `keycloak-operator-helm` 26.8.1 of keycloak/keycloak, Keycloak Operator 26.8.1, cluster-wide, CRDs of keycloak/keycloak-k8s-resources 26.8.1, level `deploys` |
| keycloak | `quay.io/keycloak/keycloak` 26.8.1, `keycloak` generator 1.1.0, `certmanager` generator 1.0.2, includes postgresql, requires `keycloak-operator`, `cert-manager` and `gateway-api`, level `deploys` |
| keycloak option `route` | `recipes.keycloak.route`, `kubernetes` generator 1.14.0, HTTPRoute `keycloak` to `<name>-service` port 8080, `applications.keycloak.gateway.name`, `.namespace` and `.section` (unset by default), `spec.http.httpEnabled: true`, `spec.proxy.headers: xforwarded` |
| strimzi | chart `strimzi-kafka-operator` 1.3.0 of strimzi/strimzi-kafka-operator, Strimzi 1.3.0, watches every namespace, CRDs of the 1.3.0 release, level `deploys` |
| kafka | `quay.io/strimzi/kafka` 1.3.0-kafka-4.3.1, Kafka 4.3.1, `strimzi` generator 1.1.0, requires `strimzi`, level `deploys` |
| blackbox-exporter | chart `prometheus-blackbox-exporter` 11.20.2 of prometheus-community/helm-charts with its defaults and the pod's seccomp profile `RuntimeDefault` (DEC-205), blackbox_exporter 0.29.1, `kubernetes` generator 1.14.0, level `deploys` (RCP-71, RCP-285, RCP-286) |
| paperless-ngx | `docker/compose/docker-compose.postgres.yml` of paperless-ngx 3.4.1, `kubernetes` generator 1.14.0, includes postgresql and valkey, option `ai` with paperless-ai 3.0.9, level `deploys` (RCP-72, RCP-73) |
| searxng | `container/docker-compose.yml` of searxng/searxng at `cccbc9e`, SearXNG `2026.11.2-cccbc9e15`, `kubernetes` generator 1.14.0, includes valkey, level `deploys` (RCP-74, RCP-75) |
| semaphore | chart `semaphore` 16.2.2 of semaphoreui/charts, Semaphore 2.19.17 by `image.tag`, includes postgresql, `kubernetes` generator 1.14.0, level `deploys` (RCP-77, RCP-78) |
| pihole | compose example in `README.md` of docker-pi-hole 2026.10.1 at `ffd0a48`, Pi-hole Core v6.5, Web v6.6.1 and FTL v6.8, `kubernetes` generator 1.14.0, level `deploys` (RCP-80 to RCP-82) |
| n8n | chart `n8n` 1.18.0 of n8n-io/n8n-hosting with `docker.io/n8nio/n8n` by `image.repository`, n8n 2.45.5 in queue mode, includes postgresql and valkey, `kubernetes` generator 1.14.0, level `deploys` (RCP-85, RCP-86) |
| jellyfin | chart `jellyfin` 3.7.0 of jellyfin/jellyfin-helm from its HTTP repository with its defaults, Jellyfin 12.4, `kubernetes` generator 1.14.0, level `deploys` (RCP-76) |
| gitea | chart `gitea` 12.7.0 of gitea/helm-gitea, Gitea 28.3.0 by `image.tag`, includes postgresql and valkey, `kubernetes` generator 1.14.0, level `deploys` (RCP-90, RCP-91) |
| forgejo | chart `forgejo` 17.3.2 of forgejo-helm/forgejo-helm, Forgejo 15.0.11 LTS, the chart's `appVersion` (DEC-140), includes postgresql (DEC-141), cache, sessions and queue on the chart's defaults (DEC-142), `SECRET_KEY` required (DEC-143), `kubernetes` generator 1.14.0, level `deploys` (RCP-220, RCP-221) |
| immich | chart `immich` 0.13.4 of immich-app/immich-charts, Immich v3.3.5 by `image.tag`, includes postgresql with `pgvector` and `earthdistance` and valkey, library claim `immich-library` 10Gi, `kubernetes` generator 1.14.0, level `deploys` (RCP-103, RCP-104) |
| authentik | chart `authentik` 2026.8.5 of goauthentik/helm, authentik 2026.8.5 without Redis, includes postgresql, worker RBAC of the subchart `authentik-remote-cluster` (DEC-42), `kubernetes` generator 1.14.0, level `deploys` (RCP-95, RCP-96) |
| vaultwarden | compose example in `README.md` of Vaultwarden 1.37.5 at `6ed6921`, signups off (DEC-55), `ADMIN_TOKEN` required (DEC-56), SQLite on the claim `vw-data` (DEC-57), `kubernetes` generator 1.14.0, level `deploys` (RCP-110 to RCP-112) |
| netbox | chart `netbox` 8.3.99 of netbox-community/netbox-chart, NetBox v4.7.4 with its RQ worker, includes postgresql and valkey, pepper ID 1 (DEC-86), `kubernetes` generator 1.14.0, level `deploys` (RCP-140 to RCP-142) |
| ollama | chart `ollama` 1.79.0 of otwld/ollama-helm from its HTTP repository, the subchart of `open-webui` 17.5.0 (DEC-75), Ollama 0.33.2 on the CPU (DEC-76), models in an `emptyDir`, `kubernetes` generator 1.14.0, level `deploys` (RCP-130, RCP-131) |
| uptime-kuma | `compose.yaml` of Uptime Kuma 2.5.9 at `df601c5`, SQLite by `UPTIME_KUMA_DB_TYPE` on the claim `data` (DEC-65), admin account from the web setup (DEC-66), `kubernetes` generator 1.14.0, level `deploys` (RCP-120 to RCP-122) |
| open-webui | chart `open-webui` 17.5.0 of open-webui/helm-charts, Open WebUI 0.12.5 on SQLite, no Pipelines (DEC-77), includes valkey (DEC-78), options `ollama` with the recipe `ollama` and `openai` (DEC-79), `WEBUI_SECRET_KEY` required (DEC-80), `kubernetes` generator 1.14.0, level `deploys` (RCP-132 to RCP-134) |
| mariadb | `docker.io/library/mariadb` 12.3.3, the 12.3 LTS line (DEC-95), readiness from `healthcheck.sh` without liveness (DEC-96), the server's zero configuration TLS (DEC-97), claim `data` 8Gi below `mariadb`, `kubernetes` generator 1.14.0, level `deploys` (RCP-160 to RCP-163) |
| wordpress | `docker.io/library/wordpress` 7.1.4 on PHP 8.5 with Apache (DEC-110, DEC-111), includes mariadb without TLS (DEC-112), claim `data` 8Gi at `wp-content`, keys and salts required, `www-data` on port 80 by the sysctl `net.ipv4.ip_unprivileged_port_start` (DEC-113), readiness on `/wp-login.php` (DEC-114), no installation rendered (DEC-115), `kubernetes` generator 1.14.0, level `deploys` (RCP-180 to RCP-184) |
| ghost | `docker.io/library/ghost` 6.75.0, variant `alpine` (DEC-210), includes mysql without TLS (DEC-211), init container `wait-for-database`, claim `content` 8Gi at `/var/lib/ghost/content`, `node` under `restricted`, readiness on `/` with `X-Forwarded-Proto: https` (DEC-212), no owner rendered (DEC-213), no mail (DEC-214), `url` required, `kubernetes` generator 1.14.0, level `deploys` (RCP-290 to RCP-294) |
| umami | `docker-compose.yml` of Umami v3.4.1 at `559e3c6`, includes postgresql, `init: true` not rendered (DEC-120), init container `wait-for-database` (DEC-121), UID 1001 under `restricted` (DEC-122), `APP_SECRET` and, by DEC-123, `TWO_FACTOR_ENCRYPTION_KEY` required, default admin from the first migration (DEC-124), no TLS to PostgreSQL (DEC-125), `kubernetes` generator 1.14.0, level `deploys` (RCP-190 to RCP-193) |
| memcached | `docker.io/library/memcached` 1.6.45 on Debian 13 (DEC-150), Bitnami's default architecture without its NetworkPolicy, PodDisruptionBudget and ServiceAccount (DEC-151), TCP readiness without liveness (DEC-152), no authentication and no TLS (DEC-153), UID 11211 under `restricted` with a read-only root filesystem, `kubernetes` generator 1.14.0, level `deploys` (RCP-230 to RCP-232) |
| stirling-pdf | chart `stirling-pdf-chart` 4.0.0 of Stirling-Tools/Stirling-PDF-chart from its HTTP repository (DEC-160), Stirling-PDF 3.2.0 (DEC-161) from Docker Hub (DEC-162), claim `stirling-pdf-stirling-pdf-chart` 8Gi at `/configs` (DEC-163), UID 1001 under `restricted` (DEC-164), first admin from `applications.stirling-pdf.admin` through the Secret `stirling-pdf-admin` (DEC-165), `kubernetes` generator 1.14.0, level `deploys` (RCP-240 to RCP-242, RCP-244) |
| zulip | chart `zulip` 2.3.0 of zulip/docker-zulip, Zulip 12.3-0, includes postgresql, rabbitmq, memcached and valkey (DEC-314), first organization and owner from parameters by a post-setup script with Zulip's strength check (DEC-315), `SECRETS_secret_key` required (DEC-316), plain HTTP behind a proxy the target sets up (DEC-317), `kubernetes` generator 1.14.0, level `deploys` (RCP-393 to RCP-395) |
| actual | `packages/sync-server/docker-compose.yml` of Actual 26.11.0 at `1766241`, data on the claim `actual-data` at `/data`, password from the web UI (DEC-220), `kubernetes` generator 1.14.0, level `deploys` (RCP-300 to RCP-302) |
| qdrant | chart `qdrant` 1.20.0 of qdrant/qdrant-helm from its HTTP repository, Qdrant 1.20.0 (DEC-230), one node (DEC-231), the unprivileged image under `restricted` (DEC-232), API key required from `applications.qdrant.api_key` (DEC-233), claim template `qdrant-storage` 10Gi, `kubernetes` generator 1.14.0, level `deploys` (RCP-310 to RCP-313) |
| ejabberd | compose example "Customized Example" in `CONTAINER.md` of ejabberd 26.09 at `5ef8f25` (DEC-300), image `26.09.1`, `./conf/ejabberd.yml` not rendered (DEC-301), `restricted` with `NET_BIND_SERVICE` (DEC-302), admin password required, registration from loopback only (DEC-303), preStop `ejabberdctl stop` (DEC-304), `ERLANG_COOKIE` required (DEC-305), Mnesia on the claim `database`, `kubernetes` generator 1.14.0, level `deploys` (RCP-380 to RCP-384) |
| mattermost | chart `mattermost-team-edition` 6.6.111 of mattermost/mattermost-helm from its HTTP repository, unsupported upstream (DEC-290), Team Edition 12.0.2 (DEC-291), includes postgresql with `PGPASSWORD` (DEC-292), UID 2000 under `restricted` (DEC-293), open sign-up off (DEC-294), first admin by `mmctl --local` from the README (DEC-295), `kubernetes` generator 1.14.0, level `deploys` (RCP-370 to RCP-373) |
