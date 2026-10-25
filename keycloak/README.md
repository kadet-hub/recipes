# keycloak

Keycloak 26.8.1 as one `Keycloak` resource of the Keycloak Operator, on the
PostgreSQL of the `postgresql` recipe and with a cert-manager certificate,
designed in kadet-hub on Keycloak's image and rendered by the kadet-hub
`keycloak` and `certmanager` generators.

Source: `quay.io/keycloak/keycloak:26.8.1@sha256:a78d6b79572168cb25886b80a8b5b8d4ed4390743e3eecb810538683e209dd6b`

Level: `deploys`

Requires: `keycloak-operator`, `cert-manager`

The Keycloak project ships no chart for a Keycloak server. Its guides run
Keycloak through the Keycloak Operator, so the recipe renders the
operator's resource with the project's image (DEC-14 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The operator creates
the StatefulSet `keycloak`, the Services `keycloak-service` and
`keycloak-discovery` and the Secret `keycloak-initial-admin`. Install
`keycloak-operator` at the same Keycloak version: one operator supports only
the Keycloak version it was released with. The project rebuilds a release
under the same tag, so the digest is that of one build. Keycloak is
Apache-2.0.

## Replaces

This recipe replaces the `keycloak` recipe of kadet-hub/examples, which
stood in for Bitnami's `keycloak` chart. Moving from it changes these
objects:

| kadet-hub/examples | This recipe |
|---|---|
| Namespace `keycloak`, rendered by the recipe | no Namespace. The target sets `namespace` and creates it. |
| the Keycloak Operator, cert-manager and the CloudNativePG operator from their charts, compiled with the recipe | the prerequisites `keycloak-operator`, `cert-manager` and `cloudnative-pg`, each in a target of its own. `keycloak-operator` watches every namespace. |
| Keycloak `sso`, with the StatefulSet `sso`, the Services `sso-service` and `sso-discovery` and the Secret `sso-initial-admin` | Keycloak `keycloak`, with `keycloak`, `keycloak-service`, `keycloak-discovery` and `keycloak-initial-admin` |
| Cluster `keycloak-db`, two instances, database `keycloak` | Cluster `postgresql-cluster` of the included recipe `postgresql`, database `app` |
| Issuer `keycloak-selfsigned`, Certificate and Secret `sso-tls` for `sso.example.com` and `sso-service.keycloak.svc` | Certificate and Secret `keycloak-tls` for `applications.keycloak.host` and `keycloak-service.<namespace>.svc`, from the issuer `applications.keycloak.issuer` |

Keycloak keeps its realms, users and sessions in the database, so the data
does not move with the names. Move a target in this order:

1. Delete the examples recipe's operator: the Deployment and Service
   `keycloak-operator` in `keycloak`, and the ClusterRoles and
   ClusterRoleBindings its chart rendered. Keep the CRDs. Deleting them
   deletes every `Keycloak` resource.
2. Install `keycloak-operator` in its own target.
3. Delete the Keycloak `sso`, so nothing writes to `keycloak-db` any more.
4. Import `keycloak-db` into `postgresql-cluster` with CloudNativePG's
   import bootstrap, which runs once, when the Cluster is created. In the
   target: TODO, the values for `postgresql`'s Cluster, set once that
   recipe is on `main`.
5. Apply this recipe. Once Keycloak serves the imported realms, delete the
   Cluster `keycloak-db`, the Issuer `keycloak-selfsigned` and the Secret
   `sso-tls`.

## Include

```yaml
classes:
  - recipes.keycloak
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
```

## Required parameters

`applications.keycloak.host`, the host name Keycloak serves and its
certificate names, and `applications.keycloak.issuer`, the `name` and
`kind` of the cert-manager Issuer or ClusterIssuer that issues the
certificate. Without them the compile stops with
`Interpolation key 'applications.keycloak.host' not found`. `postgresql`
requires no parameter.

## Settings

| Setting | Inventory |
|---|---|
| Keycloak version | `applications.keycloak.version`, together with the digest in `generators.keycloak.instances.keycloak.image` |
| instances, 1 | `generators.keycloak.instances.keycloak.instances` |
| resources | `generators.keycloak.instances.keycloak.resources` |
| an Ingress of the operator, off | `generators.keycloak.instances.keycloak.ingress` |
| any other field of the `Keycloak` resource | `generators.keycloak.instances.keycloak.spec` |

Keycloak serves HTTPS only, on port 8443 of `keycloak-service`. Exposing it
is left to the target, for example a route with TLS passthrough or a
BackendTLSPolicy towards that port.

## Proof

`check keycloak --level deploys` with `tests/target.yml`, on kind
`kindest/node:v1.37.0`, with `keycloak-operator`, `cert-manager` and,
through `postgresql`, `cloudnative-pg` installed first. The image has no
Kubernetes objects to compare with, so the recipe is proven by deploying
it (RCP-44, RCP-58). `tests/target.yml` adds the self-signed Issuer
`keycloak-selfsigned`. `tests/smoke` waits for the Cluster and the
`Keycloak` to be ready, then gets `/realms/master` over TLS with the host
name and the CA of `keycloak-tls`, a token for the temporary admin of
`keycloak-initial-admin`, and `/health/ready` on the management port.
