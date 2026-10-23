# cert-manager

The cert-manager controller, cainjector and webhook with their RBAC, and
optionally the CRDs, rendered by the kadet-hub `kubernetes` generator 1.7.0.
Derived from the cert-manager Helm chart v1.21.2:

Source: `oci://quay.io/jetstack/charts/cert-manager:v1.21.2@sha256:634dce9c13b56677a2c05e2ab76c312d0be2664022d5dd05815da67e1fd5f610`

Level: `deploys`

## Include

```yaml
classes:
  - recipes.cert-manager
  - recipes.cert-manager.crds   # the chart's crds.enabled
parameters:
  namespace: cert-manager
  kapitan:
    vars:
      target: cert-manager
```

`crds.yml` copies `vendor/cert-manager.crds.yaml` from the cert-manager
release v1.21.2, SHA-256
`262fef78478492cd35b73a1b227106b7802f9c056361d1f561d04b32d751337f`.

## Settings

| Chart value | Inventory |
|---|---|
| `namespace` (release namespace) | `namespace` |
| `image.tag` of all images | `applications.cert-manager.version`, together with the digests in the `image` lines and `components.cert-manager.args.acme-http01-solver-image` |
| `global.logLevel` | `applications.cert-manager.log_level` |
| `global.leaderElection.namespace` | `applications.cert-manager.leader_election_namespace` |
| `replicaCount`, `webhook.replicaCount`, `cainjector.replicaCount` | `components.cert-manager.replicas`, `components.cert-manager-webhook.replicas`, `components.cert-manager-cainjector.replicas` |
| `resources` | `components.<component>.resources` |
| `nodeSelector` | `applications.cert-manager.component_defaults.node_selector` |
| `tolerations`, `affinity` | `components.<component>.tolerations`, `components.<component>.affinity` |
| `podAnnotations` | `applications.cert-manager.component_defaults.pod_annotations` |
| `extraArgs` | `components.<component>.args.<key>`, a new key for an extra argument or a recipe key such as `verbosity` to replace one |
| `webhook.timeoutSeconds` | `timeoutSeconds` in `components.cert-manager-webhook.webhooks` and `validating_webhooks` |

`args` is a mapping and renders in the recipe's key order, with new keys
after them. A string value is one argument, a list several, and `~` drops
the entry, for example `components.cert-manager.args.verbosity: --v=4`.

Any other list set in the target is appended to the recipe's list. To
replace one, set the key to `~` in a class included after the recipe and the
new list in the target.

No parameter has to be set.

## Left out

The chart's `startupapicheck` hook runs only inside `helm install`, where it
waits until the webhook answers. `tests/smoke` checks the same on the
installed recipe. These hook objects are not rendered:
`Job/cert-manager-startupapicheck`,
`ServiceAccount/cert-manager-startupapicheck`,
`Role/cert-manager-startupapicheck:create-cert` and
`RoleBinding/cert-manager-startupapicheck:create-cert`.

## Renamed RBAC objects

The generator rejects `:` in names. Each role keeps its own entry and its
binding.

| Chart | Recipe |
|---|---|
| `cert-manager:leaderelection` | `cert-manager-leaderelection` |
| `cert-manager-cainjector:leaderelection` | `cert-manager-cainjector-leaderelection` |
| `cert-manager-controller-approve:cert-manager-io` | `cert-manager-controller-approve-cert-manager-io` |
| `cert-manager-webhook:subjectaccessreviews` | `cert-manager-webhook-subjectaccessreviews` |
| `cert-manager-webhook:dynamic-serving` | `cert-manager-webhook-dynamic-serving` |

## Proof

`check cert-manager --level deploys` with `tests/values.yaml`
(`crds.enabled: true`) and `tests/target.yml`, on kind
`kindest/node:v1.37.0`. The objects outside RBAC differ only in these
classes:

- Selector scheme: the Deployments and Services select on `name`, the chart
  on `app.kubernetes.io/name`, `instance` and `component`.
- Explicit default: the pods set `automountServiceAccountToken: true`.
- Port by name: the controller's and the cainjector's Service target
  `http-metrics`, the chart's `9402`.
- Derived name: the controller's container is named `cert-manager`, the
  webhook configurations `cert-manager-cert-manager-webhook`, and container
  ports are sorted by name.

All ServiceAccounts and users bound to `view`, `edit` and `admin` have the
same permissions. `aggregate-to-cluster-reader` targets an OpenShift role and
is not tested. `tests/smoke` has a self-signed ClusterIssuer issue a
Certificate.

## Replacing a Helm release

Not tested.

1. Delete the Deployments `cert-manager`, `cert-manager-cainjector` and
   `cert-manager-webhook` with `--cascade=orphan`, because their selectors
   change.
2. Delete the release's Helm secrets `sh.helm.release.v1.cert-manager.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pods are ready, delete the orphaned ReplicaSets, the
   webhook configurations `cert-manager-webhook` and the RBAC objects listed
   under Renamed RBAC objects by their chart names.
