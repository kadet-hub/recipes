# paperless-ngx

Paperless-ngx 3.4.1, a document management system with OCR, rendered by the
kadet-hub `kubernetes` generator 1.14.0 from its Docker Compose file for
PostgreSQL. The database is the included recipe `postgresql`, the task
queue `valkey`. The option `ai` adds paperless-ai.

<!-- renovate: tag=v3.4.1 -->
Source: `https://github.com/paperless-ngx/paperless-ngx/blob/b67cfdf3fdfcde4883c4ac136c8545835f679d21/docker/compose/docker-compose.postgres.yml@sha256:85206b8ae6cd74db70998de6479b4c1f7b50c077772a1af2c026c9ecb35b689c`

Level: `deploys`

The commit is the tag `v3.4.1`. The compose file and the image are
GPL-3.0, and the recipe copies no text from them. `postgresql` requires
`cnpg`, so install `cnpg` first, in a target of its own. The image starts
as root and runs paperless-ngx as the user `paperless`, UID 1000, so the
target's namespace needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.paperless-ngx
  - recipes.paperless-ngx.ai   # paperless-ai, optional
parameters:
  namespace: paperless-ngx
  kapitan:
    vars:
      target: paperless-ngx
  applications:
    paperless-ngx:
      secret_key: <ref>
      ai:
        user: <paperless-ngx user>
        token: <ref>
        url: <endpoint>
        model: <model>
        api_key: <ref>
        jwt_secret: <ref>
    valkey:
      password: <ref>
```

Fetch `postgresql` and `valkey` at the same commit as this recipe, each
with a `git` dependency of its own with `subdir: <recipe>` and
`output_path: inventory/classes/recipes/<recipe>`.

## Required parameters

`applications.paperless-ngx.secret_key` signs paperless-ngx's sessions.
Paperless-ngx refuses to start with the compose file's `change-me`.
`applications.valkey.password`, which the included recipe `valkey`
requires, is written into `PAPERLESS_REDIS` as it is, so it must not
contain characters a URL reserves, such as `@`, `/`, `:` or `?`. Set both
as refs with the backend of your choice.

With the option `ai`, also set these. Their values must not contain `=`
or line breaks. paperless-ai reads its settings file line by line and
drops what follows a second `=` in a line.

- `applications.paperless-ngx.ai.user`, the paperless-ngx user that
  paperless-ai acts as, and `applications.paperless-ngx.ai.token`, that
  user's API token from its profile in paperless-ngx, as a ref;
- `applications.paperless-ngx.ai.url`, an OpenAI-compatible endpoint up to
  `/v1`, such as `https://api.openai.com/v1` or Ollama's
  `http://<host>:11434/v1`, `applications.paperless-ngx.ai.model`, and
  `applications.paperless-ngx.ai.api_key`, as a ref, with any value for an
  endpoint without keys;
- `applications.paperless-ngx.ai.jwt_secret`, as a ref, which signs the
  logins of paperless-ai's web interface. Unset, paperless-ai uses a fixed
  string.

Without one of them the compile stops with
`Interpolation key '<key>' not found`.

## Settings

| Setting | Inventory |
|---|---|
| paperless-ngx version | `components.paperless-ngx.image`, tag and digest |
| `PAPERLESS_URL`, required once paperless-ngx is reached under a domain | `components.paperless-ngx.env.PAPERLESS_URL` |
| `PAPERLESS_TIME_ZONE`, `PAPERLESS_OCR_LANGUAGE`, `PAPERLESS_OCR_LANGUAGES` and the other variables of `docker-compose.env` | `components.paperless-ngx.env.<variable>` |
| `PAPERLESS_ADMIN_USER` and `PAPERLESS_ADMIN_PASSWORD`, a superuser created at start | `components.paperless-ngx.env.<variable>`, the password with `secretKeyRef` |
| size of the claims `data`, `media`, `export` and `consume`, `1Gi` each | `components.paperless-ngx.volume_claims.<claim>.spec.resources.requests.storage` |
| resources | `components.paperless-ngx.resources` |
| the Cluster and its database | `applications.postgresql`, which `postgresql`'s README lists |
| paperless-ai version | `components.paperless-ngx-ai.image`, tag and digest |
| size of paperless-ai's claim `data`, `1Gi` | `components.paperless-ngx-ai.volume_claims.data.spec.resources.requests.storage` |

The Service `paperless-ngx` is a ClusterIP Service on port 8000. The
compose file publishes that port on the host. Here an Ingress or Gateway
in the target exposes it. The compose file creates no account.
Paperless-ngx asks for a superuser on the first visit of its web
interface, or creates one from `PAPERLESS_ADMIN_USER`.

`consume` is the folder paperless-ngx watches for new documents, and
`export` the one its document exporter writes backups to. In compose both
are folders next to the compose file on the host. Here they are claims, so
put files in with `kubectl cp` or mount storage that other systems reach,
such as a scanner's network share, in their place. The consumer reads as
UID 1000, and `kubectl cp` keeps a file's owner and mode, so a file must be
readable by others, such as with mode 644.

## The option `ai`

