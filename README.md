# kadet-hub recipes

Third-party Kubernetes applications rebuilt from their Helm charts or Docker
Compose files, or designed on the project's image where it ships neither, as
Kapitan inventory classes for the kadet-hub generators. `check` proves each
against its chart or, for a compose file or an image, by deploying it.
The design is in [docs/specs/recipes.md](docs/specs/recipes.md).

## Using a recipe

These steps were tested with Kapitan 0.36.3 and the omegaconf backend,
using `kapitan` as:

```sh
uv run --with 'kapitan[omegaconf,reclass-rs]==0.36.3' --with omegaconf==2.4.0.dev4 --with oras kapitan
```

omegaconf stays on 2.4.0.dev4 because later releases removed
`ListMergeMode` (kapicorp/kapitan#1621). `oras` is needed for the generator
the recipe pins as an `oci` dependency.

Select the backend in `.kapitan`:

```yaml
global:
  inventory-backend: omegaconf
```

reclass and reclass-rs do not resolve the recipes, which use omegaconf's
interpolations and resolvers (DEC-191 in
[docs/specs/recipes.md](docs/specs/recipes.md)). A recipe's `recipe.yaml`
lists the backends it resolves on and the parameters a target must set.

Recipes are fetched by a separate fetch inventory, `fetch/targets/recipes.yml`,
with one `oci` dependency per recipe your targets include, pinned by version
and digest. The recipe's page on [kadet-hub.org](https://kadet-hub.org/recipes/)
shows the entry for its latest version:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/cert-manager:1.0.3@sha256:99d27b9b0ed0afa330d48e1b12cc0bee25f37c5a4b5129ba07a68dfe5063bbef
        output_path: inventory/classes/recipes/cert-manager
```

The consumer workflow of the
[consumers guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md),
section "Recipes", adds the recipes a pinned recipe includes at the digests
its index record lists, and verifies them in CI. The guide also has the
verification steps by hand. A commit of `main` that is not released yet can be
fetched as a `git` dependency with `ref` set to its full SHA, `subdir` to
the recipe and the same `output_path`.

Your target, for example `inventory/targets/cert-manager.yml`, includes the
recipe as `recipes.<name>` and its options as `recipes.<name>.<option>`, and
sets `namespace` and `kapitan.vars.target`. Anything the recipe sets can be
overridden here. The recipe's README lists its options and settings.

```yaml
classes:
  - recipes.cert-manager
  - recipes.cert-manager.crds
parameters:
  namespace: cert-manager
  kapitan:
    vars:
      target: cert-manager
  components:
    cert-manager:
      replicas: 2
      args:
        verbosity: --v=4
```

Pull each recipe by digest as the consumers guide shows under "Verifying a
recipe by hand", or fetch the pinned ones with Kapitan. Kapitan's fetch
reads no index, so pull the recipes they include by digest in either case,
as the recipe's page shows. Then compile:

```sh
kapitan compile --inventory-path fetch --force-fetch --output-path .
kapitan compile --fetch
```

The first command fetches the recipes into `inventory/classes/recipes/` and
then exits with status 1 and `No such file or directory: .../compiled`,
because the fetch target compiles nothing. It verifies nothing. The second
fetches the generator the recipe pins into `lib/` and writes the manifests
to `compiled/<target>/manifests/`.

Two commands are needed because Kapitan loads the inventory before it
fetches, so a class cannot be fetched by the inventory that uses it
(kapicorp/kapitan#1638).

### Verifying the generator

Kapitan's `--fetch` checks neither the digest nor the attestation of the
generator. [krab](https://github.com/kapicorp/krab) checks the digest: it
writes nothing when the manifest or a layer does not match the pinned
`sha256`. It does not check the attestation either. The recipe's `init.yml`
pins it as
`ghcr.io/kadet-hub/<generator>:<version>@sha256:<digest>`. Verify it as the
[consumers guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
describes under "Verifying by hand": `gh attestation verify` the latest
index and the generator's digest, check that the index lists the digest
under that version, `oras pull` it by digest into `lib/<generator>` and run
the second command without `--fetch`. The guide's consumer workflow does
these checks in CI, but has not been tested with a fetch inventory yet.

### Updating

Change version and digest of the recipe, delete
`inventory/classes/recipes/<name>` and the directories of the recipes it
includes, pull those at the digests the new record lists and run both
commands again. `--force-fetch` copies the new version over the
old one but leaves the files it removed.

The kadet-hub Renovate preset updates the recipe pins in `fetch/` from
[kadet-hub/renovate-config#21](https://github.com/kadet-hub/renovate-config/pull/21)
on, one pull request per recipe. With only the recipes your targets include
pinned, each update is complete, because the consumer workflow takes the
included recipes from the new record
([kadet-hub/registry#536](https://github.com/kadet-hub/registry/pull/536)).

## Converting your own chart

`kadet-convert` turns a chart and your values file into a Kapitan project
for the `kubernetes` generator and proves with `check`'s comparison that it
renders the same objects as `helm template`:

```sh
uvx --from 'git+https://github.com/kadet-hub/recipes@check-v<version>#subdirectory=check' \
  kadet-convert oci://ghcr.io/stefanprodan/charts/podinfo:6.17.0 \
  --name podinfo --namespace podinfo -f values.yaml --out podinfo
```

It needs helm, kubectl, kind, Docker, oras and gh, as `check` does. Usage
and the report are in [docs/convert.md](docs/convert.md), the design in
[docs/specs/converter.md](docs/specs/converter.md).

## Adding a recipe

The `to-recipe` skill of the `kapitan-recipes` plugin
([Moep90/agent-skills](https://github.com/Moep90/agent-skills)) migrates a
chart, a Kustomize base, a compose file or a published image into a recipe
directory and proves it with the pinned `check`. Before opening a pull
request, run in a clone of this repository:

```sh
uv run --locked --project check check/check.py lint <name>
uv run --locked --project check check/check.py <name> --level renders
uv run --locked --project check check/check.py <name> --level deploys
```

`renders` and `deploys` need Docker, kind and kubectl. Skip `deploys` for a
recipe at level `renders`. For a recipe at level `migrates`, run
`--level migrates` in its place, which also installs the chart with helm 4.
A recipe whose `Requires:` line names `gateway-api` needs
cloud-provider-kind, which touches every kind cluster on the host, so prove
that part in CI.

The rules `check lint` and the registry gate apply are in
[docs/specs/recipes.md](docs/specs/recipes.md): the README lines and the
300-character description (RCP-23, RCP-32), the shipped files and their
licenses (RCP-33, RCP-42), generator pins by digest, and `recipe.yaml`
against the README and Kapitan (RCP-260 to RCP-263).
[CONTRIBUTING.md](CONTRIBUTING.md) describes the spec change a recipe
starts with, and how CI and the review take a pull request to the merge.

## Security

Report vulnerabilities privately, as [SECURITY.md](SECURITY.md) describes.
