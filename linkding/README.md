# linkding

linkding 1.47.0, a bookmark manager with a web UI and a REST API, with its
SQLite database on a claim and its first superuser from the inventory,
rendered by the kadet-hub `kubernetes` generator 1.16.0 from its Docker
Compose file.

<!-- renovate: tag=v1.47.0 -->
Source: `https://github.com/sissbruecker/linkding/blob/24b5ad6cc9bde497b5d1b1e86aed5a2fb7d25c2f/docker-compose.yml@sha256:d8f0b8b359100e6721dbdf240cf8fb62afc37bd9c737eaa35fc18c0f58d2785f`

Level: `deploys`

linkding publishes no Helm chart. The commit is the tag `v1.47.0` of the
release whose image is `1.47.0`. linkding is MIT. The image is an index
for linux/amd64, linux/arm64 and linux/arm/v7, which `latest` pointed to on
2026-11-12. linkding runs as UID 33, `www-data`, and passes the Pod
Security level `restricted`. The settings follow the
[installation](https://linkding.link/installation/) and
[options](https://linkding.link/options/) pages, which are
`docs/src/content/docs/` of sissbruecker/linkding at v1.47.0.

## Include

```yaml
classes:
  - recipes.linkding
parameters:
  namespace: linkding
  kapitan:
    vars:
      target: linkding
  applications:
    linkding:
      superuser_name: admin
      superuser_password: <ref>
```

## Required parameters

`applications.linkding.superuser_name` and
`applications.linkding.superuser_password` are `LD_SUPERUSER_NAME` and
`LD_SUPERUSER_PASSWORD`. linkding creates this superuser at a start when
no user of that name exists (DEC-341 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). Set the password as a
ref.

linkding reads the password only when it creates the user, so a changed
parameter does not change the password of an existing superuser. Change
it in the admin app at `/admin` or with `python manage.py changepassword`
in the pod. A changed name creates a second superuser.

Without either parameter the compile stops with `Interpolation key` and
its name.

## Access

linkding has no sign-up. The superuser logs in to the web UI and adds
further users in the admin app at `/admin`, as linkding's
[admin page](https://linkding.link/admin/) describes. The REST API answers
a request without a session or an API token with 401, and the web UI
redirects it to the login. Each user finds the API tokens in the settings.

Behind a route or Ingress, linkding's installation page names
`LD_CSRF_TRUSTED_ORIGINS` for logins that fail with
`CSRF verification failed`. Set it to the URL that browsers use.

## Settings

| Setting | Inventory |
|---|---|
| linkding version | `components.linkding.image`, tag and digest |
| linkding's options, such as `LD_CSRF_TRUSTED_ORIGINS` or `LD_DISABLE_URL_VALIDATION` | `components.linkding.env.<variable>`, credentials through `components.linkding.secrets` with a ref |
| size of the claim `data`, `1Gi` | `components.linkding.volume_claims.data.spec.resources.requests.storage` |
| exposure | a route or Ingress of the target to the Service `linkding` on port 9090 |
| resources | `components.linkding.resources` |

The claim `data` is mounted at `/etc/linkding/data`. It holds the SQLite
database `db.sqlite3`, the key `secretkey.txt` with which Django signs
sessions, and the folders of favicons, preview images and uploaded assets.
SQLite allows one replica. linkding's
[backups page](https://linkding.link/backups/) describes
`python manage.py full_backup`, which runs in the pod as well.

The background tasks are off: `LD_DISABLE_BACKGROUND_TASKS` is `True`
(DEC-340 in the spec). The image starts its task processor through
supervisord, which refuses to start as a user other than root. Favicons,
preview images, snapshots on the Internet Archive and the refresh of
titles and descriptions therefore do nothing, even when a user turns them
on in the settings. The REST API still reads the title and description of
a page when it creates a bookmark without them.

## Mapping

The service `linkding` becomes the component `linkding`. Its name stays,
so no reference is rewritten.

| Compose | Recipe |
|---|---|
| service `linkding` | StatefulSet `linkding`, Service `linkding`, Secret `linkding` with `LD_SUPERUSER_PASSWORD` |
| `sissbruecker/linkding:latest` | `docker.io/sissbruecker/linkding:1.47.0@sha256:e35cb50e0581178f245125ffaa909c565416c94c9f22ace305a7d234a4345522`, which `latest` was at migration |
| port `${LD_HOST_PORT:-9090}:9090` | Service port `http` on 9090, `ClusterIP` |
| bind mount `${LD_HOST_DATA_DIR:-./data}` at `/etc/linkding/data` | claim template `data`, `ReadWriteOnce`, `1Gi` |
| `env_file: .env`, which the documentation copies from `.env.sample` | `env` with each line of `.env.sample` but the ones below |
| `LD_SUPERUSER_NAME=` and `LD_SUPERUSER_PASSWORD=` | the required parameters, the password through the Secret `linkding` (DEC-341) |
| `LD_DISABLE_BACKGROUND_TASKS=False` | `True` (DEC-340) |
| `LD_DB_PASSWORD=` | not rendered, linkding reads it only for PostgreSQL |
| the image's `HEALTHCHECK`, `curl -f` on `/health` | readiness probe with the same `sh -c` command every 30 seconds with a timeout of 1 second and 3 failures |
| `container_name`, `restart: unless-stopped` | not rendered |
| no `user`, so the image's root | UID, GID and `fsGroup` 33 under `restricted` (DEC-339) |

`.env.sample` has the SHA-256
`12a0e13fc1b005ea484b96c666813d1a601de5ad85c9db82262b67950dcb10bf`.

## Proof

`check linkding --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests. A compose file has no Kubernetes objects to
compare with, so the recipe is proven by deploying it (RCP-38).

`tests/smoke` checks that the pod passes Pod Security `restricted` and
starts a pod of linkding's image, which carries `curl`. From there,
through the cluster IP of the Service `linkding` on port 9090, it

- gets `/health`
- gets 401 from `/api/bookmarks/` without credentials, and again after a
  login with a wrong password
- logs in through the login form as the superuser of `tests/target.yml`,
  creates a bookmark through the REST API with `disable_scraping`, so
  linkding loads nothing from its URL, and lists it
- deletes the pod `linkding-0` and, once its successor is ready, lists the
  bookmark again in the session from before the restart.

## Not proven

PostgreSQL in place of SQLite. The web UI in a browser, the browser
extension and API tokens. A route or Ingress in front of the Service, and
`LD_CSRF_TRUSTED_ORIGINS`. The background tasks, which need root. An
authentication proxy or OIDC.
