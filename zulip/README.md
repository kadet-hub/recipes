# zulip

Zulip 12.3, team chat organized by channel and topic, with its first
organization and owner created from parameters, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from Zulip's Helm chart 2.3.0, on the
included recipes `postgresql`, `rabbitmq`, `memcached` and `valkey`.

Source: `oci://ghcr.io/zulip/helm-charts/zulip:2.3.0@sha256:e462aaa5d39e89661927ad9a744c57b938f8d75e09c5660712314111a2802593`

Level: `deploys`

The chart comes from [zulip/docker-zulip](https://github.com/zulip/docker-zulip),
tag `helm-2.3.0`, and is Apache-2.0 like Zulip. It runs
`ghcr.io/zulip/zulip-server:12.3-0`, the chart's `appVersion`, pinned to
its index for amd64 and arm64. The container runs as root and starts nginx,
Django, Tornado and Zulip's queue workers under supervisord, so it
does not meet Pod Security `restricted`. `postgresql` requires `cnpg`, and
`rabbitmq` requires `rabbitmq-cluster-operator`, which requires
`cert-manager`. Install `cert-manager`, `rabbitmq-cluster-operator` and
`cnpg` first, each in a target of its own.

## Include

```yaml
classes:
  - recipes.zulip
parameters:
  namespace: zulip
  kapitan:
    vars:
      target: zulip
  applications:
    zulip:
      host: chat.example.com
      administrator: admin@example.com
      secret_key: <ref>
      owner_password: <ref>
    valkey:
      password: <ref>
```

The recipe includes `recipes.postgresql`, `recipes.rabbitmq`,
`recipes.memcached` and `recipes.valkey`. Pin only this recipe in the fetch
inventory. The consumer workflow adds the four at the digests this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull them by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.zulip.host` is `SETTING_EXTERNAL_HOST`, the host name users
reach Zulip at. `applications.zulip.administrator` is
`SETTING_ZULIP_ADMINISTRATOR`, the address that gets Zulip's error and
support mail, and the login of the organization's owner. Zulip refuses to
start with the documentation's examples `zulip.example.com` and
`zulip-admin@example.com`.

`applications.zulip.secret_key` is Django's `SECRET_KEY`, which signs
sessions, so a new key logs every user out. Any random string works, such
as one that `openssl rand -base64 48` prints.
`applications.zulip.owner_password` is the owner's password. It needs 8
characters or more and must pass Zulip's strength check, which rejects a
password that zxcvbn guesses in fewer than 10000 attempts.

`applications.valkey.password`, which the included recipe `valkey`
requires, is the password of Valkey's user `default`, with which Zulip
connects to Redis. `postgresql`, `rabbitmq` and `memcached` require no
parameter. Set the three secrets as refs with the backend of your choice.
Without one of the parameters the compile stops with
`Interpolation key '<key>' not found`.

## The organization and its owner

On every start the image runs the scripts of the ConfigMap
`zulip-post-setup-scripts` after its database migrations. The recipe's
script `create-organization.sh` creates the organization `Zulip` with the
owner `Owner` through `manage.py create_realm`, once, while the server has
no organization at its root domain. The owner's login is
`applications.zulip.administrator` and the password
`applications.zulip.owner_password`. Rename both in Zulip's settings. A
later change of the parameters does not reach the account.

Before it creates anything, the script checks the password with Zulip's
strength check. A rejected password stops the script with
`ZULIP_OWNER_PASSWORD is too weak for Zulip.` in the pod's log, Zulip runs
without an organization, and the next start tries again. `create_realm`
also needs RabbitMQ, which can still be starting. The script waits for it
up to 30 times, 5 seconds apart. If RabbitMQ never answers, the script
stops with `RabbitMQ does not answer, the next start tries again.` and
creates nothing.

The organization requires an invitation to join, Zulip's default for a new
organization. An administrator invites users, which needs outgoing mail,
or creates them with `manage.py create_user`. Creating another
organization needs a link from `manage.py generate_realm_creation_link`,
because `OPEN_REALM_CREATION` stays at its default, off.

## Exposure

Zulip serves plain HTTP on port 80 of the Service `zulip`, the chart's
default with `CERTIFICATES` unset. It expects TLS to end at a proxy in
front of it, such as an Ingress or a Gateway, which the recipe does not
render. Zulip answers a request without proxy headers only from the
loopback, as through `kubectl port-forward`. It trusts `X-Forwarded-For`
and `X-Forwarded-Proto` only from the addresses in `LOADBALANCER_IPS`, and
answers every other request with 500 and `Reverse proxy misconfiguration`
in `/var/log/zulip/errors.log`. Set `LOADBALANCER_IPS` in
`components.zulip.env` to the proxy's addresses or range.

## Settings

`<c>` stands for `components.zulip`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `zulip.environment` | `<c>.env`, such as `LOADBALANCER_IPS` or `SETTING_EMAIL_HOST` |
| `zulip.persistence.size`, 10Gi | `<c>.persistent_volume_claims.zulip-data.storage` |
| `zulip.persistence.storageClass` | `<c>.persistent_volume_claims.zulip-data.storage_class` |
| `postSetup.scripts` | `generators.kubernetes.configs.zulip-post-setup-scripts.data` |
| `externalPostgresql.host`, `.database`, `.user` | `applications.postgresql.cluster`, `.database` and `.owner`, which `postgresql`'s README lists |
| `service.type` | `<c>.service.type` |
| `resources` | `<c>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |

Zulip searches messages with PostgreSQL's `pg_catalog.english`, because
the CloudNativePG image lacks the dictionaries of Zulip's own PostgreSQL
image. The first migration logs a warning about it. The chart's Ingress is
off by default and not part of the recipe.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check zulip --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests, with
`cnpg`, `cert-manager` and `rabbitmq-cluster-operator` installed first.
`tests/target.yml` runs one PostgreSQL instance and one RabbitMQ node. The
objects of the included recipes are left out of the comparison and applied
with the recipe. The StatefulSet and the Service select on `name`, the
chart on `app.kubernetes.io/name` and `instance`, and both select the same
pods. The pod and the ServiceAccount set `automountServiceAccountToken:
true`, the API default the chart leaves unset. The container ports are
sorted by name. The Secret `zulip` is only in the recipe, accepted as a
Referenced Secret: the chart's container reads exactly its keys
`secret-key` and `owner-password`.

`tests/smoke` reaches Zulip through the Service `zulip`. The owner logs in,
and a member created with `manage.py create_user` and the owner each read
the other's message in the channel `general`. Zulip's queue workers
consume RabbitMQ, its cache holds items in memcached without SASL, and
`manage.py check_redis` reaches Valkey. A signup without an invitation and
a new organization without a creation link are refused. After the Zulip pod
and the PostgreSQL primary are deleted, the owner logs in again and reads
both messages.

## Replacing a Helm release

Not tested. A release named `zulip` has the same object names. Its data is
in the PostgreSQL that the release used, which this recipe does not read.
Moving that data to the Cluster of `postgresql` is not covered here.

1. Set `applications.zulip.secret_key` to the release's
   `SECRETS_secret_key`.
2. Delete the StatefulSet `zulip`, because its selector changes. The claim
   `zulip-data` is no claim template, so it stays.
3. Delete the release's Helm secrets `sh.helm.release.v1.zulip.*`.
4. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
5. Once Zulip is ready, delete the objects of the chart's subcharts, which
   the recipe does not render.
