# cnpg

The CloudNativePG operator 1.30.1 with its webhooks and RBAC, and optionally
its CRDs, rendered by the kadet-hub `kubernetes` generator 1.8.0 from the
project's Helm chart `cloudnative-pg` 0.29.1.

Source: `oci://ghcr.io/cloudnative-pg/charts/cloudnative-pg:0.29.1@sha256:3245fa051bb21d0dd9246272f57a2760b4234817a164a3167d2a1e7fb9f63fd9`

Level: `deploys`

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

## Required parameters

No parameter has to be set.
