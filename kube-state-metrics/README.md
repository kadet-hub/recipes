# kube-state-metrics

kube-state-metrics 2.20.0, which serves the state of the cluster's objects
as metrics on port 8080, rendered by the kadet-hub `kubernetes` generator
1.14.0 from the prometheus-community Helm chart `kube-state-metrics` 9.1.0
with its default values.

Source: `oci://ghcr.io/prometheus-community/charts/kube-state-metrics:9.1.0@sha256:f341491481d7fe1b2de3c704a0e607dace7aaa479bba6f4c05664521d252e4ca`

Level: `deploys`

The chart comes from [prometheus-community/helm-charts](https://github.com/prometheus-community/helm-charts),
tag `kube-state-metrics-9.1.0`. Its HTTP repository
`https://prometheus-community.github.io/helm-charts` serves the same
archive, SHA-256
`eaf73a801025efba856a6d1567c64888a19300ad642908e5890c3c556cb60b20`. The
chart and kube-state-metrics are Apache-2.0. The image
`registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.20.0` is a
multi-arch index for amd64, arm/v7, arm64, ppc64le and s390x.

With the release name `kube-state-metrics` the chart names every object
`kube-state-metrics`: the Deployment with one replica, the Service on port
8080, the ServiceAccount, the ClusterRole and the ClusterRoleBinding. The
ClusterRole lets the pod list and watch the 28 kinds that `--resources`
names, Secrets among them. The pod runs as UID 65534 with every capability
dropped, a read-only root file system and the seccomp profile
`RuntimeDefault`, and passes Pod Security `restricted`.

kube-state-metrics 2.20.0 is built with client-go 0.36, as
`kube_state_metrics_build_info` reports. Its compatibility matrix lists
Kubernetes 1.36 for 2.20.0 and 1.37 only for the unreleased `main`. The
proof deploys it on 1.35, 1.36 and 1.37.

## Include

```yaml
classes:
  - recipes.kube-state-metrics
parameters:
  namespace: kube-state-metrics
  kapitan:
    vars:
      target: kube-state-metrics
```

## Required parameters

No parameter has to be set.

## Settings

`<c>` stands for `components.kube-state-metrics`, `<r>` for
`generators.kubernetes.rbac.kube-state-metrics`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `collectors` | `<c>.args.resources` and `<r>.rules` |
| `metricAllowlist`, `metricDenylist`, `extraArgs` | `<c>.args.<key>`, such as `metric-allowlist: --metric-allowlist=kube_pod_info` |
| `service.port` | `<c>.ports.http.service_port` and `<c>.args.port` |
| `selfMonitor.enabled` | `<c>.ports.metrics.service_port: 8081` |
| `rbac.extraRules` | `<r>.rules`, appended |
| `replicas` | `<c>.replicas` |
| `resources` | `<c>.resources` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `securityContext` | `<c>.workload_security_context` |
| `containerSecurityContext` | `<c>.security_context` |

The telemetry port 8081, where kube-state-metrics reports on itself, is a
container port only, as in the chart.

`args` is a mapping, so a target changes or drops one argument by its key.
Any list set in the target is appended to the recipe's list. To replace
one, such as the ClusterRole's `rules`, set the key to `~` in a class
included after the recipe and the new list in the target.

### Pods only

A target that needs only the restart counters of the pods' containers
narrows the collectors, the metrics and the ClusterRole to pods. The class
`inventory/classes/kube-state-metrics-rules.yml` resets the rules:

```yaml
parameters:
  generators:
    kubernetes:
      rbac:
        kube-state-metrics:
          rules: ~
```

The target includes it after the recipe and sets the arguments and the new
rules:

```yaml
classes:
  - recipes.kube-state-metrics
  - kube-state-metrics-rules
parameters:
  namespace: kube-state-metrics
  kapitan:
    vars:
      target: kube-state-metrics
  components:
    kube-state-metrics:
      args:
        resources: --resources=pods
        metric-allowlist: --metric-allowlist=kube_pod_container_status_restarts_total
  generators:
    kubernetes:
      rbac:
        kube-state-metrics:
          rules:
            - apiGroups:
                - ""
              resources:
                - pods
              verbs:
                - list
                - watch
```

The Deployment and the ClusterRole then carry the arguments and the rule
that the chart renders with `collectors: [pods]` and
`metricAllowlist: [kube_pod_container_status_restarts_total]`. Without the
class, the target's rule is merged into the recipe's 28 rules and the
ClusterRole keeps all of them.

## Left out

The chart's ServiceMonitor, ScrapeConfig, NetworkPolicy,
PodDisruptionBudget, VerticalPodAutoscaler, kube-rbac-proxy with its
ConfigMap, custom resource state with its ConfigMap, kubeconfig Secret,
autosharding as a StatefulSet with its Role, Roles per namespace instead of
the ClusterRole and extra manifests are off by default and not part of the
recipe. A ServiceMonitor or ScrapeConfig needs the CRDs of the Prometheus
Operator, which `check` does not install.

## Proof

`check kube-state-metrics --level deploys` with `tests/values.yaml`, the
chart's defaults, and `tests/target.yml`, on kind for each Kubernetes
minor CI tests. The Deployment and the Service differ from the chart's in
one class, the selector scheme: they select on `name`, the chart on
`app.kubernetes.io/name` and `app.kubernetes.io/instance`, and both select
the same pods. The ClusterRole grants the ServiceAccount the same
permissions as the chart's.

`tests/smoke` reads `/metrics` through the Service and requires
`kube_pod_info` for the CoreDNS pods and available replicas of the
Deployment `coredns` in `kube-system`, which the recipe does not render.
On port 8081 of the pod it requires `kube_state_metrics_build_info` with
the version of the Deployment's image. A server-side dry run of the label
`pod-security.kubernetes.io/enforce=restricted` on the namespace must
return no warning about the running pod.

## Replacing a Helm release

Not tested. A release named `kube-state-metrics` has the same object
names.

1. Delete the Deployment `kube-state-metrics` with `--cascade=orphan`,
   because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.kube-state-metrics.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
