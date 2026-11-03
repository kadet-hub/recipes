# blackbox-exporter

The Prometheus blackbox exporter 0.29.1 with the module `http_2xx`, rendered
by the kadet-hub `kubernetes` generator 1.9.0 from the prometheus-community
Helm chart `prometheus-blackbox-exporter` 11.20.2 with its default values.

Source: `oci://ghcr.io/prometheus-community/charts/prometheus-blackbox-exporter:11.20.2@sha256:dff2a707004310c712745e884f548c4c63e6af43be14b831673b519b530c0fe8`

Level: `deploys`

The chart comes from [prometheus-community/helm-charts](https://github.com/prometheus-community/helm-charts),
tag `prometheus-blackbox-exporter-11.20.2`. Its HTTP repository
`https://prometheus-community.github.io/helm-charts` serves the same
archive, SHA-256
`b5116657063fe1776a04dd6ec0922066cee3a2c6860cd575811400f146f706b1`. The
chart and the exporter are Apache-2.0.

The chart names its objects `<release>-prometheus-blackbox-exporter`, so
with the release name `blackbox-exporter` the Deployment, Service,
ServiceAccount and ConfigMap are all `blackbox-exporter-prometheus-blackbox-exporter`.

## Include

```yaml
classes:
  - recipes.blackbox-exporter
parameters:
  namespace: blackbox-exporter
  kapitan:
    vars:
      target: blackbox-exporter
```

## Required parameters

No parameter has to be set.

## Settings

`<c>` stands for `components.blackbox-exporter-prometheus-blackbox-exporter`.

| Chart value | Inventory |
|---|---|
| `config` | `<c>.config_maps.config.data["blackbox.yaml"].value`, the whole file as text |
| `image.tag` | `<c>.image`, tag and digest |
| `replicas` | `<c>.replicas` |
| `extraArgs` | `<c>.args.<key>`, such as `log-level: --log.level=debug` |
| `resources` | `<c>.resources` |
| `service.type` | `<c>.service.type` |
| `podAnnotations` | `<c>.pod_annotations` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `securityContext` | `<c>.security_context` |

The pod annotation `checksum/config` is the chart's hash of its ConfigMap
for the default `config`. It does not change with the recipe's
`blackbox.yaml`, so after changing it restart the exporter with
`kubectl rollout restart deployment/blackbox-exporter-prometheus-blackbox-exporter`.
The module configuration is the chart's, with its license in
`blackbox-exporter.yml.LICENSE`.

The chart's ServiceMonitor, PodMonitoring, PrometheusRule, Ingress, route,
NetworkPolicy, PodDisruptionBudget and config reloader are off by default
and not part of the recipe. A ServiceMonitor needs the CRDs of the
Prometheus Operator, which `check` does not install.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Proof

`check blackbox-exporter --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The four
objects differ in three ways. The Deployment and the Service select on
`name`, the chart on `app.kubernetes.io/name` and `instance`, and both
select the same pods. The container is named after the component, the
chart's `blackbox-exporter`. The ServiceAccount sets
`automountServiceAccountToken: true`, the API default the chart leaves
unset, while the pod opts out as in the chart. The chart binds no role.

`tests/smoke` calls `/probe` with the module `http_2xx` through the Service
and the API server's service proxy. The target is CoreDNS's metrics
endpoint on the Service `kube-dns` in `kube-system`: `/metrics` gives
`probe_success 1`, and a path CoreDNS does not serve gives
`probe_success 0`.

## Replacing a Helm release

Not tested. A release named `blackbox-exporter` has the same object names.

1. Delete the Deployment `blackbox-exporter-prometheus-blackbox-exporter`
   with `--cascade=orphan`, because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.blackbox-exporter.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
