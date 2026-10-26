# miniflux

Miniflux, a minimalist feed reader, and its PostgreSQL database, rendered by
the kadet-hub `kubernetes` generator 1.9.0 from the Docker Compose file of
Miniflux 2.3.4.

Source: `https://github.com/miniflux/v2/blob/238c5614e584ebc87894e7d9f10bc91373a0b2c2/contrib/docker-compose/basic.yml@sha256:2fc122f1b1c9cc550e0ae0b1d442a445d9a408909d0fcfdf55abb647c3856120`

Level: `deploys`

## Include

```yaml
classes:
  - recipes.miniflux
parameters:
  namespace: miniflux
  kapitan:
    vars:
      target: miniflux
  applications:
    miniflux:
      database:
        password: <ref>
      admin:
        password: <ref>
```

## Required parameters

`applications.miniflux.database.password` and
`applications.miniflux.admin.password` must be set, as refs with the
backend of your choice.
Without them the compile stops with
`Interpolation key 'applications.miniflux.database.password' not found`.
The database password is written into `DATABASE_URL` as it is, so it must
not contain characters a URL reserves, such as `@`, `/`, `:` or `?`.

## Settings

| Compose | Inventory |
|---|---|
| `miniflux/miniflux` image tag | `applications.miniflux.version`, together with the digest in `components.miniflux.image` |
| `POSTGRES_USER`, `POSTGRES_DB` and the same names in `DATABASE_URL` | `applications.miniflux.database.user`, `applications.miniflux.database.name` |
| `POSTGRES_PASSWORD` and the password in `DATABASE_URL` | `applications.miniflux.database.password` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | `applications.miniflux.admin.username`, `applications.miniflux.admin.password` |
| `DEBUG`, `RUN_MIGRATIONS`, `CREATE_ADMIN` | `components.miniflux.env.<variable>` |
| published port `80` | `components.miniflux.ports.http.service_port` |
| size of the volume `miniflux-db` | `components.miniflux-db.volume_claims.miniflux-db.spec.resources.requests.storage`, default `1Gi` |

The Service `miniflux` is a ClusterIP Service on port 80. The compose file
publishes that port on the host. Here an Ingress or Gateway in the target
exposes it.

## Mapping

The service `db` is renamed to `miniflux-db`, also as the host in
`DATABASE_URL`.

| Compose | Recipe |
|---|---|
| service `miniflux` | Deployment `miniflux`, Service `miniflux` from port 80 to 8080, Secret `miniflux` with `DATABASE_URL` and `ADMIN_PASSWORD` |
| service `db` | StatefulSet `miniflux-db`, Service `miniflux-db` on port 5432, Secret `miniflux-db` with `POSTGRES_PASSWORD` |
| `${MINIFLUX_IMAGE:-miniflux/miniflux:latest}` | `miniflux/miniflux:2.3.4@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e`, which `latest` was at migration |
| `postgres:latest` | `postgres:18.6@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6`, which `latest` was at migration |
| `healthcheck` of `db` | readiness probe `pg_isready -U miniflux` every 10s with the compose default timeout of 30s. `start_period` is dropped. |
| port 5432 of `db` | declared, because miniflux connects to it. Compose needs no declaration for that. |
| volume `miniflux-db` at `/var/lib/postgresql` | volume claim template `miniflux-db`, `ReadWriteOnce`, `1Gi` |
| `depends_on` with `condition: service_healthy` | not rendered. miniflux restarts until the Service `miniflux-db` has a ready endpoint. |
| `restart: always`, `container_name` | not rendered. Pods restart with `restartPolicy: Always` and are named by their workload. |

The commented-out healthcheck of `miniflux` is not part of the file's
configuration and is not migrated.

## Proof

`check miniflux --level deploys` with `tests/target.yml`, which sets the
passwords of the compose file, on kind `kindest/node:v1.37.0`. A compose
file has no Kubernetes objects to compare with, so the recipe is proven by
deploying it (RCP-38). `tests/smoke` runs `pg_isready` in the database pod,
expects `OK` from `/healthcheck` on the Service's port 80, and creates a
category through the API with the admin account and reads it back.
