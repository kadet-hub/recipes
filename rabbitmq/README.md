# rabbitmq

RabbitMQ 4.3.6 as a cluster of three nodes with persistent storage,
designed in kadet-hub on the RabbitMQ Cluster Operator and rendered by the
kadet-hub `rabbitmq` generator 1.1.0.

Source: `docker.io/library/rabbitmq:4.3.6-management@sha256:54cb013d76cd1fd6c0a0708f34062ad61c452bb6f016b434c6c33f1a765d2b58`

Level: `deploys`

Requires: `rabbitmq-cluster-operator`

The operator ships no chart for a RabbitMQ cluster, so the recipe renders
its RabbitmqCluster resource with the Docker Official Image `rabbitmq` as
its source ([docs/specs/recipes.md](../docs/specs/recipes.md), RabbitMQ).
Install `rabbitmq-cluster-operator` first, in a target of its own, and
before it `cert-manager`, which the operator requires. The image is the
`management` variant, an index for linux/amd64, arm64 and four more
platforms.

## Replaces

This recipe replaces the `rabbitmq` recipe of kadet-hub/examples, which
stood in for Bitnami's `rabbitmq` chart. The examples class named the
cluster `production`. A target that moves from it keeps the name, so the
cluster keeps its claims `persistence-production-server-<n>` and with them
its queues and messages. Clients keep the Service `production` and the
credentials in `production-default-user`.

```yaml
parameters:
  generators:
    rabbitmq:
      rabbitmqcluster:
        rabbitmq:
          name: production
```

Moving changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| RabbitMQ Cluster Operator from its release manifest, applied by hand | the recipe `rabbitmq-cluster-operator`, installed in a target of its own |
| cert-manager in the class, from its chart | the recipe `cert-manager`, installed in a target of its own |
| Namespace `messaging`, rendered by the recipe | no Namespace. The target sets `namespace: messaging`. Do not delete the Namespace when the examples class goes, because deleting it deletes the claims. |

The move is not tested.

## Include

```yaml
classes:
  - recipes.rabbitmq
parameters:
  namespace: messaging
  kapitan:
    vars:
      target: rabbitmq
```

## Required parameters

No parameter has to be set. The operator creates the default user and its
credentials in the Secret `rabbitmq-default-user`.

## Settings

| Setting | Inventory |
|---|---|
| RabbitMQ version, 4.3.6 | `generators.rabbitmq.rabbitmqcluster.rabbitmq.spec.image`, tag and digest |
| nodes, 3 | `generators.rabbitmq.rabbitmqcluster.rabbitmq.spec.replicas` |
| volume size, 10Gi, the operator's default | `generators.rabbitmq.rabbitmqcluster.rabbitmq.spec.persistence.storage` |
| resources, 250m CPU and 1Gi memory requested, 1Gi memory limit | `generators.rabbitmq.rabbitmqcluster.rabbitmq.spec.resources` |
| configuration, plugins | `generators.rabbitmq.rabbitmqcluster.rabbitmq.spec.rabbitmq` |

The operator creates the Service `rabbitmq` with AMQP on 5672, the
management API on 15672 and Prometheus metrics on 15692, and the headless
Service `rabbitmq-nodes`. Queues, users and policies are custom resources
of the Messaging Topology Operator, which the `rabbitmq` generator renders
under `generators.rabbitmq` and which no recipe here installs.

## Proof

`check rabbitmq --level deploys` with `tests/target.yml` on kind
`kindest/node:v1.37.0`, with `cert-manager` and then
`rabbitmq-cluster-operator` installed first. The image has no Kubernetes
objects to compare with, so the recipe is proven by deploying it (RCP-44,
RCP-58). `tests/smoke` is the check of the kadet-hub/examples recipe: all
replicas are ready and `rabbitmq-diagnostics check_running` passes. Through
the Service `rabbitmq` it then publishes a message to a quorum queue over
the management API on 15672 and reads it back, gets the AMQP protocol
header answered on 5672 and reads metrics on 15692.
