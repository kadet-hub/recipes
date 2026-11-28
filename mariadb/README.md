# mariadb

MariaDB Server as a single instance with one database and its user,
designed in kadet-hub on the MariaDB Foundation's image and rendered by the
kadet-hub `kubernetes` generator 1.16.0.

Source: `docker.io/library/mariadb:12.3.3@sha256:d46e102fa8b9b72bfcdeb56f9dd538742092119dc8b11f31fe662605cd234cd9`

Level: `deploys`

The MariaDB Foundation publishes no chart, Kustomize base or compose file
for a single server. It maintains the Docker Official Image `mariadb` in
[MariaDB/mariadb-docker](https://github.com/MariaDB/mariadb-docker), and
docker-library builds the image from there, so the recipe is designed on
that image (DEC-11 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
The compose files in that repository's `examples` run a debug build,
replication or a migration from MySQL. The image's documentation is its
[Docker Hub page](https://hub.docker.com/_/mariadb). MariaDB Server is
GPL-2.0. The recipe follows the 12.3 LTS release line, which the Foundation
supports until 2029-06-12. The digest is that of the index for
linux/amd64, linux/arm64/v8, linux/ppc64le and linux/s390x.

The recipe can stand in for Bitnami's `mariadb` chart in its default
`standalone` architecture. Moving a release of that chart to the recipe is
not tested.

## Include

```yaml
classes:
  - recipes.mariadb
parameters:
  namespace: mariadb
  kapitan:
    vars:
      target: mariadb
  applications:
    mariadb:
      password: <ref>
      root_password: <ref>
```

## Required parameters

`applications.mariadb.password`, the password of the user `app`, and
`applications.mariadb.root_password` must be set, as refs with the backend
of your choice. Without them the compile stops with
`Interpolation key 'applications.mariadb.password' not found`.

## Settings

| Setting | Inventory |
|---|---|
| MariaDB version | `components.mariadb.image`, tag and digest |
| database and its user, `app` | `applications.mariadb.database`, `applications.mariadb.user` |
| volume size, 8Gi | `components.mariadb.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.mariadb.resources` |
| server options, such as `--require-secure-transport=ON` | `components.mariadb.args` as a mapping, each value one option |

MariaDB reads the database, the user and both passwords only when it
initializes an empty data directory. Changing them later changes the
Secret, not the database. The root user may log in from any host, the
image's default.

The pod runs as the image's user `mysql`, UID 999, and passes Pod Security
`restricted`. The data lives in the subdirectory `mariadb` of the volume,
because MariaDB lists a `lost+found` at the volume's root as a database.

The readiness probe runs the image's `healthcheck.sh --connect
--innodb_initialized` every 10 seconds, the check of the
[image's documentation](https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/using-healthcheck-sh).
There is no liveness probe. MariaDB opens its port only after InnoDB's
crash recovery, and a liveness probe would restart a recovery that takes
longer than its threshold.

MariaDB serves TLS on port 3306 with a self-signed certificate that it
generates, because no certificate is configured. Clients from 11.4
on verify that certificate by default through the password of a
`mysql_native_password` or `ed25519` account, such as `app`
([Zero-Configuration SSL](https://mariadb.com/docs/server/security/encryption/data-in-transit-encryption/zero-configuration-ssl)).
The server also accepts clients without TLS. `--require-secure-transport=ON`
refuses them.

## Proof

`check mariadb --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke`
connects as the user `app` to its database `app` through the Service
`mariadb` on port 3306, with TLS and the server's certificate verified. It
creates a table, writes a row and reads it back, and requires the server
version of the image's tag. It checks that the pod passes Pod Security
`restricted`, deletes the pod `mariadb-0` and reads the row again through
the Service once the new pod is ready.
