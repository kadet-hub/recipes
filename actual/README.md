# actual

Actual Budget's sync server, a personal finance app with its web UI, with
its data on a claim, rendered by the kadet-hub `kubernetes` generator 1.14.0
from the Docker Compose file of Actual 26.11.0.

<!-- renovate: tag=v26.11.0 -->
Source: `https://github.com/actualbudget/actual/blob/1766241e3f4b3c578e424c4fa15f1eb83c0da17d/packages/sync-server/docker-compose.yml@sha256:bdf050bf6247938005c871b20d2c27647e09843a21631ef5ca430dfc4e5982a6`

Level: `deploys`

Actual publishes no Helm chart. The commit is the tag `v26.11.0`, the
release the image `26.11.0` belongs to. Actual is MIT. The image is an
index for linux/amd64 and linux/arm64. It runs as root, so the target's
namespace needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.actual
parameters:
  namespace: actual
  kapitan:
    vars:
      target: actual
```

## Required parameters

No parameter has to be set.

Actual takes its server password on the first visit of the web UI, through
`/account/bootstrap`, which needs no login (DEC-220 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). Until then anyone who
reaches the Service can set it. Set it before the target exposes the
Service, for example through
`kubectl port-forward -n actual service/actual 5006` and
`http://localhost:5006`.

## Settings

| Setting | Inventory |
|---|---|
| Actual version | `components.actual.image`, tag and digest |
| settings of Actual's configuration page, such as `ACTUAL_UPLOAD_FILE_SYNC_SIZE_LIMIT_MB` | `components.actual.env.<variable>` |
| exposure | `components.actual.service.type`, or a route or Ingress of the target to the Service `actual` on port 5006 |
| size of the claim `actual-data`, `1Gi` | `components.actual.volume_claims.actual-data.spec.resources.requests.storage` |
| resources | `components.actual.resources` |

Actual keeps its state in `/data` on the claim. `server-files/account.sqlite`
holds the password hash, the sessions and the list of budget files, and
`user-files` holds the budget files and their sync messages. SQLite allows
one replica.

The Service `actual` serves plain HTTP on port 5006, the port the compose
file publishes. Actual's documentation asks for HTTPS for all of its
features, unless the browser reaches it on `localhost` as above, so expose
it through a route or Ingress that terminates TLS.

## Mapping

The service `actual_server` becomes the component `actual`. No environment
value, command or config names the service, so nothing is rewritten.

| Compose | Recipe |
|---|---|
| service `actual_server` | StatefulSet `actual`, Service `actual` |
| `docker.io/actualbudget/actual-server:latest` | `docker.io/actualbudget/actual-server:26.11.0@sha256:06cf186569cf58d93e12659ff1a517b65b5b0ebee7050a3991d4bd8a1d398da6`, which `latest` was at migration |
| port `5006:5006` | Service port `http` on 5006 to the container's port 5006, `ClusterIP` |
| `environment` without an entry | not rendered |
| bind mount `./actual-data` at `/data` | claim template `actual-data`, `ReadWriteOnce`, `1Gi` |
| `healthcheck`, `node scripts/health-check.js` | readiness probe `sh -c 'node scripts/health-check.js'` every 60 seconds with a timeout of 10 seconds and 3 failures |
| `restart: unless-stopped` | not rendered |

Every line of the file's `environment` is a comment, and the file asks to
remove the key when no option is set. Docker Compose 5.6.1 refuses the file
as it is, with `services.actual_server.environment must be a mapping`.

## Proof

`check actual --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests, with check 0.16.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38).

`tests/smoke` starts a pod of Actual's image, which carries `node`. From
there, through the Service `actual` on port 5006, it

- requires `UP` from `/health` and the version of the image tag from `/info`
- gets 401 from `/sync/list-user-files` without a login
- sets the password through `/account/bootstrap`, and gets
  `already-bootstrapped` from a second call and `invalid-password` from a
  login with another password
- logs in, uploads a budget file through `/sync/upload-user-file`, and
  finds it in `/sync/list-user-files` and unchanged from
  `/sync/download-user-file`
- deletes the pod `actual-0` and, once the new pod is ready, logs in with
  the same password and downloads the same file, which needs both on the
  claim.

The uploaded file is a fixed byte string. The server stores an upload as it
is and reads it only when a client downloads it, so the test needs no
budget that the web UI built.

Not tested: the web UI in a browser, synchronization of budget changes
through `/sync/sync`, bank synchronization, OpenID and HTTPS.
