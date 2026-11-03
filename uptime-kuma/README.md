# uptime-kuma

Uptime Kuma, a self-hosted monitoring tool with status pages, with its data
in SQLite on a claim, rendered by the kadet-hub `kubernetes` generator 1.14.0
from the Docker Compose file of Uptime Kuma 2.5.9.

Source: `https://github.com/louislam/uptime-kuma/blob/df601c58d9205562f34cfe5ef35264b341019d19/compose.yaml@sha256:f62a065cabc4671225ec4e58575dd9cca364b0d0b5087b57451278791672a54b`

Level: `deploys`

Uptime Kuma publishes no Helm chart. The commit is the tag `2.5.9`. Uptime
Kuma is MIT. The image is an index for linux/amd64,
linux/arm64 and linux/arm/v7. It runs as root, so the target's namespace
needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.uptime-kuma
parameters:
  namespace: uptime-kuma
  kapitan:
    vars:
      target: uptime-kuma
```

## Required parameters

No parameter has to be set.

Uptime Kuma creates its admin account in the web UI on the first visit,
without a login (DEC-66 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). Until then anyone who
reaches the Service can claim the instance, so create the account before
the target exposes it.

## Settings

| Setting | Inventory |
|---|---|
| Uptime Kuma version | `components.uptime-kuma.image`, tag and digest |
| database type, `sqlite` | `components.uptime-kuma.env.UPTIME_KUMA_DB_TYPE` |
| other environment variables of Uptime Kuma, such as `UPTIME_KUMA_WS_ORIGIN_CHECK` | `components.uptime-kuma.env.<variable>` |
| exposure | `components.uptime-kuma.service.type`, or a route or Ingress of the target to the Service `uptime-kuma` on port 3001 |
| size of the claim `data`, `1Gi` | `components.uptime-kuma.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.uptime-kuma.resources` |

Uptime Kuma keeps its state in `/app/data` on the claim: the SQLite
database `kuma.db`, `db-config.json`, which it writes from
`UPTIME_KUMA_DB_TYPE` at every start, and uploaded files. SQLite allows one
replica.

The Service `uptime-kuma` serves plain HTTP on port 3001, the port the
compose file publishes. The web UI talks to the server over socket.io,
which upgrades to a WebSocket on the same port. A route or Ingress in front
of it must pass the WebSocket upgrade and keep the `Host` header, because
Uptime Kuma refuses a WebSocket whose `Origin` names another host.

A logged-in user's monitors reach whatever the pod reaches, a cloud's
metadata endpoint among them. Upstream leaves that to the platform
(GHSA-qjxc-h5jf-c7rj), so restrict the pod's egress where it matters.

## Mapping

The service `uptime-kuma` becomes the component `uptime-kuma`. Its name
stays, so no reference is rewritten.

| Compose | Recipe |
|---|---|
| service `uptime-kuma` | StatefulSet `uptime-kuma`, Service `uptime-kuma` |
| `louislam/uptime-kuma:2` | `docker.io/louislam/uptime-kuma:2.5.9@sha256:e88415a90dd2f7efecdbc18de0490aff292764a3ac471531bf1d0481725591bd`, which `2` was at migration |
| port `3001:3001` | Service port `http` on 3001 to the container's port 3001, `ClusterIP` |
| bind mount `./data` at `/app/data` | claim template `data`, `ReadWriteOnce`, `1Gi` |
| the image's `HEALTHCHECK`, `extra/healthcheck` | readiness probe `sh -c extra/healthcheck` every 60 seconds with a timeout of 30 seconds and 5 failures |
| `restart: unless-stopped` | not rendered |
| not in the compose file | `UPTIME_KUMA_DB_TYPE: sqlite` (DEC-65) |

## Proof

`check uptime-kuma --level deploys` with `tests/target.yml`, on kind for
each Kubernetes minor CI tests, with check 0.14.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38).

`tests/smoke` starts a pod of Uptime Kuma's image, which carries `curl`,
`node` and the socket.io client. From there, through the Service
`uptime-kuma` on port 3001, it

- requires `entryPage` from `/api/entry-page`, so the database setup page
  did not start, and the web UI from `/`
- gets 401 from `/metrics` without a login
- creates the admin account with the socket.io event `setup`, logs in, adds
  an HTTP monitor against CoreDNS' metrics on `kube-dns.kube-system:9153`
  and waits for a heartbeat UP
- requires the monitor UP from `/metrics` with the admin account
- deletes the pod `uptime-kuma-0` and, once the new pod is ready, logs in
  again, finds the monitor and waits for a new heartbeat UP, which needs
  `kuma.db` on the claim.

Not tested: the web UI in a browser, notifications, status pages, and a
route or Ingress in front of the Service.
