# umami

Umami 3.4.1, web analytics without cookies, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from its Docker Compose file. The database is
the included recipe `postgresql`.

<!-- renovate: tag=v3.4.1 -->
Source: `https://github.com/umami-software/umami/blob/559e3c607c23d2c72d9bd4f6481bda428255323c/docker-compose.yml@sha256:fb542a641c14fc2b1ff0d59558a197ed4f607b6608bf812afd20dad662ae0e8c`

Level: `deploys`

Umami publishes no Helm chart. The commit is the tag `v3.4.1`, and the
image's build provenance names it. Umami is MIT. The image is an index for
linux/amd64 and linux/arm64. `postgresql` requires `cnpg`, so install
`cnpg` first, in a target of its own. Umami runs as the image's user
`nextjs`, UID 1001, and passes the Pod Security level `restricted`.

## Include

```yaml
classes:
  - recipes.umami
parameters:
  namespace: umami
  kapitan:
    vars:
      target: umami
  applications:
    umami:
      app_secret: <ref>
      two_factor_encryption_key: <ref>
```

Fetch `postgresql` at the same commit as this recipe, with a `git`
dependency of its own with `subdir: postgresql` and
`output_path: inventory/classes/recipes/postgresql`.

## Required parameters

`applications.umami.app_secret` is `APP_SECRET`, which signs Umami's login
sessions and the tokens it returns to the tracker. A new value logs every
user out. `applications.umami.two_factor_encryption_key` is
`TWO_FACTOR_ENCRYPTION_KEY`, 64 hexadecimal digits such as the output of
`openssl rand -hex 32`. It encrypts the secrets of two-factor
authentication, so keep it once a user has enabled that. Umami offers no
two-factor authentication with any other value. Set both as refs with the
backend of your choice. Without one of them the compile stops with
`Interpolation key '<key>' not found`.

## The admin account

Umami's first database migration creates the user `admin` with the
password `umami`, as the compose file does. The recipe changes neither
(DEC-124 in [docs/specs/recipes.md](../docs/specs/recipes.md)). Change the
password before the target exposes the Service: log in and use the page
`/settings/profile` of the web UI, or log in through the API and send the
new password with the login's token, as here from a pod in the namespace.

```sh
token=$(curl -fsS -H 'Content-Type: application/json' \
  --data '{"username": "admin", "password": "umami"}' \
  http://umami:3000/api/auth/login | jq -r .token)
curl -fsS -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  --data '{"currentPassword": "umami", "newPassword": "<new password>"}' \
  http://umami:3000/api/me/password
```

The new password needs at least 8 characters. The change ends every
session that was signed in before it.

## Settings

| Setting | Inventory |
|---|---|
| Umami version | `components.umami.image`, tag and digest |
| Umami's other environment variables, such as `COLLECT_API_ENDPOINT` or `SALT_ROTATION` | `components.umami.env.<variable>` |
| exposure | a route or Ingress of the target to the Service `umami` on port 3000 |
| resources | `components.umami.resources` |
| the Cluster, its database and its size | `applications.postgresql`, which `postgresql`'s README lists |

The Service `umami` is a ClusterIP Service on port 3000. The compose file
publishes that port on the host. Here an Ingress or Gateway in the target
exposes it. Visitors' browsers load the tracker `/script.js` and send to
`/api/send` on the same address as the web UI.

## Mapping

The service `umami` becomes the component `umami`. `db` becomes the
included recipe `postgresql`, and Umami reaches it through the Service
`postgresql-cluster-rw` in place of `db`.

| Compose | Recipe |
|---|---|
| service `umami` | Deployment `umami`, Service `umami` on port 3000, Secret `umami` with `APP_SECRET` and `TWO_FACTOR_ENCRYPTION_KEY` |
| `ghcr.io/umami-software/umami:latest` | `ghcr.io/umami-software/umami:3.4.1@sha256:e69d1a7932e9dab0fc523edc7be1f3a53f3c261f57856fc2167ae74a8fc022e8`, which `latest` was at migration |
| service `db`, `postgres:15-alpine` with the database, user and password `umami` and the volume `umami-db-data` | the included recipe `postgresql`, PostgreSQL 18.6 on CloudNativePG, with the database and user `app` |
| `DATABASE_URL: postgresql://umami:umami@db:5432/umami` | the key `uri` of the Secret `postgresql-cluster-app`, with the generated password and without TLS, as in the compose file (DEC-125) |
| `APP_SECRET` and `TWO_FACTOR_ENCRYPTION_KEY`, placeholders | `applications.umami.app_secret` and `.two_factor_encryption_key` in the Secret `umami` |
| port `3000:3000` | Service port 3000, `ClusterIP` |
| healthcheck `curl http://localhost:3000/api/heartbeat` every 5s, timeout 5s, 5 retries | readiness probe with the same values |
| `depends_on` `db` with `condition: service_healthy` | the init container `wait-for-database` of Umami's image, which waits until the Service `postgresql-cluster-rw` accepts connections, because Umami's start script exits while the database does not answer (DEC-121) |
| `init: true` | not rendered. The server runs as PID 1 and ends on `SIGTERM` (DEC-120). |
| `restart: always` | not rendered |
| not in the compose file | UID 1001 and GID 65533 under `restricted` (DEC-122) |

## Proof

`check umami --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests, with check 0.15.0 and `cnpg` installed first.
The objects of `postgresql` are applied with the recipe. A compose file has
no Kubernetes objects to compare with, so the recipe is proven by
deploying it (RCP-38). `tests/target.yml` sets low-entropy test values for
both parameters and runs one PostgreSQL instance.

`tests/smoke` requires that the pods pass Pod Security `restricted` and
that Umami did not restart while the Cluster started. It then starts a pod
of Umami's image, which carries `curl`. From there, through the Service
`umami` on port 3000, it

- gets `{"ok":true}` from `/api/heartbeat`
- gets 401 for a wrong password and logs in as `admin` with `umami`
- requires `isConfigured` from `/api/2fa/status`, so the key reached Umami
- creates a website and sends a page view to `/api/send` as the tracker
  script does, with a browser's `User-Agent`, since Umami drops requests
  from bots such as curl
- requires one page view from `/api/websites/<id>/stats`, which Umami reads
  from PostgreSQL
- changes the password as above and logs in with the new one
- restarts the Deployment and reads the page view again with the session
  of that login, which the new pod accepts only with the same
  `APP_SECRET`, and gets 401 for `umami`.

Not tested: the tracker script in a browser, the web UI, two-factor
authentication itself, and a route or Ingress in front of the Service.
