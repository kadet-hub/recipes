# open-archiver

Open Archiver 0.6.2, a self-hosted email archive with full-text search,
rendered by the kadet-hub `kubernetes` generator 1.14.0 from its Docker
Compose file. PostgreSQL and Valkey are the included recipes `postgresql`
and `valkey`, Meilisearch and Apache Tika run as components.

<!-- renovate: tag=v0.6.2 -->
Source: `https://github.com/LogicLabs-OU/OpenArchiver/blob/1903f17ef46296d41265ea4769086e32b13d9af9/docker-compose.yml@sha256:1e50d761d447294d901df562be5cc2786397cdd366826e674c3f731370e34f01`

Level: `deploys`

The commit is the tag `v0.6.2`. Open Archiver is AGPL-3.0, and the recipe
copies no text from it. `postgresql` requires `cnpg`, so install `cnpg`
first, in a target of its own. Open Archiver and Meilisearch run as root,
as their images set no user, so the target's namespace needs the Pod
Security level `baseline`. Tika runs as the image's user 35002.

Open Archiver's image carries no `node_modules`. Its entrypoint runs
`pnpm install --frozen-lockfile --prod` and the database migrations at
every start, so the pod needs the npm registry and `cdn.sheetjs.com`, from
which `pnpm-lock.yaml` takes `xlsx`, each time it starts.

## Include

```yaml
classes:
  - recipes.open-archiver
parameters:
  namespace: open-archiver
  kapitan:
    vars:
      target: open-archiver
  applications:
    open-archiver:
      app_url: https://archive.example.com
      jwt_secret: <ref>
      encryption_key: <ref>
      meili_master_key: <ref>
    valkey:
      password: <ref>
```

The recipe includes `recipes.postgresql` and `recipes.valkey`. Pin only
this recipe in the fetch inventory. The consumer workflow adds both at the
digests this version's index record lists under `includes`.

## Required parameters

- `applications.open-archiver.jwt_secret` is `JWT_SECRET`, which signs the
  access tokens of the web UI and the API. A new value logs every user
  out.
- `applications.open-archiver.encryption_key` is `ENCRYPTION_KEY`, 64
  hexadecimal digits such as the output of `openssl rand -hex 32`. It
  encrypts the credentials of the ingestion sources in the database, so
  keep it once a source exists. Open Archiver does not start without it.
- `applications.open-archiver.meili_master_key` is the master key of
  Meilisearch, which Open Archiver sends as `MEILI_MASTER_KEY`.
- `applications.valkey.password`, which the included recipe `valkey`
  requires, reaches Open Archiver as `REDIS_PASSWORD`.

Set them as refs with the backend of your choice. Without one of them the
compile stops with `Interpolation key '<key>' not found`.

## Settings

| Setting | Inventory |
|---|---|
| the address users open, `APP_URL` and `ORIGIN` | `applications.open-archiver.app_url` |
| Open Archiver version | `components.open-archiver.image`, tag and digest |
| Open Archiver's other variables, such as `NODE_ENV`, `SYNC_FREQUENCY` or `STORAGE_ENCRYPTION_KEY` | `components.open-archiver.env.<variable>` |
| the size of the mail store | `components.open-archiver.volume_claims.archiver-data.spec.resources.requests.storage` |
| the size of Meilisearch's database | `components.open-archiver-meilisearch.volume_claims.meilidata.spec.resources.requests.storage` |
| Meilisearch's snapshots, every 86400 s | `components.open-archiver-meilisearch.env.MEILI_SCHEDULE_SNAPSHOT`, empty to turn them off |
| without Tika | `components.open-archiver-tika.enabled: false` and `components.open-archiver.env.TIKA_URL: ""`. Open Archiver then parses attachments itself |
| resources | `components.<component>.resources` |
| the Cluster, its database and its size | `applications.postgresql`, which `postgresql`'s README lists |

`.env.example` sets `NODE_ENV` to `development` and `SYNC_FREQUENCY` to
every minute, and the recipe keeps both. A target for production sets
`production` and a schedule of its own. A credential such as
`STORAGE_ENCRYPTION_KEY` or the S3 keys belongs into a Secret of the
target, referenced with `secretKeyRef`. Any list set in the target is
appended to the recipe's list.

The Service `open-archiver` is a ClusterIP Service on port 3000. The
compose file publishes that port on the host. Here an Ingress or Gateway
in the target exposes it, under the address of `app_url`.

## Mapping

