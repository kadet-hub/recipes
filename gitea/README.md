# gitea

Gitea 28.3.0, a self-hosted Git service with a web UI and an API, as one
replica with its admin account, rendered by the kadet-hub `kubernetes`
generator 1.9.0 from Gitea's Helm chart 12.7.0. The included recipe
`postgresql` is the database, `valkey` holds cache, sessions and queues.

Source: `oci://docker.gitea.com/charts/gitea:12.7.0@sha256:4b709d7e9214bef9e1c71383924e88944cdb0d6dcd892a32971aca52ccc5f596`

Level: `deploys`

The chart comes from [gitea/helm-gitea](https://gitea.com/gitea/helm-gitea),
tag `v12.7.0`. Its HTTP repository `https://dl.gitea.com/charts/` serves the
same archive, SHA-256
`5881ef9c59400bee2d5547e77c4cd0efb925143c2f5d93fb4f38446db76b0167`. The
chart and Gitea are MIT.

The chart's default is Gitea 1.27.0. Gitea publishes security fixes only for
its most recent major release, now 28. 28.1.0 and 28.3.0 fixed advisories
rated high that affect 1.27, such as
[GHSA-9v6p-xpcp-7488](https://github.com/go-gitea/gitea/security/advisories/GHSA-9v6p-xpcp-7488).
The recipe therefore runs the image `docker.gitea.com/gitea:28.3.0-rootless`,
the chart's `image.tag: 28.3.0`, built for amd64, arm64 and riscv64. Its
tag does not follow the chart's version, so move it by hand together with
`applications.gitea.labels.version`. `postgresql` requires `cnpg`, so
install `cnpg` first, in a target of its own.

## Include

```yaml
classes:
  - recipes.gitea
parameters:
  namespace: gitea
  kapitan:
    vars:
      target: gitea
  applications:
    gitea:
      admin:
        username: <login>
        password: <ref>
      secret_key: <ref>
      internal_token: <ref>
    valkey:
      password: <ref>
```

Fetch `postgresql` and `valkey` at the same commit as this recipe, each with
a `git` dependency of its own with `subdir: <recipe>` and
`output_path: inventory/classes/recipes/<recipe>`.

## Required parameters

`applications.gitea.admin.username` and `applications.gitea.admin.password`
are the login and password of the admin account. The init container
`configure-gitea` creates the account on the first start and sets its
password on every later start, the chart's
`gitea.admin.passwordMode: keepUpdated`. Gitea refuses to set a password of
fewer than 8 characters, which then stops the pod's start.

`applications.gitea.secret_key` and `applications.gitea.internal_token` are
`SECRET_KEY` and `INTERNAL_TOKEN` of `[security]` in `app.ini`, random
strings as `openssl rand -hex 32` prints them. Gitea encrypts stored secrets
such as two-factor keys with the first one. The init container
`init-app-ini` writes both only while the claim holds no `app.ini`, so a
later change in the target does not reach Gitea.

`applications.valkey.password` is the password of `valkey`. Gitea reads it
inside a `redis://` URL that the recipe does not encode, so use letters and
digits only, as `openssl rand -hex 32` prints them.

Set the passwords, the key and the token to refs with the backend of your
choice. Without one of them the compile stops with
`Interpolation key '<key>' not found`. `postgresql` requires no parameter.

## Settings

`<c>` stands for `components.gitea`, `<ini>` for
`<c>.init_containers.init-app-ini.env`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest, and `applications.gitea.labels.version` |
| `gitea.admin.email` | `applications.gitea.admin.email`, `gitea@local.domain` |
| `gitea.admin.passwordMode` | `<c>.init_containers.configure-gitea.env.GITEA_ADMIN_PASSWORD_MODE`, `keepUpdated` |
| `gitea.config.<section>.<KEY>` | `<ini>.GITEA__<SECTION>__<KEY>`, such as `GITEA__SERVER__ROOT_URL` |
| `gitea.additionalConfigFromEnvs` | `<ini>` |
| `gitea.config.database.HOST`, `.NAME` | `applications.postgresql.cluster` and `.database`, which `postgresql`'s README lists |
| `persistence.size`, `persistence.storageClass` | `<c>.persistent_volume_claims.gitea-shared-storage.storage`, `.storage_class`, 10Gi |
| `service.ssh.type`, `service.ssh.annotations` | `<c>.additional_services.gitea-ssh.type`, `.annotations`, with `headless: false` for a type other than `ClusterIP` |
| `resources` | `<c>.resources` |
| `initContainers.resources` | `<c>.init_containers.init-directories.resources`, which the other init containers take |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |

`init-app-ini` writes `app.ini` on the claim on every start, from the
Secret `gitea-inline-config` and then from the `GITEA__*` variables of its
environment, which win. The recipe keeps the chart's `ROOT_URL`
`http://git.example.com`, so set `<ini>.GITEA__SERVER__ROOT_URL`,
`GITEA__SERVER__DOMAIN` and `GITEA__SERVER__SSH_DOMAIN` to the address users
reach Gitea at. The Services `gitea-http` on port 3000 and `gitea-ssh` on
port 22 are headless, as the chart renders them. The API does not change
the `clusterIP` of an existing Service, so delete the Service before
switching `headless` off. The chart's Ingress,
Gateway API routes and OpenShift Route are off by default and not part of
the recipe.

Cache, sessions and queues use `valkey`, which the chart's own Valkey
subcharts would provide. The database connection uses `sslmode=require`,
because CloudNativePG serves TLS. All containers run with
`runAsNonRoot: true`, the chart's `containerSecurityContext` in
`tests/values.yaml`. The rootless image runs as UID 1000.

The pod annotation `checksum/config` is the chart's hash of its config
Secrets for the values of `tests/values.yaml`. It does not follow the
target's values, so after changing a Secret restart Gitea with
`kubectl rollout restart deployment/gitea`. The scripts in the Secrets
`gitea` and `gitea-init` are the chart's, with its license in
`gitea.yml.LICENSE`.

The chart 12.7.0 has no Actions runner. act_runner, which needs Docker in
Docker, has a chart of its own in gitea/helm-actions and is not part of the
recipe. The chart's LDAP and OAuth sources, GPG signing and metrics are off
by default and not part of the recipe either. Its PostgreSQL, PostgreSQL HA,
Valkey and Valkey Cluster subcharts are Bitnami's and stay off.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's test pod runs only inside `helm test`. `tests/smoke` checks the
same and more on the installed recipe. It is not rendered:
`Pod/gitea-test-connection`.

## Proof

`check gitea --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with `cnpg`
installed first. The objects of `postgresql` and `valkey` are left out of
the comparison and applied with the recipe. The Deployment and the two
Services select on `name`, and the Services also on the label `version`,
the chart on `app.kubernetes.io/name` and `instance`. All three select the
same pods. The Services target the ports by name, `http` and `ssh`, the
chart by number, 3000 and 2222. The container ports are sorted by name. The
pod sets `automountServiceAccountToken: true`, the API default the chart
leaves unset. The chart binds no role. `tests/target.yml` runs one
PostgreSQL instance.

`tests/smoke` waits for the Cluster and gets `/api/healthz` through the
Service and the API server's service proxy, which must report `pass` for
the database and the cache. `/api/v1/version` must report the version of
the Deployment's image tag. As the admin it creates the repository `smoke`
through `POST /api/v1/user/repos`. A pod running Gitea's image clones it
over HTTP through the Service `gitea-http`, commits a file and pushes it,
and the API must return that commit for the branch `main` and the file's
content. Valkey must then hold keys.

## Replacing a Helm release

Not tested. A release named `gitea` has the same object names. A release on
the chart's default PostgreSQL HA subchart keeps its database there, which
this recipe does not read. Moving it to `postgresql` is not covered here.

1. Set `applications.gitea.secret_key` and `internal_token` to the values in
   the release's `app.ini`, which
   `kubectl exec deployment/gitea -- grep -E '^(SECRET_KEY|INTERNAL_TOKEN) ' /data/gitea/conf/app.ini`
   prints. The claim keeps its `app.ini`, so they matter only for a new
   claim.
2. Delete the Deployment `gitea` with `--cascade=orphan`, because its
   selector changes.
3. Delete the release's Helm secrets `sh.helm.release.v1.gitea.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
