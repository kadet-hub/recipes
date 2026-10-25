# powerdns

PowerDNS Authoritative Server with one zone in SQLite and its HTTP API,
designed in kadet-hub on PowerDNS's image and rendered by the kadet-hub
`kubernetes` generator 1.8.0.

Source: `docker.io/powerdns/pdns-auth-51:5.1.5@sha256:77ff4efdbb9ec30e9309c8a1cbed6121a67fa3be25c848bbbfa756fc75bf9a27`

Level: `deploys`

PowerDNS publishes no chart and no Kustomize base, and its compose file
builds the images from the repository, so the recipe is designed on the
image PowerDNS builds (DEC-11 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
PowerDNS is GPL-2.0. PowerDNS publishes one repository per release line,
and `pdns-auth-51` holds the 5.1 releases. The tag is an index for
linux/amd64 and linux/arm64.

## Replaces

This recipe replaces the PowerDNS part of the `external-dns-powerdns`
recipe of kadet-hub/examples, which stood in for Bitnami's `external-dns`
chart. The external-dns part follows as a recipe of this repository that
includes this one. Moving from it changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| ref `powerdns/api-key` with the `base64` backend in the class | `applications.powerdns.api_key`, set by the target with the ref backend of your choice |
| Namespace `dns`, rendered by the recipe | no Namespace. The target sets `namespace` and creates it. |
| zone `example.internal` in the init container `zone` | `applications.powerdns.zone`, `example.internal` by default |
| PowerDNS 5.1.4 | PowerDNS 5.1.5 |

The StatefulSet `powerdns` with its claim template `data`, the Service
`powerdns` and the Secret `powerdns` with the key `api-key` keep their
names, so the claim `data-powerdns-0` and its zones stay. PowerDNS reads
the API key at every start, so the ref may hold a new key. external-dns
reads it from the same Secret.

## Include

```yaml
classes:
  - recipes.powerdns
parameters:
  namespace: dns
  kapitan:
    vars:
      target: powerdns
  applications:
    powerdns:
      api_key: <ref>
```

## Required parameters

`applications.powerdns.api_key`, the key of the HTTP API, must be set as a
ref with the backend of your choice. Without it the compile stops with
`Interpolation key 'applications.powerdns.api_key' not found`.

## Settings

| Setting | Inventory |
|---|---|
| PowerDNS version | `applications.powerdns.version`, together with the digest in `components.powerdns.image` |
| zone, `example.internal` | `applications.powerdns.zone` |
| volume size, 1Gi | `components.powerdns.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.powerdns.resources` |

The init container `seed` copies the image's empty database onto an empty
claim, which hides it in `/var/lib/powerdns`. The init container `zone`
creates the zone with the name server `ns1.<zone>` when the database lacks
it. Changing the zone later adds the new zone and keeps the old one.

The image runs as the user `pdns`, UID 953, and binds port 53 through the
sysctl `net.ipv4.ip_unprivileged_port_start`, which Pod Security's
`restricted` level allows. The readiness probe tests DNS over TCP.

The image's entrypoint serves the API on port 8081 to every address
(`webserver-allow-from=0.0.0.0/0` in `dockerdata/startup.py` of
PowerDNS/pdns), so any pod that reaches the Service with the key can change
the zones. A NetworkPolicy in the target narrows that down.

## Proof

`check powerdns --level deploys` with `tests/target.yml` on kind
`kindest/node:v1.37.0`. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke`
writes an A record into `example.internal` through the API on the Service
`powerdns`, with the key from the Secret, and reads it back through the
Service over UDP and TCP on port 53. The kadet-hub/examples recipe checked
a record that external-dns wrote.
