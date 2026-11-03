# vaultwarden

Vaultwarden, a password server for the Bitwarden clients, with its vault in
SQLite on a claim, rendered by the kadet-hub `kubernetes` generator 1.9.0
from the Docker Compose example in the README of Vaultwarden 1.37.5.

Source: `https://github.com/dani-garcia/vaultwarden/blob/6ed6921cc2b0e03b4d74189574d2a5e71c512e97/README.md@sha256:5c7e29e287f600fe1979d196d53f94cd8f87f9c0de1acf6481fde510fbfdd4fc`

Level: `deploys`

Vaultwarden publishes no Helm chart. It ships its compose example only as
the code block under "Docker Compose" of its README, so the `Source` line
pins the README, as for `pihole` (DEC-28 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The commit is the tag
`1.37.5`, from which the image `1.37.5` was built. Vaultwarden and its
image are AGPL-3.0. The image is an index for linux/amd64, linux/arm64,
linux/arm/v7 and linux/arm/v6. It runs as root, so the target's namespace
needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.vaultwarden
parameters:
  namespace: vaultwarden
  kapitan:
    vars:
      target: vaultwarden
  applications:
    vaultwarden:
      domain: https://vault.example.com
      admin_token: <ref>
```

## Required parameters

`applications.vaultwarden.domain` is the URL clients reach Vaultwarden at,
with its scheme, such as `https://vault.example.com`. Vaultwarden builds
the links in its emails and the addresses it gives clients from it.

`applications.vaultwarden.admin_token` is the token of the admin page
`/admin`, set as a ref with the backend of your choice. Vaultwarden
recommends an Argon2id PHC string over the token itself.
`docker run --rm -it docker.io/vaultwarden/server:1.37.5 /vaultwarden hash`
asks for the token twice and prints the string as `ADMIN_TOKEN='<string>'`.
Without either parameter the compile stops with `Interpolation key` and
its name.

## Settings

| Setting | Inventory |
|---|---|
| Vaultwarden version | `components.vaultwarden.image`, tag and digest |
| signups, off | `components.vaultwarden.env.SIGNUPS_ALLOWED` |
| other settings of `.env.template`, such as `SMTP_HOST` | `components.vaultwarden.env.<variable>` |
| exposure | `components.vaultwarden.service.type`, or a route or Ingress of the target to the Service `vaultwarden` on port 8000 |
| size of the claim `vw-data`, `1Gi` | `components.vaultwarden.volume_claims.vw-data.spec.resources.requests.storage` |
| resources | `components.vaultwarden.resources` |

Vaultwarden keeps its state in `/data` on the claim: the SQLite database
`db.sqlite3`, the attachments and Sends, the key that signs its sessions
and `config.json`. Settings saved on the admin page go to `config.json` and
take precedence over the environment, so a setting changed there no longer
follows the inventory. SQLite allows one replica.

Signups are off (DEC-55 in the spec). The admin page invites users, and an
invited user creates the account in the web vault with the invited
address. Without SMTP settings Vaultwarden sends no invitation mail, and
nobody but the admin knows of the invitation.

The Service `vaultwarden` serves plain HTTP on port 8000, the port the
compose example publishes, with the web vault, the API and the WebSocket
notifications. The web vault works only over HTTPS, so expose it through a
route or Ingress that terminates TLS at the address of `domain`. A path in
`domain` moves every route below it, the health check's `/alive` too.

## Mapping

The service `vaultwarden` becomes the component `vaultwarden`. Its name
stays, so no reference is rewritten.

| Compose | Recipe |
|---|---|
| service `vaultwarden` | StatefulSet `vaultwarden`, Service `vaultwarden`, Secret `vaultwarden` with `ADMIN_TOKEN` |
| `vaultwarden/server:latest` | `docker.io/vaultwarden/server:1.37.5@sha256:4fe17f415f90087377d37c755e0ea3cf189dcc6794e49cdd2a9adbb4937d9e1f`, which `latest` was at migration |
| port `127.0.0.1:8000:80` | Service port `http` on 8000 to the container's port 80, `ClusterIP` |
| `DOMAIN`, `https://vw.domain.tld` | `env` from `applications.vaultwarden.domain` |
| bind mount `./vw-data/` at `/data/` | claim template `vw-data`, `ReadWriteOnce`, `1Gi` |
| the image's `HEALTHCHECK`, `/healthcheck.sh` | readiness probe every 60 seconds with a timeout of 10 seconds and 3 failures |
| `restart: unless-stopped`, `container_name` | not rendered |
| not in the example | `ADMIN_TOKEN` from `applications.vaultwarden.admin_token` (DEC-56), `SIGNUPS_ALLOWED: "false"` (DEC-55) |

The example keeps the vault in SQLite, Vaultwarden's default, and so does
the recipe (DEC-57).

## Proof

`check vaultwarden --level deploys` with `tests/target.yml`, on kind for
each Kubernetes minor CI tests, with check 0.14.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38). `tests/target.yml` sets the compose example's domain and the
Argon2id PHC string of a test token.

`tests/smoke` starts a pod of Vaultwarden's image, which carries `curl`.
From there, through the Service `vaultwarden` on port 8000, it

- gets `/alive`
- requires that `/api/version` names the image tag the StatefulSet runs,
  and that `/api/config` names the domain
- gets 401 from `/admin` with a wrong token, logs in with the test token,
  lists the users through `/admin/users` and reads `signups_allowed: false`
  from `/admin/diagnostics/config`
- invites `smoke@example.com` through `/admin/invite`, deletes the pod
  `vaultwarden-0`, and finds the user in `/admin/users` once the new pod is
  ready, which needs the database on the claim.

Not tested: the web vault in a browser, a client's login, mail, and a
route that terminates TLS.
