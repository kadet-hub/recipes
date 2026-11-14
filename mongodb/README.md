# mongodb

MongoDB Community Server as a single instance with authentication and the
user `root`, designed in kadet-hub on MongoDB's image and rendered by the
kadet-hub `kubernetes` generator 1.16.0.

Source: `docker.io/mongodb/mongodb-community-server:9.0.4-ubi9-slim@sha256:096eb497dea8c13c10ee040c0dd8ea29ff56bd75ac4cfce2e9a5ec1e11bda65c`

Level: `deploys`

MongoDB publishes no chart for a single server. Its charts install
MongoDB's operators or resources they manage, so the recipe is designed on
the image MongoDB builds (DEC-11 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
MongoDB Community Server is licensed SSPL-1.0, which the OSI does not
approve as open source. The recipe follows MongoDB's 9.0 major release and
runs the `ubi9-slim` variant, an index for linux/amd64 and linux/arm64.
MongoDB rebuilds the tag regularly, so the digest is that of one build.

## Replaces

This recipe replaces the `mongodb` recipe of kadet-hub/examples, which
stood in for Bitnami's `mongodb` chart. Moving from it changes these
objects:

| kadet-hub/examples | This recipe |
|---|---|
| ref `mongodb/password` with the `base64` backend in the class | `applications.mongodb.password`, set by the target with the ref backend of your choice |
| Namespace `mongodb`, rendered by the recipe | no Namespace. The target sets `namespace` and creates it. |
| `MONGO_INITDB_ROOT_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD` | `MONGODB_INITDB_ROOT_USERNAME`, `MONGODB_INITDB_ROOT_PASSWORD`, the names the image's entrypoint asks for. The pod restarts once. |

The StatefulSet `mongodb` with its claim template `data`, the Service
`mongodb` and the Secret `mongodb` with the key `password` keep their
names, so the claim `data-mongodb-0` and its data stay. MongoDB created the
user `root` when it initialized that data, so set the parameter to a ref
that holds the value of the old ref.

## Include

```yaml
classes:
  - recipes.mongodb
  - recipes.mongodb.replica-set   # a replica set of one member
  - recipes.mongodb.users         # users with rights on their database only
parameters:
  namespace: mongodb
  kapitan:
    vars:
      target: mongodb
  applications:
    mongodb:
      password: <ref>
      users:
        app:
          value: <ref>
```

## Required parameters

`applications.mongodb.password`, the password of the user `root`, must be
set as a ref with the backend of your choice. Without it the compile stops
with `Interpolation key 'applications.mongodb.password' not found`.

With the option `users`, `applications.mongodb.users` maps the name of
each user to an entry whose `value` is the user's password, set as a ref.
Without the map the compile stops with
`Interpolation key 'applications.mongodb.users' not found`.

## Settings

| Setting | Inventory |
|---|---|
| MongoDB version | `components.mongodb.image`, tag and digest |
| root user, `root` | `components.mongodb.env.MONGODB_INITDB_ROOT_USERNAME` |
| volume size, 8Gi | `components.mongodb.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.mongodb.resources` |

MongoDB reads the root user and its password only when it initializes an
empty data directory. Changing them later changes the Secret, not the
database.

The image runs as the user `mongod`, so the recipe sets its UID, 1000, for
`runAsNonRoot`. The probes test port 27017: the entrypoint creates the
root user on a first `mongod` bound to localhost, so the port opens on the
pod IP once that is done.

## The option `replica-set`

`recipes.mongodb.replica-set` runs MongoDB as the replica set `rs0` with
one member, which change streams and transactions need. A postStart hook
of the container initiates it with the member `localhost:27017` on the
first start and waits on every start until the member is primary. Clients
connect through the Service `mongodb` with `directConnection=true`,
because the member's address `localhost:27017` reaches it only from its
own pod.

mongod needs a key file once authorization and a replica set are on, and
an init container writes a random one into an `emptyDir` on each pod
start. With one member no other server authenticates with it. A second
member is not supported: it would need the same key and an address that
the other members and clients reach.

Adding the option to a running `mongodb` restarts the pod with the
replica set on the data it has, which MongoDB documents as converting a
standalone server to a replica set. That path is not tested. The name
`rs0` is `applications.mongodb.replica_set`. Change it only before the
first start, because the hook does not rename a replica set that exists.

## The option `users`

`recipes.mongodb.users` creates a user per application, so that the
application connects with rights on its own database instead of as
`root`. Each user is created in the database of its name, and
authenticates there, with `readWrite` on that database as its only role.
A client connects with `mongodb://<name>:<password>@mongodb:27017/<name>`,
and with the option `replica-set` adds `directConnection=true`. The map
`applications.mongodb.users` becomes the Secret `mongodb-users` as it is,
which is why an entry has the shape of a Secret entry of the `kubernetes`
generator, `value` included.

The container `users` in the pod applies the map in its postStart hook,
on every start of the pod. Once the server answers `root` as a writable
primary, the hook creates each user that does not exist and sets password
and role of each one that does. The pod becomes ready only after that.
When the hook fails 90 times, 2 seconds apart, the pod's event
`FailedPostStartHook` shows mongosh's last output, and the container
starts again. Its own process waits and exits on `SIGTERM`. Its memory
limit is 256Mi, as mongosh needed up to 154 MiB for the hook.

A changed password changes the Secret but not the pod, so it takes effect
once the pod restarts:

```sh
kubectl rollout restart statefulset/mongodb
```

Restart the client after that, as it reads its password when it starts.
A role granted to such a user by hand is gone after the next start. A
user removed from the map stays in MongoDB until an admin drops it with
`dropUser`.

## Proof

`check mongodb --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke` runs
`ping` after mongosh authenticates as the user `root` in `admin`, through
the Service `mongodb`, the check of the kadet-hub/examples recipe.

`tests/target.yml` includes the option `users` with the user `app`.
`tests/smoke` writes and reads a document as `app`, puts a new password
into the Secret `mongodb-users` and deletes the pod. It then requires that
the new password logs in, that the old one is refused and that `app` has
`readWrite` on `app` as its only role. `check` counts the Secret
`mongodb-users` as an object of `mongodb` because this target renders it,
which keeps it out of the comparison of a parent with its chart.

`tests/target.yml` leaves out the option `replica-set`. The CI check of
`rocketchat`, which includes both options, proves them on a replica set
(RCP-50): the member is primary before and after its pod is replaced, a
change stream as Rocket.Chat's user delivers a document that Rocket.Chat
wrote, and that user gets `Unauthorized` outside its database.

Without the option `users` the recipe renders as before the option
existed. A compile of `tests/target.yml` of the commit before it, alone
and with `replica-set`, gave the same files with and without the change.
