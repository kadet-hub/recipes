# n8n

n8n 2.45.5, the workflow automation tool, in queue mode with one main
instance and two workers, rendered by the kadet-hub `kubernetes` generator
1.14.0 from n8n's Helm chart 1.18.0. The database is the included recipe
`postgresql`, the queue the included recipe `valkey`.

Source: `oci://ghcr.io/n8n-io/n8n-helm-chart/n8n:1.18.0@sha256:da0d216953b83656935ae31b7869437a796dd2ed68718b623ddbfa5346dbfc0d`

Level: `deploys`

The chart comes from [n8n-io/n8n-hosting](https://github.com/n8n-io/n8n-hosting),
tag `v1.18.0`, and is MIT. n8n is under the
[Sustainable Use License](https://github.com/n8n-io/n8n/blob/master/LICENSE.md),
which the OSI does not approve as open source. It allows use and changes
of n8n only for internal business purposes and for non-commercial or
personal use, and its Enterprise features need an n8n Enterprise License.
This recipe contains no n8n code. Running the image is subject to n8n's
license.

The chart's default image is `docker.n8n.io/n8nio/n8n`, which serves
Docker Hub's `n8nio/n8n` and answered anonymous pulls with 429 when the
recipe was written. The recipe runs `docker.io/n8nio/n8n:2.45.5`, the
chart's `appVersion`, built for amd64 and arm64. `postgresql` requires
`cnpg`, so install `cnpg` first, in a target of its own.

## Include

```yaml
classes:
  - recipes.n8n
parameters:
  namespace: n8n
  kapitan:
    vars:
      target: n8n
  applications:
    n8n:
      encryption_key: <ref>
    valkey:
      password: <ref>
```

Fetch `postgresql` and `valkey` at the same commit as this recipe, each
with a `git` dependency of its own with `subdir: <recipe>` and
`output_path: inventory/classes/recipes/<recipe>`.

## Required parameters

`applications.n8n.encryption_key` is `N8N_ENCRYPTION_KEY`. n8n encrypts
the credentials of its workflows with it before it stores them in
PostgreSQL, so keep it for the life of the database. Any random string
works, such as one that `openssl rand -base64 32` prints.
`applications.valkey.password`, which the included recipe `valkey`
requires, is the password of Valkey's user `default`, with which n8n
connects to the queue. Set both as refs with the backend of your choice.
Without one of them the compile stops with
`Interpolation key '<key>' not found`. `postgresql` requires no parameter.

## Settings

`<m>` stands for `components.n8n-main`, `<w>` for `components.n8n-worker`
and `<d>` for `applications.n8n.component_defaults`, which both
components take.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<d>.image`, tag and digest |
| `queueMode.workerReplicaCount` | `<w>.replicas`, 2 |
| `queueMode.workerConcurrency` | `<w>.args.concurrency`, `--concurrency=10` |
| `secretRefs.env.N8N_HOST`, `N8N_PROTOCOL` | `generators.kubernetes.secrets.n8n.string_data.N8N_HOST.value` and `.N8N_PROTOCOL.value`, `n8n.example.com` and `http` |
| `service.port`, `secretRefs.env.N8N_PORT` | `applications.n8n.port`, `"5678"`, a string |
| `config.timezone` | `generators.kubernetes.configs.n8n.data.TZ.value`, `UTC` |
| `database.database`, `database.user`, `database.host` | `applications.postgresql.database`, `.owner` and `.cluster`, which `postgresql`'s README lists |
| `executions.*` | `<m>.env.EXECUTIONS_*` |
| `webhook.url`, `editor.url`, `config.extraEnv` | `N8N_WEBHOOK_URL`, `N8N_EDITOR_BASE_URL` and other variables in `<m>.env` and `<w>.env` |
| `resources.main`, `resources.worker` | `<d>.resources` for both, or `<m>.resources` and `<w>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<d>.node_selector`, `<d>.tolerations`, `<d>.affinity` |

The worker takes each variable of the chart from `<m>.env` by name, so a
change there reaches both Deployments. A variable added to `<m>.env`
reaches n8n-main only. Values are strings, so quote `"true"` and numbers.

The chart's queue settings, `QUEUE_*` in the ConfigMap `n8n`, are below
`generators.kubernetes.configs.n8n.data`. n8n connects to PostgreSQL with
TLS and does not verify the server's certificate, because CloudNativePG
signs it with its own CA. This is the chart's `database.ssl.enabled: true`
with `rejectUnauthorized: false`, as `tests/values.yaml` sets them.

The pod annotations `checksum/config` and `checksum/secret` are the
chart's hashes for the values of `tests/values.yaml`. They do not follow
the target's values, so after changing the ConfigMap or the Secret restart
both Deployments with `kubectl rollout restart`. The ConfigMap's
`N8N_DEPLOYMENT_ARTIFACT` is `helm-chart/1.18.0`, as the chart sets it for
n8n's telemetry.

The ServiceAccount `n8n` of both Deployments may read every ConfigMap and
Secret of the namespace through the Role `n8n`, as the chart's
`rbac.create` sets it up. Webhook processors, multi-main, task runners,
the Ingress, the HPA, KEDA, S3 storage and the NetworkPolicy are off by
default and not part of the recipe. Without task runners the chart still
renders the Secret `n8n-task-runners` with a random token that no
container reads. `tests/values.yaml` keeps it from rendering, and the
recipe has none.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's Helm test runs only inside `helm test`, and `tests/smoke`
checks more on the installed recipe. It is not rendered:
`Pod/n8n-test-connection`.

## Proof

`check n8n --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with
`cnpg` installed first. The objects of `postgresql` and `valkey` are left
out of the comparison and applied with the recipe. The Deployments and the
Service select on `name`, the chart on `app.kubernetes.io/name`,
`instance` and `component`, and both select the same pods. The pods and
the ServiceAccount set `automountServiceAccountToken: true`, the API
default the chart leaves unset. `tests/target.yml` runs one PostgreSQL
instance.

`tests/smoke` waits for the Cluster and gets `ok` from `/healthz` and
`/healthz/readiness` of n8n-main through the Service, and from
`/healthz/readiness` of each worker pod, which needs its connections to
PostgreSQL and Valkey. It sets up the owner account through
`/rest/owner/setup`, logs in through `/rest/login`, activates a workflow
with a production webhook and calls it. In queue mode n8n-main queues the
execution in Valkey and a worker runs it, so the answer comes from a
worker. It then restarts n8n-main, whose home is an emptyDir, logs in
again and calls the webhook again, which needs the owner and the workflow
from PostgreSQL.

## Replacing a Helm release

Not tested. A release named `n8n` has the same object names. Its data is
in the PostgreSQL that its `database.host` names, which this recipe does
not read. Moving that data to the Cluster of `postgresql` is not covered
here.

1. Set `applications.n8n.encryption_key` to the release's key, from
   `kubectl get secret n8n -o jsonpath='{.data.N8N_ENCRYPTION_KEY}' | base64 -d`.
   With another key n8n cannot read the credentials it stored.
2. Delete the Deployments `n8n-main` and `n8n-worker` with
   `--cascade=orphan`, because their selectors change.
3. Delete the release's Helm secrets `sh.helm.release.v1.n8n.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pods are ready, delete the orphaned ReplicaSets and
   the Secret `n8n-task-runners`, which the recipe does not render.
