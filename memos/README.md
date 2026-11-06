# memos

Memos 26.11.0, a self-hosted note-taking app with a timeline of Markdown
notes, with its data in SQLite on a claim, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from the Docker Compose example in the Memos
documentation.

<!-- renovate: branch=main -->
Source: `https://github.com/usememos/dotcom/blob/b5fd0a3dff1408783452c627b05dc7aecf745c47/content/docs/deploy/docker-compose.mdx@sha256:f2d53cb23eea5cd5f65beb4b716d443ac2e225027e398ac41ab9e9fa79d5ef02`

Level: `deploys`

The compose file is the code block under "Basic setup" of the
documentation's Docker Compose page, which usememos/dotcom holds (DEC-170
in [docs/specs/recipes.md](../docs/specs/recipes.md)). The compose file in
the Memos repository mounts a directory of the user's home, and the chart
of usememos/helm is served by no chart repository. The documentation has
no releases, so the commit is the newest of `main` on 2026-11-05, the one
that added the changelog of Memos 26.11.0. Memos is MIT. The documentation
repository has no license file, and the recipe copies no text of it. The
image is an index for linux/amd64, linux/arm64 and linux/arm/v7. Memos runs
as the image's user `nonroot`, UID 10001, and passes the Pod Security level
`restricted`.

## Include

```yaml
classes:
  - recipes.memos
parameters:
  namespace: memos
  kapitan:
    vars:
      target: memos
  applications:
    memos:
      instance_url: https://memos.example.com
```

## Required parameters

`applications.memos.instance_url` is `MEMOS_INSTANCE_URL`, the URL users
reach Memos at, with its scheme, such as `https://memos.example.com`.
Memos builds the links of its sitemap from it and allows cross-origin
requests with cookies from that origin. On the first start the URL also
makes the instance public, so visitors without an account see the memos
marked public (DEC-171). An admin can change that in the instance
settings. A later change of the URL leaves it as it is. Without
the parameter the compile stops with
`Interpolation key 'applications.memos.instance_url' not found`.

## The admin account

The recipe creates no account (DEC-173). The first account that signs up,
in the web UI or through the API, becomes the admin. After that Memos
refuses every sign-up without a login, and the admin creates further
accounts in the web UI. Until the target exposes the Service, only the
cluster reaches the sign-up, so create the admin account first, as here
from a pod in the namespace.

```sh
curl -fsS -H 'Content-Type: application/json' \
  --data '{"username": "admin", "password": "<password>"}' \
  http://memos:5230/api/users
```

The recipe closes the registration with Memos' declarative configuration
(`content/docs/configuration/declarative-configuration.mdx` of the
documentation). The ConfigMap `memos` mounts `instance.json` at
`/etc/memos/config`, and Memos applies it at every start. The file sets
`disallowUserRegistration` of the setting group `GENERAL` to `true`, so
the web UI and the API refuse to change that field. It leaves the group's
other fields, such as the instance's title, to the web UI. To open the
registration, set the value of
`components.memos.config_maps.config.data.instance.json` in the target
with `false`. Memos stops at startup when a declaration it applied
disappears from the files, so a target that drops it adds a `removed`
entry for `instance/settings/GENERAL`.

## Settings

| Setting | Inventory |
|---|---|
| Memos version | `components.memos.image`, tag and digest |
| instance URL | `applications.memos.instance_url` |
| other environment variables of Memos, such as `MEMOS_LOG_LEVEL` or `MEMOS_WEBHOOK_PRIVATE_NETWORK_ALLOWLIST` | `components.memos.env.<variable>` |
| exposure | a route or Ingress of the target to the Service `memos` on port 5230 |
| size of the claim `data`, `1Gi` | `components.memos.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.memos.resources` |

Memos keeps its state in `/var/opt/memos` on the claim: the SQLite
database `memos_prod.db` and uploaded files. SQLite allows one replica.
Memos answers `/healthz` with `Service ready.` while its database answers.
The recipe renders no probe, because neither the compose file nor the
image defines a health check.

The Service `memos` serves plain HTTP on port 5230, the port the compose
file publishes, for the web UI and the API alike. TLS belongs to the
route or Ingress in front of it.

## Mapping

The service `memos` becomes the component `memos`. Its name stays, so no
reference is rewritten.

| Compose | Recipe |
|---|---|
| service `memos` | StatefulSet `memos`, Service `memos` |
| `neosmemo/memos:stable` | `docker.io/neosmemo/memos:26.11.0@sha256:087e7dc6b76b31fcd1107a5767398b2a310ced209adb791efd8760c745dc8034`, which `stable` was at migration |
| port `5230:5230` | Service port `http` on 5230 to the container's port 5230, `ClusterIP` |
| bind mount `./data` at `/var/opt/memos` | claim template `data`, `ReadWriteOnce`, `1Gi` |
| `MEMOS_PORT: 5230`, `MEMOS_DRIVER: sqlite` | the same variables |
| `MEMOS_INSTANCE_URL: https://memos.example.com` | `applications.memos.instance_url` (DEC-171) |
| `container_name: memos` | not rendered |
| `restart: unless-stopped` | not rendered |
| not in the compose file | UID and GID 10001 with `fsGroup` 10001 under `restricted` (DEC-172) |
| not in the compose file | ConfigMap `memos` with `instance.json` at `/etc/memos/config`, registration closed (DEC-173) |

## Proof

`check memos --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests, with check 0.16.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38). `tests/target.yml` sets the instance URL to the Service's own
address, `http://memos:5230`.

`tests/smoke` requires that the pod passes Pod Security `restricted`. It
then starts a pod of Memos' image, whose busybox carries `wget`. From
there, through the Service `memos` on port 5230, it

- gets `Service ready.` from `/healthz` and the web UI from `/`
- requires from `/api/instance/profile` the image's version, the instance
  URL, the public access policy and that the instance needs its setup
- creates the first account through `/api/users` without a login and
  requires the role `ADMIN`, then gets 403 there for a second account
- gets 400 from `/api/auth/signin` for a wrong password, signs in, creates
  a private memo with the access token and reads it back, and gets 401 for
  the memo without a token
- deletes the pod `memos-0` and, once the new pod is ready, requires that
  the instance needs no setup, signs in again and reads the memo, which
  needs `memos_prod.db` on the claim.

Not tested: the web UI in a browser, attachments, MySQL or PostgreSQL in
place of SQLite, and a route or Ingress in front of the Service.
