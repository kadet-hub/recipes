# mlflow

MLflow 3.18.0, the tracking server with its model registry and basic auth,
on the PostgreSQL of the included recipe `postgresql` with artifacts on a
claim, rendered by the kadet-hub `kubernetes` generator 1.16.0 from
MLflow's Helm chart `mlflow` 3.18.0.

Source: `oci://ghcr.io/mlflow/charts/mlflow:3.18.0@sha256:14838bbc4d897fd1675edef7930c5eb0135f0791d4479be2c3357dde5d5b259e`

Level: `deploys`

The chart lives in `charts/` of mlflow/mlflow, Apache-2.0, and MLflow's
release workflow publishes it with each stable release, after the images.
The recipe runs the chart's default image `ghcr.io/mlflow/mlflow:v3.18.0-full`,
an index for linux/amd64 and linux/arm64, which carries the PostgreSQL
driver and the basic auth app. `postgresql` requires `cnpg`, so install
`cnpg` first, in a target of its own.

## Include

```yaml
classes:
  - recipes.mlflow
parameters:
  namespace: mlflow
  kapitan:
    vars:
      target: mlflow
  applications:
    mlflow:
      admin_password: <ref>
      secret_key: <ref>
```

The recipe includes `recipes.postgresql`. Pin only this recipe in the fetch
inventory. The consumer workflow adds `postgresql` at the digest this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.mlflow.admin_password` is the password of the basic auth
user `admin`, at least 12 characters. MLflow creates `admin` with it on the
first start against an empty user store and ignores it once the user
exists, so a later change of the parameter does not reach the account.
Change the password through `PATCH /api/2.0/mlflow/users/update-password`
as `admin`. `applications.mlflow.secret_key` is
`MLFLOW_FLASK_SERVER_SECRET_KEY`, which signs the CSRF tokens of the
sign-up page. MLflow does not start with basic auth without it. Set both as
refs with the backend of your choice. Without one of them the compile stops
with `Interpolation key '<key>' not found`.

## Accounts

Every request needs a login, except `/health`, the server info and the
static files of the web UI. MLflow has no self-registration. `admin` creates further users on
the page `/signup` or through `POST /api/2.0/mlflow/users/create`, and
grants them permissions on experiments and registered models. Users that
are granted nothing get `READ` on everything, MLflow's default.

Clients log in with HTTP basic auth, the Python client through
`MLFLOW_TRACKING_USERNAME` and `MLFLOW_TRACKING_PASSWORD`:

```sh
export MLFLOW_TRACKING_URI=http://mlflow-mlflow:5000
export MLFLOW_TRACKING_USERNAME=admin MLFLOW_TRACKING_PASSWORD=<password>
```

## Storage

Runs, metrics, parameters and the model registry are in the database `app`
of `postgresql`. MLflow reads its URI from the key `uri` of the Secret
`postgresql-cluster-app`. The URI sets no `sslmode`, so the driver takes
libpq's default `prefer` and encrypts without verifying the server's
certificate. The tracking server
stores artifacts on the claim `mlflow-mlflow` below `/mlflow/artifacts` and
serves them to clients (`--serve-artifacts`), so clients need no access to
a bucket. The users and permissions of basic auth are in the SQLite file
`/mlflow/basic_auth.db` on the same claim, because MLflow reads the auth
database's URI only from its configuration file. A backup takes the
database and the claim.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `components.mlflow-mlflow.image`, tag and digest |
| `server.value_options.allowed_hosts`, the host names clients reach MLflow by | `applications.mlflow.allowed_hosts`, by default the Service's names in the cluster on port 5000 |
| `server.value_options.workers`, 4 | `components.mlflow-mlflow.command`, the element `--workers=4` |
| `storage.size`, 10Gi | `components.mlflow-mlflow.persistent_volume_claims.mlflow-mlflow.storage` |
| `resources` | `components.mlflow-mlflow.resources` |
| `env` | `components.mlflow-mlflow.env.<variable>` |
| the Cluster, its database and its size | `applications.postgresql`, which `postgresql`'s README lists |

MLflow answers only requests whose `Host` header is localhost, a private
address or one of `applications.mlflow.allowed_hosts`. Add the host name of
an Ingress or route of the target there. Lists set in the target are
appended to the recipe's lists, so `command` changes only in a class
included after the recipe that sets it to `~`, with the new list in the
target.

The chart's Ingress, HorizontalPodAutoscaler, NetworkPolicy, ServiceMonitor,
garbage collection CronJob, TLS and External Secrets objects are off by
default and not part of the recipe. The chart renders no hook. Its
ServiceAccount has no role, and neither it nor the pod mounts a token.

## Proof

`check mlflow --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with check
0.16.0 and `cnpg` installed first. The objects of `postgresql` are applied
with the recipe and left out of the comparison. The remaining differences
are of the classes Selector scheme, Derived name (the container
`mlflow-mlflow`), Explicit default (the pod's `automountServiceAccountToken:
false`, as its ServiceAccount sets it) and Referenced Secret (the Secret
`mlflow-mlflow` with the admin password, the Flask secret key and
`basic_auth.ini`).

`tests/smoke` starts a pod of the MLflow image and talks to the Service
`mlflow-mlflow` on port 5000. It requires 401 for a request and a sign-up
without a login and for a wrong password. As `admin` with the password of
the Secret, it logs a run with a parameter, a metric and an artifact,
registers version 1 of the model `smoke` from the run and reads all of it
back. It then deletes the pod and reads everything again from its
successor.

Not tested: the web UI, users other than `admin`, permissions, and an
Ingress or route in front of the Service.

## Replacing a Helm release

Not tested.

1. Delete the Deployment `mlflow-mlflow` with `--cascade=orphan`, because
   its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.mlflow.*`, so Helm
   forgets the release without deleting its objects.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
