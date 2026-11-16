# homepage

homepage, a dashboard of links, service widgets and bookmarks, with its
dashboard written in the inventory and optional service discovery in the
cluster, designed in kadet-hub on homepage's image and rendered by the
kadet-hub `kubernetes` generator 1.16.0.

Source: `ghcr.io/gethomepage/homepage:v2.7.0@sha256:19c5c09184458a41b7b5915e71463a39f36cd33540f41bdbed008791b8182d5f`

Level: `deploys`

homepage publishes no Helm chart, Kustomize base or compose file. Its
README and its Docker installation page carry a compose example that
bind-mounts an absolute host path at `/app/config` and, optionally, the
Docker socket, on which Compose sources stop, so the recipe is designed on
the image (DEC-225 in [docs/specs/recipes.md](../docs/specs/recipes.md)).
The image's documentation is
[gethomepage.dev](https://gethomepage.dev/installation/k8s/), whose
Kubernetes installation page the recipe follows for the user, the
ClusterRole and the files below `/app/config`. homepage is GPL-3.0. The
recipe follows homepage's newest release, v2.7.0 of 2026-10-23. The digest
is that of its index for linux/amd64 and linux/arm64.

The recipe renders the Deployment `homepage` with one replica, the Service
`homepage` on port 3000 and the ConfigMap `homepage-<hash>` with the
dashboard. The pod runs as UID and GID 1000 and passes Pod Security
`restricted`.

## Include

```yaml
classes:
  - recipes.homepage
  # Optional: service discovery and statistics from the cluster's API.
  - recipes.homepage.kubernetes
parameters:
  namespace: homepage
  kapitan:
    vars:
      target: homepage
  applications:
    homepage:
      allowed_hosts: home.example.com
      settings:
        title: Home
      services:
        - Media:
            - Jellyfin:
                href: https://jellyfin.example.com/
                description: Media server
      bookmarks: []
      widgets: []
```

## Required parameters

`applications.homepage.allowed_hosts` is the value of
`HOMEPAGE_ALLOWED_HOSTS` (DEC-227 in the spec): the hosts, comma-separated
and without spaces, that clients name in the `Host` header of their
requests, each with the port where the URL has one, such as
`home.example.com` behind an Ingress or `homepage.homepage.svc:3000` inside
the cluster. homepage answers every other host with 400, its health check
too. `localhost:3000` and `127.0.0.1:3000` are always allowed, so
`kubectl port-forward` to the local port 3000 works without an entry. `*`
turns the check off, which homepage's documentation advises against.
Without the parameter the compile stops with `Interpolation key` and its
name.

## Settings

The dashboard is four parameters, each written as YAML to its file in
`/app/config` (DEC-226). Each takes what homepage's documentation shows for
its file, as inventory YAML. The recipe sets each empty, so the dashboard is
what the target writes.

| homepage file | Inventory | Default |
|---|---|---|
| `settings.yaml` | `applications.homepage.settings` | `{}` |
| `services.yaml` | `applications.homepage.services` | `[]` |
| `bookmarks.yaml` | `applications.homepage.bookmarks` | `[]` |
| `widgets.yaml` | `applications.homepage.widgets` | `[]` |
| `kubernetes.yaml`, with the option `kubernetes` | `applications.homepage.kubernetes` | `mode: cluster` |

Kapitan's resolver `yaml` writes the keys of a mapping in sorted order.
homepage orders the groups of the page by `layout` in `settings.yaml`, so
write `layout` as a list of one-key mappings, which homepage reads in list
order:

```yaml
settings:
  layout:
    - Media:
        style: row
    - Infrastructure:
        style: column
```

A list set in the target is appended to the list of the classes before it.
To replace a list a class sets, set it to `~` in a class included after
that class, and the new list in the target.

The ConfigMap's name carries a hash of its content, so a changed dashboard
rolls out a new pod. Earlier ConfigMaps stay in the namespace until they
are deleted. homepage reads secrets for widgets from `{{HOMEPAGE_VAR_*}}`
and `{{HOMEPAGE_FILE_*}}` placeholders in these files. Set such variables
through `components.homepage.env` and `components.homepage.secrets` with a
ref, rather than writing a credential into the dashboard.

| Setting | Inventory |
|---|---|
| homepage version | `components.homepage.image`, tag and digest |
| exposure | `components.homepage.service.type`, or a route or Ingress of the target to the Service `homepage` on port 3000 |
| other variables, such as `LOG_LEVEL` or homepage's login with `HOMEPAGE_AUTH_ENABLED` | `components.homepage.env.<variable>`, credentials through `components.homepage.secrets` |
| `custom.css`, `custom.js` and other files of `/app/config` | `components.homepage.config_maps.config.data.<file>.value` with a mount in `components.homepage.volume_mounts`, as `homepage.yml` mounts `settings.yaml` |
| resources | `components.homepage.resources` |

homepage serves the dashboard without a login, as its default (DEC-229).
Anyone who reaches the Service sees the dashboard and what its widgets
fetch from the services they name. homepage's documentation asks for a
reverse proxy with authentication, or its own login, in front of a public
deployment.

`/app/config` is an `emptyDir`. homepage writes its log there and copies
each file it reads and the recipe does not mount, such as `docker.yaml`,
from the defaults in its image. The dashboard's files are mounted over it
from the ConfigMap.

## The option `kubernetes`

`recipes.homepage.kubernetes` lets homepage read the cluster through the
ServiceAccount `homepage` (DEC-228). It renders the ClusterRole `homepage`
with the rules of homepage's Kubernetes installation page and binds it to
the ServiceAccount with the ClusterRoleBinding `homepage`. The rules read
Namespaces, Pods, Nodes, Ingresses, Traefik IngressRoutes, Gateway API
HTTPRoutes and Gateways and the metrics of Nodes and Pods, cluster-wide,
with `get` and `list` only. They grant no Secret.

`kubernetes.yaml` turns on the discovery of Ingresses with the annotation
`gethomepage.dev/enabled: "true"`. `gateway: true` adds HTTPRoutes and
`traefik: true` IngressRoutes. Pod statistics need a metrics server in the
cluster. Each homepage instance discovers every annotated Ingress of the
cluster unless the Ingress names an `instance`, which homepage matches
against `instanceName` in `settings.yaml`.

## Proof

`check homepage --level deploys` with `tests/target.yml`, which includes
the option `kubernetes`, on kind for each Kubernetes minor CI tests, with
check 0.17.0. The image has no Kubernetes objects to compare with, so the
recipe is proven by deploying it (RCP-44). `check lint` accepts the
ClusterRole because it only reads and the binding because it binds that
ClusterRole (RCP-308).

`tests/smoke` checks that the pod passes Pod Security `restricted` and
starts a pod of homepage's image, which carries `node`. From there, through
the Service `homepage` on port 3000, it

- requires 200 from `/api/healthcheck` and the title of `tests/target.yml`
  from `/`, and 400 from `/` with a `Host` outside
  `applications.homepage.allowed_hosts`
- finds the service and the bookmark of `tests/target.yml` in
  `/api/services` and `/api/bookmarks`
- requires that the ServiceAccount `homepage` may list Ingresses and may
  not read Secrets, create Ingresses or delete Pods
- creates an Ingress with homepage's annotations and finds it as a service
  in `/api/services`
- compiles `tests/target.yml` with the service renamed, applies the result
  and, once the new pod rolled out, finds the new name and not the old one.

Not tested: the page in a browser, service widgets, Gateway API and
Traefik discovery, Pod statistics, which need a metrics server, and
homepage's login.
