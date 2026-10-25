# rabbitmq-cluster-operator

The RabbitMQ Cluster Operator 2.23.1 with its webhooks, RBAC and CRD,
rendered by the kadet-hub `kubernetes` generator 1.9.0 and `certmanager`
generator 1.0.2 from the project's release manifest.

Source: `https://github.com/rabbitmq/cluster-operator/releases/download/v2.23.1/cluster-operator.yml@sha256:ae35a547751656bc64bb734026249a845d226d96aba5a73783e05c5ec3444687`

Level: `deploys`

Requires: `cert-manager`

rabbitmq/cluster-operator publishes no chart. Its install guide applies
`cluster-operator.yml` of the latest release, which this recipe rebuilds
([docs/specs/recipes.md](../docs/specs/recipes.md), RabbitMQ). The operator
watches every namespace. Install the recipe once per cluster, in a target
of its own, before any recipe that requires it, such as `rabbitmq`.

cert-manager issues the webhook certificate. The recipe needs cert-manager
1.18 or later with the feature gate `DefaultPrivateKeyRotationPolicyAlways`
on, its default, because its Certificates set `privateKey.rotationPolicy:
Always` where the manifest leaves it to that default. The `cert-manager`
recipe installs 1.21.2.

## Include

```yaml
classes:
  - recipes.rabbitmq-cluster-operator
parameters:
  namespace: rabbitmq-system
  kapitan:
    vars:
      target: rabbitmq-cluster-operator
```

The recipe renders the Namespace `namespace`, as the manifest renders
`rabbitmq-system`. `init.yml` copies
`vendor/rabbitmq.com_rabbitmqclusters.yaml`,
`config/crd/bases/rabbitmq.com_rabbitmqclusters.yaml` of
rabbitmq/cluster-operator v2.23.1 with SHA-256
`6203b7216bbb76aa6eeedc8ee3d07e4750b8ed66c9498346e6098be9a89c309e`, MPL-2.0.
It is the CRD of the manifest.

## Required parameters

No parameter has to be set.

## Settings

| Setting | Inventory |
|---|---|
| operator version, 2.23.1 | `applications.rabbitmq-cluster-operator.version`, together with the digest in `components.rabbitmq-cluster-operator.image` |
| replicas, 1 | `components.rabbitmq-cluster-operator.replicas` |
| resources | `components.rabbitmq-cluster-operator.resources` |
| operator arguments | `components.rabbitmq-cluster-operator.args.<key>` |
| operator environment | `components.rabbitmq-cluster-operator.env.<name>` |

The webhook Service `cluster-operator-webhook-service` has one port without
a name, as in the manifest. The recipe writes it with an empty key, which
the API stores as no name. The Certificate `metrics-certs` keeps the
manifest's DNS names `SERVICE_NAME.SERVICE_NAMESPACE.svc`, placeholders its
Kustomize base does not replace. No pod mounts its Secret.

## Renamed RBAC objects

The `kubernetes` generator names a role and its binding after the entry.
The roles keep the manifest's names.

| Manifest | Recipe |
|---|---|
| ClusterRoleBinding `rabbitmq-cluster-operator-rolebinding` | `rabbitmq-cluster-operator-role` |
| RoleBinding `rabbitmq-cluster-leader-election-rolebinding` | `rabbitmq-cluster-leader-election-role` |

## Proof

`check rabbitmq-cluster-operator --level deploys` with `tests/target.yml`,
on kind `kindest/node:v1.37.0`, with `cert-manager` installed first. The
objects outside RBAC differ only in these classes:

- Selector scheme: the Deployment and both Services select on `name`, the
  manifest on `app.kubernetes.io/name` and, in the Services,
  `app.kubernetes.io/component`.
- Explicit default: the pod and the ServiceAccount set
  `automountServiceAccountToken: true`, and both Certificates
  `privateKey.rotationPolicy: Always`.
- Derived name: the container is named after the component, where the
  manifest names it `operator`.

The ServiceAccount and users bound to `view`, `edit` and `admin` have the
same permissions. `tests/smoke` creates a RabbitmqCluster in the namespace
`rabbitmq-smoke`. The webhooks admit it with the CA that cert-manager
injected, the mutating webhook sets its image, and its replica becomes
ready.

## Replacing a kubectl install

Not tested. An install of `cluster-operator.yml` v2.23.1 has the recipe's
object names, except the bindings listed under Renamed RBAC objects.

1. Delete the Deployment `rabbitmq-cluster-operator` in `rabbitmq-system`
   with `--cascade=orphan`, because its selector changes.
2. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
3. Once the recipe's pod is ready, delete the orphaned ReplicaSet and the
   two bindings by their manifest names.
