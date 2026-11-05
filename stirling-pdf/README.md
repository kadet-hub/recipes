# stirling-pdf

Stirling-PDF 3.2.0, a web UI and HTTP API that merges, splits, converts
and edits PDF files, with its settings and users on a claim, rendered by
the kadet-hub `kubernetes` generator 1.14.0 from the project's Helm chart
`stirling-pdf-chart` 4.0.0.

Source: `https://docs.stirlingpdf.com/Stirling-PDF-chart/stirling-pdf-chart:4.0.0@sha256:fe3700310f5422606f5f983000afb39ddf6b54b66d034c6f041fefb8c0e788f9`

Level: `deploys`

The chart comes from [Stirling-Tools/Stirling-PDF-chart](https://github.com/Stirling-Tools/Stirling-PDF-chart),
tag `stirling-pdf-chart-4.0.0`. It is published only in that HTTP
repository and as a release asset, so the digest is the SHA-256 of the
archive its `index.yaml` lists. The chart is MIT. The init container's
command is the chart's, with its license in `stirling-pdf.yml.LICENSE`.
Stirling-PDF is MIT except the directories its `LICENSE` names, such as
`app/proprietary/`, which holds the login.

`tests/values.yaml` changes three things against the chart's defaults
(DEC-162 to DEC-164 in [docs/specs/recipes.md](../docs/specs/recipes.md)):

- the image comes from `docker.io` instead of `docker.stirlingpdf.com`,
  a proxy in front of Docker Hub that answered anonymous pulls with 429;
- `/configs`, where Stirling-PDF keeps `settings.yml`, its H2 database
  with the users and its keys, is a claim instead of an `emptyDir`;
- the pod runs as `stirlingpdfuser`, UID and GID 1001, and passes Pod
  Security `restricted`.

The chart names its objects `<release>-stirling-pdf-chart`, so with the
release name `stirling-pdf` the Deployment, Service, ServiceAccount and
claim are all `stirling-pdf-stirling-pdf-chart`. The claim asks for 8Gi
with ReadWriteOnce and names no StorageClass. The Deployment stops the old
pod before it starts a new one, because one pod at a time opens the
database.

## Include

```yaml
classes:
  - recipes.stirling-pdf
parameters:
  namespace: stirling-pdf
  kapitan:
    vars:
      target: stirling-pdf
```

## Required parameters

No parameter has to be set.

## Login

Stirling-PDF 3.2.0 turns the login on by default, and every API call needs
a session or an API key. On its first start it creates the user `admin`
with the password `stirling`, and the web UI asks for a new password at the
first login. Log in and change it before you expose the Service. To create
the first account with other credentials, set
`SECURITY_INITIALLOGIN_USERNAME` and `SECURITY_INITIALLOGIN_PASSWORD` in
`components.stirling-pdf-stirling-pdf-chart.env` before the first start.

## Settings

`<c>` stands for `components.stirling-pdf-stirling-pdf-chart`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `envs` | `<c>.env`, a mapping of name to value |
| `persistence.size` | `<c>.persistent_volume_claims.stirling-pdf-stirling-pdf-chart.storage` |
| `persistence.storageClass` | `<c>.persistent_volume_claims.stirling-pdf-stirling-pdf-chart.storage_class` |
| `resources` | `<c>.resources` |
| `service.type` | `<c>.service.type` |
| `rootPath` | `<c>.env.SYSTEM_ROOTURIPATH` and the `path` of each probe in `<c>.healthcheck` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `deployment.preStopSleepSeconds`, `.terminationGracePeriodSeconds` | `<c>.lifecycle.preStop.exec.command`, `<c>.grace_period` |
| `probes.startup.failureThreshold` | `<c>.healthcheck.startup.failure_threshold` |

The chart's `resources` are empty. Its README asks for a memory limit,
because the image sizes the Java heap from it. Without one the heap may
grow to 70% of the node's memory.

Running as `stirlingpdfuser`, the image cannot start LibreOffice as its
second user `stirlingofficeuser`, which needs root. LibreOffice then runs
as `stirlingpdfuser` in the image's Landlock and seccomp sandbox.

The chart's Ingress, HTTPRoute, ServiceMonitor, PodDisruptionBudget,
HorizontalPodAutoscaler and cluster mode with PostgreSQL, Valkey, S3 and a
licence are off by default and not part of the recipe. The ServiceAccount
has no role.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check stirling-pdf --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The four
objects differ in three ways. The Deployment and the Service select on
`name`, the chart on `app.kubernetes.io/name` and `instance`, and both
select the same pods. The container is named after the component, the
chart's `stirling-pdf-chart`. The ServiceAccount sets
`automountServiceAccountToken: true`, the API default the chart leaves
unset, while the pod opts out as in the chart. The chart binds no role.

`tests/smoke` checks that the pod passes Pod Security `restricted` and
that `/api/v1/info/status` reports the image tag through the Service. The
merge endpoint answers 401 without a login. As `admin` it merges two
one-page PDFs that the test writes, and `qpdf --check` and `pdftotext` in
the image find a valid file with both pages in order. The test changes the
setting `ui.appNameNavbar` through the admin API, deletes the pod, and
reads the new value from its successor, which loads it from `settings.yml`
on the claim.

## Replacing a Helm release

Not tested. A release named `stirling-pdf` has the same object names, so
the claim and its data stay. A release installed with the chart's
defaults has no claim and loses `/configs` with its pod.

1. Delete the Deployment `stirling-pdf-stirling-pdf-chart` with
   `--cascade=orphan`, because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.stirling-pdf.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Delete the orphaned ReplicaSet. Its pod holds the ReadWriteOnce claim,
   so a recipe pod on another node starts only after that.
