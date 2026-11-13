# memcached

memcached as a single in-memory cache without authentication, designed in
kadet-hub on the Docker Official Image `memcached` and rendered by the
kadet-hub `kubernetes` generator 1.14.0.

Source: `docker.io/library/memcached:1.6.45@sha256:a395a1bcf5e0e2b0fa4a0142e12b4e24a2320ba4b7c6ffa8655a1a86e8f29dee`

Level: `deploys`

The memcached project publishes no chart, Kustomize base or image. The
`docker-compose.yml` of [memcached/memcached](https://github.com/memcached/memcached)
builds test images from the Dockerfiles in `devtools/`, which run
`make test`. docker-library builds the Docker Official Image `memcached`
from the release tarball of memcached.org in
[docker-library/memcached](https://github.com/docker-library/memcached), so
the recipe is designed on that image (DEC-150 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The image's
documentation is its [Docker Hub page](https://hub.docker.com/_/memcached).
memcached is BSD-3-Clause. The recipe follows memcached's newest release,
1.6.45 of 2026-07-10. The tag `1.6.45` is the image's default variant on
Debian 13, and the digest is that of its index for linux/amd64,
linux/arm/v5, linux/arm/v7, linux/arm64/v8, linux/386, linux/ppc64le,
linux/riscv64 and linux/s390x.

The recipe can stand in for Bitnami's `memcached` chart in its default
`standalone` architecture. It renders the Deployment `memcached` with one
replica and the Service `memcached` on port 11211 (DEC-151). Moving a
release of that chart to the recipe is not tested.

## Include

```yaml
classes:
  - recipes.memcached
parameters:
  namespace: memcached
  kapitan:
    vars:
      target: memcached
```

## Required parameters

No parameter has to be set.

## Settings

| Setting | Inventory |
|---|---|
| memcached version | `components.memcached.image`, tag and digest |
| cache size, 64 megabytes | `components.memcached.args` as a mapping, such as `memory-limit: --memory-limit=1024`, with `components.memcached.resources.limits.memory` raised above it |
| other server options, such as `--conn-limit=4096` | `components.memcached.args` as a mapping, each value one option |
| resources | `components.memcached.resources` |
| Service type, `ClusterIP` | `components.memcached.service.type` |
| `nodeSelector`, `tolerations`, `affinity` | `components.memcached.node_selector`, `components.memcached.tolerations`, `components.memcached.affinity` |

memcached accepts every client that reaches the Service, without
authentication and without TLS, as Bitnami's chart does by default
(DEC-153). It listens on TCP port 11211 only. UDP is off, memcached's
default. The cache lives in the pod's memory and is empty after every
restart.

With its cache of 64 megabytes full, memcached used 70 MiB of the memory
limit of 192Mi on kind. Raise the limit together with `--memory-limit`.

The pod runs as the image's user `memcache`, UID 11211, with a read-only
root filesystem, and passes Pod Security `restricted`. A readiness probe
connects to port 11211. There is no liveness probe (DEC-152).

## Left out

Bitnami's chart 8.8.7 renders these with its defaults as well:

- `NetworkPolicy/memcached`. It admits port 11211 from every source and
  all egress, and memcached listens on no other port.
- `PodDisruptionBudget/memcached`. `maxUnavailable: 1` of one replica
  allows every eviction.
- `ServiceAccount/memcached`. No role binds it. The recipe's pod runs as
  `default` without a token, as the chart's pod runs without one.
- On the Deployment, the liveness probe `pgrep memcached`, which the
  pinned image cannot run, the preferred pod anti-affinity, which does
  nothing for one replica, the CPU limit of 150m, the ephemeral-storage
  request and limit, and the environment variables and `emptyDir` mounts
  of Bitnami's image.
- On the Service, `publishNotReadyAddresses: true`.

## Proof

`check memcached --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke`
connects with bash's `/dev/tcp` from the memcached pod to the Service
`memcached` on port 11211. It stores a value, reads it back on a second
connection, and requires `stats` to report the version of the image tag.
It checks that the pod passes Pod Security `restricted`.
