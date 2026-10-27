# keycloak-operator

The Keycloak Operator 26.8.1, watching every namespace, with its RBAC and
optionally its CRDs, rendered by the kadet-hub `kubernetes` generator 1.9.0.
Derived from the Keycloak project's operator chart, which the `keycloak`
recipe requires.

Source: `oci://quay.io/keycloak/keycloak-operator-helm:26.8.1@sha256:650f7e1021def78ff799aa5ada703818a1a7d0e3cb6ee7eba6d5e1b557656a17`

Level: `deploys`

The Keycloak project publishes this chart with each release since 26.8.0
and calls it experimental. It installs the operator cluster-wide, which the
project calls a preview: a `Keycloak` resource cannot set its own
ServiceAccount, and the operator supports only Keycloak 26.8.1. Install it
once per cluster, in a target of its own ([docs/specs/recipes.md](../docs/specs/recipes.md),
Keycloak). The project rebuilds a release under the same tag, so the
digests are those of one build.

## Include

```yaml
classes:
  - recipes.keycloak-operator
  - recipes.keycloak-operator.crds   # the chart's crds.enabled
parameters:
  namespace: keycloak-operator
  kapitan:
    vars:
      target: keycloak-operator
```

`crds.yml` copies the four CRDs from keycloak/keycloak-k8s-resources at tag
26.8.1, the same files the chart renders, with their SHA-256 in the
comments.

## Required parameters

No parameter has to be set.

## Settings

| Chart value | Inventory |
|---|---|
| `namespace` (release namespace) | `namespace` |
| `operator.image` | `components.keycloak-operator.image`, tag and digest |
| `operator.envs.RELATED_IMAGE_KEYCLOAK`, `operator.envs.kc.operator.keycloak.image` | `applications.keycloak-operator.keycloak_image`, the image of a `Keycloak` resource that sets none |
| `operator.envs.QUARKUS_OPERATOR_SDK_CONTROLLERS_<controller>_NAMESPACES` | `components.keycloak-operator.env.QUARKUS_OPERATOR_SDK_CONTROLLERS_<controller>_NAMESPACES`, a comma-separated list of namespaces in place of `JOSDK_ALL_NAMESPACES` |
| `operator.replicas` | `components.keycloak-operator.replicas` |
| `operator.resources` | `components.keycloak-operator.resources` |
| `crds.enabled` | the class `recipes.keycloak-operator.crds` |

A narrowed watch keeps the ClusterRoles of the chart.

## Renamed RBAC objects

The `kubernetes` generator names a role and its binding after the entry,
and every entry starts with the recipe's name.

| Chart | Recipe |
|---|---|
| ClusterRoleBinding `keycloak-operator-clusterrole-binding` | `keycloak-operator-clusterrole` |
| ClusterRole `keycloakcontroller-cluster-role`, ClusterRoleBinding `keycloakcontroller-role-binding` | `keycloak-operator-keycloakcontroller` |
| ClusterRole `keycloakrealmimportcontroller-cluster-role`, ClusterRoleBinding `keycloakrealmimportcontroller-role-binding` | `keycloak-operator-keycloakrealmimportcontroller` |
| ClusterRole `keycloakoidcclientcontroller-cluster-role`, ClusterRoleBinding `keycloakoidcclientcontroller-role-binding` | `keycloak-operator-keycloakoidcclientcontroller` |
| ClusterRole `keycloaksamlclientcontroller-cluster-role`, ClusterRoleBinding `keycloaksamlclientcontroller-role-binding` | `keycloak-operator-keycloaksamlclientcontroller` |

## Proof

`check keycloak-operator --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind `kindest/node:v1.37.0`.

`tests/smoke` creates a `Keycloak` resource in `default` and waits for the
operator to create its StatefulSet with the default image.

## Replacing a Helm release

Not tested. Delete the release's Helm secrets
`sh.helm.release.v1.keycloak-operator.*`, delete the Deployment
`keycloak-operator` with `--cascade=orphan` because its selector changes,
apply the recipe with `kubectl apply --server-side --force-conflicts`, then
delete the orphaned ReplicaSet and the chart's RBAC objects listed under
Renamed RBAC objects by their chart names.
