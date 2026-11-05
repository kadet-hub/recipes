# netbox

NetBox v4.7.4, the source of truth for network infrastructure and IP
addresses, with its RQ worker, rendered by the kadet-hub `kubernetes`
generator 1.14.0 from NetBox's Helm chart 8.3.99. The included recipe
`postgresql` is the database, `valkey` holds tasks and cache.

Source: `oci://ghcr.io/netbox-community/netbox-chart/netbox:8.3.99@sha256:dbc14803e984f924d5d3b4db6955e02ebd94debf95d02af0507707aa53651be8`

Level: `deploys`

The chart comes from
[netbox-community/netbox-chart](https://github.com/netbox-community/netbox-chart),
tag `netbox-8.3.99`. Its HTTP repository
`https://charts.netbox.oss.netboxlabs.com/` serves the same archive, SHA-256
`681766d72479ac9018c544a3c3fa1798f2f3363260192b7bc200e7d306c63103`. The
chart, NetBox and the image of netbox-community/netbox-docker are
Apache-2.0. The image `ghcr.io/netbox-community/netbox:v4.7.4` is built for
amd64 and arm64. `postgresql` requires `cnpg`, so install `cnpg` first, in a
target of its own.

## Include

```yaml
classes:
  - recipes.netbox
parameters:
  namespace: netbox
  kapitan:
    vars:
      target: netbox
  applications:
    netbox:
      superuser:
        name: <login>
        email: <address>
        password: <ref>
      secret_key: <ref>
      api_token_pepper: <ref>
    valkey:
      password: <ref>
```

Pin only this recipe in the fetch inventory. The consumer workflow adds
`postgresql` and `valkey` at the digests this version's index record lists
under `includes`. Kapitan's `--fetch` reads no index, so for a local
compile pull them by digest as the recipe's page on kadet-hub.org shows.

## Required parameters

`applications.netbox.superuser.name`, `applications.netbox.superuser.email`
and `applications.netbox.superuser.password` are the superuser's login,
address and password. The image creates the superuser on
a start when no user of that name exists and leaves an existing one alone.
A later change of the address or the password in the target does not reach
NetBox, and a new name creates a second superuser.

`applications.netbox.secret_key` is NetBox's `SECRET_KEY`, at least 50
characters, as `openssl rand -hex 32` prints them. Another key ends every
session.

`applications.netbox.api_token_pepper` is the pepper with ID 1 of
`API_TOKEN_PEPPERS`, with which NetBox hashes v2 API tokens. It must be at
least 50 characters. The recipe writes it into a JSON string without
encoding, so use letters and digits only, as `openssl rand -hex 32` prints
them. Another pepper invalidates every v2 token hashed with the old one.

`applications.valkey.password` is the password of `valkey`.

Set the passwords, the key and the pepper to refs with the backend of your
choice. Without one of these parameters the compile stops with
`Interpolation key '<key>' not found`. `postgresql` requires no parameter.

## Settings

`<c>` stands for `components.netbox`, `<w>` for `components.netbox-worker`,
`<s>` for `generators.kubernetes.secrets.netbox-config.string_data`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `replicaCount` | `<c>.replicas`, with `ReadWriteMany` in `<c>.persistent_volume_claims.netbox-media.access_modes` |
| `worker.replicaCount` | `<w>.replicas` |
| `allowedHosts`, `csrf.trustedOrigins`, `loginRequired`, `timeZone`, `email` | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `LOGIN_REQUIRED`, `TIME_ZONE`, `EMAIL` in a file of `extraConfig`, see below |
| `email.password` | `<s>.email_password.value` |
| `apiTokenPeppers` | `<s>.api_token_peppers.value`, for a second pepper |
| `externalDatabase.host`, `.database`, `.username` | `applications.postgresql.cluster`, `.database` and `.owner`, which `postgresql`'s README lists |
| `persistence.size`, `persistence.storageClass` | `<c>.persistent_volume_claims.netbox-media.storage`, `.storage_class`, 1Gi |
| `resources`, `worker.resources` | `<c>.resources`, `<w>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity`, and the same below `<w>` |
| `service.type` | `<c>.service.type` |

The ConfigMap `netbox` holds the chart's `netbox.yaml` for the values of
`tests/values.yaml`. `configuration.py` loads it first and then every
`/run/config/extra/<n>/*.yaml`, each merged over the settings before it.
The chart's `extraConfig` changes settings this way. To change a setting,
put a YAML file with the changed keys into a ConfigMap of the target. Add
it to `<c>.volumes` and `<w>.volumes`, and mount it at
`/run/config/extra/0` in both `volume_mounts`.

The database connection uses `sslmode=require`, because CloudNativePG
serves TLS. NetBox keeps its tasks in database 0 and its cache in database 1
of `valkey`. The worker mounts the media claim too, so with a
`ReadWriteOnce` claim it runs on the same node as NetBox.

The pod annotations `checksum/config` and `checksum/secret` are the chart's
hashes for the values of `tests/values.yaml`. They do not follow the
target's values, so after changing the ConfigMap or a Secret restart both
Deployments with `kubectl rollout restart deployment/netbox deployment/netbox-worker`.
`configuration.py` and `netbox.yaml` in the ConfigMap `netbox` are the
chart's, with its license in `netbox.yml.LICENSE`.

The chart's housekeeping CronJob is off by default, because NetBox 4.6 and
later run housekeeping as a job of their own. The chart's Ingress, HTTPRoute,
LDAP, metrics, ServiceMonitors, PodDisruptionBudgets, autoscalers and the
claims for reports and scripts are off by default and not part of the recipe
either. Its PostgreSQL and Valkey subcharts are Bitnami's and stay off.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's test pod runs only inside `helm test`. `tests/smoke` checks the
same and more on the installed recipe. It is not rendered:
`Pod/netbox-test-connection`.

## Proof

`check netbox --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with `cnpg`
installed first. The objects of `postgresql` and `valkey` are left out of
the comparison and applied with the recipe. The Deployments and the Service
select on `name`, the chart on `app.kubernetes.io/name`, `instance` and
`component`. They select the same pods. The Role `netbox` grants the
ServiceAccount `netbox` the same as the chart's. `tests/target.yml` runs one
PostgreSQL instance. NetBox migrates its empty database on the first start.
On kind the Deployment became available up to 570 seconds after the apply,
so the proof needs check 0.14.1 or later, which waits up to 900 seconds for
a rollout.

`tests/smoke` waits for the Cluster and gets `/login/` and `/api/status/`
through the Service and the API server's service proxy. The status must
report the version of the Deployment's image tag and at least one running
worker. It provisions a v2 token through `/api/users/tokens/provision/` with
the superuser's login, and another token must get 403. With the token it
creates a site and the prefix `192.0.2.0/24` on it and reads both back. It
syncs a local data source, a job that NetBox queues in Valkey, and the job
must finish in the worker. Every connection of `app` to PostgreSQL must use
TLS.

## Replacing a Helm release

Not tested. A release named `netbox` has the same object names. A release on
the chart's default PostgreSQL subchart keeps its database there, which this
recipe does not read. Moving it to `postgresql` is not covered here.

1. Set `applications.netbox.secret_key` to the key `secret_key` of the
   release's Secret `netbox-config`, and `api_token_pepper` to the entry
   `1` of the JSON object in its key `api_token_peppers`, so sessions and
   v2 tokens stay valid. A release with more peppers needs all of them in
   `api_token_peppers`, as under Settings.
2. Delete the Deployments `netbox` and `netbox-worker` with
   `--cascade=orphan`, because their selectors change.
3. Delete the release's Helm secrets `sh.helm.release.v1.netbox.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pods are ready, delete the orphaned ReplicaSets.
