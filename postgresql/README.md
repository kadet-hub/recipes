# postgresql

One CloudNativePG Cluster running PostgreSQL 18.6, rendered by the kadet-hub
`cloudnative-pg` generator 1.1.2 from CloudNativePG's Helm chart `cluster`
0.9.0.

Source: `oci://ghcr.io/cloudnative-pg/charts/cluster:0.9.0@sha256:c8130c6573ab59e7629390ee5c468e5bc3d8536e6ec4ca8deea1aee792c4a9e5`

Level: `deploys`

Requires: `cnpg`

The chart comes from [cloudnative-pg/charts](https://github.com/cloudnative-pg/charts),
tag `cluster-v0.9.0`. Install the `cnpg` recipe first, in a target of its
own. The operator writes the Secret `<cluster>-app` with the keys
`username`, `password`, `host` and `dbname` and generates the password.
The read-write Service is `<cluster>-rw`. `<cluster>` is
`applications.postgresql.cluster`, `postgresql-cluster` by default.

## Replaces

This recipe replaces the `postgresql` recipe of kadet-hub/examples, which
stood in for Bitnami's `postgresql` and `postgresql-ha` charts. The
examples class named the Cluster `app-db`. A target that moves from it
keeps that name and the size of its volumes, so the Cluster keeps its
claims `app-db-<n>` and with them its data. Clients keep the Secret
`app-db-app` and the Service `app-db-rw`.

```yaml
parameters:
  namespace: databases
  applications:
    postgresql:
      cluster: app-db
      storage: 10Gi
```

Moving changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| CloudNativePG operator in the class, from its chart through a `helm` compile entry | the recipe `cnpg` in a target of its own, with the same object names in `cnpg-system`. Replace it as the `cnpg` README describes under "Replacing a Helm release". The examples class left no Helm secrets. |
| Namespace `databases`, rendered by the class | no Namespace. Keep the Namespace when the examples class goes, because deleting it deletes the claims. |
| Pooler `app-db-pooler-rw` in transaction mode | not rendered. A target whose clients connect through it sets the examples class's entry `generators.cloudnative-pg.poolers.app-db-pooler-rw`. |
| Cluster settings | the chart's: `enableSuperuserAccess: true`, which adds the Secret `app-db-superuser`, `primaryUpdateMethod: switchover` and anti-affinity across zones, `topologyKey: topology.kubernetes.io/zone` |
| no ConfigMap | `postgresql-cluster-monitoring-logical-replication`, the chart's logical replication queries |

The move is not tested.

## Include

```yaml
classes:
  - recipes.postgresql
  - recipes.postgresql.pgvector         # the extension vector in the database
  - recipes.postgresql.earthdistance    # the extensions cube and earthdistance
parameters:
  namespace: <namespace>
  kapitan:
    vars:
      target: <target>
```

## Required parameters

No parameter has to be set.

## Settings

| Chart value | Inventory |
|---|---|
| `fullnameOverride`, the Cluster's name, `postgresql-cluster` | `applications.postgresql.cluster` |
| `cluster.initdb.database`, `app` | `applications.postgresql.database` |
| `cluster.initdb.owner`, `app` | `applications.postgresql.owner` |
| `cluster.storage.size`, 8Gi | `applications.postgresql.storage` |
| `cluster.instances`, 3 | `applications.postgresql.instances` |
| `cluster.imageName` | `generators.cloudnative-pg.clusters.postgresql.image_name`, tag and digest |

The database and owner take effect only when the Cluster is created. The
logical replication queries are the chart's, Apache-2.0, with the license
in `cluster.yml.LICENSE`.

## The option `pgvector`

`recipes.postgresql.pgvector` adds `CREATE EXTENSION IF NOT EXISTS vector`
to the Cluster's `bootstrap.initdb.postInitApplicationSQL`. CloudNativePG
runs it as superuser in the database once, when it creates the Cluster.
The owner cannot create the extension itself, since pgvector is not a
trusted extension. The image needs no change, because the pinned
`18.6-system-trixie` ships pgvector 0.8.7. On a Cluster that exists
already the option does nothing. There a superuser runs the statement in
the database by hand.

## The option `earthdistance`

`recipes.postgresql.earthdistance` adds
`CREATE EXTENSION IF NOT EXISTS earthdistance CASCADE` to the same list,
which creates `cube` with it. Both are contrib modules of PostgreSQL in the
image. The owner may create `cube` but not `earthdistance`. On a Cluster
that exists already the option does nothing, as `pgvector` does not. With
both options the statements run in the order the target includes them.

## Left out

`Job/postgresql-cluster-ping-test`, the chart's Helm test.

## Proof

`check postgresql --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with `cnpg`
installed first. `tests/values.yaml` sets the database and owner that
CloudNativePG gives an empty `initdb`, so the chart renders them like the
recipe. `tests/target.yml` includes the options `pgvector` and
`earthdistance`, whose statements `tests/values.yaml` sets as
`cluster.initdb.postInitApplicationSQL`.
`tests/smoke` checks what the chart's ping test and the
kadet-hub/examples recipe checked: the Cluster is ready, and the owner
reaches its database through `postgresql-cluster-rw` with the credentials of
`postgresql-cluster-app`. As the owner it then reads the version of `vector`
from `pg_extension` and computes a distance between two vectors, and it
requires `cube` and `earthdistance` in `pg_extension` and computes the
length of one degree of longitude on the equator with `earth_distance`.
