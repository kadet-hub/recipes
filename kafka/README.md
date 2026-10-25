# kafka

Apache Kafka 4.3.1 as a KRaft cluster of three nodes that are controllers
and brokers, with mutual TLS and ACLs, designed in kadet-hub on Strimzi's
operator and rendered by the kadet-hub `strimzi` generator 1.1.0.

Source: `quay.io/strimzi/kafka:1.3.0-kafka-4.3.1@sha256:1f189b1f0f32684302d8b018b1d21b411e2469a9c465fbdc18fa3599cb5bbdad`

Level: `deploys`

Requires: `strimzi`

Strimzi ships a chart for its operator but none for a Kafka cluster, so the
recipe renders the operator's resources with Strimzi's Kafka image as its
source ([docs/specs/recipes.md](../docs/specs/recipes.md), Kafka). Install
the `strimzi` recipe first, in a target of its own. The image is built by
Strimzi for its release 1.3.0 and moves with `strimzi`.

## Replaces

This recipe replaces the `kafka` recipe of kadet-hub/examples, which stood
in for Bitnami's `kafka` chart. The examples class named the Kafka `events`
and its node pool `dual`. A target that moves from it keeps both names, so
the Kafka keeps its claims `data-0-events-dual-<n>` and with them its
messages. Clients keep the Service `events-kafka-bootstrap`, the CA in
`events-cluster-ca-cert` and their certificates.

```yaml
parameters:
  generators:
    strimzi:
      kafkas:
        kafka:
          name: events
          node_pools:
            kafka-dual:
              name: dual
```

Moving changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| Strimzi operator in the class, from its chart through a `helm` compile entry | the recipe `strimzi`, installed in a target of its own. Delete the examples Deployment `strimzi-cluster-operator` first, because its selector changes. |
| Namespace `kafka`, rendered by the recipe | no Namespace. The target sets `namespace: kafka`. Keep the Namespace when the examples class goes, because deleting it deletes the claims. |
| Kafka image from the operator's version map, by tag | `spec.kafka.image`, pinned by digest |
| topic `orders`, user `orders-app` | not rendered. The target sets its topics and users under their old names. |

The move is not tested.

## Include

```yaml
classes:
  - recipes.kafka
parameters:
  namespace: kafka
  kapitan:
    vars:
      target: kafka
```

## Required parameters

No parameter has to be set.

## Settings

| Setting | Inventory |
|---|---|
| Kafka version, 4.3.1 | `applications.kafka.version`, together with `metadata_version` and the digest in `generators.strimzi.kafkas.kafka.spec.kafka.image` |
| nodes, 3 | `generators.strimzi.kafkas.kafka.node_pools.kafka-dual.replicas` |
| volume size, 10Gi | `generators.strimzi.kafkas.kafka.node_pools.kafka-dual.storage` |
| resources | `generators.strimzi.kafkas.kafka.node_pools.kafka-dual.resources` |
| broker configuration | `generators.strimzi.kafkas.kafka.config` |
| topics, users | `generators.strimzi.topics.<name>`, `generators.strimzi.users.<name>` |

The `strimzi` generator renders one internal listener `tls` on port 9093
with mutual TLS, simple authorization, so a user can do only what its ACLs
allow, and the Entity Operator, which reconciles topics and users. It
derives the replication settings from the three brokers. A topic or user
the target sets belongs to the only Kafka.

## Proof

`check kafka --level deploys` with `tests/target.yml` on kind
`kindest/node:v1.37.0`, with `strimzi` installed first. The image has no
Kubernetes objects to compare with, so the recipe is proven by deploying
it (RCP-44, RCP-58). `tests/target.yml` adds the examples class's topic
`orders` as the KafkaTopic `kafka-orders` and its user as
`kafka-orders-app` (RCP-3). `tests/smoke` is the check of the
kadet-hub/examples recipe: the Kafka, the topic and the user are Ready, and
a client with the user's certificate writes a message to the topic and
reads it back over mutual TLS through the Service `kafka-kafka-bootstrap`.
