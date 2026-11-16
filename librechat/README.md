# librechat

LibreChat v0.8.8, a chat UI for many model providers, on the MongoDB of
the included recipe `mongodb`, with registration closed and without
search, rendered by the kadet-hub `kubernetes` generator 1.16.0 from
LibreChat's Helm chart `librechat` 3.0.0.

Source: `oci://ghcr.io/librechat-ai/librechat-chart/librechat:3.0.0@sha256:5d50ecaf2685295fb5d28da016a964b03610e7897d6e366c0b573086fb23775a`

Level: `deploys`

The chart lives in `helm/librechat` of LibreChat-AI/LibreChat, MIT, and the
project's workflow publishes each `chart-<version>` tag. The recipe runs
the chart's default image `registry.librechat.ai/librechat-ai/librechat:v0.8.8`,
an index for linux/amd64 and linux/arm64. That registry is the project's
name for `ghcr.io/librechat-ai/librechat` and serves the same index.
LibreChat runs as the image's user `node`, UID 1000, and passes the Pod
Security level `restricted`.

## Include

```yaml
classes:
  - recipes.librechat
parameters:
  namespace: librechat
  kapitan:
    vars:
      target: librechat
  applications:
    librechat:
      creds_key: <ref>
      creds_iv: <ref>
      jwt_secret: <ref>
      jwt_refresh_secret: <ref>
    mongodb:
      password: <ref>
```

The recipe includes `recipes.mongodb`. Pin only this recipe in the fetch
inventory. The consumer workflow adds `mongodb` at the digest this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.librechat.creds_key` is `CREDS_KEY`, 64 hexadecimal digits
such as the output of `openssl rand -hex 32`, and
`applications.librechat.creds_iv` is `CREDS_IV`, 32 hexadecimal digits
(`openssl rand -hex 16`). LibreChat encrypts stored credentials with them,
such as API keys that users enter themselves, so keep both for the life of
the database. `applications.librechat.jwt_secret` and
`applications.librechat.jwt_refresh_secret` are `JWT_SECRET` and
`JWT_REFRESH_SECRET`, which sign the logins. A new value logs every user
out. `applications.mongodb.password` is the password of MongoDB's user
`root`, with which LibreChat connects. It goes into `MONGO_URI` unencoded,
so use letters and digits only. Set all of them as refs with the backend
of your choice. Without one of them the compile stops with
`Interpolation key '<key>' not found`.

## The first user

Registration is closed (`ALLOW_REGISTRATION: "false"`), and LibreChat has
no way to create an account from its environment. Create the first user
with LibreChat's script in the running container. LibreChat makes the
first user of a new database an admin.

```sh
kubectl exec -it deployment/librechat-librechat -- npm run create-user -- <email> <name> <username>
```

The script asks for the password and whether the email address counts as
verified. Further users are created the same way.

## Endpoints

The recipe configures no model provider. The target adds LibreChat's
variables to the ConfigMap `librechat-librechat-configenv`, and API keys as
keys of the Secret `librechat-credentials-env` with an `env` entry that
reads each one, as `tests/target.yml` does for an OpenAI-compatible
endpoint:

```yaml
parameters:
  generators:
    kubernetes:
      configs:
        librechat-librechat-configenv:
          data:
            OPENAI_REVERSE_PROXY:
              value: <base URL of the endpoint>
      secrets:
        librechat-credentials-env:
          string_data:
            OPENAI_API_KEY:
              value: <ref>
  components:
    librechat-librechat:
      env:
        OPENAI_API_KEY:
          secretKeyRef:
            name: librechat-credentials-env
            key: OPENAI_API_KEY
```

LibreChat's `librechat.yaml`, for custom endpoints and the interface, is
not part of the recipe. A target can render it as a ConfigMap and mount it
at `/app/librechat.yaml` with `sub_path: librechat.yaml`, which is not
tested. Without it LibreChat logs that the file is missing and runs with
its defaults.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `components.librechat-librechat.image`, tag and digest |
| `librechat.configEnv` | `generators.kubernetes.configs.librechat-librechat-configenv.data.<variable>.value` |
| `global.librechat.env` | `components.librechat-librechat.env.<variable>` |
| `librechat.imageVolume.size`, 10G | `components.librechat-librechat.persistent_volume_claims.librechat-librechat-images.storage` |
| `resources` | `components.librechat-librechat.resources` |
| `ingress` | a route or Ingress of the target to the Service `librechat-librechat` on port 3080, with `DOMAIN_CLIENT` and `DOMAIN_SERVER` set to its URL |
| the MongoDB server, its size and version | `applications.mongodb` and the settings `mongodb`'s README lists |

The pod annotation `checksum/configEnv` is the chart's hash of its
ConfigMap for `tests/values.yaml`. It does not follow a change of the
ConfigMap, so restart the Deployment after one.

The claim `librechat-librechat-images` keeps the images below
`/app/client/public/images`, as the chart's `imageVolume` does. Other
uploads and the logs stay in the container. LibreChat's schedules need
Redis, which the recipe does not render, or `SCHEDULES_SINGLE_PROCESS:
"true"` for a single replica. Without either LibreChat refuses new
schedules and logs an error at every start.

The chart's subcharts are not rendered. MongoDB is the included recipe
`mongodb` in place of Bitnami's chart. Meilisearch, which LibreChat's
conversation search needs, the RAG API with its PostgreSQL for file
search, and Redis are left out. LibreChat's search stays off while
`SEARCH` is unset. A target that runs Meilisearch elsewhere sets `SEARCH`,
`MEILI_HOST` and `MEILI_MASTER_KEY`, the RAG API `RAG_API_URL`, and Redis
`USE_REDIS` and `REDIS_URI`, as described above. The chart's Ingress, the
Langfuse fanout and the HorizontalPodAutoscaler are off. The chart's test
pod `Pod/librechat-librechat-test-connection`, a Helm hook, is left out.

## Proof

`check librechat --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with check
0.16.0. The objects of `mongodb` are applied with the recipe and left out
of the comparison. The remaining differences are of the classes Selector
scheme, Explicit default (the pod's `automountServiceAccountToken: true`)
and Referenced Secret (the Secret `librechat-credentials-env`).

`tests/values.yaml` sets the chart's `lifecycle` to null, because the
chart renders its default `{}` as an empty `lifecycle` on the container,
which the generator does not render. Both mean no hook.

`tests/smoke` requires that the pods pass Pod Security `restricted`. It
starts an OpenAI-compatible stub, busybox's `httpd` with a script that
lists the model `stub` and answers every completion with the same reply,
streamed or not, which `tests/target.yml` configures as the endpoint
`openAI`. It creates the first user with `npm run create-user` as above.
From a pod of the LibreChat image, through the Service
`librechat-librechat` on port 3080, it

- gets `OK` from `/health`
- gets 403 for a registration
- logs in as the user and requires the role `ADMIN`
- requires the model `stub` of the endpoint `openAI` in `/api/models`
- sends a message to `stub` and waits until the conversation holds the
  stub's reply
- deletes the LibreChat and MongoDB pods and, once their successors are
  ready, logs in again and reads the conversation and both messages back.

Not tested: the web UI, a real model provider, `librechat.yaml`, file
uploads, search, and replacing a running Helm release.

## Replacing a Helm release

Not tested.

1. Delete the Deployment `librechat-librechat` with `--cascade=orphan`,
   because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.librechat.*`, so
   Helm forgets the release without deleting its objects.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet. The
   chart's MongoDB, Meilisearch and their claims stay. Move the data of
   the chart's MongoDB into `mongodb` before deleting them.
