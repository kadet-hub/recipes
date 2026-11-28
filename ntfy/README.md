# ntfy

ntfy 2.37.2, a server that sends push notifications to phones, browsers
and scripts subscribed to a topic, as a private instance with its message
cache, users and attachments on a claim, designed in kadet-hub on ntfy's
image and rendered by the kadet-hub `kubernetes` generator 1.16.0.

Source: `docker.io/binwiederhier/ntfy:v2.37.2@sha256:1875ddcf815c8a3c981d6d78c67a93452d0abba79b1ab9520b1f5f5238902bd7`

Level: `deploys`

ntfy publishes no Helm chart or Kustomize base. Its compose file and the
compose examples of its documentation bind-mount host paths on which
Compose sources stop, so the recipe is designed on the image (DEC-335 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The settings follow
the example "Docker Compose (w/ auth, cache, attachments)" of the
[configuration page](https://docs.ntfy.sh/config/), and the workload the
stateful set of the
[Kubernetes installation](https://docs.ntfy.sh/install/#kubernetes), both
in `docs/` of binwiederhier/ntfy at v2.37.2. ntfy is dual-licensed under
Apache-2.0 and GPL-2.0. The digest is that of the index for linux/amd64,
linux/arm64, linux/arm/v6 and linux/arm/v7, which `latest` pointed to on
2026-11-12.

The recipe renders the StatefulSet `ntfy` with one replica, the Service
`ntfy` on port 80, the Secret `ntfy` with the users and the claim `data`.
The pod runs as UID and GID 1000 and passes Pod Security `restricted`.

## Include

```yaml
classes:
  - recipes.ntfy
parameters:
  namespace: ntfy
  kapitan:
    vars:
      target: ntfy
  applications:
    ntfy:
      base_url: https://ntfy.example.com
      auth_users: <ref>
```

## Required parameters

`applications.ntfy.base_url` is `NTFY_BASE_URL`, the URL that phones and
browsers reach ntfy at, such as `https://ntfy.example.com` behind an
Ingress (DEC-338 in the spec). ntfy builds the links of attachments from
it, and refuses to start with a path in the URL.

`applications.ntfy.auth_users` is `NTFY_AUTH_USERS`, the users of the
private instance as `<name>:<bcrypt hash>:<role>`, several separated by
commas, with the role `admin` or `user` (DEC-337). Set it as a ref.
`ntfy user hash` of the image asks for a password and prints its hash.

Without either parameter the compile stops with `Interpolation key` and
its name.

## Access

ntfy runs as a private instance, as the configuration page's example sets
it up. `NTFY_AUTH_DEFAULT_ACCESS` is `deny-all`, so a request without the
credentials of a user gets 403 and one with a wrong password 401. An admin
reads and writes every topic. A user with the role `user` needs access
entries, which `NTFY_AUTH_ACCESS` provisions in the same way, such as
`backup-script:backups:rw`. Clients log in with HTTP Basic auth, and the
web app logs in because `NTFY_ENABLE_LOGIN` is `true`. Sign-up stays off.

ntfy creates or updates the users of `auth_users` at every start, and
deletes a user that the parameter listed before and no longer lists. Users
created with `ntfy user add` in the pod stay until the parameter lists them
once and drops them again.

An attachment is served to anyone who has its URL, also under `deny-all`.
With the pinned image a request without credentials got the file from
`/file/<id>`.

For ntfy's default, an open instance on which anyone who reaches it reads
and writes every topic, set `NTFY_AUTH_DEFAULT_ACCESS` to `read-write`.

## Settings

| Setting | Inventory |
|---|---|
| ntfy version | `components.ntfy.image`, tag and digest |
| access entries, tokens and other settings, such as `NTFY_AUTH_ACCESS` or `NTFY_CACHE_DURATION` | `components.ntfy.env.<variable>`, credentials through `components.ntfy.secrets` with a ref |
| size of the claim `data`, `1Gi` | `components.ntfy.volume_claims.data.spec.resources.requests.storage` |
| exposure | a route or Ingress of the target to the Service `ntfy` on port 80 |
| resources | `components.ntfy.resources` |

The claim `data` is mounted at `/var/lib/ntfy`. It holds the message cache
`cache.db`, the user database `auth.db` and the directory `attachments`.
ntfy keeps messages for 12 hours and attachments for 3 hours by default.
SQLite allows one replica.

`NTFY_BEHIND_PROXY` is `true`, so ntfy counts each visitor by the last
address in `X-Forwarded-For`, which an Ingress or a Gateway adds. Without
it every visitor behind the proxy would share one rate limit. A client
that reaches the Service directly can set the header itself.

ntfy listens on its default port 80. The pod sets the sysctl
`net.ipv4.ip_unprivileged_port_start` to 0, so UID 1000 binds the port
without a capability (DEC-336 in the spec). Pod Security `baseline` and
`restricted` allow this sysctl.

The readiness probe gets `/v1/ready`, the endpoint ntfy's documentation
names for load balancers. There is no liveness probe.

## Proof

`check ntfy --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44).

`tests/smoke` checks that the pod passes Pod Security `restricted` and
starts a pod of ntfy's image, which carries the `ntfy` client and busybox
`wget`. From there, through the Service `ntfy` on port 80, it

- gets `/v1/health`
- gets 403 for a message without credentials and 401 for one with a wrong
  password
- publishes a message and a file of 4096 random bytes as the admin of
  `tests/target.yml`, finds both with `poll=1`, requires that the file's
  attachment URL starts with the base URL of `tests/target.yml`, and
  downloads the file byte for byte from `/file/`
- deletes the pod `ntfy-0` and, once its successor is ready, finds both
  messages again as the admin and downloads the file again.

## Not proven

The phone apps, and their instant delivery through ntfy.sh. Web push,
e-mail and the web app in a browser. A route or Ingress in front of the
Service, and the rate limits behind it. PostgreSQL in place of SQLite.
