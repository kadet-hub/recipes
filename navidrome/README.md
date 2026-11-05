# navidrome

Navidrome 0.64.2, a music server with a web UI and the Subsonic API, with
its SQLite database and its music on claims, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from its Docker Compose file.

<!-- renovate: tag=v0.64.2 -->
Source: `https://github.com/navidrome/navidrome/blob/101145742f4762164202cb4858c9126258bdc463/contrib/docker-compose/docker-compose.yml@sha256:ef8a611ca3cf06af8879253809632b7005ff47cb892018006bb3e290022f8958`

Level: `deploys`

Navidrome publishes no Helm chart. The commit is the tag `v0.64.2`, from
which the image `0.64.2` was built. Navidrome is GPL-3.0. The image is an
index for linux/amd64, linux/arm64, linux/arm/v7, linux/arm/v6, linux/386
and linux/riscv64. Navidrome runs as UID 1000 and passes the Pod Security
level `restricted`.

## Include

```yaml
classes:
  - recipes.navidrome
parameters:
  namespace: navidrome
  kapitan:
    vars:
      target: navidrome
```

## Required parameters

No parameter has to be set.

## The admin account

The recipe creates no account (DEC-218 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The first visitor of
the web UI creates the first user, who is an admin, so create it before
the target exposes the Service to others. The web UI posts to
`/auth/createAdmin`, which `tests/smoke` calls from a pod in the namespace.
Navidrome refuses a second first admin, and it has no self-registration.
The admin creates further users in the web UI.

## Music

Navidrome reads the music below `/music`, from the claim `music`, mounted
read-only. Put files on it from a pod of your own that mounts the claim
`music-navidrome-0`. The claim is `ReadWriteOnce`, so that pod has to run
on the node of `navidrome-0`. Navidrome finds new files with its scanner,
which a scan in the web UI or `/rest/startScan` starts.

A StatefulSet uses a claim of the name `music-navidrome-0` that exists
before its pod, in place of creating one. A library on a PersistentVolume
of its own, such as an NFS share, can therefore be bound to a claim of
that name that the target creates first. This is not tested.

## Settings

| Setting | Inventory |
|---|---|
| Navidrome version | `components.navidrome.image`, tag and digest |
| Navidrome's settings, such as `ND_SCANSCHEDULE` or `ND_BASEURL` | `components.navidrome.env.<variable>` |
| size of the claim `data`, `1Gi` | `components.navidrome.volume_claims.data.spec.resources.requests.storage` |
| size of the claim `music`, `1Gi` | `components.navidrome.volume_claims.music.spec.resources.requests.storage` |
| exposure | a route or Ingress of the target to the Service `navidrome` on port 4533 |
| resources | `components.navidrome.resources` |

The claim `data` holds the SQLite database, the cache of transcoded files
and artwork, and Navidrome's settings. SQLite allows one replica.

The root filesystem is read-only, as the compose file asks. `/tmp` is an
`emptyDir`, because SQLite needs a temporary file for a database migration
of the first start (DEC-215 in the spec). With the compose file alone,
Navidrome 0.64.2 exits at its first start for that reason.

## Mapping

The service `navidrome` becomes the component `navidrome`. Its name stays,
so no reference is rewritten.

| Compose | Recipe |
|---|---|
| service `navidrome` | StatefulSet `navidrome`, Service `navidrome` |
| `deluan/navidrome:latest` | `docker.io/deluan/navidrome:0.64.2@sha256:38dc2727bfcfd5ede290f8ada114fc90368146f265ae4701ddddbcbe2a44ee52`, which `latest` was at migration |
| port `4533:4533` | Service port `http` on 4533, `ClusterIP` |
| volume `navidrome_data` at `/data` | claim template `data`, `ReadWriteOnce`, `1Gi` |
| `read_only: true` | `readOnlyRootFilesystem: true` and an `emptyDir` at `/tmp` (DEC-215) |
| `version`, `container_name`, `restart: unless-stopped` | not rendered |
| the comment `#- "/mnt/music:/music:ro"` | claim template `music`, `ReadWriteOnce`, `1Gi`, read-only at `/music` (DEC-216) |
| the comment `# user: 1000:1000` | UID, GID and `fsGroup` 1000 under `restricted` (DEC-217) |

## Proof

`check navidrome --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests. A compose file has no Kubernetes objects to
compare with, so the recipe is proven by deploying it (RCP-38).

`tests/smoke` checks that the pod passes Pod Security `restricted`. It
starts a pod of Navidrome's image, which carries `curl` and `ffmpeg`, as
UID 1000 with the claim `music-navidrome-0` mounted, and writes a FLAC file
of three seconds of silence with a title, an artist and an album. From
there, through the Service `navidrome` on port 4533, it

- gets `/ping`, and Subsonic error 40 from `/rest/ping` before a user exists
- creates the admin through `/auth/createAdmin` and gets 403 for a second
  one
- gets `ok` from `/rest/ping` as the admin, and error 40 for a wrong
  password
- starts a scan with `/rest/startScan`, finds the track by its title with
  `/rest/search3`, 3 seconds long, and downloads it byte for byte with
  `/rest/download`
- deletes the pod `navidrome-0` and, once its successor is ready, gets `ok`
  as the admin and finds the track again.

## Not proven

A library of real size and how long its scan takes. Transcoding, and
streaming to a Subsonic client or a browser. The web UI in a browser. An
existing volume of music mounted in place of the claim `music`. A route
or Ingress in front of the Service.
