# velero

The Velero 1.18.4 backup server with the AWS plugin for S3-compatible
object stores, its RBAC and its CRDs, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from the vmware-tanzu Helm chart `velero`
12.2.5.

Source: `https://vmware-tanzu.github.io/helm-charts/velero:12.2.5@sha256:faf074aacc580ddffa63e85582cafd54b3dde018442af9623a710a3825f644b8`

Level: `deploys`

The chart comes from [vmware-tanzu/helm-charts](https://github.com/vmware-tanzu/helm-charts),
tag `velero-12.2.5`, and is published only in that HTTP repository, so the
digest is the SHA-256 of the archive its `index.yaml` lists (RCP-23 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). Velero, the plugin and
the chart are Apache-2.0. The recipe runs `docker.io/velero/velero`
v1.18.4, ahead of the chart's 1.18.2 (DEC-353), and
`docker.io/velero/velero-plugin-for-aws` v1.14.4, the plugin line for
Velero 1.18. Both images are built for amd64 and arm64.

Velero watches only its own namespace. Install the recipe once per cluster,
in a target of its own.

## Include

```yaml
classes:
  - recipes.velero
parameters:
  namespace: velero
  kapitan:
    vars:
      target: velero
  applications:
    velero:
      s3:
        access_key_id: <ref>
        secret_access_key: <ref>
```

## Required parameters

`applications.velero.s3.access_key_id` and
`applications.velero.s3.secret_access_key` are the S3 keys with which
Velero reaches the buckets. The recipe writes them as the profile `default`
into the key `cloud` of the Secret `velero`, which the server mounts at
`/credentials`. Set them as refs with the backend of your choice. Without
one of them the compile stops with `Interpolation key '<key>' not found`.

## Locations, schedules and backups

The recipe renders no BackupStorageLocation, VolumeSnapshotLocation,
Schedule or Backup. Write them with the kadet-hub
[`velero` generator](https://kadet-hub.org/generators/velero/), 1.0.3 on
2026-11-17 and built for Velero 1.18.4, in the recipe's namespace. A
location on an S3 store other than AWS sets `provider: aws`, the bucket,
and the plugin's `config`, such as `region`, `s3ForcePathStyle: "true"` and
`s3Url`. A location without `credential` uses the Secret `velero`.

## Settings

| Chart value | Inventory |
|---|---|
| `namespace` (release namespace) | `namespace` |
| `image.tag` | `components.velero.image`, tag and digest |
| `initContainers` | `components.velero.init_containers.<name>`; `velero-plugin-for-aws: ~` drops the AWS plugin |
| `configuration.*` server flags, `configuration.extraArgs` | `components.velero.args.<key>`, such as `uploader-type` |
| `configuration.extraEnvVars` | `components.velero.env.<name>` |
| `configuration.repositoryMaintenanceJob.repositoryConfigData.global` | `generators.kubernetes.configs.velero-repo-maintenance.data.global.value` |
| `resources`, `nodeSelector`, `tolerations`, `affinity` | `components.velero.resources`, `.node_selector`, `.tolerations`, `.affinity` |
| `terminationGracePeriodSeconds` | `components.velero.grace_period` |

`args` is a mapping and renders in the recipe's key order, with new keys
after them. Any other list set in the target is appended to the recipe's
list.

The CRDs are the chart's, those of Velero 1.18.2. Velero 1.18.3 added
`spec.resourcePolicy` to Restore. The CRD does not have it, so the API
server rejects the field, or drops it for a client without strict field
validation, and such a restore runs without its filters.

## Left out

The node agent, the chart's `deployNodeAgent`, is not rendered, so file
system backups with Kopia are not available. Velero finds the agent's
DaemonSet by the name `node-agent`, and the recipe can render it only under
its own name (DEC-354).

The chart's hook `upgrade-crds` runs `velero install --crds-only` inside
`helm install` and `helm upgrade`. The recipe applies the CRDs itself. These
hook objects are not rendered: `ServiceAccount/velero-server-upgrade-crds`,
`ClusterRole/velero-upgrade-crds`, `ClusterRoleBinding/velero-upgrade-crds`
and `Job/velero-upgrade-crds`.

## Proof

`check velero --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The values
empty the chart's lists of locations and name the Secret `velero` as
`credentials.existingSecret`. The objects differ only in these classes:

- Selector scheme: the Deployment and the Service select on `name` alone,
  the chart's on `app.kubernetes.io/name` and `app.kubernetes.io/instance`,
  its Service on `name` as well.
- Explicit default: the container `velero` has `securityContext: {}`.
- Referenced Secret: the Secret `velero`, which the chart's pod mounts.

The ServiceAccount `velero-server` has the same permissions on both sides.
`tests/smoke` runs SeaweedFS as the S3 store, puts a location on it and
backs up a namespace with a ConfigMap. Once the namespace is deleted, it
restores it from the backup in the bucket.

## Replacing a Helm release

Not tested. A release named `velero` in `velero` has the same object names.
The release's locations stay as they are, without an owner, until the
target writes them with the `velero` generator under the same names.

1. Delete the Deployment `velero` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.velero.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
