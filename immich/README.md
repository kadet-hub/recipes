# immich

Immich v3.3.5, the photo and video management server, with its machine
learning service on the CPU and a library claim, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from Immich's Helm chart 0.13.4. The database
is the included recipe `postgresql` with pgvector, the queue `valkey`.

Source: `oci://ghcr.io/immich-app/immich-charts/immich:0.13.4@sha256:9957cfe69ed64f4d4550f39b369c6cf3b2b040bb4d9a5abdced9a60c1153093f`

Level: `deploys`

The chart comes from [immich-app/immich-charts](https://github.com/immich-app/immich-charts),
tag `immich-0.13.4`. It builds on the bjw-s common library 5.2.1. Chart and
Immich are AGPL-3.0, and this recipe contains no text of the chart. The
chart's default image is Immich v3.2.0, which GHSA-q89f-h332-8q2h, an
authenticated code execution through SVG uploads, probably affects. The
recipe runs `ghcr.io/immich-app/immich-server` and
`ghcr.io/immich-app/immich-machine-learning` v3.3.5, built for amd64 and
arm64. `postgresql` requires `cnpg`, so install `cnpg` first, in a target
of its own. Applied together with its PostgreSQL Cluster, the server
restarts until the database answers. Applying the Cluster first and
waiting for it to be ready avoids that.

## Include

```yaml
classes:
  - recipes.immich
parameters:
  namespace: immich
  kapitan:
    vars:
      target: immich
  applications:
    valkey:
      password: <ref>
```

The recipe includes `recipes.postgresql` with its options
`recipes.postgresql.pgvector` and `recipes.postgresql.earthdistance`, and
`recipes.valkey`. Pin `postgresql` and `valkey` in the fetch inventory next to this recipe, each as an `oci` dependency at the
digest this version's index record lists under `includes`, with
`output_path: inventory/classes/recipes/<recipe>`. The recipe's page on
kadet-hub.org shows the whole fetch inventory.

## Required parameters

`applications.valkey.password`, which the included recipe `valkey`
requires, is the password of Valkey's user `default`, with which Immich
connects to its job queue. Set it as a ref with the backend of your choice.
Without it the compile stops with
`Interpolation key 'applications.valkey.password' not found`. Immich and
`postgresql` require no parameter. The first user who signs up through the
web interface or `/api/auth/admin-sign-up` becomes the admin, so sign up
before the server is reachable by others.

## Settings

`<s>` stands for `components.immich-server`, `<m>` for
`components.immich-machine-learning` and `<d>` for
`applications.immich.component_defaults`, which both components take.

| Chart value | Inventory |
|---|---|
| `controllers.main.containers.main.image.tag` | `<s>.image` and `<m>.image`, tag and digest |
| the library claim of `immich.persistence.library.existingClaim`, 10Gi | `applications.immich.library_storage` |
| `server.controllers.main.containers.main.env` | `<s>.env` |
| `machine-learning.controllers.main.containers.main.env` | `<m>.env` |
| `machine-learning.persistence.cache`, an emptyDir | `<m>.volumes.cache` |
| `controllers.main.containers.main.resources` | `<s>.resources`, `<m>.resources` |
| `defaultPodOptions.nodeSelector`, `.tolerations`, `.affinity` | `<d>.node_selector`, `<d>.tolerations`, `<d>.affinity` |

`DB_VECTOR_EXTENSION=pgvector` keeps Immich on pgvector, which the option
`pgvector` of `postgresql` creates. `DB_SSL_MODE=require` encrypts the
connection to PostgreSQL without verifying CloudNativePG's certificate.
Immich connects as the database owner `app`, which is no superuser. The
options of `postgresql` create `vector` and `earthdistance`, which only a
superuser may create, when CloudNativePG creates the Cluster. Immich's
nightly database backup runs `pg_dump` as `app` and works. A restore
through Immich replays the dump as `app`, whose `DROP EXTENSION` lines for
`vector` and `earthdistance` need a superuser, so expect it to fail. It is
not tested. Moving
to VectorChord later needs an image with VectorChord, `vchord.so` in
`shared_preload_libraries` and `CREATE EXTENSION vchord CASCADE` as
superuser, which `postgresql` does not render. Immich then rebuilds its
vector indexes `clip_index` and `face_index`.

Machine learning downloads its models into `/cache` when a job first
needs them, again on every new pod: CLIP and face models from Hugging Face,
OCR models from ModelScope, about 2.2 GB together, at the unpinned `main`
revision. A claim for `/cache` keeps them. GPU images and hardware acceleration are not tested.

The chart's Ingress, its ServiceMonitors behind `immich.metrics.enabled`
and the configuration file behind `immich.configuration` are off by
default and not part of the recipe.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check immich --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with
`cnpg` installed first. The objects of `postgresql` and `valkey` are left
out of the comparison and applied with the recipe. The chart expects the
library claim to exist, so `tests/values.yaml` creates `immich-library`
through the library's `rawResources`, and `check` compares it with the
recipe's claim. The Deployments and Services select on `name`, the chart on
`app.kubernetes.io/name`, `instance` and `controller`, and both select the
same pods. The ServiceAccounts set `automountServiceAccountToken: true`,
the API default the chart leaves unset. Containers carry an empty
`securityContext` and are named after their component. `tests/target.yml`
runs one PostgreSQL instance.

`tests/smoke` gets `pong` from `/api/server/ping` and from machine
learning's `/ping` through their Services and requires that
`/api/server/version` reports the Deployment's image tag. It signs up the
admin, checks that a wrong password gets 401, logs in, uploads a JPEG
through `/api/assets` and reads back its details with its SHA-1, the
original byte for byte and the thumbnail, which a job queued in Valkey
creates. Every connection of `app` to PostgreSQL must use TLS. It does not
wait for the machine learning jobs.

## Replacing a Helm release

Not tested. A release named `immich` has the same object names. Its data
is in the PostgreSQL that its `DB_*` variables name, which this recipe does
not read, and on the claim of its `existingClaim`. Moving the database to
the Cluster of `postgresql` is not covered here.

1. Name the release's claim in `<s>.volumes.data.persistentVolumeClaim.claimName`
   and set `<s>.persistent_volume_claims` to `~` in a class included after
   the recipe, or give the claim the name `immich-library`.
2. Delete the Deployments `immich-server` and `immich-machine-learning`
   with `--cascade=orphan`, because their selectors change.
3. Delete the release's Helm secrets `sh.helm.release.v1.immich.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once the recipe's pods are ready, delete the orphaned ReplicaSets.
