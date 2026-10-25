# cnpg

The CloudNativePG operator 1.30.1 with its webhooks and RBAC, and optionally
its CRDs, rendered by the kadet-hub `kubernetes` generator 1.9.0 from the
project's Helm chart `cloudnative-pg` 0.29.1.

Source: `oci://ghcr.io/cloudnative-pg/charts/cloudnative-pg:0.29.1@sha256:3245fa051bb21d0dd9246272f57a2760b4234817a164a3167d2a1e7fb9f63fd9`

Level: `deploys`

The chart comes from [cloudnative-pg/charts](https://github.com/cloudnative-pg/charts),
tag `cloudnative-pg-v0.29.1`. The recipe is named after the release name
`cnpg`, with which every object the chart renders starts with `cnpg`.

## Include

```yaml
classes:
  - recipes.cnpg
  - recipes.cnpg.crds   # the chart's crds.create
parameters:
  namespace: cnpg-system
  kapitan:
    vars:
      target: cnpg
```

`crds.yml` copies `vendor/cnpg.crds.yaml`, the chart's
`templates/crds/crds.yaml` without its first and last line, the condition
on `crds.create`. SHA-256 of the vendored file:
`d35964ebdb5ff843ce12ff84c673f838537d11ec1e8ac0dab65498e37ed835b3`.

The operator runs once per cluster and watches every namespace. Install it
in a target of its own before any recipe that requires it, such as
`postgresql`.

## Required parameters

No parameter has to be set.

## Settings

| Chart value | Inventory |
|---|---|
| `namespace` (release namespace) | `namespace` |
| `image.tag` | `applications.cnpg.version`, together with the digest in `components.cnpg-cloudnative-pg.image` |
| `replicaCount` | `components.cnpg-cloudnative-pg.replicas` |
| `config.maxConcurrentReconciles` | `components.cnpg-cloudnative-pg.args.max-concurrent-reconciles` |
| `additionalArgs` | `components.cnpg-cloudnative-pg.args.<key>` |
| `additionalEnv` | `components.cnpg-cloudnative-pg.env.<name>` |
| `config.data` | `generators.kubernetes.configs.cnpg-controller-manager-config.data` |
| `monitoringQueriesConfigMap.queries` | `generators.kubernetes.configs.cnpg-default-monitoring.data.queries.value` |
| `resources`, `nodeSelector`, `tolerations`, `affinity` | `components.cnpg-cloudnative-pg.resources`, `.node_selector`, `.tolerations`, `.affinity` |

The operator writes its CA into the two webhook configurations, which it
finds by the names `cnpg-mutating-webhook-configuration` and
`cnpg-validating-webhook-configuration`, and it finds its own Deployment by
the label `app.kubernetes.io/name: cloudnative-pg`. Do not change these.
The chart passes the operator image by tag in `OPERATOR_IMAGE_NAME`, and
the operator gives it to the bootstrap container of every instance pod.

The pod annotations `checksum/rbac`, `checksum/config` and
`checksum/monitoring-config` are the chart's hashes for `tests/values.yaml`.
They do not change with the recipe, so restart the operator with
`kubectl rollout restart deployment/cnpg-cloudnative-pg` after changing its
ConfigMaps. The monitoring queries are the chart's, Apache-2.0, with the
license in `operator.yml.LICENSE`.

## Proof

`check cnpg --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind `kindest/node:v1.37.0`. The objects differ in
their selector scheme, the explicit `automountServiceAccountToken: true`
of the pod and the ServiceAccount, and the container name, which the
generator derives from the component. The permissions of the operator's
ServiceAccount are equal.

`tests/smoke` creates a one-instance Cluster in another namespace. The
webhooks admit it, the mutating webhook fills in its defaults, and it
becomes ready.

## Replacing a Helm release

Not tested. A release named `cnpg` in `cnpg-system` has the same object
names.

1. Delete the Deployment `cnpg-cloudnative-pg` with `--cascade=orphan`,
   because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.cnpg.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
