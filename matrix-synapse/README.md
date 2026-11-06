# matrix-synapse

Synapse 1.164.2, the Matrix homeserver, with federation and open
registration off and its first admin registered by a Job, with Element
Web and OpenID Connect as options, rendered by the kadet-hub `kubernetes`
generator 1.14.0 from Synapse's image. The database is the included recipe
`postgresql`.

Source: `ghcr.io/element-hq/synapse:v1.164.2@sha256:f0df87cff259872637b4b5e5174b9977e5e3046dd421505407803b5e45c5f842`

Level: `deploys`

element-hq publishes Synapse's image as `ghcr.io/element-hq/synapse` and
`docker.io/matrixdotorg/synapse`, built for amd64 and arm64, and documents
it in `docker/README.md` of element-hq/synapse. Its Kubernetes chart, the
Element Server Suite Community chart `matrix-stack` of element-hq/ess-helm,
renders fields the `kubernetes` generator cannot express, so the recipe is
designed on the image (DEC-280 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
The recipe follows Synapse's releases. Synapse and Element Web are
AGPL-3.0. The recipe copies no text of either. `postgresql` requires
`cnpg`, so install `cnpg` first, in a target of its own.

Synapse runs as UID and GID 991, the user the image's `start.py` switches
to as root, and passes Pod Security `restricted`. Its configuration is the
ConfigMap `matrix-synapse` at `/config`, whose `*.yaml` files Synapse reads
in name order. The claim `data` of the StatefulSet holds the signing key,
which Synapse creates on its first start, and the media.

## Include

```yaml
classes:
  - recipes.matrix-synapse
  - recipes.matrix-synapse.element-web    # Element Web
  - recipes.matrix-synapse.federation     # federation with other servers
  - recipes.matrix-synapse.oidc           # login through OpenID Connect
parameters:
  namespace: matrix-synapse
  kapitan:
    vars:
      target: matrix-synapse
  applications:
    matrix-synapse:
      server_name: example.com
      registration_shared_secret: <ref>
      admin:
        username: admin
        password: <ref>
      oidc:
        issuer: https://keycloak.example.com/realms/example
        client_id: synapse
        client_secret: <ref>
```

The recipe includes `recipes.postgresql`. Pin only this recipe in the fetch
inventory. The consumer workflow adds `postgresql` at the digest this
version's index record lists under `includes`. Kapitan's `--fetch` reads no
index, so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.matrix-synapse.server_name` is the domain in every user ID
and room alias, such as `example.com` in `@admin:example.com`. It cannot
change later: Synapse refuses to start on a database that holds users of
another server name.

`applications.matrix-synapse.registration_shared_secret` lets
`register_new_matrix_user` and the admin API register accounts, admins
included, and also signs Synapse's macaroons. Set it to a long random
string, such as one that `openssl rand -hex 32` prints.

`applications.matrix-synapse.admin.username` and
`applications.matrix-synapse.admin.password` are the localpart and the
password of the first admin. The Job `matrix-synapse-admin` registers the
account with `register_new_matrix_user --exists-ok` once Synapse answers,
and leaves an existing account as it is. A later change of the password
does not reach the account. Change it in a client or through the admin API.

The option `oidc` needs `applications.matrix-synapse.oidc.issuer`, the
issuer URL of the OpenID Connect provider, such as a Keycloak realm, and
`applications.matrix-synapse.oidc.client_id` and
`applications.matrix-synapse.oidc.client_secret`, Synapse's client at the
provider.

Set the shared secret, the password and the client secret as refs with
the backend of your choice. Without one of the parameters the compile
stops with `Interpolation key '<key>' not found`. `postgresql` requires no
parameter.

## Registration and federation

Registration is off, Synapse's default. Accounts come from the admin, such
as through `PUT /_synapse/admin/v2/users/<user ID>`. Synapse answers a
registration through the client API with 403.

Federation is off by default. The listener serves the client API only,
and `federation_domain_whitelist: []` denies federation with every server.
The option `federation` replaces the ConfigMap's file `federation.yaml`:
the listener on port 8008 then also serves the federation API and the
server keys, and Synapse serves `/.well-known/matrix/server`, which sends
other servers to port 443 of `server_name`. Other servers then need one of
these routes of the target:

- `https://<server_name>/` on port 443 to the Service `matrix-synapse`,
  port 8008, at least for `/_matrix` and `/.well-known/matrix/server`;
- a file `/.well-known/matrix/server` on the web server of `server_name`
  with `{"m.server": "<host>:443"}`, which delegates to the host of
  `public_baseurl` (Synapse's `docs/delegate.md`);
- port 8448 of `server_name` with TLS to the Service, without delegation.

Synapse does not federate with addresses in private ranges such as
`10.0.0.0/8`, its default `ip_range_blacklist`. Servers that reach each
other on such addresses, such as two in one cluster, need those ranges in
`ip_range_whitelist`, in a file of the ConfigMap (Settings).

## OpenID Connect

The option `oidc` adds one provider to the ConfigMap's file `oidc.yaml`,
after the Keycloak example of Synapse's `docs/openid.md`. It asks for the
scopes `openid` and `profile`, takes the localpart of a new account from
the claim `preferred_username` and its display name from `name`, and names
the login button `applications.matrix-synapse.oidc.name`, `Single sign-on`
by default. The provider redirects back to
`<public_baseurl>_synapse/client/oidc/callback`, which its client allows.
Synapse creates the account on the first login through the provider, also
with registration off, as the provider's `enable_registration` defaults to
true. It loads the provider's metadata in the background
when it starts and keeps running when that fails.

## Element Web

The option `element-web` runs Element Web 1.12.33 from
`ghcr.io/element-hq/element-web`, built for amd64 and arm64, as the
Deployment and Service `matrix-synapse-element-web` on port 80. Its
`config.json` from the ConfigMap `matrix-synapse-element-web` names
`public_baseurl` as the homeserver and `server_name`. The image's nginx
listens on 8080 as UID 101, because the user may not bind port 80 under
Pod Security `restricted`. Element Web runs in the browser, so the target
exposes both Services, and `public_baseurl` must be the URL the browser
reaches Synapse at. The file is mounted with `subPath`, so a
changed `config.json` reaches the pod only after
`kubectl rollout restart deployment/matrix-synapse-element-web`.

## Settings

`<s>` stands for `components.matrix-synapse`, `<w>` for
`components.matrix-synapse-element-web`.

| Setting | Inventory |
|---|---|
| URL clients reach Synapse at, `https://<server_name>/` | `applications.matrix-synapse.public_baseurl`, such as `https://matrix.example.com/` when Synapse has a host of its own |
| Synapse version | `<s>.image`, tag and digest |
| Element Web version | `<w>.image`, tag and digest |
| other Synapse settings | a key `<name>.yaml` in `<s>.config_maps.config.data` with the settings as its `value`. Synapse reads the files in name order, and a later file replaces a top-level key of an earlier one, so keep each top-level key in one file. |
| further keys of Element Web's `config.json` | `<w>.config_maps.config.data.config\.json.value` |
| size of the claim `data`, `10Gi` | `<s>.volume_claims.data.spec.resources.requests.storage` |
| resources | `<s>.resources`, `<w>.resources` |
| exposure | a route or Ingress of the target to the Service `matrix-synapse` on port 8008, and to `matrix-synapse-element-web` on port 80 |

Synapse reads its configuration only when it starts, so after a change
restart it with `kubectl rollout restart statefulset/matrix-synapse`.
Synapse reads the database password from `postgresql-cluster-app` as
`PGPASSWORD` and connects with `sslmode=require`, which encrypts the
connection without verifying the server's certificate. Synapse requires
the collation `C` for its database, which CloudNativePG gives a new
Cluster by default.

The Job `matrix-synapse-admin` waits in an init container until Synapse
answers through its Service, and goes 10 minutes after it finished.
Applying a new version of the recipe creates it again, and it changes
nothing for an existing admin.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check matrix-synapse --level deploys` with `tests/target.yml`, on kind for
each Kubernetes minor CI tests, with `cnpg` installed first. An image has
no Kubernetes objects to compare with, so the recipe is proven by
deploying it (RCP-44). `tests/target.yml` includes the options
`element-web` and `oidc`, runs one PostgreSQL instance and sets
`public_baseurl` to the Service `matrix-synapse`, so that the test reaches
the homeserver at the URL Element Web names. Its OpenID Connect issuer
does not resolve.

`tests/smoke` checks that the pods pass Pod Security `restricted`. Through
the Service, Synapse reports the version of the image tag, answers the
federation API and the server keys with 404, and a registration with 403.
The admin of the Job logs in, creates a second user, a room with that user
invited, an upload and a message. The second user joins and reads the
message and the upload, again after the test deleted the pod
`matrix-synapse-0`, with the same signing key on the claim. The login
flows name the provider of the option `oidc`. Element Web answers through
its Service, and the homeserver answers at the URL its `config.json`
names. In Chrome, driven through ChromeDriver, Element Web's login page
names `example.com` and the provider `Single sign-on`, which it read from
the homeserver at that URL. GitHub's runners bring Chrome and
ChromeDriver. Elsewhere set `CHROMEDRIVER` to a ChromeDriver of the
installed Chrome's version. A login through an OpenID Connect provider is
not tested.

`check` deploys one target, so the option `federation` is proven by hand
on kind. Two targets with the option federated, and with the option off
on one of them the join got 404 (RCP-362 in
[docs/specs/recipes.md](../docs/specs/recipes.md)).
