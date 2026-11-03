# open-webui

Open WebUI 0.12.5, a web interface and API for chatting with language
models, on SQLite with Valkey for its websockets, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from Open WebUI's Helm chart 17.5.0. Ollama
and OpenAI-compatible endpoints are options.

Source: `oci://ghcr.io/open-webui/helm-charts/open-webui:17.5.0@sha256:93635790db231b584041cd11c3fa0d80e3238d906ab8bf4dcb2bc055ad733527`

Level: `deploys`

The chart comes from [open-webui/helm-charts](https://github.com/open-webui/helm-charts),
tag `open-webui-17.5.0`. Its HTTP repository `https://helm.openwebui.com`
serves the same archive, SHA-256
`50dc7cf3f7fe409d4d85aa044c67bbcdea887b4fd7593a9aaff722fc393aa140`. The
chart is MIT. Open WebUI is under the Open WebUI License, a BSD-3-Clause
license with a fourth clause that forbids changing its branding in
deployments with more than 50 users in 30 days unless the copyright holder
allows it. The recipe ships no Open WebUI code and names the image only.

The recipe renders the StatefulSet `open-webui` with the claim
`open-webui` of 2Gi at `/app/backend/data`, which holds the SQLite
database and uploads, the Service `open-webui` on port 80 and the
ServiceAccount `open-webui-sa`. The included recipe `valkey` carries Open
WebUI's websockets and state shared between workers. The image
`ghcr.io/open-webui/open-webui:0.12.5` is pinned to its index for amd64
and arm64. It is 1643 MB compressed for amd64 and 1481 MB for arm64 (sums
of the layer sizes, MB = 10^6 bytes).

## Include

```yaml
classes:
  - recipes.open-webui
  # Ollama in the same namespace, through the included recipe ollama
  - recipes.open-webui.ollama
  # An OpenAI-compatible endpoint, such as vLLM, SGLang or a hosted API
  - recipes.open-webui.openai
parameters:
  namespace: open-webui
  kapitan:
    vars:
      target: open-webui
  applications:
    open-webui:
      secret_key: <ref>
      openai:
        url: https://llm.example.com/v1
        api_key: <ref>
    valkey:
      password: <ref>
```

Without an option Open WebUI starts with both its Ollama and its OpenAI
API turned off. An admin can add connections in the admin settings.

`recipes.open-webui.ollama` includes the recipe `ollama`, which runs
Ollama on the CPU in the same namespace, and points Open WebUI at
`http://ollama:11434`. `recipes.open-webui.openai` points Open WebUI at
the endpoint `applications.open-webui.openai.url` with the key
`applications.open-webui.openai.api_key`. vLLM and SGLang serve such an
endpoint below `/v1` and are not part of any recipe: they need a GPU and
multi-GB images that the proof on kind cannot run.

## Required parameters

- `applications.open-webui.secret_key`, as a ref. Open WebUI signs its
  logins with it. Without it the image generates a key in each new
  container, so every restart signs every user out.
- `applications.valkey.password`, as a ref, for the included recipe
  `valkey`. It is part of the Redis URL in the Secret `open-webui`, so use
  letters and digits only.
- With `recipes.open-webui.openai`: `applications.open-webui.openai.url`
  and `applications.open-webui.openai.api_key`, the key as a ref.

Without one of them the compile stops with `Interpolation key ... not
found` and that key.

## Signup

Signup is open until the first account signs up, which the chart does
not change. That account becomes admin, and Open WebUI then turns signup
off in its settings (`signup_handler` in `backend/open_webui/routers/auths.py`
of 0.12.5). Whoever reaches the Service first therefore owns the instance,
so create the admin account before others can reach the Service. Later
accounts come from the admin, who can also turn signup back on in the admin
settings. Accounts that sign up then get the role `pending` until the admin
approves them.

Open WebUI copies the backend settings, such as the Ollama and OpenAI URLs
and `ENABLE_SIGNUP`, into its database on the first start, and later
starts keep the database's values (`seed_defaults` in
`backend/open_webui/models/config.py` of 0.12.5). A changed URL in the
target reaches a running instance only through the admin settings.

## Settings

`<c>` stands for `components.open-webui`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `persistence.size` | `applications.open-webui.storage` |
| `persistence.storageClass` | `<c>.persistent_volume_claims.open-webui.storage_class` |
| `extraEnvVars` | `<c>.env`, a mapping of name to value |
| `resources` | `<c>.resources` |
| `service.type` | `<c>.service.type` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `podSecurityContext`, `containerSecurityContext` | `<c>.workload_security_context`, `<c>.security_context` |
| `sso.*` | `<c>.env` with Open WebUI's `OAUTH_*` and `OPENID_*` variables |
| `databaseUrl` | `<c>.env.DATABASE_URL` as a `secretKeyRef`, not tested |

The chart's Pipelines and Ollama subcharts are off in the recipe. Ollama
comes from the option `ollama` instead. The chart's own Redis is replaced
by the included recipe `valkey`. Tika, Terminals, the Ingress, the
HTTPRoute, GKE's ManagedCertificate and S3, GCS or Azure storage are off by
default and not part of the recipe.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check open-webui --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The target
includes both options. `tests/values.yaml` turns the chart's Ollama,
Pipelines and Redis off, points the chart at `ollama` and `valkey`, and
creates the Secret `open-webui` through `extraResources`, as a user would
next to the chart. It gives the Ollama and OpenAI variables through
`extraEnvVars`, in the order the options add them, and sets
`allowPrivilegeEscalation: false` on both containers, because `check`
does not accept the empty `securityContext` that the generator renders on
an init container.

The five objects differ in one way. The StatefulSet and the Service select
on `name`, the chart on `app.kubernetes.io/instance` and `component`, and
both select the same pods. The chart binds no role. The objects of `ollama`
and `valkey` are proven by their own recipes.

`tests/smoke` waits for `/health` through the Service, because the chart
sets no probes. It signs up the first account, which becomes admin, and
requires 403 for a second signup.
It starts an OpenAI-compatible stub, pulls `smollm:135m` into Ollama
through Open WebUI's `/ollama/api/pull`, finds both models in
`/api/models` and gets a chat completion from each through
`/api/chat/completions`. Valkey must hold keys of Open WebUI, and the
admin's token must still work after the pod restarted. It prints how long
the pull and the completion took.

## Replacing a Helm release

Not tested. A release named `open-webui` has the same object names, so the
claim and its data stay.

1. Delete the StatefulSet `open-webui` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.open-webui.*`.
3. Create the Secret values in the target, with the release's
   `WEBUI_SECRET_KEY` if it had one, so existing logins stay valid.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Delete the orphaned pod `open-webui-0` and the chart's Redis, Pipelines
   and Ollama objects, `open-webui-redis`, `open-webui-pipelines` and
   `open-webui-ollama`, with the claim `open-webui-pipelines`.
