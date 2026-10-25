# postgresql

One CloudNativePG Cluster running PostgreSQL 18, rendered by the kadet-hub
`cloudnative-pg` generator 1.0.1 from CloudNativePG's Helm chart `cluster`
0.9.0.

Source: `oci://ghcr.io/cloudnative-pg/charts/cluster:0.9.0@sha256:c8130c6573ab59e7629390ee5c468e5bc3d8536e6ec4ca8deea1aee792c4a9e5`

Level: `deploys`

Requires: `cnpg`

## Include

```yaml
classes:
  - recipes.postgresql
parameters:
  namespace: <namespace>
  kapitan:
    vars:
      target: <target>
```

## Required parameters

No parameter has to be set.

## Left out

`Job/postgresql-cluster-ping-test`
