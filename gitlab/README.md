# gitlab

GitLab CE 19.5.5 in sameersbn's image, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from the Docker Compose file of
sameersbn/docker-gitlab. The database is the included recipe `postgresql`,
the cache, sessions and job queues `valkey`.

<!-- renovate: tag=19.5.5 -->
Source: `https://github.com/sameersbn/docker-gitlab/blob/d03fbcedffc0c3eb76e5a13120ad772e6c110383/docker-compose.yml@sha256:bbffbaf5513e923529fbb157dd0186b7e2874503e7048d8535c9effa8eacf31a`

Level: `deploys`

The commit is the tag `19.5.5`. The compose file and the image are MIT.
The image is a third party's build of GitLab CE from source, not GitLab's
Omnibus image or chart. It runs nginx, Puma, Sidekiq, Workhorse, Gitaly,
gitlab-shell, sshd and cron under supervisord in one container and is
built for linux/amd64 only. `postgresql` requires `cnpg`, so install
`cnpg` first, in a target of its own. The image starts as root and drops
to the user `git` for GitLab, while nginx, sshd and cron stay root, so the
target's namespace needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.gitlab
parameters:
  namespace: gitlab
  kapitan:
    vars:
      target: gitlab
  applications:
    gitlab:
      host: <host>
      db_key_base: <ref>
      secret_key_base: <ref>
      otp_key_base: <ref>
      active_record_encryption_primary_key: <ref>
      active_record_encryption_deterministic_key: <ref>
      active_record_encryption_key_derivation_salt: <ref>
    valkey:
      password: <ref>
