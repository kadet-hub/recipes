# home-assistant

Home Assistant Core, the home automation server, with its configuration
and database on a claim, designed in kadet-hub on the project's image and
rendered by the kadet-hub `kubernetes` generator 1.16.0.

Source: `ghcr.io/home-assistant/home-assistant:2026.11.0@sha256:c6c1ca9931036bf3a2c4cc088d8db25dfea3b33935a5ecc83c40349462e2f69e`

Level: `deploys`

Home Assistant publishes no Helm chart. Its container guide shows a
compose example only as a template in the documentation's repository, and
that example runs the container privileged on the host's network with
host paths mounted, which no recipe maps. The recipe is therefore designed
on the image that home-assistant/core builds (DEC-130 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The image's
documentation is the
[installation guide](https://www.home-assistant.io/installation/linux#install-home-assistant-container).
Home Assistant and its image are Apache-2.0. The recipe follows Home
Assistant's monthly releases and their patch releases. The digest is that
of the index for linux/amd64 and linux/arm64.

The image runs as root, so the target's namespace needs the Pod Security
level `baseline`. The recipe runs it on the pod network and without
`privileged`. Home Assistant supports its container only "on the host
network as root with full privileges"
([ADR-0013](https://github.com/home-assistant/architecture/blob/master/adr/0013-home-assistant-container.md)),
so this is a setup that Home Assistant does not support (DEC-131). "Left
out" lists what does not work in it.

## Include

```yaml
classes:
  - recipes.home-assistant
parameters:
  namespace: home-assistant
  kapitan:
    vars:
      target: home-assistant
```

With the node's network, include the option as well:

```yaml
classes:
  - recipes.home-assistant
  - recipes.home-assistant.host-network
```

## Required parameters

No parameter has to be set.

## Settings

| Setting | Inventory |
|---|---|
| Home Assistant version | `components.home-assistant.image`, tag and digest |
| time zone of the container's processes, UTC | `components.home-assistant.env.TZ`, a tz database name such as `Europe/Amsterdam` |
| size of the claim `config`, `1Gi` | `components.home-assistant.volume_claims.config.spec.resources.requests.storage` |
| exposure | `components.home-assistant.service.type`, or a route or Ingress of the target to the Service `home-assistant` on port 8123 |
| resources | `components.home-assistant.resources` |

Home Assistant keeps its state in `/config` on the claim:
`configuration.yaml`, the users and tokens in `.storage`, and the
recorder's database `home-assistant_v2.db`. The database grows with the
number of entities and the days of history the recorder keeps, ten by
default. Home Assistant's own time zone is set in the onboarding and
stored in `.storage`, apart from `TZ`.

The recipe creates no account (DEC-133). The first visitor of the web UI
creates the owner in the onboarding, without a login. Create the owner
before the target exposes the Service. Until then only the cluster reaches
it.

The pod has no probe, because neither the image nor its documentation
names a check. It is ready once the container runs, before Home Assistant
listens on port 8123. Its termination grace period is 60 seconds, the stop
timeout of the container guide, so that Home Assistant closes its
database. Until Home Assistant has started, a SIGTERM ends it before it
writes the changes it holds back, such as a new token. A preStop hook
holds the stop until Home Assistant catches SIGTERM (DEC-333).

Behind a route or Ingress, Home Assistant refuses forwarded requests until
its `http` integration names the proxy's addresses in
`trusted_proxies` with `use_x_forwarded_for: true` in
`configuration.yaml`.

## The option `host-network`

`recipes.home-assistant.host-network` runs the pod on its node's network,
with `hostNetwork: true` and `dnsPolicy: ClusterFirstWithHostNet` (DEC-132).
Home Assistant then receives the multicast of the node's LAN, which
discovery over mDNS and SSDP and HomeKit need. The proof renders the
option but does not deploy it.
Pod Security `baseline` forbids `hostNetwork`, so the namespace needs the
level `privileged`. Home Assistant binds port 8123 and the ports of its
integrations on the node, so no other process of the node may use them.
The option adds no `privileged` and no device.

## Left out

Without the option `host-network`, Home Assistant has no multicast or
broadcast of the LAN. These do not work:

- discovery of devices over mDNS (zeroconf), SSDP and DHCP. Integrations
  that take a host or address, such as Google Cast's known hosts, still
  connect.
- HomeKit. The HomeKit Bridge announces Home Assistant over mDNS, and
  HomeKit Device finds accessories over mDNS. For the bridge, Home
  Assistant's HomeKit documentation describes an mDNS reflector on the LAN
  together with the option `advertise_ip`.

With or without the option, the recipe renders no `privileged`, no device
and no host path. That leaves out:

- Bluetooth, which needs the host's D-Bus at `/run/dbus`.
- USB and serial devices, such as Zigbee and Z-Wave coordinators.
- the host's `/etc/localtime`, for which `TZ` stands in.

Home Assistant Container has no apps (add-ons), with or without the
recipe.

## Proof

`check home-assistant --level deploys` with `tests/target.yml`, on kind for
each Kubernetes minor CI tests. The image has no Kubernetes objects to
compare with, so the recipe is proven by deploying it (RCP-44).

`tests/smoke` checks that the pod passes Pod Security `baseline`. It then
starts a pod of Home Assistant's image, which carries `curl`. From there,
through the Service `home-assistant` on port 8123, it

- requires that no onboarding step is done, creates the owner through
  `/api/onboarding/users` and exchanges the code it returns at
  `/auth/token` for an access and a refresh token
- gets 403 for a second owner
- gets 401 from `/api/` without a token and `API running.` with the access
  token, and requires that `/api/config` names the image tag as `version`
- deletes the pod `home-assistant-0` and, once Home Assistant answers
  again, finds the owner's step done, gets a new access token with the
  refresh token and `API running.` with it, which needs `.storage` on the
  claim.

The option `host-network` is proven by its render only: compiled with
`tests/target.yml`, it changes nothing but `hostNetwork` and `dnsPolicy`,
and `check home-assistant --level renders` passes with it. CI deploys the
recipe without it.

Not tested: the web UI in a browser, an integration, a device, and a route
or Ingress in front of the Service.
