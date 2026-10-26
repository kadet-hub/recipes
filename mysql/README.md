# mysql

MySQL Community Server as a single instance with one database and its
user, designed in kadet-hub on Oracle's image and rendered by the kadet-hub
`kubernetes` generator 1.9.0.

Source: `container-registry.oracle.com/mysql/community-server:9.7.4@sha256:cb9cfddeccbbd9922bf927cd67bdb58067b357a1fc75d132988d1f5cc4cb17bb`

Level: `deploys`

MySQL publishes no chart for a single server. Oracle's charts
`mysql-operator` and `mysql-innodbcluster` install the MySQL Operator and
an InnoDB Cluster it manages, so the recipe is designed on the image the
MySQL team builds (DEC-11 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
MySQL Community Server is GPL-2.0. The recipe follows the 9.7 LTS release
line. The tag is a linux/amd64 image, and the arm64 build has its own tag,
`9.7.4-aarch64`.

## Replaces

This recipe replaces the `mysql` recipe of kadet-hub/examples, which stood
in for Bitnami's `mysql` chart. Moving from it changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| refs `mysql/password` and `mysql/root-password` with the `base64` backend in the class | `applications.mysql.password` and `applications.mysql.root_password`, set by the target with the ref backend of your choice |
| Namespace `mysql`, rendered by the recipe | no Namespace. The target sets `namespace` and creates it. |

The StatefulSet `mysql` with its claim template `data`, the Service `mysql`
and the Secret `mysql` with the keys `password` and `root-password` keep
their names, so the claim `data-mysql-0` and its data stay. MySQL set the
passwords when it initialized that data, so set the two parameters to refs
that hold the values of the old refs.

## Include

```yaml
classes:
  - recipes.mysql
parameters:
  namespace: mysql
  kapitan:
    vars:
      target: mysql
  applications:
    mysql:
      password: <ref>
      root_password: <ref>
```

## Required parameters

`applications.mysql.password`, the password of the user `app`, and
`applications.mysql.root_password` must be set, as refs with the backend of
your choice. Without them the compile stops with
`Interpolation key 'applications.mysql.password' not found`.

## Settings

| Setting | Inventory |
|---|---|
| MySQL version | `applications.mysql.version`, together with the digest in `components.mysql.image` |
| database and its user, `app` | `applications.mysql.database`, `applications.mysql.user` |
| volume size, 8Gi | `components.mysql.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.mysql.resources` |
| arm64 nodes | `components.mysql.image` with the tag `<version>-aarch64` and its digest |

MySQL reads the database, the user and both passwords only when it
initializes an empty data directory. Changing them later changes the
Secret, not the database.

The data lives in the subdirectory `mysql` of the volume, because
`mysqld --initialize` refuses a directory with `lost+found` in it. The
probes test port 3306: the entrypoint initializes the data directory with
networking off, so the port opens once the server is ready.

## Proof

`check mysql --level deploys` with `tests/target.yml` on kind
`kindest/node:v1.37.0`. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke` runs
`select 1` as the user `app` in the database `app` through the Service
`mysql`, the check of the kadet-hub/examples recipe.
