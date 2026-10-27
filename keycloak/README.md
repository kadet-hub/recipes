# keycloak

Keycloak 26.8.1 as one `Keycloak` resource of the Keycloak Operator, on the
PostgreSQL of the `postgresql` recipe and with a cert-manager certificate,
and optionally an HTTPRoute to a Gateway the cluster already runs.

Designed in kadet-hub on Keycloak's image and rendered by the kadet-hub
`keycloak` generator 1.1.0, `certmanager` generator 1.0.2 and, for the route,
`kubernetes` generator 1.9.0.

Source: `quay.io/keycloak/keycloak:26.8.1@sha256:a78d6b79572168cb25886b80a8b5b8d4ed4390743e3eecb810538683e209dd6b`

Level: `deploys`

Requires: `keycloak-operator`, `cert-manager`, `gateway-api`

The Keycloak project ships no chart for a Keycloak server. Its guides run
Keycloak through the Keycloak Operator, so the recipe renders the
operator's resource with the project's image (DEC-14 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The operator creates
the StatefulSet `<name>`, the Services `<name>-service` and
`<name>-discovery` and the Secret `<name>-initial-admin`, where `<name>` is
`applications.keycloak.name`, `keycloak` by default. Install
`keycloak-operator` at the same Keycloak version: one operator supports only
the Keycloak version it was released with. The project rebuilds a release
under the same tag, so the digest is that of one build. Keycloak is
Apache-2.0.

## Replaces

This recipe replaces the `keycloak` recipe of kadet-hub/examples, which
stood in for Bitnami's `keycloak` chart. The examples recipe named the
Keycloak `sso` and its Cluster `keycloak-db`. A target that moves from it
keeps both names. Keycloak then keeps its realms, users and sessions in
the database `keycloak`, and the Cluster keeps its claims
`keycloak-db-<n>`. Clients keep the Service `sso-service`, and the
temporary admin stays in `sso-initial-admin`.

```yaml
parameters:
  namespace: keycloak
  applications:
    keycloak:
      name: sso
      host: sso.example.com
      issuer:
        name: keycloak-selfsigned
        kind: Issuer
    postgresql:
      cluster: keycloak-db
      database: keycloak
      owner: keycloak
      storage: 10Gi
      instances: 2
  generators:
    certmanager:
      issuers:
        keycloak-selfsigned:
          spec:
            selfSigned: {}
```

Moving changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| Namespace `keycloak`, rendered by the recipe | no Namespace. The target sets `namespace: keycloak`. Keep the Namespace when the examples recipe goes, because deleting it deletes the claims. |
| the Keycloak Operator, cert-manager and the CloudNativePG operator in the recipe, from their charts through `helm` compile entries | the recipes `keycloak-operator`, `cert-manager` and `cnpg`, each in a target of its own. `keycloak-operator` watches every namespace. |
| Issuer `keycloak-selfsigned`, rendered by the recipe | not rendered. The snippet renders it in the target. |
| Certificate and Secret `sso-tls` | Certificate and Secret `keycloak-tls`, for the same DNS names |
| Cluster settings | `postgresql`'s, which its README lists under Replaces |

Move a target in this order:

1. Delete the examples recipe's Keycloak Operator: the Deployment, Service
   and ServiceAccount `keycloak-operator` and the RoleBinding
   `keycloak-operator-view` in `keycloak`, and the cluster roles and
   bindings by the chart names that `keycloak-operator`'s README lists
   under Renamed RBAC objects. Keep the CRDs, because deleting them
   deletes the Keycloak `sso`.
2. Install `keycloak-operator` in a target of its own. Replace cert-manager
   and the CloudNativePG operator as the READMEs of `cert-manager` and
   `cnpg` describe under "Replacing a Helm release". The examples recipe
   left no Helm secrets.
3. Apply this recipe. The operator restarts `sso` with `keycloak-tls`.
4. Delete the Certificate and the Secret `sso-tls`.

The move is not tested.

## Include

```yaml
classes:
  - recipes.keycloak
  - recipes.keycloak.route   # an HTTPRoute to port 8080
parameters:
  namespace: keycloak
  kapitan:
    vars:
      target: keycloak
  applications:
    keycloak:
      host: sso.example.com
      issuer:
        name: <issuer>
        kind: ClusterIssuer
      gateway:
        name: <gateway>
        namespace: <gateway namespace>
```

`gateway-api` on the `Requires:` line applies to the option `route` only.

## Required parameters

`applications.keycloak.host`, the host name Keycloak serves and its
certificate names, and `applications.keycloak.issuer`, the `name` and
`kind` of the cert-manager Issuer or ClusterIssuer that issues the
certificate. Without them the compile stops with
`Interpolation key 'applications.keycloak.host' not found`. With the option
`route`, `applications.keycloak.gateway.name` and
`applications.keycloak.gateway.namespace` name the Gateway the route
attaches to, whose listener must admit routes from the target's namespace.
`postgresql` requires no parameter.

## Settings

| Setting | Inventory |
|---|---|
| Keycloak version | `generators.keycloak.instances.keycloak.image`, tag and digest |
| name of the `Keycloak` resource, `keycloak` | `applications.keycloak.name` |
| the Cluster and its database | `applications.postgresql`, which `postgresql`'s README lists |
| instances, 1 | `generators.keycloak.instances.keycloak.instances` |
| resources | `generators.keycloak.instances.keycloak.resources` |
| an Ingress of the operator, off | `generators.keycloak.instances.keycloak.ingress` |
| the Gateway listener of the route, its `sectionName`, unset | `applications.keycloak.gateway.section` |
| any other field of the `Keycloak` resource | `generators.keycloak.instances.keycloak.spec` |

Keycloak serves HTTPS on port 8443 of `<name>-service`. The option `route`
adds an HTTPRoute `keycloak` for the host to port 8080 of `<name>-service`.
It turns on Keycloak's HTTP listener, which the operator adds to the
Service, and sets the proxy headers to `xforwarded`. The Gateway terminates
TLS and sends plain HTTP to Keycloak, which Keycloak's reverse proxy guide
calls less secure than re-encrypting to port 8443. cloud-provider-kind, on
which `check` proves the route, implements neither BackendTLSPolicy nor
TLSRoute, so the recipe renders neither (DEC-17 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). For TLS up to
Keycloak, leave the option out and expose port 8443 yourself.

With `xforwarded`, Keycloak takes the client's address from the
`X-Forwarded-For` header of any request on port 8080, also of one that
bypasses the Gateway. Set
`proxy-trusted-addresses` to the addresses of the Gateway implementation's
proxies, as an entry `name: proxy-trusted-addresses` with `value` in
`generators.keycloak.instances.keycloak.additional_options`. It has no
default.

## Proof

`check keycloak --level deploys` with `tests/target.yml`, on kind
`kindest/node:v1.37.0`, with `keycloak-operator`, `cert-manager`,
`gateway-api` and, through `postgresql`, `cnpg` installed first. The image
has no Kubernetes objects to compare with, so the recipe is proven by
deploying it (RCP-44, RCP-58). `tests/target.yml` adds the self-signed
Issuer `keycloak-selfsigned` and includes the option `route` towards the
Gateway of `check`. `tests/smoke` waits for the Cluster and the `Keycloak`
to be ready, then gets `/realms/master` over TLS with the host name and the
CA of `keycloak-tls`, a token for the temporary admin of
`keycloak-initial-admin`, and `/health/ready` on the management port.
Through the Gateway, with the route's host name, it gets `/realms/master`
and a token over HTTP, and it reads `KC_PROXY_HEADERS=xforwarded` from the
StatefulSet. Without the option the recipe compiles to the same files as
before the option existed.
