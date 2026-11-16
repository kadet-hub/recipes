# langfuse

Langfuse 4.75.0, LLM observability with traces and evaluations, rendered by
the kadet-hub `kubernetes` generator 1.16.0 from Langfuse's Helm chart
2.2.3. PostgreSQL and Valkey are included recipes, ClickHouse and SeaweedFS
as the S3 store are options.

Source: `oci://ghcr.io/langfuse/langfuse-k8s/charts/langfuse:2.2.3@sha256:8550d6913086be7e3f1ff9efc1b8ee98c0d4f2e46af29f5144b1f818ea3caa08`

Level: `deploys`

The chart comes from [langfuse/langfuse-k8s](https://github.com/langfuse/langfuse-k8s),
tag `langfuse-2.2.3`, and is MIT. Langfuse is MIT except the directories
below `ee/` that its [`LICENSE`](https://github.com/langfuse/langfuse/blob/v4.75.0/LICENSE)
names, which need a Langfuse Enterprise license. The recipe runs
`ghcr.io/langfuse/langfuse` and `ghcr.io/langfuse/langfuse-worker`, the
same images as the chart's default registry `docker.langfuse.com`, which
passes pulls to Docker Hub under one shared anonymous limit. All images
are built for amd64 and arm64. `postgresql` requires `cnpg`, so install
`cnpg` first, in a target of its own.

## Include

```yaml
classes:
  - recipes.langfuse
  - recipes.langfuse.clickhouse   # one ClickHouse server
  - recipes.langfuse.s3           # SeaweedFS as the S3 store
parameters:
  namespace: langfuse
  kapitan:
    vars:
      target: langfuse
  applications:
    langfuse:
      salt: <ref>
      encryption_key: <ref>
      nextauth_secret: <ref>
      init:
        user_email: <email>
        user_password: <ref>
        public_key: <ref>
        secret_key: <ref>
      clickhouse:
        password: <ref>
      s3:
        secret_access_key: <ref>
    valkey:
      password: <ref>
```

The recipe includes `recipes.postgresql` and `recipes.valkey`. Pin only
this recipe in the fetch inventory. The consumer workflow adds `postgresql`
and `valkey` at the digests this version's index record lists under
`includes`. Kapitan's `--fetch` reads no index, so for a local compile pull
them by digest as the recipe's page on kadet-hub.org shows.

To use a ClickHouse or an S3 store that runs elsewhere, leave out the
option and set the settings below that point Langfuse at it. Both options
are what `check` proves. Without them the recipe is not tested.

## Required parameters

`applications.langfuse.salt` hashes the API keys and
`applications.langfuse.encryption_key` encrypts stored credentials, such
as the API keys of LLM connections, so keep both for the life of the
database. The encryption key is 64 hexadecimal digits, as
`openssl rand -hex 32` prints them. `applications.langfuse.nextauth_secret`
signs the session cookies. Any random string works for the salt and the
cookie secret, such as one that `openssl rand -base64 32` prints.

Langfuse has no default account, and sign-up is off. On each start the web
server creates what is missing of the organization `langfuse`, its project
`langfuse` with the API keys `applications.langfuse.init.public_key` and
`applications.langfuse.init.secret_key`, and the user
`applications.langfuse.init.user_email` with the password
`applications.langfuse.init.user_password` as the organization's owner.
The public key starts with `pk-lf-` and the secret key with `sk-lf-`. A
later change of the password does not reach the user. Change it in
Langfuse.

`applications.langfuse.clickhouse.password` is the password with which
Langfuse connects to ClickHouse, and the one the option `clickhouse` gives
its user. `applications.langfuse.s3.secret_access_key` is the S3 secret key
with which Langfuse reaches its bucket, and the one the option `s3`
accepts. The option writes it into SeaweedFS' identities, a JSON text, as
it is, so it must not contain `"`, `\` or a control character.
`applications.valkey.password`, which the included recipe `valkey`
requires, is the password of Valkey's user `default`, with which Langfuse
connects to its queue and cache. It is written into
`REDIS_CONNECTION_STRING` as it is, so it must not contain characters a URL
reserves, such as `@`, `/`, `:`, `?` or `%`. `openssl rand -hex 32` prints
one that fits.

Set the email as a plain value and all others as refs with the backend of
your choice. Without one of them the compile stops with
`Interpolation key '<key>' not found`. `postgresql` requires no parameter.

## Settings

`<a>` stands for `applications.langfuse`, `<web>` for
`components.langfuse-web`, `<worker>` for `components.langfuse-worker`.

| Chart value | Inventory |
|---|---|
| `langfuse.image.tag` | `<web>.image` and `<worker>.image`, tag and digest |
| `langfuse.nextauth.url`, the address users open Langfuse at | `<a>.url`, `http://localhost:3000` |
| `langfuse.web.replicas`, `langfuse.worker.replicas` | `<web>.replicas`, `<worker>.replicas`, 1 |
| `langfuse.resources` | `<web>.resources`, `<worker>.resources`, none |
| `langfuse.web.pdb`, `langfuse.worker.pdb` | `<web>.auto_pdb: true`, `<worker>.auto_pdb: true`, a PodDisruptionBudget with `maxUnavailable: 1` named after the component |
| `langfuse.features.telemetryEnabled` | `<web>.env.TELEMETRY_ENABLED`, `"true"`, anonymous usage data to Langfuse |
| `langfuse.additionalEnv`, `langfuse.smtp`, `langfuse.auth` | further variables in `<web>.env` |
| `postgresql.auth`, `postgresql.host` | `applications.postgresql`, which `postgresql`'s README lists |
| `clickhouse.host`, `clickhouse.auth.username` | `<a>.clickhouse.host`, `langfuse-clickhouse`, and `<a>.clickhouse.user`, `clickhouse` |
| `clickhouse.cluster.storage.size`, `clickhouse.cluster.resources` | `components.langfuse-clickhouse.volume_claims.data.spec.resources.requests.storage`, 100Gi, and `.resources` |
| `s3.endpoint`, `s3.bucket`, `s3.region` | `<a>.s3.endpoint`, `http://langfuse-s3-all-in-one:8333`, `<a>.s3.bucket`, `langfuse`, `<a>.s3.region`, `auto` |
| `s3.auth.rootUser` | `<a>.s3.access_key_id`, `langfuse` |
| `s3.allInOne.data.size`, `s3.allInOne.resources` | `components.langfuse-s3-all-in-one.persistent_volume_claims.langfuse-s3-all-in-one-data.storage`, 50Gi, and `.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `node_selector`, `tolerations`, `affinity` of each component |

The worker takes each of its variables from `<web>.env` by name, so a
change there reaches both Deployments. A variable added to `<web>.env`
reaches the web server only. Values are strings, so quote `"true"` and
numbers. The web server's Service `langfuse-web` is a ClusterIP Service on
port 3000. An Ingress or Gateway in the target exposes it, and `<a>.url`
names the address users open.

For a ClickHouse elsewhere, it needs a database `default` and the user of
`<a>.clickhouse.user`, and it must run in UTC. Langfuse connects with plain
HTTP on port 8123 and the native protocol on port 9000, without
replication. For an S3 store elsewhere, the bucket of `<a>.s3.bucket` must
exist, and Langfuse uses path-style requests.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart creates the bucket and the SFTP users of SeaweedFS in Helm hooks,
which run only inside `helm install`. They are not rendered:
`Job/langfuse-bucket-hook`, `Secret/langfuse-s3-sftp-secret`. SeaweedFS
4.52 creates the bucket on Langfuse's first upload, and the all-in-one
server does not start SFTP.

The chart's PodDisruptionBudgets `langfuse-web-pdb` and
`langfuse-worker-pdb` and SeaweedFS' ClusterRole and ClusterRoleBinding
`langfuse-s3-rw-cr` and `langfuse-s3-rw-crb` are off in
`tests/values.yaml` and not rendered. The ClusterRole grants every verb on
pods in all namespaces, which the all-in-one server does not use. The
ServiceAccount `seaweedfs` is rendered as the subchart renders it, and no
pod uses it.

## Proof

`check langfuse --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with
`cnpg` installed first. The objects of `postgresql` and `valkey` are left
out of the comparison and applied with the recipe. `tests/values.yaml`
switches the chart's subcharts for PostgreSQL and Valkey off and points it
at the included recipes. It keeps the subchart `seaweedfs`, whose objects
the option `s3` renders. The chart renders ClickHouse as resources of the
ClickHouse operator, which no generator renders, so `tests/values.yaml`
gives the chart the StatefulSet and Service of the option `clickhouse` as
`extraManifests`. Those two are compared only with their copy, and only the
smoke test proves them.

The workloads and Services select on `name`, the chart on
`app.kubernetes.io/name`, `instance` and `app`, and both select the same
pods. SeaweedFS' Service and anti-affinity select on the subchart's labels,
which the recipe puts on its pod. The pods and the ServiceAccount
`langfuse` set `automountServiceAccountToken: true`, the API default.
Containers carry an empty `securityContext` and are named after their
component. The Secrets `langfuse` and `langfuse-clickhouse-auth` exist only
in the recipe, and the chart's pods read exactly their keys.
`tests/target.yml` runs one PostgreSQL instance.

`tests/smoke` requires `OK` from `/api/public/health` and
`/api/public/ready` of the web server through its Service and `ok` from
the worker's `/api/health`. With the API keys of the Secret `langfuse` it
sends a span to `/api/public/otel/v1/traces`. The web server stores it as a
file in the bucket and queues a job in Valkey, and the worker writes it to
ClickHouse. The test reads the span with its input back from
`/api/public/v2/observations` and the stored file from the bucket through
SeaweedFS' filer. `/api/auth/signup` answers 422 with
`Sign up is disabled.`, the first user's login gets 200 and a session as
the owner of the organization, and a wrong password gets 401 and no
session. It then deletes the
pods of web, worker, ClickHouse and SeaweedFS and, once their successors
are ready, reads the same span and file, logs in again and sends and reads
a second span. Langfuse 4 takes traces only through OpenTelemetry by
default, so neither `/api/public/ingestion` nor `/api/public/traces` serve
them.

On kind with Kubernetes 1.37, after the smoke test, the pods' working sets
were 1335 MiB for the web server, 692 MiB for the worker, 270 MiB for
ClickHouse, 174 MiB for PostgreSQL, 96 MiB for SeaweedFS and 6 MiB for
Valkey, 2573 MiB together, from the kubelet's summary API. Web and worker
request nothing, as the chart sets them. ClickHouse requests 1 CPU and 2Gi,
SeaweedFS 0.5 CPU and 1Gi and Valkey 0.1 CPU and 128Mi, 1.6 CPUs and
3.1Gi together.

## Replacing a Helm release

Not tested. A release named `langfuse` has the same names for web and
worker. Its data is in the stores the release ran, which this recipe does
not read: the subchart PostgreSQL, the operator's ClickHouse and its
SeaweedFS claim. Moving the data is not covered here.

1. Set `applications.langfuse.salt`, `.encryption_key` and
   `.nextauth_secret` to the keys of the release's Secret `langfuse-app`,
   such as from
   `kubectl get secret langfuse-app -o jsonpath='{.data.salt}' | base64 -d`.
   With another salt the API keys stop working, with another encryption
   key Langfuse cannot read what it encrypted.
2. Delete the Deployments `langfuse-web`, `langfuse-worker` and
   `langfuse-s3-all-in-one` with `--cascade=orphan`, because their
   selectors change.
3. Delete the release's Helm secrets `sh.helm.release.v1.langfuse.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pods are ready, delete the orphaned ReplicaSets, the
   PodDisruptionBudgets `langfuse-web-pdb` and `langfuse-worker-pdb`, the
   ClusterRole `langfuse-s3-rw-cr` and its binding `langfuse-s3-rw-crb`.