The service `open-archiver` becomes the component `open-archiver`,
`meilisearch` and `tika` the components `open-archiver-meilisearch` and
`open-archiver-tika`. `postgres` and `valkey` become the included recipes
`postgresql` and `valkey`. Open Archiver reaches them through the Services
`open-archiver-meilisearch`, `open-archiver-tika`, `postgresql-cluster-rw`
and `valkey`.

| Compose | Recipe |
|---|---|
| service `open-archiver` | StatefulSet `open-archiver`, Service `open-archiver` on port 3000, Secret `open-archiver` with `JWT_SECRET`, `ENCRYPTION_KEY` and `MEILI_MASTER_KEY` |
| `logiclabshq/open-archiver:latest` | `docker.io/logiclabshq/open-archiver:v0.6.2@sha256:ec2e954959f7d0ee0089c4338437720da9b85520a23779cb6d7642943b3ae8e5`, which `latest` was at migration |
| `env_file: .env` | the values of `.env.example` at the same commit (SHA-256 `5b59546933968cff45158b1266b04ef235ade48f3f82ebc4942680c3089ec272`), which the documentation copies to `.env`, with the renames below |
| `MEILI_HOST: http://meilisearch:7700`, `TIKA_URL: http://tika:9998` | `http://open-archiver-meilisearch:7700`, `http://open-archiver-tika:9998` |
| `DATABASE_URL` with `postgres` and the password `password` | the key `uri` of the Secret `postgresql-cluster-app`, with the generated password |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` in `.env` | not rendered. They configure the compose service `postgres`, and Open Archiver reads only `DATABASE_URL` |
| `REDIS_PASSWORD: defaultredispassword` | the key `default-password` of the Secret `valkey-auth` |
| `JWT_SECRET`, `ENCRYPTION_KEY`, `MEILI_MASTER_KEY` in `.env`, placeholders or empty | `applications.open-archiver.jwt_secret`, `.encryption_key` and `.meili_master_key` |
| volume `archiver-data` | claim template `archiver-data`, `ReadWriteOnce`, `1Gi` |
| service `meilisearch`, `getmeili/meilisearch:v1.38` with `MEILI_SCHEDULE_SNAPSHOT` 86400 and the volume `meilidata` | StatefulSet `open-archiver-meilisearch` with `docker.io/getmeili/meilisearch:v1.38.2@sha256:448a5b1b3e9303fabf39b84a2672f184295f665b1cb8eaffb11c738273430e5e`, which `v1.38` was at migration, Service port 7700, claim template `meilidata`, `ReadWriteOnce`, `1Gi` |
| service `tika`, `apache/tika:4.1.0-full` | Deployment `open-archiver-tika` with `docker.io/apache/tika:4.1.0-full@sha256:d69fab827fa004a5e1db786e6d78da947a6cfeedbf595bc5c353ef99622bb2e2`, Service port 9998 |
| service `postgres`, `postgres:17-alpine` with the volume `pgdata` | the included recipe `postgresql`, PostgreSQL 18.6 on CloudNativePG, with the database and user `app` |
| service `valkey`, `valkey/valkey:8-alpine` with `--requirepass` and the volume `valkeydata` | the included recipe `valkey`, Valkey 9.1.2 with the password of the ACL user `default` |
| port `3000:3000` | Service port 3000, `ClusterIP` |
| `depends_on`, `restart`, `container_name`, `networks`, `version` | not rendered. Open Archiver restarts until PostgreSQL answers its migrations |

No service sets a `healthcheck`, and no image has a `HEALTHCHECK`, so the
recipe renders no probe.

## Proof

`check open-archiver --level deploys` with `tests/target.yml`, with check
0.24.2 on kind for each Kubernetes minor CI tests, with `cnpg` installed
first. The objects of `postgresql` and `valkey` are applied with the
recipe. A compose file has no Kubernetes objects to compare with, so the
recipe is proven by deploying it (RCP-38). `tests/target.yml` sets test values for the four
parameters and runs one PostgreSQL instance.

`tests/smoke` starts a pod of the Meilisearch image, which carries `curl`.
From there, through the Service `open-archiver` on port 3000, it

- requires `needsSetup` from `/api/v1/auth/status` on the new database
- sets up the first admin through `/api/v1/auth/setup`, which Open
  Archiver writes to PostgreSQL, and requires `needsSetup` false
- logs the admin in and reads `/api/v1/index-admin/overview`, which needs
  Meilisearch with the master key
- gets `/version` of Tika through the Service `open-archiver-tika`
- requires the scheduler's sync job in Valkey
- deletes the pod `open-archiver-0` and logs the admin in again once its
  successor is ready.

Not tested: an ingestion source and the mail it archives, the search
itself, Tika's text extraction, S3 storage and the web UI in a browser.