```

Pin only this recipe in the fetch inventory. The consumer workflow adds
`postgresql` and `valkey` at the digests this version's index record lists
under `includes`. Kapitan's `--fetch` reads no index, so for a local
compile pull them by digest as the recipe's page on kadet-hub.org shows.

## Required parameters

`applications.gitlab.host` is the host name in the URLs GitLab generates,
`GITLAB_HOST`, such as the host of the route or Ingress in front of the
Service.

The other six are GitLab's keys. Set them as refs with the backend of your
choice. GitLab encrypts data in the database with them, so they live as
long as the database, and an installation that moves here keeps its
values:

- `applications.gitlab.db_key_base`, `GITLAB_SECRETS_DB_KEY_BASE`, for CI
  variables and import credentials;
- `applications.gitlab.secret_key_base`, `GITLAB_SECRETS_SECRET_KEY_BASE`,
  for sessions and password reset links;
- `applications.gitlab.otp_key_base`, `GITLAB_SECRETS_OTP_KEY_BASE`, for
  two-factor secrets;
- `applications.gitlab.active_record_encryption_primary_key`,
  `applications.gitlab.active_record_encryption_deterministic_key` and
  `applications.gitlab.active_record_encryption_key_derivation_salt`, the
  `GITLAB_SECRETS_ACTIVE_RECORD_ENCRYPTION_*` of GitLab's encrypted
  columns. A key may list several values as `["<key>","<old key>"]`.

The image's README asks for at least 64 random characters for the first
three and for 32 for the other three. The image stops without the first
three. Without the other three GitLab generates new keys at every start,
and what it encrypted with the old ones becomes unreadable.

`applications.valkey.password`, which the included recipe `valkey`
requires, is the password GitLab uses for Valkey. It may contain any
character.

Without one of them the compile stops with
`Interpolation key '<key>' not found`.

## Settings

| Setting | Inventory |
|---|---|
| GitLab version | `components.gitlab.image`, tag and digest |
| `GITLAB_HTTPS`, `GITLAB_TIMEZONE`, `TZ`, `GITLAB_BACKUP_SCHEDULE` and the other variables of the compose file and of the image's README | `components.gitlab.env.<variable>` |
| a credential, such as `SMTP_PASS` or `GITLAB_ROOT_PASSWORD` | `components.gitlab.secrets.credentials.string_data.<variable>.value` as a ref, and `components.gitlab.env.<variable>.secretKeyRef.key: <variable>` |
| SSH | `components.gitlab.ports.ssh` with `service_port: 22`, and `GITLAB_SSH_PORT` |
| size of the claim `data`, `1Gi` | `components.gitlab.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.gitlab.resources` |
| the Cluster and its database | `applications.postgresql`, which `postgresql`'s README lists |

The Service `gitlab` is a ClusterIP Service on port 80, named `http`.
Expose it with a route or Ingress in the target. Behind one that
terminates TLS, set `GITLAB_HTTPS` to `"true"`: GitLab then generates
`https` URLs on port 443, and nginx in the pod keeps serving HTTP on port
80. `GITLAB_PORT` and `GITLAB_SSH_PORT` are empty, so the image derives 80,
or 443 with `GITLAB_HTTPS`, and 22. sshd runs in the pod, but the Service
has no port for it.

The StatefulSet `gitlab` mounts its claim `data-gitlab-0` at
`/home/git/data`. The claim holds the repositories, uploads, LFS objects,
artifacts, packages, the SSH host keys and the backups, which the compose
file's `GITLAB_BACKUP_SCHEDULE` and `GITLAB_BACKUP_TIME` write daily at
01:00 to `/home/git/data/backups`, so size the claim for them. The
image's `config/secrets.yml` has no `openid_connect_signing_key`, so at
every start GitLab generates a new one, which signs CI ID tokens and its
OpenID Connect tokens, and moves the previous file with all keys in plain
text to `/home/git/data/backups/secrets.yml.orig.<time>`. GitLab used
about 4.5 GiB of memory on kind.

The first start sets up the database, which took about four minutes on
kind once the image was pulled. The startup probe allows an hour for it.
The probes get `/users/sign_in` on port `http`. With a
`GITLAB_RELATIVE_URL_ROOT`, set that path in
`components.gitlab.healthcheck.startup.path` and `.readiness.path` too.

`GITLAB_ROOT_PASSWORD` sets the password of `root` when GitLab sets up an
empty database. The compose file leaves it empty, and GitLab then gives
`root` a random password that it does not print. Set it before the first
start, or later in the pod as the user `git` with
`bundle exec rake "gitlab:password:reset[root]"`. Sign-up is on, the
image's default for `GITLAB_SIGNUP_ENABLED`, and GitLab holds new accounts
until an admin approves them. `GITLAB_SECRETS_ENCRYPTED_SETTINGS_KEY_BASE`
is not in the compose file. Without it GitLab generates a key at every
start for encrypted settings files, which only exist once someone writes
one with a `gitlab:*:secret:write` task.

## Mapping

The service `gitlab` becomes the component `gitlab`. `postgresql` and
`redis` become the included recipes `postgresql`, with its option
`createdb`, and `valkey`. GitLab reaches them through the Services
`postgresql-cluster-rw` and `valkey` in place of `postgresql` and `redis`.

| Compose | Recipe |
|---|---|
| service `gitlab`, `sameersbn/gitlab:19.5.5` | StatefulSet `gitlab` with `docker.io/sameersbn/gitlab:19.5.5@sha256:65b58defc2d1bf864b32532a28a848f88e6459ab7dcee43ba046c19ff1e9db04`, the linux/amd64 image of the tag |
| service `postgresql`, `kkimurak/sameersbn-postgresql:17` with the database `gitlabhq_production` and the user `gitlab` | the included recipe `postgresql`, PostgreSQL 18.6 on CloudNativePG, with its option `createdb`. GitLab reads the host, database, user and the generated password from the Secret `postgresql-cluster-app`. |
| `DB_EXTENSION=pg_trgm,btree_gist` of `postgresql` | not rendered. GitLab creates both extensions as the database's owner, which PostgreSQL allows for them. |
| `PG_PARAM_MAX_LOCKS_PER_TRANSACTION=128` of `postgresql` | not rendered. PostgreSQL keeps its default of 64. A target sets 128 in `generators.cloudnative-pg.clusters.postgresql.postgresql.parameters.max_locks_per_transaction`. |
| service `redis`, `redis:7` with `--loglevel warning` and without a password | the included recipe `valkey`, Valkey 9.1.2 with the password of the ACL user `default` from the Secret `valkey-auth` |
| `REDIS_HOST=redis` | `valkey`, with `REDIS_PASSWORD` from `valkey-auth` and the ConfigMap `gitlab`, described below |
| `DB_HOST=postgresql` and the other `DB_*` | from the Secret `postgresql-cluster-app` |
| `GITLAB_HOST=localhost` | `applications.gitlab.host` |
| `GITLAB_PORT=10080`, `GITLAB_SSH_PORT=10022` | empty |
| `GITLAB_SECRETS_*` | the six required parameters in the Secret `gitlab` |
| `SMTP_PASS`, `IMAP_PASS`, `GITLAB_ROOT_PASSWORD` and the OAuth providers' secrets | not rendered. SMTP, IMAP and OAuth are off, and the other two are empty. |
| every other variable of `environment` | `env` with the same value, such as `TZ=Asia/Kolkata` and the SMTP and IMAP servers of Gmail |
| volume `gitlab-data` | claim template `data`, `ReadWriteOnce`, `1Gi` |
| volumes `postgresql-data` and `redis-data` | the claims of the included recipes |
| port `10080:80` | Service port 80, `ClusterIP` |
| port `10022:22` | not rendered |
| `healthcheck`, `/usr/local/sbin/healthcheck` every 5m, timeout 10s, 3 retries | readiness probe on `/users/sign_in` with the same values, and a startup probe every 10 seconds for up to an hour |
| `depends_on`, `restart: always` | not rendered. The image waits a minute for the database and Valkey at start, and the kubelet restarts it when it gives up. |
| SELinux option `Z` of the volumes | not rendered |

The image has no setting for a Redis password. The ConfigMap `gitlab`
holds a `resque.yml` that the pod mounts over the image's template
`/etc/docker-gitlab/runtime/config/gitlabhq/resque.yml`, SHA-256
`685f143b6435c93d6e80970b425635db3d7489d569b9c39e7c0863064fafd357` in
19.5.5. At every start the image copies the template to GitLab's
`config/resque.yml` and fills in `REDIS_HOST`, `REDIS_PORT` and
`REDIS_DB_NUMBER`. GitLab evaluates the file with ERB and takes the
password from `REDIS_PASSWORD`, URL-encoded. After an image update,
compare the image's template with that SHA-256.

The compose file's health check, `/usr/local/sbin/healthcheck`, requests
`https://127.0.0.1/-/liveness` when `GITLAB_HTTPS` is `true`, also when
nginx serves only HTTP behind a load balancer, so the probes request
`/users/sign_in` on port 80.

## Proof

`check gitlab --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests, with `cnpg` installed first. The objects of
`postgresql` and `valkey` are applied with the recipe. A compose file has
no Kubernetes objects to compare with, so the recipe is proven by
deploying it (RCP-38). `tests/target.yml` sets test values for the six
keys, a Valkey password with `:`, `@` and `/`, and `GITLAB_ROOT_PASSWORD`,
and runs one PostgreSQL instance.

`tests/smoke` checks that the pods pass Pod Security `baseline`. From a
pod of the gitlab image, through the cluster IP of the Service `gitlab`
on port 80, it gets the sign-in page, gets 401 from `/api/v4/user`
without a session, logs in as `root` through the form and gets `root`
from `/api/v4/user` in that session, which GitLab keeps in Valkey. It
pushes to `root/smoke` over HTTP, which creates the project, and clones
it. After it deleted `gitlab-0` and the new pod is ready, it clones the
project again from the claim `data`.

Not tested: Git over SSH, mail, OAuth and LDAP, the backups, an upgrade
from an older image, a route or Ingress with `GITLAB_HTTPS`, the
container registry, Pages, CI with a runner, and moving an existing
installation's data.
