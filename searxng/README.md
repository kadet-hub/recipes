# searxng

SearXNG, a metasearch engine that merges the results of other search
engines without tracking its users, rendered by the kadet-hub `kubernetes`
generator 1.14.0 from the Docker Compose file of the SearXNG repository.
Valkey is the included recipe `valkey`.

<!-- renovate: branch=master -->
Source: `https://github.com/searxng/searxng/blob/cccbc9e158b0ac3bb2158e9841a647a5bec57b57/container/docker-compose.yml@sha256:0e56d5fa968a06e441353261f3134e7cea620c8a81d45a890842aef6c4d3ee11`

Level: `deploys`

SearXNG has no releases. Every commit on `master` is published as an image
tagged `<date>-<commit>`, and the pinned commit is the one the image
`2026.11.2-cccbc9e15` was built from. The compose file used to live in
searxng/searxng-docker, which is archived and points to `container/` of
searxng/searxng. The compose file and the image are AGPL-3.0-or-later.
The image sets no user, so SearXNG runs as root and the target's namespace
needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.searxng
parameters:
  namespace: searxng
  kapitan:
    vars:
      target: searxng
  applications:
    searxng:
      secret_key: <ref>
    valkey:
      password: <ref>
```

Fetch `valkey` at the same commit as this recipe, with a `git` dependency
of its own with `subdir: valkey` and
`output_path: inventory/classes/recipes/valkey`.

## Required parameters

`applications.searxng.secret_key` is SearXNG's `server.secret_key`, which
signs the URLs of its image proxy. SearXNG refuses to start with
`ultrasecretkey`, the value in the image's settings template.
`applications.valkey.password`, which the included recipe `valkey`
requires, is written into `SEARXNG_VALKEY_URL` as it is, so it must not
contain characters a URL reserves, such as `@`, `/`, `:` or `?`. Set both
as refs with the backend of your choice. Without one of them the compile
stops with `Interpolation key '<key>' not found`.

## Settings

| Setting | Inventory |
|---|---|
| SearXNG version | `components.searxng.image`, tag and digest |
| `settings.yml`, such as `search.formats` for the JSON API, `general.instance_name` or `server.limiter` | `components.searxng.config_maps.config.data.settings.yml.value`, the whole file |
| settings with an environment variable, such as `SEARXNG_BASE_URL` or `SEARXNG_LIMITER`, and the `GRANIAN_*` options of the web server | `components.searxng.env.<variable>` |
| size of the claim `core-data`, `1Gi` | `components.searxng.volume_claims.core-data.spec.resources.requests.storage` |
| resources | `components.searxng.resources` |
| Valkey's configuration | `applications.valkey.config`, which `valkey`'s README lists |

`settings.yml` holds the settings of the image's template,
`use_default_settings: true` and `server.image_proxy: true`, and SearXNG's
defaults apply to the rest. The template enables only the format `html`, so
`/search?format=json` answers 403. Add `json` to `search.formats` in the
target's file to use the JSON API, as `tests/target.yml` does. The file is
mounted at `/etc/searxng` with the other files SearXNG reads there, such as
`limiter.toml`, as further keys of the ConfigMap. Leave `secret_key` out of
the file, because `SEARXNG_SECRET` overrides it. At start the image's
entrypoint tries to give `/etc/searxng` to the user `searxng` and logs a
`Read-only file system` line for each file of the ConfigMap. SearXNG runs
as root, reads the files and starts.

The Service `searxng` is a ClusterIP Service on port 8080. The compose
file publishes that port on the host, and SearXNG's documentation asks for
a reverse proxy in front of a public instance. Here an Ingress or Gateway
in the target exposes it, and `SEARXNG_BASE_URL` names its public URL. The
limiter, SearXNG's bot protection, is off as in the template. It needs
Valkey, which the recipe connects, and the proxy's addresses in
`botdetection.trusted_proxies` of `limiter.toml`.

SearXNG checks the connection to Valkey once at start. If Valkey did not
answer then, SearXNG logs `can't connect valkey DB` and runs without it
until the pod restarts. Restart it with
`kubectl delete pod searxng-0` in that case.

## Mapping

The service `core` becomes the component `searxng`. `valkey` becomes the
included recipe `valkey`, whose Service keeps the compose service's name
`valkey`.

| Compose | Recipe |
|---|---|
| service `core` | StatefulSet `searxng`, Service `searxng` on port 8080, ConfigMap `searxng` with `settings.yml`, Secret `searxng` with `SEARXNG_SECRET` |
| `docker.io/searxng/searxng:${SEARXNG_VERSION:-latest}` | `docker.io/searxng/searxng:2026.11.2-cccbc9e15@sha256:892ed5710603e38f9dc201e6a0b2f3f14dbdb8108edcadac30e55b165c979fb7`, which `latest` was at migration |
| port `${SEARXNG_PORT:-8080}:${SEARXNG_PORT:-8080}` with an optional `SEARXNG_HOST` | Service port 8080, `ClusterIP` |
| `env_file: ./.env`, which the documentation copies from `.env.example` | nothing. Every line of `.env.example` is a comment. |
| bind mount `./core-config/` at `/etc/searxng/`, which the entrypoint fills from `settings.template.yml` with a random `secret_key` | ConfigMap `searxng` at `/etc/searxng`, with the template's settings without `secret_key` |
| the random `secret_key` | `SEARXNG_SECRET` from `applications.searxng.secret_key` in the Secret `searxng` |
| the bind mount's SELinux option `:Z` | not rendered |
| volume `core-data` at `/var/cache/searxng/` | claim template `core-data`, `ReadWriteOnce`, `1Gi` |
| service `valkey`, `valkey:9-alpine` with `--save 300 1 --save 60 1000 --loglevel warning` and the volume `valkey-data` | the included recipe `valkey`: Valkey 9.1.2 with `appendonly yes`, the claim `valkey` and the password of the ACL user `default` from the Secret `valkey-auth` |
| no Valkey URL in the settings template | `SEARXNG_VALKEY_URL` set to `valkey://:$(VALKEY_PASSWORD)@valkey:6379/0`, the password from `valkey-auth` |
| `restart: always`, `container_name`, the project `name: searxng` | not rendered |

The settings come from `container/settings.template.yml` at the pinned
commit, SHA-256
`32d2844f5fcedf74e4f5eb80b0a32a65641beb3f3c244af505e3c6fbfa68017b`.
`.env.example` has the SHA-256
`55a210b9a6433bfc8260d7fdd5581edcccd17f42daebc29002677167fb0c674a`.

## Proof

`check searxng --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests. The objects of `valkey` are applied with the
recipe. A compose file has no Kubernetes objects to compare with, so the
recipe is proven by deploying it (RCP-38). `tests/target.yml` sets a
secret key and the Valkey password, and adds the format `json` to the
settings.

`tests/smoke` restarts SearXNG once Valkey is ready, because SearXNG
checks the connection only at start. Through the Service's port 8080 it
expects `OK` from `/healthz` and searches for `kubernetes` with
`format=json`. The response must name the query and carry a list of
results, which is empty when the search engines do not answer. It then
loads the start page and finds the limiter's link token
`SearXNG_limiter.token` in Valkey, which SearXNG writes there through
`SEARXNG_VALKEY_URL`.

Not tested: the results of the search engines, the image proxy and the
limiter.
