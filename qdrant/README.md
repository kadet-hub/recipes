# qdrant

Qdrant 1.20.0, a vector database with a REST and a gRPC API, as one node
with its data on a claim and an API key required on every request, rendered
by the kadet-hub `kubernetes` generator 1.16.0 from Qdrant's own Helm chart.

Source: `https://qdrant.github.io/qdrant-helm/qdrant:1.20.0@sha256:dbd9a79e4d00e9d4fc117aa0a568b53ccf07f13dd8d26ac858b76fa14eb36bac`

Level: `deploys`

The chart comes from [qdrant/qdrant-helm](https://github.com/qdrant/qdrant-helm),
tag `qdrant-1.20.0`. Its release workflow publishes the archive with
chart-releaser as a GitHub release asset and in the HTTP repository above,
the URL its README gives to `helm repo add`. It pushes no OCI artifact. The
chart and Qdrant are Apache-2.0. The recipe runs
`docker.io/qdrant/qdrant:v1.20.0-unprivileged`, Qdrant's build of the
chart's `appVersion` that runs as UID 1000, pinned to its index for amd64
and arm64. The pod passes the Pod Security level `restricted`.

## Include

```yaml
classes:
  - recipes.qdrant
parameters:
  namespace: qdrant
  kapitan:
    vars:
      target: qdrant
  applications:
    qdrant:
      api_key: <ref>
```

## Required parameters

`applications.qdrant.api_key` is the API key that Qdrant requires on every
request, in the header `api-key` or as `Authorization: Bearer <key>`. Set it
as a ref with the backend of your choice. Without it the compile stops with
`Interpolation key 'applications.qdrant.api_key' not found`. The recipe
puts it into the Secret `qdrant-apikey`, key `api-key`, from which clients
in the namespace can read it.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `components.qdrant.image`, tag and digest |
| `apiKey` | `applications.qdrant.api_key` |
| `env` | `components.qdrant.env.<variable>`, such as `QDRANT__TELEMETRY_DISABLED: "true"` |
| `persistence.size` | `components.qdrant.volume_claims.qdrant-storage.spec.resources.requests.storage` |
| `persistence.storageClassName` | `components.qdrant.volume_claims.qdrant-storage.spec.storageClassName` |
| `resources` | `components.qdrant.resources` |
| `config` | the key `production.yaml` of `generators.kubernetes.configs.qdrant.data` |
| `service.type` | `components.qdrant.additional_services.qdrant.type` |
| `podAnnotations` | `components.qdrant.pod_annotations` |
| `nodeSelector`, `tolerations`, `affinity` | `components.qdrant.node_selector`, `components.qdrant.tolerations`, `components.qdrant.affinity` |

Qdrant reads `QDRANT__<SECTION>__<KEY>` variables over its configuration
file, so `env` is the shorter way to change one setting. With the chart's
defaults Qdrant sends anonymous usage statistics to Qdrant, which
`QDRANT__TELEMETRY_DISABLED: "true"` turns off.

The recipe runs one node. `replicaCount` is not a setting, because the
generator cannot render the chart's `podManagementPolicy: Parallel`, and
with the API default `OrderedReady` the chart warns that the nodes of a
cluster wait for each other forever.

The pod annotation `checksum/config` is the chart's hash for the values in
`tests/values.yaml`. It does not change with the ConfigMap `qdrant`, so after
changing it restart the pod with `kubectl rollout restart statefulset/qdrant`.
A changed API key needs the same restart.

The script `initialize.sh` in the ConfigMap `qdrant` is the chart's,
rendered for one node without snapshot restoration. It is Apache-2.0, and
its license is in `qdrant.yml.LICENSE`.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's test runs only inside `helm test`. `tests/smoke` checks more on
the installed recipe. It is not rendered: `ConfigMap/qdrant-test-db-interaction`,
`Pod/qdrant-test-db-interaction`.

## Proof

`check qdrant --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests.
`tests/values.yaml` switches to the unprivileged image, adds what Pod
Security `restricted` asks for beyond the chart's defaults, sets the API
key from the recipe's Secret, and sets `podManagementPolicy: OrderedReady`
and the label `name` on the claim template, which the generator renders.
The objects differ in five ways, all of classes `check` accepts. The
StatefulSet and both Services select on `name`, the chart on `app` and
`app.kubernetes.io/*`, and both select the same pods. The Services target
the container ports by name, the chart by number. The container ports are
sorted by name. The pod and the ServiceAccount set
`automountServiceAccountToken: true`, which the chart leaves unset. The
Secret `qdrant-apikey` exists only in the recipe, and the chart's pod reads
it. The chart binds no role.

`tests/smoke` requires that the namespace would pass Pod Security
`restricted`, and the image tag's version from `/` through the Service. It
gets 401 without the API key and with a wrong one. With the key of the
Secret it creates a collection, writes three points with vectors and
payload, and gets the nearest point with its payload from a query. It
deletes the pod `qdrant-0`, waits for its successor on the same claim, and
finds the three points and the same nearest point again.

## Replacing a Helm release

Not tested.

1. Delete the StatefulSet `qdrant` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.qdrant.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Delete the orphaned pod `qdrant-0`, so the StatefulSet starts it again
   on the claim `qdrant-storage-qdrant-0`.
