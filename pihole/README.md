# pihole

Pi-hole, a DNS server that blocks ads and trackers for every device of a
network, rendered by the kadet-hub `kubernetes` generator 1.9.0 from the
Docker Compose example in the README of docker-pi-hole 2026.10.1.

Source: `https://github.com/pi-hole/docker-pi-hole/blob/ffd0a489a633d0f2512818c46fd651ac50789175/README.md@sha256:003d42d4097951284d6334af39399076490c696711b21f70081953ca3dd5596d`

Level: `deploys`

docker-pi-hole ships its compose example only as the code block under
"Quick Start" of its README, so the `Source` line pins the README (DEC-28).
The commit is the tag `2026.10.1`, from which the image `2026.10.1` was
built, with Pi-hole Core v6.5, Web v6.6.1 and FTL v6.8. The compose
example and the image are EUPL-1.2. The image starts as root and runs FTL,
Pi-hole's DNS core, as the user `pihole`, UID 1000, so the target's
namespace needs the Pod Security level `baseline`.

## Include

```yaml
classes:
  - recipes.pihole
parameters:
  namespace: pihole
  kapitan:
    vars:
      target: pihole
  applications:
    pihole:
      password: <ref>
```

## Required parameters

`applications.pihole.password` is the password of the web interface and
the API, set as a ref with the backend of your choice. Without it the
compile stops with
`Interpolation key 'applications.pihole.password' not found`. An empty
string turns the login off.

## Settings

| Setting | Inventory |
|---|---|
| Pi-hole version | `components.pihole.image`, tag and digest |
| time zone, `Europe/London` as in the compose example | `components.pihole.env.TZ` |
| upstream DNS servers, Google's `8.8.8.8` and `8.8.4.4` while unset | `components.pihole.env.FTLCONF_dns_upstreams`, separated by `;` |
| other settings of `pihole.toml`, such as `dns.dnssec` | `components.pihole.env.FTLCONF_<section>_<setting>`, such as `FTLCONF_dns_dnssec` |
| exposure | `components.pihole.service.type`, such as `LoadBalancer` |
| size of the claim `etc-pihole`, `1Gi` | `components.pihole.volume_claims.etc-pihole.spec.resources.requests.storage` |
| resources | `components.pihole.resources` |

FTL keeps its settings in `/etc/pihole/pihole.toml` on the claim, next to
the blocklists and the query log. It treats a setting from the environment
as read-only, so the web interface cannot change it.

The Service `pihole` is a ClusterIP Service with DNS on port 53 over TCP
and UDP, HTTP on port 80 and HTTPS on port 443, where FTL serves a
self-signed certificate it generates. The compose example publishes these
ports on the host. Devices outside the cluster reach Pi-hole once the
target exposes the Service, such as with `type: LoadBalancer`. Whether a
load balancer serves TCP and UDP on one address depends on its
implementation. `FTLCONF_dns_listeningMode: ALL` lets Pi-hole answer every
client that reaches it, so expose port 53 only to the networks it serves,
or it becomes an open resolver.

At its first start Pi-hole downloads its default blocklist, the hosts file
of StevenBlack/hosts, from raw.githubusercontent.com, and a cron job in the
container updates it every week.

The compose example adds three capabilities, which the recipe leaves out
(DEC-29 in the spec), and FTL logs a warning for each at start.
`NET_ADMIN` is needed only for Pi-hole's DHCP server. `SYS_TIME` lets FTL's
NTP client set the clock, which in a pod is the node's clock. `SYS_NICE`
lets FTL raise its own priority.

The DHCP server is not set up. DHCP needs Pi-hole on the LAN, through host
networking, a macvlan network or a DHCP relay, as Pi-hole's documentation
describes, and the compose example leaves its port 67/udp commented out.
The NTP server that FTL runs on port 123/udp is not published either, as in
the compose example.

## Mapping

The service `pihole` becomes the component `pihole`. Its name stays, so no
reference is rewritten.

| Compose | Recipe |
|---|---|
| service `pihole` | StatefulSet `pihole`, Service `pihole`, Secret `pihole` with `FTLCONF_webserver_api_password` |
| `pihole/pihole:latest` | `docker.io/pihole/pihole:2026.10.1@sha256:30f803ad5dd60ff96cc0a63008a2e9271af481c1b0399a182192b2e91152c1f9`, which `latest` was at migration |
| ports `53:53/tcp`, `53:53/udp`, `80:80/tcp` and `443:443/tcp` | Service ports `dns-tcp` and `dns-udp` on 53, `http` on 80 and `https` on 443, `ClusterIP` |
| `TZ` and `FTLCONF_dns_listeningMode` | `env` with the compose example's values |
| `FTLCONF_webserver_api_password` | from `applications.pihole.password` in the Secret `pihole` |
| bind mount `./etc-pihole` at `/etc/pihole` | claim template `etc-pihole`, `ReadWriteOnce`, `1Gi` |
| the image's `HEALTHCHECK`, `dig` for `pi.hole` at `127.0.0.1` | readiness probe every 30 seconds with a timeout of 30 seconds and 3 failures, the compose defaults |
| `cap_add` with `NET_ADMIN`, `SYS_TIME` and `SYS_NICE` | not rendered |
| `restart: unless-stopped`, `container_name` | not rendered |

## Proof

`check pihole --level deploys` with `tests/target.yml`, on kind for each
Kubernetes minor CI tests, with check 0.14.0. A compose file has no
Kubernetes objects to compare with, so the recipe is proven by deploying it
(RCP-38). `tests/target.yml` sets the compose example's password and points
Pi-hole's upstream at the cluster's DNS,
`kube-dns.kube-system.svc.cluster.local`, because a network may not let a
pod reach Google's resolvers.

`tests/smoke` starts a pod of Pi-hole's image, which carries `dig` and
`curl`. From there, through the Service `pihole`, it

- resolves `example.com` over UDP and over TCP
- logs in at `/api/auth` on port 80 with the password of the Secret
  `pihole`, and gets 401 with a wrong password
- loads `/admin/login` on port 443
- denies `blocked.smoke.example` through the API and then gets `0.0.0.0`
  for it over UDP and over TCP, the answer of Pi-hole's default blocking
  mode.

The domain lies under the reserved TLD `.example`, so it is NXDOMAIN until
it is denied, whatever the downloaded blocklist holds.

Not tested: the downloaded blocklist, the web interface beyond its login
page, and a LoadBalancer Service.
