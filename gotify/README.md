# gotify

gotify 3.1.1, a server that takes messages from applications through a
REST API and delivers them to its web UI and Android app, with its SQLite
database on a claim, designed in kadet-hub on gotify's image and rendered
by the kadet-hub `kubernetes` generator 1.14.0.

Source: `docker.io/gotify/server:3.1.1@sha256:44fc5bbd1c0618878e33073d38c2c13126b48f245c3fe12236b1da48eb203b86`

Level: `deploys`

gotify publishes no Helm chart, Kustomize base or compose file. The
compose example of its [installation page](https://gotify.net/docs/install)
is a code block of the documentation, so the recipe is designed on the
image (DEC-342 in [docs/specs/recipes.md](../docs/specs/recipes.md)). The
settings follow that example and `gotify-server.env.example` of
gotify/server at v3.1.1, the list of every variable with its default that
the [configuration page](https://gotify.net/docs/config) shows. gotify is
MIT. The digest is that of the index for linux/amd64, linux/arm64,
linux/386, linux/arm/v7 and linux/riscv64, built from the tag `v3.1.1`,
which `latest` pointed to on 2026-11-12.

The recipe renders the StatefulSet `gotify` with one replica, the Service
`gotify` on port 80, the Secret `gotify` with the admin's password and the
claim `data`. The pod runs as UID and GID 1234 and passes Pod Security
`restricted`.

## Include

```yaml
classes:
  - recipes.gotify
parameters:
  namespace: gotify
  kapitan:
    vars:
      target: gotify
  applications:
    gotify:
      admin_password: <ref>
```

## Required parameters

`applications.gotify.admin_password` is `GOTIFY_DEFAULTUSER_PASS`, the
password of the admin `admin` that gotify creates at a start while its
database has no user (DEC-344 in the spec). Set it as a ref.

gotify reads the password only when it creates the admin, so a changed
parameter does not change the password of an existing admin. Change it in
the web UI.

Without the parameter the compile stops with `Interpolation key` and its
name.

## Access

The API answers a request without credentials, or with a wrong password or
token, with 401. Applications push messages with the token gotify returns
when the application is created, and users read them in the web UI or
through a client with their password or a client token. Each user sees the
messages of their own applications. Registration stays off, gotify's
default, so the admin adds every further user in the web UI.

The admin's name is `admin`, gotify's default for
`GOTIFY_DEFAULTUSER_NAME`. For another name, set
`components.gotify.env.GOTIFY_DEFAULTUSER_NAME` before the first start.

## Settings

| Setting | Inventory |
|---|---|
| gotify version | `components.gotify.image`, tag and digest |
| the variables of `gotify-server.env.example`, such as `GOTIFY_DEFAULTUSER_NAME` or `GOTIFY_SERVER_TRUSTEDPROXIES` | `components.gotify.env.<variable>`, credentials through `components.gotify.secrets` with a ref |
| size of the claim `data`, `1Gi` | `components.gotify.volume_claims.data.spec.resources.requests.storage` |
| exposure | a route or Ingress of the target to the Service `gotify` on port 80 |
| resources | `components.gotify.resources` |

The claim `data` is mounted at `/app/data`, the directory that the
installation page mounts. It holds the SQLite database `gotify.db`, the
uploaded application images in `images` and the directory `plugins`, from
which gotify loads plugins at its start. SQLite allows one replica.

gotify listens on its default port 80. The pod sets the sysctl
`net.ipv4.ip_unprivileged_port_start` to 0, so UID 1234 binds the port
without a capability (DEC-343 in the spec). Pod Security `baseline` and
`restricted` allow this sysctl.

The readiness probe gets `/health`, which the `HEALTHCHECK` of gotify's
Dockerfile asks. There is no liveness probe.

## Proof

`check gotify --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44).

`tests/smoke` checks that the pod passes Pod Security `restricted` and
starts a pod of gotify's image, which carries `curl`. From there, through
the cluster IP of the Service `gotify` on port 80, it

- gets `/health`
- gets 401 from `/message` without credentials and with a wrong password,
  and for a message pushed with a wrong application token
- creates an application as the admin of `tests/target.yml`, pushes a
  message with the application's token and lists it as the admin
- deletes the pod `gotify-0` and, once its successor is ready, lists the
  message again as the admin.

## Not proven

The web UI in a browser, the Android app and the WebSocket stream. A route
or Ingress in front of the Service, and `GOTIFY_SERVER_TRUSTEDPROXIES`.
Plugins, OIDC, MySQL or PostgreSQL in place of SQLite, and TLS in gotify
itself.
