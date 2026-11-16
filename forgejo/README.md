# forgejo

Forgejo 15.0.11, a self-hosted Git forge with a web UI and an API, as one
replica with its admin account, rendered by the kadet-hub `kubernetes`
generator 1.16.0 from Forgejo's Helm chart 17.3.2. The included recipe
`postgresql` is the database.

Source: `oci://code.forgejo.org/forgejo-helm/forgejo:17.3.2@sha256:73accaef0604d6e701a7b141e71a8b9a007c1475807240403d8bca0aeda24b74`

Level: `deploys`

The chart comes from
[forgejo-helm/forgejo-helm](https://code.forgejo.org/forgejo-helm/forgejo-helm),
tag `v17.3.2`. The chart is MIT, Forgejo is GPL-3.0-or-later.

The recipe runs the chart's `appVersion`, Forgejo 15.0.11 of the 15.0 LTS
line, which Forgejo supports until 15 July 2027. The chart's maintainers
keep it on that line. The image `code.forgejo.org/forgejo/forgejo:15.0.11-rootless`
is built for amd64, arm64 and arm/v6. Its tag follows the chart, so move it
with the chart's version, together with `applications.forgejo.labels.version`.
`postgresql` requires `cnpg`, so install `cnpg` first, in a target of its
own.

## Include

```yaml
classes:
  - recipes.forgejo
parameters:
  namespace: forgejo
  kapitan:
    vars:
      target: forgejo
  applications:
    forgejo:
      admin:
        username: <login>
        password: <ref>
      secret_key: <ref>
```

The recipe includes `recipes.postgresql`. Pin only this recipe in the fetch
inventory. The consumer workflow adds `postgresql` at the digest this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.forgejo.admin.username` and `applications.forgejo.admin.password`
are the login and password of the admin account, which the recipe writes
into the Secret `forgejo-admin`. The init container `configure-gitea`
creates the account on the first start and sets its password on every later
start, the chart's `gitea.admin.passwordMode: keepUpdated`. Forgejo rejects
the login `admin`.

`applications.forgejo.secret_key` is `SECRET_KEY` of `[security]` in
`app.ini`, a random string as `openssl rand -hex 32` prints it. Forgejo
encrypts stored secrets such as two-factor keys with it, and they live in
the database, apart from the claim. The init container `init-app-ini`
writes the key only while the claim holds no `app.ini`, so a later change
in the target does not reach Forgejo.

Set the password and the key to refs with the backend of your choice.
Without one of the three parameters the compile stops with
`Interpolation key '<key>' not found`. `postgresql` requires no parameter.

## Settings

`<c>` stands for `components.forgejo`, `<ini>` for
`<c>.init_containers.init-app-ini.env`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest, and `applications.forgejo.labels.version` |
| `gitea.admin.email` | `applications.forgejo.admin.email`, `gitea@local.domain` |
| `gitea.admin.passwordMode` | `<c>.init_containers.configure-gitea.env.GITEA_ADMIN_PASSWORD_MODE`, `keepUpdated` |
| `gitea.config.<section>.<KEY>` | `<ini>.FORGEJO__<SECTION>__<KEY>`, such as `FORGEJO__SERVER__ROOT_URL` |
| `gitea.additionalConfigFromEnvs` | `<ini>` |
| `gitea.config.database.HOST`, `.NAME` | `applications.postgresql.cluster` and `.database`, which `postgresql`'s README lists |
| `persistence.size`, `persistence.storageClass` | `<c>.persistent_volume_claims.gitea-shared-storage.storage`, `.storage_class`, 10Gi |
| `service.http.type`, `service.ssh.type`, their `annotations` | `<c>.service.type`, `<c>.additional_services.forgejo-ssh.type`, `.annotations` |
| `resources` | `<c>.resources` |
| `initContainers.resources` | `<c>.init_containers.init-directories.resources`, which the other init containers take |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |

`init-app-ini` writes `app.ini` on the claim on every start, from the
Secret `forgejo-inline-config` and then from the `FORGEJO__*` variables of
its environment, which win. The recipe keeps the chart's `ROOT_URL`
`http://git.example.com`, so set `<ini>.FORGEJO__SERVER__ROOT_URL`,
`FORGEJO__SERVER__DOMAIN` and `FORGEJO__SERVER__SSH_DOMAIN` to the address
users reach Forgejo at. The Services are `forgejo-http` on port 3000 and
`forgejo-ssh` on port 22. The chart's Ingress, Gateway API routes and
OpenShift Route are off by default and not part of the recipe.

The database connection uses `sslmode=require`, because CloudNativePG
serves TLS. Cache and sessions stay in Forgejo's memory and the queue in a
LevelDB on the claim, the chart's defaults, so sessions end with the pod.
For Valkey, include `recipes.valkey` and set the `FORGEJO__CACHE__*`,
`FORGEJO__SESSION__*` and `FORGEJO__QUEUE__*` variables in `<ini>` as the
chart's README describes. The Deployment replaces its pod with the strategy
`Recreate`, because the claim is `ReadWriteOnce`. The rootless image runs
as UID 1000.

The pod annotation `checksum/config` is the chart's hash of its config
Secrets for the values of `tests/values.yaml`. It does not follow the
target's values, so after changing a Secret restart Forgejo with
`kubectl rollout restart deployment/forgejo`. The scripts in the Secrets
`forgejo` and `forgejo-init` are the chart's, with its license in
`forgejo.yml.LICENSE`.

The chart's LDAP and OAuth sources, GPG and SSH commit signing, metrics,
ServiceMonitor, PodDisruptionBudget and ServiceAccount are off by default
and not part of the recipe. It renders no Forgejo Actions runner.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's test pod runs only inside `helm test`. `tests/smoke` checks the
same and more on the installed recipe. It is not rendered:
`Pod/forgejo-test-connection`.

## Proof

`check forgejo --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with `cnpg`
installed first. The objects of `postgresql` are left out of the comparison
and applied with the recipe. The Deployment and the two Services select on
`name`, and the Services also on the label `version`, the chart on
`app.kubernetes.io/name` and `instance`. All three select the same pods.
The container ports are sorted by name. The pod sets
`automountServiceAccountToken: true`, the API default the chart leaves
unset. The chart binds no role. `tests/target.yml` runs one PostgreSQL
instance.

`tests/smoke` waits for the Cluster and gets `/api/healthz` and the web UI
through the Service and the API server's service proxy. The first must
report `pass` for the database. `/api/v1/version` must report the version
of the Deployment's image tag, and the login of `forgejo-admin` must be an
admin. As that account it creates the repository `smoke` through
`POST /api/v1/user/repos`. A pod running Forgejo's image clones it over
HTTP through the Service `forgejo-http`, commits a file and pushes it, and
the API must return that commit for the branch `main` and the file's
content. The test then deletes the Forgejo pod and reads both back again
from the pod that replaces it.

## Replacing a Helm release

Not tested. A release named `forgejo` has the same object names. A release
on the chart's default SQLite keeps its database on the claim, which this
recipe does not read. Moving it to `postgresql` is not covered here.

1. Set `applications.forgejo.secret_key` to the value in the release's
   `app.ini`, which
   `kubectl exec deployment/forgejo -- grep -E '^SECRET_KEY ' /data/gitea/conf/app.ini`
   prints. The claim keeps its `app.ini`, so it matters only for a new
   claim.
2. Delete the Deployment `forgejo` with `--cascade=orphan`, because its
   selector changes.
3. Delete the release's Helm secrets `sh.helm.release.v1.forgejo.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
