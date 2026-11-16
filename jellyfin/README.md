# jellyfin

The Jellyfin 12.4 media server with its web client and API on port 8096,
rendered by the kadet-hub `kubernetes` generator 1.16.0 from the Jellyfin
project's Helm chart `jellyfin` 3.7.0 with its default values.

Source: `https://jellyfin.github.io/jellyfin-helm/jellyfin:3.7.0@sha256:d649534398b4e04f08ab6a38f7344f09ac7d6d9767dc000820c7e61d9f7a8b8b`

Level: `deploys`

The chart comes from [jellyfin/jellyfin-helm](https://github.com/jellyfin/jellyfin-helm),
tag `jellyfin-3.7.0`. It is published only in that HTTP repository and as
a release asset, so the digest is the SHA-256 of the archive its
`index.yaml` lists (RCP-23 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
The chart and Jellyfin are GPL-2.0. The recipe copies no text of the chart
(DEC-16 there).

The release name `jellyfin` equals the chart's name, so the Deployment,
Service and ServiceAccount are all `jellyfin`. The chart's defaults claim
two volumes from the cluster's default StorageClass: `jellyfin-config`
with 5Gi at `/config`, and `jellyfin-media` with 25Gi, mounted read-only
at `/media`. `/cache` is an `emptyDir`.

## Include

```yaml
classes:
  - recipes.jellyfin
parameters:
  namespace: jellyfin
  kapitan:
    vars:
      target: jellyfin
```

## Required parameters

No parameter has to be set.

## Settings

`<c>` stands for `components.jellyfin`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `persistence.config.size` | `<c>.persistent_volume_claims.jellyfin-config.storage` |
| `persistence.media.size` | `<c>.persistent_volume_claims.jellyfin-media.storage` |
| `persistence.*.storageClass` | `<c>.persistent_volume_claims.<claim>.storage_class` |
| `jellyfin.env` | `<c>.env`, a mapping of name to value |
| `resources` | `<c>.resources` |
| `service.type` | `generators.kubernetes.services.jellyfin.type` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `podSecurityContext`, `securityContext` | `<c>.workload_security_context`, `<c>.security_context` |
| `volumes`, `volumeMounts` | `<c>.volumes.<name>`, `<c>.volume_mounts.<name>` |
| `startupProbe.failureThreshold` | `<c>.healthcheck.startup.failure_threshold` |

Hardware transcoding is not tested, because kind has no GPU. The chart's
README enables it with the capability `SYS_ADMIN` in `securityContext`
and the host's `/dev/dri` as a `hostPath` volume. In the recipe these are
`<c>.security_context`, `<c>.volumes` and `<c>.volume_mounts`.

The chart's Ingress, HTTPRoute, NetworkPolicy, ServiceMonitor with its
metrics hook, and DLNA on the host network are off by default and not part
of the recipe.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check jellyfin --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The five
objects differ in two ways. The Deployment and the Service select on
`name`, the chart on `app.kubernetes.io/name` and `instance`, and both
select the same pods. The pod sets `automountServiceAccountToken: true`,
which the chart leaves unset while its ServiceAccount allows the token.
The chart binds no role.

`tests/smoke` calls Jellyfin through the Service and the API server's
service proxy. `/health` answers `Healthy`. `/System/Info/Public`, which
answers without a login, is JSON whose `Version` is the Deployment's image
tag. Jellyfin reports the tag `12.4` as `12.4.0`, and the test accepts
either form.

## Replacing a Helm release

Not tested. A release named `jellyfin` has the same object names, so the
claims and their data stay.

1. Delete the Deployment `jellyfin` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.jellyfin.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Delete the orphaned ReplicaSet. Its pod holds the ReadWriteOnce claims,
   so a recipe pod on another node starts only after that.
