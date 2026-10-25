# nextcloud

Nextcloud 35.0.2 as one replica with its background jobs and an HTTPRoute
to a Gateway the cluster already runs, rendered by the kadet-hub
`kubernetes` generator 1.9.0 from Nextcloud's Helm chart 9.4.1. The
database is the included recipe `postgresql`, the cache and file locking
the included recipe `valkey`.

Source: `oci://ghcr.io/nextcloud/helm/nextcloud:9.4.1@sha256:90ffc4c8dd014e25343ecd37de7262f04d1c2cacb47a48315316d7798e7b35cb`

Level: `deploys`

Requires: `gateway-api`

The chart comes from [nextcloud/helm](https://github.com/nextcloud/helm),
tag `nextcloud-9.4.1`, and runs the Docker official image
`nextcloud:35.0.2-apache`. Its OCI package has the SHA-256 of the GitHub
release asset `nextcloud-9.4.1.tgz`,
`e3d768864800bcc23eb66e6f65cbf5f0545b1506cf8c65f55a91d21af3bad4bf`. The
chart is AGPL-3.0, and the recipe copies no text from its templates.

`postgresql` requires `cnpg`, so install `cnpg` first, in a target of its
own. Apache starts as root and serves as `www-data`, UID 33, so the
target's namespace needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.nextcloud
parameters:
  namespace: nextcloud
  kapitan:
    vars:
      target: nextcloud
  applications:
    nextcloud:
      host: <host>
      admin:
        password: <ref>
      gateway:
        name: <gateway>
        namespace: <gateway namespace>
    valkey:
      password: <ref>
```

Fetch `postgresql` and `valkey` at the same commit as this recipe, each
with a `git` dependency of its own with `subdir: <recipe>` and
`output_path: inventory/classes/recipes/<recipe>`.

## Required parameters

`applications.nextcloud.host` is the host name of the route and Nextcloud's
trusted domain. `applications.nextcloud.gateway.name` and
`applications.nextcloud.gateway.namespace` name the Gateway the route
attaches to, whose listener must admit routes from the target's namespace.
`applications.nextcloud.admin.password`, the admin account's password, and
`applications.valkey.password`, which the included recipe `valkey`
requires, are refs with the backend of your choice. Without one of them the
compile stops with `Interpolation key '<key>' not found`.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `applications.nextcloud.version`, together with the digest in `components.nextcloud.image` |
| `nextcloud.host`, `nextcloud.trustedDomains`, `httpRoute.hostnames` | `applications.nextcloud.host` |
| `nextcloud.username` | `applications.nextcloud.admin.username`, `admin` by default |
| `nextcloud.password` | `applications.nextcloud.admin.password` |
| `httpRoute.parentRefs` | `applications.nextcloud.gateway.name` and `.namespace`, and `.section` for the listener's `sectionName`, unset by default |
| `persistence.size`, `persistence.storageClass` | `components.nextcloud.persistent_volume_claims.nextcloud-nextcloud.storage`, `.storage_class` |
| `persistence.nextcloudData.size`, `persistence.nextcloudData.storageClass` | `components.nextcloud.persistent_volume_claims.nextcloud-nextcloud-data.storage`, `.storage_class` |
| `nextcloud.extraEnv` | `components.nextcloud.env`, which the cron sidecar gets too |
| `resources` | `components.nextcloud.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `components.nextcloud.node_selector`, `components.nextcloud.tolerations`, `components.nextcloud.affinity` |

The database, its owner and the Cluster's name are settings of
`postgresql`, which its README lists. Nextcloud reads the host, database
and credentials from the Secret `<cluster>-app`, where `<cluster>` is
`applications.postgresql.cluster`.

The image writes the host into `config.php` when it installs Nextcloud. A
later change of `applications.nextcloud.host` also needs
`occ config:system:set trusted_domains`.

Set `TRUSTED_PROXIES` in `components.nextcloud.env` to the addresses of
the Gateway implementation's proxies. It has no default, and without it
Nextcloud takes the proxy's address for the client's.

The image accepts PHP uploads up to `PHP_UPLOAD_LIMIT`, 512M by default,
set in `components.nextcloud.env`. Gateway API has no request body limit
of its own, so the Gateway implementation must allow bodies of that size
in its own policy.

The chart's liveness probe restarts a container that is still installing,
and the image installs only on its first start. The recipe therefore runs
the chart's startup probe, which waits up to 330 seconds.

SMTP, notify_push, an office server, imaginary, metrics, backups and more
than one replica are not part of this version.

## Proof

`check nextcloud --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind `kindest/node:v1.37.0`, with `cnpg` and
`gateway-api` installed first. The objects of `postgresql` and `valkey` are
left out of the comparison and applied with the recipe. The Deployment and
the Service select on `name`, the chart on `app.kubernetes.io/name`,
`instance` and `component`. `tests/target.yml` runs one PostgreSQL
instance.

`tests/smoke` waits for the Cluster and reads `status.php` through the
Gateway of `check`, with the route's host name, until it reports
`"installed":true`. It then writes a file over WebDAV as the admin and
reads it back, and checks that `occ` names Redis as the file locking
backend. The redirects from `/.well-known/carddav` and
`/.well-known/caldav` to `/remote.php/dav` are compared at `renders` only,
because cloud-provider-kind drops the path of a redirect.
