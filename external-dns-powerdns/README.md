# external-dns-powerdns

external-dns writing a record for every annotated Service into a zone on a
PowerDNS Authoritative Server, rendered by the kadet-hub `kubernetes`
generator 1.9.0 from the external-dns project's own Helm chart 1.23.0.
PowerDNS is the included recipe `powerdns`.

Source: `https://kubernetes-sigs.github.io/external-dns/external-dns:1.23.0@sha256:6d149b9b04db1dc9e46b3693a4eca4ac90d6bba5e3b2a0fdd067ce3f7bfbc31e`

Level: `deploys`

The chart comes from [kubernetes-sigs/external-dns](https://github.com/kubernetes-sigs/external-dns),
tag `external-dns-helm-chart-1.23.0`, and runs external-dns 0.23.0. It is
published only in that HTTP repository, so the digest is the SHA-256 of the
archive its `index.yaml` lists (RCP-23 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
external-dns is Apache-2.0.

## Replaces

This recipe replaces the `external-dns-powerdns` recipe of
kadet-hub/examples, which stood in for Bitnami's `external-dns` chart. Its
PowerDNS part is the recipe `powerdns`, whose README lists the changes
there. Moving from it changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| Deployment and ServiceAccount `external-dns` | Deployment and ServiceAccount `external-dns-powerdns` |
| ClusterRole and ClusterRoleBinding `dns-external-dns` | ClusterRole and ClusterRoleBinding `external-dns-powerdns` |
| ingresses readable, nodes only listed | as the chart: no ingresses, nodes listed and watched |
| no Service | Service `external-dns-powerdns`, port `http` 7979 |
| no CRDs | the chart's CRDs `dnsendpoints.externaldns.k8s.io` and `dnsrecords.externaldns.k8s.io` |
| `--pdns-server=http://powerdns.dns.svc:8081` | `--pdns-server=http://powerdns:8081`, the Service in the target's namespace |
| `--domain-filter=example.internal` | `applications.powerdns.zone`, `example.internal` by default |
| UID and GID 65534 | UID and GID 65532 with `fsGroup` 65534, as the chart sets them |
| readiness probe on `/healthz` | readiness and liveness probes on `/healthz` |

external-dns keeps its state in the zone. It marks each record it writes
with a TXT record that carries `--txt-owner-id=kadet-hub-recipe`, the
examples recipe's owner ID, so the renamed Deployment takes the records over.
Delete the examples Deployment, ServiceAccount, ClusterRole and
ClusterRoleBinding first, so that only one external-dns syncs the zone.

## Include

```yaml
classes:
  - recipes.external-dns-powerdns
parameters:
  namespace: dns
  kapitan:
    vars:
      target: external-dns-powerdns
  applications:
    powerdns:
      api_key: <ref>
```

Fetch `powerdns` at the same commit as this recipe, with a second `git`
dependency with `subdir: powerdns` and
`output_path: inventory/classes/recipes/powerdns`.

## Required parameters

`applications.powerdns.api_key`, the key of PowerDNS's HTTP API, which the
included recipe `powerdns` requires. Set it as a ref with the backend of
your choice. Without it the compile stops with
`Interpolation key 'applications.powerdns.api_key' not found`.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `applications.external-dns-powerdns.version`, together with the digest in `components.external-dns-powerdns.image` |
| `domainFilters` | `applications.powerdns.zone`, which sets the zone of `powerdns` too |
| `txtOwnerId` | `components.external-dns-powerdns.args.txt-owner-id` |
| `policy` | `components.external-dns-powerdns.args.policy` |
| `interval` | `components.external-dns-powerdns.args.interval` |
| `logLevel`, `logFormat` | `components.external-dns-powerdns.args.log-level`, `components.external-dns-powerdns.args.log-format` |
| `resources` | `components.external-dns-powerdns.resources` |

`args` is a mapping, so a target replaces one argument by its key or drops
it with `~`.

external-dns reads the Services of every namespace. A Service with the
annotation `external-dns.kubernetes.io/hostname` set to a name in the zone
gets an A record with its cluster IP (`--publish-internal-services`).
With `--policy=sync` it also deletes the records it owns once their Service
is gone. Records without its TXT record stay. Two installations that write
into one zone need different owner IDs.

The API key comes from the Secret `powerdns`, key `api-key`, and the API
from the Service `powerdns`, both rendered by `powerdns`.

The CRDs DNSEndpoint and DNSRecord are the chart's `crds/`, copied into
`vendor/` from the archive of the `Source` line, with the project's
Apache-2.0 license next to each. external-dns reads them only with
`--source=crd`, which the recipe does not set.

## Proof

`check external-dns-powerdns --level deploys` with `tests/values.yaml` and
`tests/target.yml` on kind `kindest/node:v1.37.0`. The objects of
`powerdns` are left out of the comparison and applied with the recipe. The
Deployment and the Service select on `name`, the chart on
`app.kubernetes.io/name` and `instance`. The ClusterRoleBinding is named
`external-dns-powerdns`, the chart's `external-dns-powerdns-viewer`.
`check` compares what the ServiceAccount may do, not the names.

`tests/smoke` applies a Service annotated with `web.example.internal` and
waits until PowerDNS answers its A record with the Service's cluster IP
through the Service `powerdns`, as the kadet-hub/examples check did.
