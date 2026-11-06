# ejabberd

ejabberd, an XMPP server for direct and group chat, with an admin account
from a required parameter and its Mnesia database on a claim, rendered by
the kadet-hub `kubernetes` generator 1.14.0 from the compose example in the
container documentation of ejabberd 26.09.

<!-- renovate: tag=26.09 -->
Source: `https://github.com/processone/ejabberd/blob/5ef8f25445204ebc0633242aecc1ba0473e3901d/CONTAINER.md@sha256:c13e76ebc376b36cd088ed91facd15ec3fe1d253cc5620bc93e4f7f023ce29f4`

Level: `deploys`

ProcessOne ships no chart. The repository documents its container image
in `CONTAINER.md`, with three compose examples as code blocks, and the
recipe maps the one under "Customized Example" (DEC-300 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The commit is the tag
`26.09`. The image `26.09.1` is ProcessOne's rebuild of that tag from
2026-10-23, which `latest` pointed to on 2026-11-05, an index for amd64
and arm64. ejabberd and its image are GPL-2.0. The image runs as the user
`ejabberd`, UID 9000, under the Pod Security level `restricted`. The
container adds the capability `NET_BIND_SERVICE`, without which the kernel
refuses to start `beam.smp` (DEC-302). A preStop hook stops ejabberd before the
kubelet sends SIGTERM, because the image's entrypoint would otherwise kill
the Erlang VM before Mnesia saves its last writes (DEC-304).

## Include

```yaml
classes:
  - recipes.ejabberd
parameters:
  namespace: ejabberd
  kapitan:
    vars:
      target: ejabberd
  applications:
    ejabberd:
      admin_password: <ref>
      erlang_cookie: <ref>
```

## Required parameters

`applications.ejabberd.admin_password` is the password of the admin account
`admin@<host>`. `applications.ejabberd.erlang_cookie` is the Erlang cookie
of the ejabberd node, a long random string such as one that
`openssl rand -hex 32` prints. The node accepts Erlang distribution on the
pod's address with it, so whoever knows it controls ejabberd. Set both as
refs with the backend of your choice. Without one of them the compile stops
with `Interpolation key '<key>' not found`. The image registers the account only when the database on the claim is empty,
so a later change of the parameter does not change the password. Change
it with `kubectl exec ejabberd-0 -- ejabberdctl change_password admin <host> <password>`.
The cookie keeps the image's first start from failing, after which the
image would not register the account (DEC-305). Should the admin still be
missing, register it with
`kubectl exec ejabberd-0 -- ejabberdctl register admin <host> <password>`.

## Settings

| Setting | Inventory |
|---|---|
| ejabberd version | `components.ejabberd.image`, tag and digest |
| XMPP domain, `example.com` as in the compose example | `applications.ejabberd.host` |
| admin account, `admin@<host>` | `components.ejabberd.env.EJABBERD_MACRO_ADMIN` |
| commands at every start, `registered_users <host> ; status` | `components.ejabberd.env.CTL_ON_START` |
| other macros of `ejabberd.yml`, such as `STARTTLS_REQUIRED` | `components.ejabberd.env.EJABBERD_MACRO_<name>` |
| exposure | `components.ejabberd.service.type`, such as `LoadBalancer` |
| size of the claim `database`, `1Gi` | `components.ejabberd.volume_claims.database.spec.resources.requests.storage` |
| resources | `components.ejabberd.resources` |

The domain takes effect at every start. Accounts belong to the domain they
were registered in, so a new domain starts without accounts.

Nobody can register an account over XMPP. The image's `ejabberd.yml`
accepts in-band registration only from the loopback network, and its HTTP
API at `/api` only from the admin account on the loopback network. The
admin creates accounts in the pod, with `ejabberdctl register` or through
the API at `https://127.0.0.1:5443/api`, or in the web admin at `/admin`.
Port 5280 serves the web admin without TLS, so the admin's password
crosses the network in clear text there. Use `/admin` on port 5443.

The image's certificate `conf/server.pem` was generated when the image was
built, so every copy of the image carries the same private key. Before
clients connect over a network you do not trust, mount your own
certificate and key over it, such as from a cert-manager Secret through
`components.ejabberd.volume_mounts` with `sub_path`. With its default
`acme` settings, ejabberd also asks Let's Encrypt for certificates of its
domain at every start, which succeeds only when the domain's port 80 reaches
port 5280.

The Service `ejabberd` is a ClusterIP Service with client connections on
5222, server-to-server connections on 5269, the web admin on 5280 and
TLS on 5443 for BOSH at `/bosh`, WebSocket at `/websocket`, the API, the
web admin and HTTP upload. The compose example publishes these four ports
on the host. Clients outside the cluster reach ejabberd once the target
exposes the Service. Federation with other servers needs port 5269 and the
domain's DNS records. Client connections with direct TLS on 5223, the web
admin on 1880, STUN and TURN on 5478/udp and 50000 to 50099/udp, MQTT on
1883 and the file transfer proxy on 7777 run in the container but are not
published, as in the compose example.

The image's `ejabberd.yml` is in `.github/container/ejabberd.yml.example` of
processone/ejabberd. To change more than its macros, mount a file of your
own at `/opt/ejabberd/conf/ejabberd.yml`, from a ConfigMap through
`components.ejabberd.config_maps` and a `volume_mounts` entry with
`sub_path`.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Mapping

The service `main` becomes the component `ejabberd`. No environment value,
command or config names `main`, so no reference is rewritten.

| Compose | Recipe |
|---|---|
| service `main` | StatefulSet `ejabberd`, Service `ejabberd`, Secret `ejabberd` with `REGISTER_ADMIN_PASSWORD` and `ERLANG_COOKIE` |
| `ghcr.io/processone/ejabberd` without a tag | `ghcr.io/processone/ejabberd:26.09.1@sha256:1842577c33c8088ea15a2a7f940a7b8ffcfb09a4d1c0e713caf03df663f3b069`, which `latest` was at migration |
| ports `5222`, `5269`, `5280` and `5443` | Service ports `xmpp-client`, `xmpp-server`, `http` and `https`, `ClusterIP` |
| `EJABBERD_MACRO_HOST`, `EJABBERD_MACRO_ADMIN`, `CTL_ON_START` | `env`, with the compose example's `example.com` from `applications.ejabberd.host` |
| `REGISTER_ADMIN_PASSWORD` | from `applications.ejabberd.admin_password` in the Secret `ejabberd` |
| not in the example | `ERLANG_COOKIE` from `applications.ejabberd.erlang_cookie` in the Secret `ejabberd` (DEC-305) |
| bind mount `./conf/ejabberd.yml` at `/opt/ejabberd/conf/ejabberd.yml` | not rendered: `CONTAINER.md` copies it from `ejabberd.yml.example`, and the image carries `.github/container/ejabberd.yml.example` byte for byte at that path, SHA-256 `12e320cde9dcb0b8f73cab84a33a3abe90a8aaf4e9295f087346d354385ad8fa` (DEC-301) |
| bind mount `./database` at `/opt/ejabberd/database` | claim template `database`, `ReadWriteOnce`, `1Gi` |
| the image's `HEALTHCHECK`, `ejabberdctl status` | readiness probe every 60 seconds with a timeout of 5 seconds and 10 failures, the `HEALTHCHECK`'s values |
| `version`, `container_name` | not rendered. `docker compose config` drops `version`. |
| `docker stop`, which kills the Erlang VM before Mnesia writes its log | preStop hook `ejabberdctl stop && ejabberdctl stopped` (DEC-304) |

## Proof

`check ejabberd --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests, with check 0.16.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38). `tests/target.yml` sets the compose example's password and a test cookie.

`tests/smoke` starts a pod of the ejabberd image, which carries `curl` and
`nc`. From there, through the Service `ejabberd`, it

- gets stream features on 5222 that require STARTTLS, and on 5269 for a
  stream from another domain
- gets 401 from the web admin on 5280
- asks to register an account in a BOSH session on 5443, and gets
  `forbidden`.

As the admin, through the API in the pod, it creates the accounts `alice`
and `bob` and the persistent room `smoke` with its archive. Over BOSH,
alice joins the room, writes to it and sends bob a direct message while he
is offline. bob logs in, gets the direct message, joins the room, gets
alice's message from its history and answers in the room. The admin then
reads both room messages through the API. After the pod `ejabberd-0` is
deleted and its successor is ready, the API still lists both accounts, and
bob logs in again and finds alice's messages in the room's archive and in
his own.

Not tested: STARTTLS and TLS with a client certificate check, federation
with another server, WebSocket, HTTP upload, STUN and TURN, and a
LoadBalancer Service.
