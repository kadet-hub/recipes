# rocketchat

Rocket.Chat 8.9.1, team chat, as one process with its first admin from
parameters and registration closed, rendered by the kadet-hub `kubernetes`
generator 1.14.0 from Rocket.Chat's Helm chart 7.1.0, on the included
recipe `mongodb` as a replica set on MongoDB 9.0.

Source: `https://rocketchat.github.io/helm-charts/rocketchat:7.1.0@sha256:8340abfbb3395da7489d0e9d9940879107f103b677db2214effd0fa537190bc3`

Level: `deploys`

The chart comes from [RocketChat/helm-charts](https://github.com/RocketChat/helm-charts),
tag `rocketchat-7.1.0`, a repository without a license file. The recipe
carries no template, file or values text of the chart. Rocket.Chat is MIT
outside its `ee/` directories, whose code is under Rocket.Chat's
Enterprise license and ships in the same image.

The chart's `appVersion` is 8.6.1, and the patch releases 8.6.2 and 8.6.4
list security fixes. The recipe runs 8.9.1, the newest release on
2026-11-06, as `docker.io/rocketchat/rocket.chat:8.9.1`, pinned to its
index for amd64 and arm64. The chart's default registry
`registry.rocket.chat` serves the same Docker Hub repository, which the
chart's `values.yaml` links, but on 2026-11-06 it answered manifest
requests with 429 and Docker Hub's rate-limit headers, its own anonymous
quota used up.

Rocket.Chat 8.9.1 names MongoDB 8.0 as its engine version in the release
notes, and its system requirements ask for MongoDB 8.0 or later. Neither
names 9.0. MongoDB 9.0 is this recipe's choice, proven by `tests/smoke` on
MongoDB 9.0.4, not by Rocket.Chat.

## Include

```yaml
classes:
  - recipes.rocketchat
parameters:
  namespace: rocketchat
  kapitan:
    vars:
      target: rocketchat
  applications:
    rocketchat:
      host: chat.example.com
      admin_email: admin@example.com
      admin_password: <ref>
    mongodb:
      password: <ref>
      users:
        rocketchat:
          value: <ref>
```

The recipe includes `recipes.mongodb` and its options
`recipes.mongodb.replica-set` and `recipes.mongodb.users`. Pin only this
recipe in the fetch
inventory. The consumer workflow adds `mongodb` at the digest this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.rocketchat.host` is the host name users reach Rocket.Chat
at. The recipe sets `ROOT_URL` to `https://<host>`, as the chart's `host`
does, and Rocket.Chat builds its links from it.

`applications.rocketchat.admin_email` and
`applications.rocketchat.admin_password` are the address and password of
the user `admin`, which Rocket.Chat creates on its first start.

`applications.mongodb.password`, which the included recipe `mongodb`
requires, is the password of MongoDB's user `root`.

`applications.mongodb.users.rocketchat.value` is the password of MongoDB's
user `rocketchat`, with which Rocket.Chat connects. It is part of the
MongoDB URL in the Secret `rocketchat-rocketchat`, so use letters and
digits only.

Set the three passwords as refs with the backend of your choice. Without
one of the parameters the compile stops with
`Interpolation key '<key>' not found`.

## Accounts

On its first start Rocket.Chat creates the user `admin` with the role
`admin` from `ADMIN_EMAIL` and `ADMIN_PASS`, when no user has that role.
Later starts leave the account alone, so a changed parameter changes the
Secret `rocketchat`, not the password. The address is not marked verified.

`Accounts_RegistrationForm=Disabled` closes the registration form, where
Rocket.Chat's default is `Public`. A variable named after a setting gives
the setting its first value only, so an admin can open registration later
in the administration. On a database that has the setting already, the
variable changes nothing. Admins create users through the administration
or the REST API.

Rocket.Chat asks a user with a verified address for a code by mail at
login, which it turns on for new users by default. The recipe sets up no
mail server, so such a user cannot log in until an admin configures SMTP
or turns the code off. On kind a member created with a verified address
got `totp-required`.

With an admin in place Rocket.Chat sets its setup wizard to `in_progress`,
as it logged on kind. The wizard's remaining steps in the web UI, such as
the organization and the workspace registration, are not tested. The REST
API works without them, as `tests/smoke` shows.

## MongoDB

Rocket.Chat connects to the Service `mongodb` with
`directConnection=true`, as the user `rocketchat`, and keeps its data in
the database `rocketchat`. The option `users` of `mongodb` creates that
user with `readWrite` on `rocketchat` as its only role. The option
`replica-set` runs MongoDB as the replica set `rs0` with one member.
`mongodb`'s README describes both.

That role covers what Rocket.Chat 8.9.1 does in MongoDB: its queries, its
transactions and its change stream on the collection `instances`. It
reads no oplog. Its `serverStatus` call needs `clusterMonitor`, which the
user lacks, so Rocket.Chat takes the version from `buildinfo` and reports
the storage engine as `unknown`.

A new password for `rocketchat` takes effect once the pod `mongodb-0`
restarts, and Rocket.Chat connects again only after its own restart:

```sh
kubectl rollout restart statefulset/mongodb
kubectl rollout status statefulset/mongodb
kubectl rollout restart deployment/rocketchat-rocketchat
```

Rocket.Chat 8.9.1 opens a change stream at startup. On kind, against
`mongodb` without the option, it logged
`Error in InstanceStatus change stream` with
`The $changeStream stage is only supported on replica sets or mongos`.
The admin could still create a member, and both exchanged messages through
the REST API. MongoDB runs transactions, which Rocket.Chat uses, only on
replica sets and sharded clusters.

Uploads go to GridFS in MongoDB, Rocket.Chat's default
`FileUpload_Storage_Type`. The chart's `persistence.enabled` is off by
default, so `/app/uploads` is an `emptyDir`.

## Exposure

Rocket.Chat serves plain HTTP on port 80 of the Service
`rocketchat-rocketchat`, and Prometheus metrics on port 9100, the chart's
default `prometheusScraping`. TLS ends at a proxy the target sets up for
`https://<host>`, which the recipe does not render, as the chart's
`ingress.enabled` defaults to false. A proxy in front of Rocket.Chat is
not tested.

## Settings

`<c>` stands for `components.rocketchat-rocketchat`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `host` | `applications.rocketchat.host` |
| `extraEnv` | `<c>.env`, such as `OVERWRITE_SETTING_<setting>` |
| `persistence.enabled`, `.size` | `<c>.volumes.rocket-data`, a `persistentVolumeClaim` in place of the `emptyDir`, with the claim in `<c>.persistent_volume_claims` |
| `prometheusScraping.port`, 9100 | `<c>.env.OVERWRITE_SETTING_Prometheus_Port`, `<c>.ports.metrics.service_port` and the Service annotation `prometheus.io/port` |
| `service.type` | `<c>.service.type` |
| `resources` | `<c>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |

The pod template carries the chart's annotation `checksum/secret` as the
chart renders it with `tests/values.yaml`. It does not follow a change of
the Secret.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's Bitnami MongoDB subchart gives way to `mongodb`, as
`mongodb.enabled: false` with `externalMongodbUrl` in `tests/values.yaml`.
The chart's default `microservices.enabled: true` runs Rocket.Chat as
several services with NATS, which the chart's `values.yaml` marks as
available to Enterprise users only, so `tests/values.yaml` turns both
off. The chart's own `tests/monolith-values.yaml` runs without
microservices as well. The PodMonitor
renders only where the cluster serves `monitoring.coreos.com/v1`, which
`check` does not install. Ingress, Matrix federation with Synapse, SMTP,
the registration token and the license are off by default and not part of
the recipe. More than one replica, for which the chart adds a
PodDisruptionBudget, is not tested. The chart renders no hook and no Role.

## Proof

`check rocketchat --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The
objects of `mongodb` are left out of the comparison and applied with the
recipe. The Deployment and the Service select on `name`, the chart on
`app.kubernetes.io/name` and `instance`, and both select the same pods. The
pod and the ServiceAccount set `automountServiceAccountToken: true`, the
API default the chart leaves unset. The container is named after the
Deployment, and the Service's metrics port targets the port by its name
`metrics` where the chart gives 9100. The Secret `rocketchat` is only in
the recipe, accepted as a Referenced Secret: the chart's container reads
its key `admin-password`.

`tests/smoke` reaches Rocket.Chat through the Service
`rocketchat-rocketchat`. The admin logs in and has the role `admin`,
creates a member, and the two read each other's message in the channel
`general` through the REST API. Rocket.Chat's statistics report MongoDB
9.0, the replica set `rs0` has its member as primary, Rocket.Chat logged
no error for its change stream, and a change stream on Rocket.Chat's
messages delivers the admin's message. Registration is refused with
`error-user-registration-disabled`. After the MongoDB and the Rocket.Chat
pod are deleted, the member is primary again and the admin reads both
messages.

Every connection from Rocket.Chat's pod that authenticated in MongoDB did
so as `rocketchat`, which `$currentOp` shows. The change stream on the
messages runs as that user. `listDatabases` names only `rocketchat` to it,
and it gets `Unauthorized` for a read of `local.oplog.rs`, a write in
`admin`, `serverStatus` and `createUser`. Rocket.Chat's statistics report
MongoDB 9.0 with the storage engine `unknown`. After the MongoDB pod is
deleted, the user still has `readWrite` on `rocketchat` as its only role.

## Replacing a Helm release

Not tested. A release named `rocketchat` has the same names for the
Deployment, Service, ServiceAccount and Secret. Its data is in the chart's
Bitnami MongoDB, which this recipe does not read. Moving that data to
`mongodb` is not covered here.

1. Delete the Deployment `rocketchat-rocketchat` with `--cascade=orphan`,
   because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.rocketchat.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet and the
   objects of the chart's subcharts, which the recipe does not render.
