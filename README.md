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

Recipes are fetched by a separate fetch inventory, `fetch/targets/recipes.yml`,
with one `git` dependency per recipe. Pin `ref` to a full commit SHA of this
repository. `git ls-remote https://github.com/kadet-hub/recipes.git refs/heads/main`
prints the current one.

```yaml
parameters:
  kapitan:
    vars:
      target: recipes
    dependencies:
      - type: git
        source: https://github.com/kadet-hub/recipes.git
        ref: <commit sha>
        subdir: cert-manager
        output_path: inventory/classes/recipes/cert-manager
```

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

Fetch the recipes, then compile:

```sh
kapitan compile --inventory-path fetch --fetch --output-path .
kapitan compile --fetch
```

The first command fetches the recipes into `inventory/classes/recipes/` and
then exits with status 1 and `No such file or directory: .../compiled`,
because the fetch target compiles nothing. The second fetches the generator
the recipe pins into `lib/` and writes the manifests to
`compiled/<target>/manifests/`.

Two commands are needed because Kapitan loads the inventory before it
fetches, so a class cannot be fetched by the inventory that uses it
(kapicorp/kapitan#1638). Publishing recipes through kadet-hub.org, like the
generators, is planned (OQ-3 in the spec).

### Verifying the generator

Kapitan's `--fetch` checks neither the digest nor the attestation of the
generator. The recipe's `init.yml` pins it as
`ghcr.io/kadet-hub/<generator>:<version>@sha256:<digest>`. Verify it as the
[consumers guide](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
describes under "Verifying by hand": `gh attestation verify` the latest
index and the generator's digest, check that the index lists the digest
under that version, `oras pull` it by digest into `lib/<generator>` and run
the second command without `--fetch`. The guide's consumer workflow does
these checks in CI, but has not been tested with a fetch inventory yet.

### Updating

Raise `ref` to a newer commit, delete `inventory/classes/recipes/<name>`
and run both commands again. Without the delete, `--fetch` keeps the old
recipe, and `--force-fetch` copies the new one over it but leaves the files
it removed.

This Renovate custom manager proposes the current commit of `main` for
every recipe in the fetch inventory:

```json
{
  "customManagers": [
    {
      "customType": "regex",
      "managerFilePatterns": ["/^fetch/targets/[^/]+\\.yml$/"],
      "matchStrings": [
        "source: (?<packageName>https://github\\.com/kadet-hub/recipes\\.git)\\n\\s+ref: (?<currentDigest>[0-9a-f]{40})"
      ],
      "depNameTemplate": "kadet-hub/recipes",
      "currentValueTemplate": "main",
      "datasourceTemplate": "git-refs"
    }
  ]
}
```
