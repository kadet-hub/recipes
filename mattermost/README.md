# mattermost

Mattermost Team Edition 12.0.2, a team chat server with channels, direct
messages and file sharing, with its files on a claim, rendered by the
kadet-hub `kubernetes` generator 1.16.0 from Mattermost's Helm chart
`mattermost-team-edition` 6.6.111. The database is the included recipe
`postgresql`.

Source: `https://helm.mattermost.com/mattermost-team-edition:6.6.111@sha256:ec3f1f44bd767ee25a4e3a32270ebcce428aafa2fd4d0c6247a1a41dc7e61851`

Level: `deploys`

The chart comes from [mattermost/mattermost-helm](https://github.com/mattermost/mattermost-helm),
tag `mattermost-team-edition-6.6.111`, and is Apache-2.0. It is published
only in that HTTP repository and as a release asset, so the digest is the
SHA-256 of the archive its `index.yaml` lists. The chart's README marks it
as no longer supported and points to the Mattermost Operator, for which no
kadet-hub generator exists yet. Mattermost still publishes a chart version
with every server release (DEC-290 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
The ConfigMap of the chart's Helm test carries the chart's script, with its
license in `mattermost.yml.LICENSE`.

The recipe runs `docker.io/mattermost/mattermost-team-edition:12.0.2`,
Mattermost's free edition from the open source part of
mattermost/mattermost, built for amd64 only. Team Edition has no OpenID
Connect. Its only SSO provider is GitLab. `postgresql` requires `cnpg`, so
install `cnpg` first, in a target of its own.

`tests/values.yaml` changes four things against the chart's defaults
(DEC-291 to DEC-294):

- the image names its registry and its tag without the chart's digest;
- the database is the Cluster of `postgresql` instead of the chart's MySQL
  subchart. The connection string leaves the password out, and the
  container reads it from `postgresql-cluster-app` as `PGPASSWORD`;
- the pod runs as the image's user `mattermost`, UID and GID 2000, and
  passes Pod Security `restricted`;
- `MM_TEAMSETTINGS_ENABLEOPENSERVER` is `"false"`, so nobody signs up
  without an invitation.

With a release named `mattermost` the chart names the Deployment, the
claim for files and the Secrets `mattermost-mattermost-team-edition*`, and
the Service `mattermost-team-edition`, on port 8065.

## Include

```yaml
classes:
  - recipes.mattermost
parameters:
  namespace: mattermost
  kapitan:
    vars:
      target: mattermost
  applications:
    mattermost:
      admin:
        username: admin
        email: admin@example.com
        password: <ref>
```

The recipe includes `recipes.postgresql`. Pin only this recipe in the fetch
inventory. The consumer workflow adds `postgresql` at the digest this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.mattermost.admin.username`,
`applications.mattermost.admin.email` and
`applications.mattermost.admin.password` are the first admin's account.
Set the password as a ref with the backend of your choice. Mattermost
requires at least 8 characters. Without one of the parameters the compile
stops with `Interpolation key '<key>' not found`. `postgresql` requires no
parameter.

## The first admin

Mattermost makes the first account a system admin, also one that signs up
with open sign-up off. The Job `mattermost-admin` creates that account
from the parameters through the API as soon as Mattermost answers through
the Service `mattermost-team-edition`
(DEC-295 in [docs/specs/recipes.md](../docs/specs/recipes.md)). Once an
account exists, Mattermost refuses the request, and the Job leaves the
accounts as they are. A later change of the password in the target
therefore does not reach the account. Change it in Mattermost. The Job
goes 10 minutes after it finished, and applying a new version of the
recipe creates it again.

Between the moment the pod is ready and the Job's request, a sign-up
through an exposed Service would still become the admin, and the Job would
create no account. Expose the Service only after the Job completed. Its
log says whether it created the admin. The admin creates the other
accounts or invites people through the System Console or the API.

## Settings

`<c>` stands for `components.mattermost-mattermost-team-edition`, `<s>`
for `generators.kubernetes.secrets`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `config` | `<s>.mattermost-mattermost-team-edition-config.string_data.<variable>.value`, such as `MM_SERVICESETTINGS_SITEURL` |
| `extraEnvVars` | `<c>.env` |
| `persistence.data.size` | `generators.kubernetes.persistent_volume_claims.mattermost-mattermost-team-edition.storage`, 10Gi |
| `persistence.plugins.size` | `generators.kubernetes.persistent_volume_claims.mattermost-mattermost-team-edition-plugins.storage`, 1Gi |
| `persistence.*.storageClass` | `storage_class` next to `storage` |
| `service.type` | `generators.kubernetes.services.mattermost-team-edition.type`, `ClusterIP` |
| `resources` | `<c>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `externalDB.externalConnectionString` | `<s>.mattermost-mattermost-team-edition-mattermost-dbsecret.string_data.mattermost.dbsecret.value`, from `applications.postgresql` |

Mattermost keeps its configuration in the database. A variable
`MM_<SECTION>_<SETTING>` in the Secret `mattermost-mattermost-team-edition-config`
overrides the setting and locks it in the System Console. Set
`MM_SERVICESETTINGS_SITEURL` to the URL users reach Mattermost at. Without
it Mattermost logs at start that some features will operate incorrectly.
The pod annotation `checksum/config` is the chart's hash of that Secret
for the values of `tests/values.yaml`. It does not follow the target's
values, so after changing the Secret restart the Deployment with
`kubectl rollout restart`.

Both claims are ReadWriteOnce, and the Deployment rolls out a new pod
before the old one stops. On a cluster where the new pod lands on another
node it waits for the claim until the old pod is gone. The chart's
Ingress, HTTPRoute and MySQL subchart are not part of the recipe.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check mattermost --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with
`cnpg` installed first. The objects of `postgresql` are left out of the
comparison and applied with the recipe. The Deployment and the Service
select on `name`, the chart on `app.kubernetes.io/name`, `instance` and
`managed-by`, and both select the same pods. The container is named after
the component, the chart's `mattermost-team-edition`. The pod sets
`automountServiceAccountToken: true`, the API default the chart leaves
unset. The chart binds no role. Its Helm test
`Pod/mattermost-mattermost-team-edition-test` is left out.
`tests/values.yaml` adds the Job `mattermost-admin` through the chart's
`extraDeploy`, as a user would next to the chart. The Secret
`mattermost-admin` with its password is only in the recipe, and the
chart's side reads it.
`tests/target.yml` runs one PostgreSQL instance.

`tests/smoke` checks that the pods pass Pod Security `restricted` and that
`/api/v4/system/ping` answers through the Service. It waits for the Job
`mattermost-admin` and logs in as its admin. Through the API the client
configuration names the image tag and a Team Edition build, and a sign-up
without an invitation gets 403. The admin creates a team, a channel and a
second user, and posts a message with a file. The second user reads both,
and reads them again after the test deleted the pod and its successor is
ready, which needs the database and the claim. The test also runs the Job
again, which completes without a new account, and the admin still logs
in.

## Replacing a Helm release

Not tested. A release named `mattermost` has the same object names, so the
claims and their files stay. The database of the release is the one its
`externalDB` or MySQL subchart names, which this recipe does not read.
Moving that data to the Cluster of `postgresql` is not covered here.

1. Delete the Deployment `mattermost-mattermost-team-edition` with
   `--cascade=orphan`, because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.mattermost.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Delete the orphaned ReplicaSet. Its pod holds the ReadWriteOnce claims,
   so a recipe pod on another node starts only after that.
