# authentik

authentik 2026.8.5, the identity provider for OAuth2, OpenID Connect, SAML,
LDAP and RADIUS, as one server and one worker, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from authentik's Helm chart 2026.8.5. The
database is the included recipe `postgresql`.

Source: `oci://ghcr.io/goauthentik/helm-charts/authentik:2026.8.5@sha256:9683518d02b5e41f69d045b59a779c40260608b5631d18273407ea2cfe708712`

Level: `deploys`

The chart comes from [goauthentik/helm](https://github.com/goauthentik/helm),
tag `authentik-2026.8.5`, and is GPL-3.0. Its HTTP repository
`https://charts.goauthentik.io` serves the same archive, SHA-256
`d00e8addefb2c758e071bd6eb8886f99be04eeba15c26ac869027c3d89d0a75e`. The
recipe carries no text of the chart. authentik is MIT outside its
`authentik/enterprise/` directory, which has a license of its own. The
recipe runs the image `ghcr.io/goauthentik/server:2026.8.5`, built for
amd64 and arm64.

authentik needs no Redis since
[2025.10](https://docs.goauthentik.io/releases/2025.10/), which moved its
cache, the embedded outpost's sessions and its WebSocket connections to
PostgreSQL, where its tasks already were. The recipe therefore includes
no `valkey`. `postgresql` requires `cnpg`, so install `cnpg` first, in a
target of its own.

## Include

```yaml
classes:
  - recipes.authentik
parameters:
  namespace: authentik
  kapitan:
    vars:
      target: authentik
  applications:
    authentik:
      secret_key: <ref>
      bootstrap_password: <ref>
      bootstrap_token: <ref>
```

Fetch `postgresql` at the same commit as this recipe, with a `git`
dependency of its own with `subdir: postgresql` and
`output_path: inventory/classes/recipes/postgresql`.

## Required parameters

`applications.authentik.secret_key` is `AUTHENTIK_SECRET_KEY`. authentik
signs its cookies with it, so a new key ends every session. Any random
string works, such as one that `openssl rand -base64 60` prints.

`applications.authentik.bootstrap_password` and `bootstrap_token` are the
password of the admin account `akadmin` and its API token
`authentik-bootstrap-token`, which does not expire. They are
`AUTHENTIK_BOOTSTRAP_PASSWORD` and `AUTHENTIK_BOOTSTRAP_TOKEN`. The worker
sets each only when it creates the account or the token, so a later change
in the target does not reach them. Change the password in authentik. The
worker creates a deleted token again from the target's value when a new
authentik release changes its bootstrap blueprint. To retire the token,
delete it and set `bootstrap_token` to a random value that nobody keeps.
Without a password, authentik would let anyone who reaches it first set
one through its initial setup flow.

Set the three as refs with the backend of your choice. Without one of them
the compile stops with `Interpolation key '<key>' not found`. `postgresql`
requires no parameter.

## Settings

`<s>` stands for `components.authentik-server`, `<w>` for
`components.authentik-worker`, `<d>` for
`applications.authentik.component_defaults`, which both components take,
and `<e>` for `generators.kubernetes.secrets.authentik.string_data`.

| Chart value | Inventory |
|---|---|
| `global.image.tag` | `<d>.image`, tag and digest |
| `server.replicas`, `worker.replicas` | `<s>.replicas`, `<w>.replicas`, 1 |
| `authentik.log_level` | `<e>.AUTHENTIK_LOG_LEVEL.value`, `info` |
| `authentik.email.*` | `<e>.AUTHENTIK_EMAIL__<KEY>.value`, such as `AUTHENTIK_EMAIL__HOST` |
| `authentik.error_reporting.enabled` | `<e>.AUTHENTIK_ERROR_REPORTING__ENABLED.value`, `"false"` |
| `authentik.postgresql.name`, `.user`, `.host` | `applications.postgresql.database`, `.owner` and `.cluster`, which `postgresql`'s README lists |
| `global.env`, `server.env`, `worker.env` | `<d>.env`, `<s>.env`, `<w>.env` |
| `server.service.type` | `<s>.service.type`, `ClusterIP` |
| `server.resources`, `worker.resources` | `<d>.resources` for both, or `<s>.resources` and `<w>.resources` |
| `global.nodeSelector`, `tolerations` | `<d>.node_selector`, `<d>.tolerations` |

The Secret `authentik` holds the chart's settings as authentik's
variables, `AUTHENTIK_<SECTION>__<KEY>`, and both components read all of
it. Values are strings, so quote `"true"` and numbers. authentik connects
to PostgreSQL with `sslmode=require`, which encrypts the connection without
verifying the server's certificate, because CloudNativePG signs it with its
own CA. This is `authentik.postgresql.sslmode: require` in
`tests/values.yaml`. The password comes from `postgresql`'s Secret
`postgresql-cluster-app`.

The pod annotation `checksum/secret` is the chart's hash of its Secret for
the values of `tests/values.yaml`. It does not follow the target's values,
so after changing the Secret restart both Deployments with
`kubectl rollout restart`.

The worker runs as the ServiceAccount `authentik`, which may manage
Secrets, Services, ConfigMaps, Deployments, Ingresses, HTTPRoutes, Traefik
middlewares and ServiceMonitors in the namespace and list CRDs, as the
chart's `serviceAccount.create` sets it up. authentik uses it to deploy the
outposts it manages into the namespace. The server runs as the namespace's
`default` ServiceAccount. GeoIP, email, the Ingress, the HTTPRoute, the
metrics Services, ServiceMonitors, the PrometheusRule, the HPAs and the
PodDisruptionBudgets are off by default and not part of the recipe. The
chart's PostgreSQL subchart stays off.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Renamed RBAC objects

| Chart | Recipe |
|---|---|
| `Role/authentik`, `RoleBinding/authentik` | `Role/authentik-worker`, `RoleBinding/authentik-worker` |
| `ClusterRole/authentik-<namespace>`, `ClusterRoleBinding/authentik-<namespace>` | `ClusterRole/<namespace>-authentik-worker`, `ClusterRoleBinding/<namespace>-authentik-worker` |

## Proof

`check authentik --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with
`cnpg` installed first. The objects of `postgresql` are left out of the
comparison and applied with the recipe. The Deployments select on `name`,
the chart on `app.kubernetes.io/name`, `instance` and `component`, and both
select the same pods. The pods carry the chart's labels too, so the
anti-affinity of each Deployment selects its own pods. The pods and the
ServiceAccount set `automountServiceAccountToken: true`, the API default
the chart leaves unset. The Service targets its ports by name. The chart
has no hooks or Helm tests. `tests/target.yml` runs one PostgreSQL
instance.

`tests/smoke` waits for the Cluster and gets `/-/health/live/` and
`/-/health/ready/` of the server through the Service. With the bootstrap
token it reads `/api/v3/core/users/me/`, which must name `akadmin`, and
`/api/v3/admin/version/`, which must report the version of the image tag.
The worker creates the account, the token and the default flows from
authentik's blueprints after its rollout, so these requests need the
server, the worker and PostgreSQL, and the test waits up to five minutes
for the token and for the flows. A request with another token gets 403.
It then creates an OAuth2 provider on the default flows and an
application through the API and gets the application's
`/.well-known/openid-configuration`, whose `issuer` must name the
application.

## Replacing a Helm release

Not tested. A release named `authentik` has the same object names except
the renamed RBAC objects. Its data is in the PostgreSQL that its
`authentik.postgresql.host` names, which this recipe does not read. Moving
that data to the Cluster of `postgresql` is not covered here. The
release's `akadmin` keeps its password. The worker applies the bootstrap
blueprint again only when a new authentik release changes it, and creates
the token from the target's `bootstrap_token` then if the release has
none.

1. Set `applications.authentik.secret_key` to the release's key, from
   `kubectl get secret authentik -o jsonpath='{.data.AUTHENTIK_SECRET_KEY}' | base64 -d`.
   With another key every session ends.
2. Delete the Deployments `authentik-server` and `authentik-worker` with
   `--cascade=orphan`, because their selectors change.
3. Delete the release's Helm secrets `sh.helm.release.v1.authentik.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pods are ready, delete the orphaned ReplicaSets and
   `Role/authentik`, `RoleBinding/authentik`,
   `ClusterRole/authentik-<namespace>` and
   `ClusterRoleBinding/authentik-<namespace>`.
