# strimzi

The Strimzi Cluster Operator 1.3.0, watching every namespace, with its RBAC
and the CRDs, rendered by the kadet-hub `kubernetes` generator 1.8.0.
Derived from Strimzi's operator chart, which the `kafka` recipe requires.

Source: `oci://quay.io/strimzi-helm/strimzi-kafka-operator:1.3.0@sha256:08852fb5aca9782750ec1698616cad0efe15d5eef1a366d124373129ff9c29ea`

Level: `deploys`

Strimzi publishes the chart with each release. Its package is the release
asset `strimzi-kafka-operator-helm-3-chart-1.3.0.tgz`. Install the recipe
once per cluster, in a target of its own ([docs/specs/recipes.md](../docs/specs/recipes.md),
Kafka). Strimzi 1.3.0 supports Kubernetes 1.32 and later and Kafka 4.2.0
to 4.3.1.

## Include

```yaml
classes:
  - recipes.strimzi
parameters:
  namespace: strimzi
  kapitan:
    vars:
      target: strimzi
```

`init.yml` copies `vendor/strimzi-crds.yaml`, the release asset
`strimzi-crds-1.3.0.yaml` with SHA-256
`09f6db7000e27d6121e02334e666a55f06f8d62a9124e66adee6c84ec010bf41`. It
holds the ten CRDs of the chart's `crds/` directory, which helm installs
only with the first release. The recipe applies them with every deploy.

## Required parameters

No parameter has to be set.

## Settings

| Chart value | Inventory |
|---|---|
| `namespace` (release namespace) | `namespace` |
| `defaultImageTag`, `image.tag` | `applications.strimzi.version`, together with the digest in `applications.strimzi.operator_image` |
| `watchNamespaces`, `watchAnyNamespace` | `components.strimzi-cluster-operator.env.STRIMZI_NAMESPACE`, a comma-separated list of namespaces in place of `*`. The ClusterRoleBindings stay. |
| `replicas` | `components.strimzi-cluster-operator.replicas` |
| `resources` | `components.strimzi-cluster-operator.resources` |
| `fullReconciliationIntervalMs`, `operationTimeoutMs`, `featureGates` | `components.strimzi-cluster-operator.env.STRIMZI_FULL_RECONCILIATION_INTERVAL_MS`, `STRIMZI_OPERATION_TIMEOUT_MS`, `STRIMZI_FEATURE_GATES` |
| `logLevel` | `components.strimzi-cluster-operator.env.STRIMZI_LOG_LEVEL`, read by the log configuration, `INFO` when unset |
| `extraEnvs` | `components.strimzi-cluster-operator.env.<name>` |

The operator image is pinned by digest in the container and in
`STRIMZI_DEFAULT_TOPIC_OPERATOR_IMAGE`, `STRIMZI_DEFAULT_USER_OPERATOR_IMAGE`
and `STRIMZI_DEFAULT_KAFKA_INIT_IMAGE`. The other images the operator
starts are named by tag, as the chart names them. `STRIMZI_KAFKA_IMAGES`
maps each Kafka version to its image. A Kafka that sets `spec.kafka.image`,
as the `kafka` recipe does, runs that image instead.

## Renamed RBAC objects

The `kubernetes` generator names a role and its binding after the entry.
The ClusterRoles keep the chart's names, because the operator binds
`strimzi-kafka-broker`, `strimzi-entity-operator` and `strimzi-kafka-client`
by name to the pods it starts.

| Chart | Recipe |
|---|---|
| ClusterRoleBinding `strimzi-cluster-operator` | `strimzi-cluster-operator-global` |
| ClusterRoleBinding `strimzi-cluster-operator-kafka-broker-delegation` | `strimzi-kafka-broker` |
| ClusterRoleBinding `strimzi-cluster-operator-entity-operator-delegation` | `strimzi-entity-operator` |
| ClusterRoleBinding `strimzi-cluster-operator-kafka-client-delegation` | `strimzi-kafka-client` |

## Proof

`check strimzi --level deploys` with `tests/values.yaml`
(`watchAnyNamespace: true` and the operator image by digest) and
`tests/target.yml`, on kind `kindest/node:v1.37.0`. The objects outside
RBAC differ only in these classes:

- Selector scheme: the Deployment selects on `name`, the chart on `name`
  and `strimzi.io/kind`. The pods carry both labels.
- Explicit default: the ServiceAccount sets
  `automountServiceAccountToken: true`. The pod mounts its token through
  the projected volume `kube-api-access`, as in the chart.

All ServiceAccounts and users bound to `view`, `edit` and `admin` have the
same permissions. `tests/smoke` creates a single-node Kafka on ephemeral
storage in the namespace `strimzi-smoke` and waits until it is Ready.

## Replacing a Helm release

Not tested. Delete the release's Helm secrets
`sh.helm.release.v1.strimzi.*`, delete the Deployment
`strimzi-cluster-operator` with `--cascade=orphan` because its selector
changes, apply the recipe with `kubectl apply --server-side
--force-conflicts`, then delete the orphaned ReplicaSet and the bindings
listed under Renamed RBAC objects by their chart names.
