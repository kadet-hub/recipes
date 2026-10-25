# nextcloud

Nextcloud 35.0.2 with PostgreSQL and Valkey, exposed through a Gateway API
HTTPRoute, rendered by the kadet-hub `kubernetes` generator from Nextcloud's
Helm chart 9.4.1.

Source: `oci://ghcr.io/nextcloud/helm/nextcloud:9.4.1@sha256:90ffc4c8dd014e25343ecd37de7262f04d1c2cacb47a48315316d7798e7b35cb`

Level: `deploys`

Requires: `gateway-api`

## Include

```yaml
classes:
  - recipes.nextcloud
```

## Required parameters

tbd
