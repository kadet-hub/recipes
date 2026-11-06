# litellm

LiteLLM 1.108.0, a proxy that serves one OpenAI-compatible API in front of
Ollama, vLLM and hosted model providers, with models from the inventory,
rendered by the kadet-hub `kubernetes` generator 1.14.0 from LiteLLM's own
Helm chart. The option `postgresql` adds virtual keys.

Source: `oci://ghcr.io/berriai/litellm-helm:1.108.0@sha256:97d9ad3aa28be90cd5f5b9fd47cc72bd76a6054111337bacfd537ee2dd2de2dd`

Level: `deploys`

The chart lives in [BerriAI/litellm](https://github.com/BerriAI/litellm)
below `helm/litellm-helm`, and LiteLLM publishes it with every release at
`oci://ghcr.io/berriai/litellm-helm`, versioned like the release. The recipe
runs `ghcr.io/berriai/litellm:1.108.0`, the chart's `appVersion`, pinned to
its index for amd64 and arm64. LiteLLM and the chart are MIT, except the
directory `enterprise/` of the repository. The container runs as root, as
the chart runs it.

## Include

```yaml
classes:
  - recipes.litellm
parameters:
  namespace: litellm
  kapitan:
    vars:
      target: litellm
  applications:
    litellm:
      master_key: <ref>
      model_list:
        - model_name: smollm
          litellm_params:
            model: ollama_chat/smollm:135m
            api_base: http://ollama:11434
```

Add `recipes.litellm.postgresql` below `recipes.litellm` for virtual keys
and spend tracking. That option includes `recipes.postgresql`. Pin only this
recipe in the fetch inventory. The consumer workflow adds `postgresql` at
the digest this version's index record lists under `includes`. Kapitan's
`--fetch` reads no index, so for a local compile pull it by digest as the
recipe's page on kadet-hub.org shows. `postgresql` requires `cnpg`, so
install `cnpg` first, in a target of its own.

## Required parameters

`applications.litellm.master_key` is the proxy's master key. Every request
without a virtual key sends it as `Authorization: Bearer <key>`, and it is
the only credential that can create virtual keys. LiteLLM's documentation
writes keys with the prefix `sk-`. Set it as a ref with the backend of your
choice. The recipe puts it into the Secret `litellm-masterkey`, key
`masterkey`.

`applications.litellm.model_list` is the proxy's `model_list`, as LiteLLM's
[configuration](https://docs.litellm.ai/docs/proxy/configs) describes it:
the name each model has in the API and, in `litellm_params`, the provider
and model LiteLLM routes it to. The Include snippet routes `smollm` to the
recipe `ollama` in the same namespace.

Without one of them the compile stops with
`Interpolation key '<key>' not found`.

## The option `postgresql`

Without a database the proxy routes requests with the master key only.
`/key/generate` answers 500 with `DB not connected`, so there are no
virtual keys, budgets or spend per key. `recipes.litellm.postgresql`
includes the recipe `postgresql` and sets `DATABASE_URL` from the key `uri`
of its Secret `postgresql-cluster-app`. The proxy creates and migrates its
tables at start.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `components.litellm.image`, tag and digest |
| `masterkey` | `applications.litellm.master_key` |
| `proxy_config.model_list` | `applications.litellm.model_list` |
| `proxy_config` | `applications.litellm.config`, rendered as `config.yaml` |
| `logLevel` | `components.litellm.env.LITELLM_LOG` |
| `envVars`, `extraEnvVars` | `components.litellm.env.<variable>` |
| `replicaCount` | `components.litellm.replicas` |
| `resources` | `components.litellm.resources` |
| `service.type` | `components.litellm.service.type` |
| `podAnnotations` | `components.litellm.pod_annotations` |
| `nodeSelector`, `tolerations`, `affinity` | `components.litellm.node_selector`, `components.litellm.tolerations`, `components.litellm.affinity` |

A provider's key goes into the container's environment from a Secret of
the target, such as `components.litellm.env.OPENAI_API_KEY` with a
`secretKeyRef`, and the model names it as
`api_key: os.environ/OPENAI_API_KEY`.

Further sections of `config.yaml`, such as `litellm_settings` or
`router_settings`, are keys of `applications.litellm.config`. The recipe
writes the mapping with Kapitan's resolver `yaml`, with sorted keys.

The pod annotation `checksum/config` is the chart's hash for the values in
`tests/values.yaml`. It does not change with `applications.litellm.config`,
and LiteLLM reads `config.yaml` only at start, so after changing the models
restart the pod with `kubectl rollout restart deployment/litellm`.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's tests run only inside `helm test`. `tests/smoke` checks more on
the installed recipe. They are not rendered:
`Pod/litellm-test-connection`, `Pod/litellm-env-test`.

The chart's own PostgreSQL and Redis, both Bitnami subcharts, and its
migrations Job are not part of the recipe (DEC-236).

## Proof

`check litellm --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests.
`tests/target.yml` includes the option `postgresql`, and
`tests/values.yaml` turns off the chart's database and migrations Job,
gives `DATABASE_URL` from the Secret of the recipe `postgresql`, and sets
the master key and the model list of the target. Its one model,
`smoke`, answers with LiteLLM's `mock_response`, so the proof calls no
provider. The four objects differ in two ways, both of classes `check`
accepts. The Deployment and the Service select on `name`, the chart on
`app.kubernetes.io/name` and `instance`, and both select the same pods.
The pod sets `automountServiceAccountToken: true`, which the chart leaves
unset while the ServiceAccount `default` allows the token. The chart binds
no role.

`tests/smoke` requires a healthy proxy with its database connected from
`/health/readiness` through the Service. With the master key it requires
the model healthy from `/health`, only `smoke` from `/v1/models`, and the
mock's reply from `/v1/chat/completions`. It gets 401 from both without a
key. It creates a virtual key, gets the reply with it, gets 401 with a
wrong key, and waits for spend on the virtual key in `/key/info`. After
the pod was replaced, the virtual key still gets the reply.

## Replacing a Helm release

Not tested.

1. Delete the Deployment `litellm` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.litellm.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
