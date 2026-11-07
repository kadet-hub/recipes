# kadet-convert

`kadet-convert` converts a Helm chart, rendered with your values, into a
Kapitan project for the kadet-hub `kubernetes` generator. It then proves on
two kind clusters that the project renders the same objects as
`helm template`, with the comparison `check` uses for recipes, and reports
what it could not map. The design and its limits are in
[specs/converter.md](specs/converter.md).

## Running it

From a `check` release tag, with `uvx`:

```sh
uvx --from 'git+https://github.com/kadet-hub/recipes@check-v<version>#subdirectory=check' \
  kadet-convert <chart> --name <release> --namespace <namespace> -f values.yaml --out <dir>
```

`uvx` resolves the exact versions in `check/pyproject.toml` but not
`check/uv.lock`, and installs Kapitan's capped `cryptography`, which only
Kapitan's ref functions use. For the locked environment, run it from a clone
of that tag:

```sh
uv run --locked --project check check/convert.py <chart> --name <release> --namespace <namespace> -f values.yaml --out <dir>
```

`<chart>` is a chart directory or archive, or anything `helm pull` takes:
`oci://<repository>:<version>`, `oci://<repository>@sha256:<digest>`, or a
chart name with `--repo <url> --version <version>`. The release name also
names the converted class. `--no-proof` skips the kind clusters, and
`--node-image` picks the Kubernetes version they run. The clusters are
named `convert-<release>-chart` and `convert-<release>-recipe`;
`--clusters` changes the prefix.

It needs helm, kubectl, kind, Docker, oras and gh on `PATH`. gh verifies the
generator's attestation before the generator runs, as for recipes.

## What you get

`<dir>/project/` is a Kapitan project that `kapitan compile` compiles as it
is:

| Path | Content |
|---|---|
| `inventory/classes/converted/<release>/init.yml` | The objects as generator input: workloads as components, Services, ConfigMaps, Secrets, ServiceAccounts, RBAC and Ingresses under the chart's names |
| `inventory/classes/converted/<release>/secrets.yml` | The data of the chart's Secrets. It is in `.gitignore`: replace each value with a ref that holds the same base64 value |
| `inventory/classes/converted/<release>/vendor/` | The chart's CRDs, copied unchanged |
| `inventory/targets/<release>.yml` | The target with your namespace |
| `lib/kubernetes/` | The generator, pinned by digest and verified |

The values are frozen: the project holds what `helm template` rendered.
To change a value the chart turns into an object or a field, such as
`ingress.enabled`, edit the inventory or convert again.

`<dir>/report.md` puts every rendered object into one class: exact; equal up
to the differences `check` accepts for recipes, such as the generator's own
selector; mapped with differences; not mapped; a hook left out; a CRD
copied. It lists the fields the converter does not map, fields that differ
between two renders (random passwords), renamed RBAC objects and whether
each subject's permissions are equal. Its `Values` section names, for each
chart value, the inventory fields it reached, from `<dir>/value-map.json`.

The exit status is 0 when every object is mapped and equal, 1 when
something is not, and 2 when a command failed.

## Replacing a running release

The converted workloads select their pods by the generator's `name` label.
A selector is immutable, so `kubectl apply` over a running Helm release
fails on them. Delete each Deployment and StatefulSet with
`--cascade=orphan`, delete the release's `sh.helm.release.v1.<release>.*`
Secrets so Helm forgets it, apply the project with
`kubectl apply --server-side --force-conflicts`, and delete the orphaned
ReplicaSets once the new pods are ready. These steps are not tested.
