# ollama

Ollama 0.33.2 on the CPU, which runs language models behind an HTTP API on
port 11434, rendered by the kadet-hub `kubernetes` generator 1.16.0 from the
`ollama` chart 1.79.0 that Open WebUI's chart includes.

Source: `https://otwld.github.io/ollama-helm/ollama:1.79.0@sha256:96d96ad0b422eccd40d8982b4fef834ef4f33a7fb81abfd3fc44ee0ac6e025f4`

Level: `deploys`

Ollama ships no chart. The chart comes from
[otwld/ollama-helm](https://github.com/otwld/ollama-helm), tag
`ollama-1.79.0`, which OTWLD maintains. It is MIT, as Ollama is. The chart
`open-webui` 17.5.0 pins this version as its subchart, so `open-webui`
includes this recipe in its place (DEC-75 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). otwld/ollama-helm has
moved on to 1.94.0, which the recipe does not follow until Open WebUI's
chart does.

The release name `ollama` equals the chart's name, so the Deployment,
Service and ServiceAccount are all `ollama`. Models live in the `emptyDir`
`ollama-data` at `/root/.ollama`, the chart's default, so a new pod starts
without them and pulls each model again.

The image `docker.io/ollama/ollama:0.33.2` is pinned to its index for amd64
and arm64. It carries the CUDA and ROCm libraries, 3383 MB compressed for
amd64 and 2780 MB for arm64 (sums of the layer sizes, MB = 10^6 bytes).
The recipe requests no GPU.

Ollama's API has no authentication. Every pod that reaches the Service can
pull, delete and run models. The Service is a `ClusterIP`.

## Include

```yaml
classes:
  - recipes.ollama
parameters:
  namespace: ollama
  kapitan:
    vars:
      target: ollama
```

## Required parameters

No parameter has to be set.

## Settings

`<c>` stands for `components.ollama`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `persistentVolume.enabled` | `<c>.volumes.ollama-data` as `persistentVolumeClaim` and `<c>.persistent_volume_claims.<claim>.storage` |
| `extraEnv` | `<c>.env`, a mapping of name to value, such as `OLLAMA_KEEP_ALIVE` |
| `resources` | `<c>.resources` |
| `ollama.gpu.enabled` | `<c>.resources.limits` with `nvidia.com/gpu`, not tested |
| `service.type` | `<c>.service.type` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `podSecurityContext`, `securityContext` | `<c>.workload_security_context`, `<c>.security_context` |
| `terminationGracePeriodSeconds` | `<c>.grace_period` |

GPUs are not tested, because kind has none. The chart's model pulls at
start (`ollama.models.pull`), Knative service, Ingress, HTTPRoute, Gateway
and autoscaler are off by default and not part of the recipe. The chart's
Helm test `Pod/ollama-test-connection` is left out.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check ollama --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests.
`tests/values.yaml` keeps the chart's defaults and names the image's
registry host. The three objects differ in two ways. The Deployment and the
Service select on `name`, the chart on `app.kubernetes.io/name` and
`instance`, and both select the same pods. The pod sets
`automountServiceAccountToken: true`, which the chart leaves unset while
its ServiceAccount allows the token. The chart binds no role.

`tests/smoke` requires `Ollama is running` from `/` through the Service
and the image tag's version from `/api/version`. It pulls `smollm:135m`, a
92 MB model, checks the digest of its manifest in `/api/tags` and requires
a reply from `/api/generate` on the CPU. It prints how long the pull and
the generation took.

## Replacing a Helm release

Not tested. A release named `ollama` has the same object names.

1. Delete the Deployment `ollama` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.ollama.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Delete the orphaned ReplicaSet. The new pod starts without the models of
   the old one.