[paperless-ai](https://github.com/clusterzx/paperless-ai) 3.0.9, MIT,
analyzes paperless-ngx's documents with an LLM and sets their title, tags
and correspondent. The option renders the StatefulSet `paperless-ngx-ai`
with the claim `data`, the Service `paperless-ngx-ai` on port 3000 and the
Secret `paperless-ngx-ai`, mounted as paperless-ai's settings file
`/app/data/.env`. paperless-ai reads its settings only from that file,
which its web setup writes otherwise. The file sets the API of the Service
`paperless-ngx`, the provider `custom` for an OpenAI-compatible endpoint
and the values under Required parameters.

The file is read-only, so the settings page and the web setup cannot
save. Change a setting in the target instead, by replacing
`components.paperless-ngx-ai.secrets.settings.string_data.env.value`, the
whole file, with further variables such as `SCAN_INTERVAL` or `TAGS`. The
web setup creates the login user only after it has written the file, so
the web interface has no user. The automatic processing of new documents
runs without one.

paperless-ai checks the token and the endpoint at start, with one chat
completion, and retries every 5 seconds up to 60 times. After 60 failed
tries it stays unconfigured until the pod restarts, so restart it when
paperless-ngx came up later. Once configured, it analyzes the documents at
start and every 30 minutes. The readiness probe is the image's
`HEALTHCHECK`, `/health`, which checks only paperless-ai's own database.

`/setup` answers without a login. A `POST` to it points paperless-ai's
API client at the URL it names until the pod restarts, so let only the
clients that need it reach port 3000.

The amd64 image is 4.3 GiB compressed, as it carries PyTorch, and the
arm64 image 0.6 GiB. On start paperless-ai downloads two models from
Hugging Face, so the pod needs access to it. The image sets no user, so it
runs as root, without capabilities and privilege escalation, as
paperless-ai's own compose file runs it.

## Mapping

The service `webserver` becomes the component `paperless-ngx`. `db` and
`broker` become the included recipes `postgresql` and `valkey`, and
paperless-ngx reaches them through the Services `postgresql-cluster-rw` and
`valkey` in place of `db` and `broker`.

| Compose | Recipe |
|---|---|
| service `webserver` | StatefulSet `paperless-ngx`, Service `paperless-ngx` on port 8000, Secret `paperless-ngx` with `PAPERLESS_SECRET_KEY` |
| `ghcr.io/paperless-ngx/paperless-ngx:latest` | `ghcr.io/paperless-ngx/paperless-ngx:3.4.1@sha256:1a08d8dfc2b51a08de09652dd86ad4d0c611c362382f944533ad38b73125fbc4`, which `latest` was at migration |
| service `db`, `postgres:18` with the database, user and password `paperless` | the included recipe `postgresql`, PostgreSQL 18.6 on CloudNativePG. Paperless-ngx reads the host, database, user and the generated password from the Secret `postgresql-cluster-app`. |
| service `broker`, `valkey:9-alpine` without a password | the included recipe `valkey`, Valkey 9.1.2 with the password of the ACL user `default` from the Secret `valkey-auth` |
| `PAPERLESS_REDIS: redis://broker:6379` | `redis://:$(VALKEY_PASSWORD)@valkey:6379`, the password from `valkey-auth` |
| `PAPERLESS_DBHOST: db` | from the Secret `postgresql-cluster-app`, with `PAPERLESS_DBNAME`, `PAPERLESS_DBUSER` and `PAPERLESS_DBPASS` |
| `env_file: docker-compose.env`, which sets `PAPERLESS_SECRET_KEY=change-me` | `applications.paperless-ngx.secret_key` in the Secret `paperless-ngx` |
| volumes `data` and `media` | claim templates `data` and `media`, `ReadWriteOnce`, `1Gi` |
| bind mounts `./export` and `./consume` | claim templates `export` and `consume`, `ReadWriteOnce`, `1Gi` |
| the image's `HEALTHCHECK`, `curl` on port 8000 every 30s, timeout 10s, 5 retries | readiness probe with the same values |
| port `8000:8000` | Service port 8000, `ClusterIP` |
| `depends_on`, `restart: unless-stopped` | not rendered. paperless-ngx restarts until the database and Valkey answer. |

`.env` next to the compose file sets only `COMPOSE_PROJECT_NAME`, which
names the compose project and does not reach the containers.

## Proof

`check paperless-ngx --level deploys` with `tests/target.yml`, on kind for
each Kubernetes minor CI tests, with `cnpg` installed first. The objects
of `postgresql` and `valkey` are applied with the recipe. A compose file
has no Kubernetes objects to compare with, so the recipe is proven by
deploying it (RCP-38). `tests/target.yml` sets a secret key, runs one
PostgreSQL instance and includes the option `ai`. It adds two components
that only the proof runs: `paperless-ngx-llm`, busybox's `httpd` with a
script that gives every chat completion the same reply, and the Job
`paperless-ngx-token`, which creates the superuser `admin` and the API
token that the option's settings name once paperless-ngx has migrated its
database. The script's reply names the title `tagged by paperless-ai`.

`tests/smoke` copies a PDF into the claim `consume` and finds the document
by its text through `/api/documents/` on the Service's port 8000 as
`admin`, which needs the consumer, the task queue in Valkey, the database
and the claim `media`. It then restarts `paperless-ngx-ai`, because
paperless-ai may have given up on the API before paperless-ngx answered,
reaches `/health` through its Service and finds the document under the
title `tagged by paperless-ai`. That needs paperless-ai to read the
document with the token, call the endpoint and write the title back.

Not tested: a real LLM and what it answers, paperless-ai's web interface
and the export directory.
