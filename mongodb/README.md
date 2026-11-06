# mongodb

MongoDB Community Server as a single instance with authentication and the
user `root`, designed in kadet-hub on MongoDB's image and rendered by the
kadet-hub `kubernetes` generator 1.14.0.

Source: `docker.io/mongodb/mongodb-community-server:9.0.4-ubi9-slim@sha256:449f87becbf5f3a5d915ead43356254034ea3f8d90c67e33e0e4a89acbb7313c`

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
parameters:
  namespace: mongodb
  kapitan:
    vars:
      target: mongodb
  applications:
    mongodb:
      password: <ref>
```

## Required parameters

`applications.mongodb.password`, the password of the user `root`, must be
set as a ref with the backend of your choice. Without it the compile stops
with `Interpolation key 'applications.mongodb.password' not found`.

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

## Proof

`check mongodb --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke` runs
`ping` after mongosh authenticates as the user `root` in `admin`, through
the Service `mongodb`, the check of the kadet-hub/examples recipe.
`tests/target.yml` leaves out the option `replica-set`. The CI check of
`rocketchat`, which includes it, proves it (RCP-50): the member is primary
before and after its pod is replaced, and a change stream delivers a
document that Rocket.Chat wrote.
