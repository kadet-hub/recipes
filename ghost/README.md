# ghost

Ghost 6.75.0, the publishing platform for blogs and newsletters, with its
content directory on a claim, designed in kadet-hub on Ghost's Docker
image and rendered by the kadet-hub `kubernetes` generator 1.16.0. The
database is the included recipe `mysql`.

Source: `docker.io/library/ghost:6.75.0-alpine@sha256:3af1575bb8917c6c0057beff85db92a4ac650f726956fd9de96932fea01c397c`

Level: `deploys`

Ghost publishes no chart. Its install guide for Docker runs the compose
file of [TryGhost/ghost-docker](https://github.com/TryGhost/ghost-docker),
which mounts directories of its repository into Caddy and MySQL and builds
images for its analytics, so the recipe is designed on the image that file
runs (DEC-210 in [docs/specs/recipes.md](../docs/specs/recipes.md)). Ghost
maintains that image, the Docker Official Image `ghost`, in
[TryGhost/docker-library-ghost](https://github.com/TryGhost/docker-library-ghost).
Ghost is MIT. The recipe follows Ghost's newest release in the variant
`alpine`, which Ghost's compose file runs. The digest is that of the index
for linux/amd64 and linux/arm64.

## Include

```yaml
classes:
  - recipes.ghost
parameters:
  namespace: ghost
  kapitan:
    vars:
      target: ghost
  applications:
    ghost:
      url: https://blog.example.com
    mysql:
      password: <ref>
      root_password: <ref>
```

The recipe includes `recipes.mysql`. Pin only this recipe in the fetch
inventory. The consumer workflow adds `mysql` at the digest this version's
index record lists under `includes`. Kapitan's `--fetch` reads no index,
so for a local compile pull it by digest as the recipe's page on
kadet-hub.org shows.

## Required parameters

`applications.ghost.url` is the URL readers and staff reach Ghost at, with
its scheme, such as `https://blog.example.com`. Ghost builds every link
from it. With an `https` URL Ghost redirects requests that a proxy does not
mark as HTTPS with `X-Forwarded-Proto`.

The included recipe `mysql` requires `applications.mysql.password`, the
password with which Ghost connects as the user `app`, and
`applications.mysql.root_password`. Set both as refs with the backend of
your choice. Without one of the three parameters the compile stops with
`Interpolation key` and its name.

## The owner account

The recipe creates no account (DEC-213 in the spec). The first visitor of
`/ghost/#/setup` names the site and creates the owner, so set it up before
the target exposes the Service to others. The page posts to the Admin API's
`/ghost/api/admin/authentication/setup/`, which `tests/smoke` calls from a
pod in the namespace. Ghost refuses a second setup once the owner exists.

## Mail

The recipe sets no mail (DEC-214 in the spec). Ghost's image sends with the
transport `Direct`, from the pod straight to the recipient's mail server.
Ghost mails staff invitations, password resets and the sign-in links of
members. It also mails a code for each staff login from a browser without a
verified session, because `security.staffDeviceVerification` is on. Only
the owner's first login after the setup skips that code. Every later login
from another browser, or after the session ended, fails with
`Failed to send email` until mail works. Set Ghost's mail settings as
environment variables of the component, such as
`components.ghost.env.mail__transport: SMTP` with `mail__options__host`,
`mail__options__port`, `mail__options__auth__user`,
`mail__options__auth__pass` and `mail__from`. Ghost's configuration
reference lists them. A password belongs in a Secret, referenced with
`secretKeyRef`.

## Settings

| Setting | Inventory |
|---|---|
| Ghost version | `components.ghost.image`, tag and digest |
| content volume size, 8Gi | `components.ghost.volume_claims.content.spec.resources.requests.storage` |
| resources | `components.ghost.resources` |
| further Ghost settings, such as `admin__url` or mail | `components.ghost.env.<setting>`, with `__` between the levels of Ghost's configuration |
| exposure | a route or Ingress of the target to the Service `ghost` on port 2368 |
| database, its user and both passwords | the settings of `mysql` |

The Service `ghost` serves plain HTTP on port 2368. Expose it through a
route or Ingress that terminates TLS at the address of `url` and sets
`X-Forwarded-Proto`.

The claim `content` holds what Ghost keeps outside MySQL: uploaded images
and files, themes, settings files and Ghost's log files. At each start the
image's entrypoint copies its default themes and directories onto the
claim where they are missing. Posts, members, staff users and sessions
live in MySQL. Ghost connects to it without TLS.

The pod runs as the image's user `node`, UID 1000, and passes Pod Security
`restricted`. The init container `wait-for-database` waits until the
Service `mysql` accepts connections, because Ghost exits at its start
while the database does not answer.

The readiness probe gets `/` every 10 seconds with
`X-Forwarded-Proto: https`. Ghost answers 503 while it boots and runs
database migrations, and 500 while MySQL is down, so the pod is not ready
then. There is no liveness probe, which would restart Ghost in the middle
of a migration.

MySQL is the included recipe `mysql`, MySQL 9.7 LTS. Ghost's own compose
file runs MySQL 8.0, and Ghost's CI tests against MySQL 8.0. MySQL 8.0
reached its end of life on 2026-04-30 (DEC-211 in the spec).

## Proof

`check ghost --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/target.yml`
sets the URL `http://ghost:2368`, which the test pod reaches, and
low-entropy test passwords.

`tests/smoke` checks that the pods of Ghost and MySQL pass Pod Security
`restricted` and that Ghost did not restart. From a pod of the Ghost image,
through the Service `ghost` on port 2368, it

- reads that Ghost is not set up yet and that the front page names the
  image's Ghost version
- creates the owner through the Admin API's setup and gets 403 for a
  second setup
- gets no session for a wrong password and logs in
- publishes a post through the Admin API and reads it on its URL without
  the session
- uploads a PNG and fetches it byte for byte
- deletes the pod `ghost-0` and, once the new pod is ready, reads the post
  and the PNG again and reaches `/ghost/api/admin/users/me/` with the same
  session.

## Not proven

Ghost's database migrations of later releases on MySQL 9.7, which Ghost
does not test. Mail with any transport, and with it logins after the
first, members' sign-up and newsletters. The admin app in a browser. A
route or Ingress in front of the Service with an `https` URL.
