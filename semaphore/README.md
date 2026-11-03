# semaphore

Semaphore UI 2.19.17, a web UI and API for Ansible, Terraform, OpenTofu and
shell tasks, as one replica with its admin account, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from Semaphore's Helm chart 16.2.2. The database
is the included recipe `postgresql`.

Source: `oci://ghcr.io/semaphoreui/charts/semaphore:16.2.2@sha256:7b0eb7ccdf20b5f7ecf6b93bd2565d2bfaef089b6e11c023fa2a9d47ac331c2e`

Level: `deploys`

The chart comes from [semaphoreui/charts](https://github.com/semaphoreui/charts),
tag `semaphore-16.2.2`. Its HTTP repository `https://semaphoreui.github.io/charts`
serves the same archive, SHA-256
`a7802961495579054262740908e71effa9d8d5858a15ef187d2de77498b35945`. The
chart is Apache-2.0, Semaphore is MIT.

The chart's default is Semaphore 2.18.3 on BoltDB. 2.18.3 is affected by
the advisories
[GHSA-8cj9-r88m-8945](https://github.com/semaphoreui/semaphore/security/advisories/GHSA-8cj9-r88m-8945)
and [GHSA-cxvf-gvfq-36w2](https://github.com/semaphoreui/semaphore/security/advisories/GHSA-cxvf-gvfq-36w2),
so the recipe runs the image `docker.io/semaphoreui/semaphore:v2.19.17`,
built for amd64 and arm64. Semaphore 2.19 has no BoltDB, and the recipe
connects it to the PostgreSQL of `postgresql`. `postgresql` requires
`cnpg`, so install `cnpg` first, in a target of its own.

## Include

```yaml
classes:
  - recipes.semaphore
parameters:
  namespace: semaphore
  kapitan:
    vars:
      target: semaphore
  applications:
    semaphore:
      admin:
        username: <login>
        password: <ref>
      cookie_hash: <ref>
      cookie_encryption: <ref>
      access_key_encryption: <ref>
      runner_token: <ref>
```

Fetch `postgresql` at the same commit as this recipe, with a `git`
dependency of its own with `subdir: postgresql` and
`output_path: inventory/classes/recipes/postgresql`.

## Required parameters

`applications.semaphore.admin.username` and
`applications.semaphore.admin.password` are the login and password of the
admin account. The init container `admin` creates the account on the first
start and leaves it alone afterwards, so a later change of the password in
the target does not reach it. Change it in Semaphore.

`applications.semaphore.cookie_hash`, `cookie_encryption` and
`access_key_encryption` each hold 32 random bytes in base64, as
`openssl rand -base64 32` prints them. Semaphore signs and encrypts its
session cookies with the first two. It encrypts the keys and secrets that
projects store with the third, so keep that one for the life of the
database. `applications.semaphore.runner_token` is a random string. A
runner that presents it registers itself, also while remote runners are
off.

Set the password, the three keys and the token to refs with the backend of
your choice. Without one of them the compile stops with
`Interpolation key '<key>' not found`. `postgresql` requires no parameter.

## Settings

`<c>` stands for `components.semaphore`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `admin.fullname`, `admin.email` | `applications.semaphore.admin.fullname` and `.email`, `Admin` and `admin@localhost` |
| `database.name`, `database.host` | `applications.postgresql.database` and `.cluster`, which `postgresql`'s README lists |
| `database.options` | `<c>.env.SEMAPHORE_DB_OPTIONS`, JSON, `{"sslmode":"require"}` |
| `general.maxParallelTasks` | `<c>.env.SEMAPHORE_MAX_PARALLEL_TASKS`, `"0"` for no limit |
| `general.passwordLoginDisable` | `<c>.env.SEMAPHORE_PASSWORD_LOGIN_DISABLED`, `"false"` |
| `general.nonAdminCanCreateProject` | `<c>.env.SEMAPHORE_NON_ADMIN_CAN_CREATE_PROJECT`, `"false"` |
| `general.useRemoteRunner` | `<c>.env.SEMAPHORE_USE_REMOTE_RUNNER`, `"false"` |
| `persistence.size`, `persistence.storageClass` | `<c>.persistent_volume_claims.semaphore-workdir.storage`, `.storage_class`, 10G |
| `extraEnvVariables` | `<c>.env` |
| `resources` | `<c>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |

The init container takes each variable of the chart from `<c>.env` by
name, so a change there reaches both containers. A variable added to
`<c>.env` reaches the server only. Values are strings, so quote `"false"`
and `"0"`.

The chart sends `sslmode=disable` to PostgreSQL unless `database.options`
sets one. The recipe sets `sslmode=require`, as `tests/values.yaml` does
for the chart, because CloudNativePG serves TLS. Both containers run with
`runAsNonRoot: true`, the chart's `podSecurityContext` in
`tests/values.yaml`. The image runs as UID 1001.

The pod annotations `checksum/*` are the chart's hashes of its ConfigMap
and Secrets for the values of `tests/values.yaml`. They do not follow the
target's values, so after changing a Secret restart Semaphore with
`kubectl rollout restart deployment/semaphore`. The init container's
script and `config.json` are the chart's, with its license in
`semaphore.yml.LICENSE`.

The chart's Ingress, LDAP, OIDC, the mail, Telegram and Slack alerts, extra
Python packages and a custom CA bundle are off by default and not part of
the recipe. Its MariaDB and PostgreSQL subcharts stay off.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check semaphore --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with `cnpg`
installed first. The objects of `postgresql` are left out of the
comparison and applied with the recipe. The Deployment and the Service
select on `name`, the chart on `app.kubernetes.io/name` and `instance`,
and both select the same pods. The pod and the ServiceAccount set
`automountServiceAccountToken: true`, the API default the chart leaves
unset. The chart binds no role. The chart's Helm test
`Pod/semaphore-test-connection` is left out. `tests/target.yml` runs one
PostgreSQL instance.

`tests/smoke` waits for the Cluster and gets `/api/ping` through the
Service and the API server's service proxy. It then logs in as the admin
through `/api/auth/login`, which needs the account the init container
wrote into PostgreSQL, and reads `/api/user`, `/api/projects` and
`/api/info` with the session cookie. `/api/info` must report the version of
the Deployment's image tag and remote runners off. It runs no task.

## Replacing a Helm release

Not tested. A release named `semaphore` has the same object names. A
release on the chart's default BoltDB keeps its data in the claim
`semaphore-boltdb`, which this recipe does not read. Moving that data to
PostgreSQL is not covered here.

1. Set the three keys and the runner token of the target to the values in
   the release's Secrets, such as
   `kubectl get secret semaphore-general -o jsonpath='{.data.accesskeyEncryption}' | base64 -d`.
   With other keys Semaphore cannot read the keys and secrets it stored.
2. Delete the Deployment `semaphore` with `--cascade=orphan`, because its
   selector changes.
3. Delete the release's Helm secrets `sh.helm.release.v1.semaphore.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
