# smartctl-exporter

The Prometheus smartctl exporter 0.15.0 as a privileged DaemonSet that
reports the SMART data of every node's disks, rendered by the kadet-hub
`kubernetes` generator 1.14.0 from the prometheus-community Helm chart
`prometheus-smartctl-exporter` 0.19.2 without its PodSecurityPolicy binding.

Source: `oci://ghcr.io/prometheus-community/charts/prometheus-smartctl-exporter:0.19.2@sha256:46a6b67ffcb30baf6b859aacde6bfd555ba702be1efe4d5912b1b3290f6e18bd`

Level: `deploys`

The chart comes from [prometheus-community/helm-charts](https://github.com/prometheus-community/helm-charts),
tag `prometheus-smartctl-exporter-0.19.2`. Its HTTP repository
`https://prometheus-community.github.io/helm-charts` serves the same
archive, SHA-256
`db513af2d58a992ebb49992c45f1f1b0aeccd2a28ba1c23f704f4af7b9fc2da0`. The
chart and the exporter are Apache-2.0. The image is a multi-arch index for
amd64 and arm64.

The chart names its Service and ServiceAccount
`<release>-prometheus-smartctl-exporter` and numbers its DaemonSets, one
per instance. With the release name `smartctl-exporter` and the default
single instance, the DaemonSet is
`smartctl-exporter-prometheus-smartctl-exporter-0`.

The container runs privileged as root and mounts the node's `/dev` at
`/hostdev`, because smartctl opens the disks' device files. It reads SMART
data and does not write to the disks. `--smartctl.powermode-check=standby`
skips a disk in standby, so a scrape does not spin it up. Pod Security
`baseline` forbids privileged containers and `hostPath` volumes, so the
namespace needs the level `privileged`.

## Include

```yaml
classes:
  - recipes.smartctl-exporter
parameters:
  namespace: smartctl-exporter
  kapitan:
    vars:
      target: smartctl-exporter
```

## Required parameters

No parameter has to be set.

## Settings

`<c>` stands for `components.smartctl-exporter-prometheus-smartctl-exporter-0`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `common.config.collect_not_more_than_period` | `<c>.args.interval` |
| `common.config.smartctl_powermode_check` | `<c>.args.powermode-check` |
| `config.devices`, `config.device_include`, `config.device_exclude` | `<c>.args.<key>`, such as `device-exclude: --smartctl.device-exclude=^(ram\|loop)` |
| `extraArgs` | `<c>.args.<key>` |
| `hostNetwork` | `<c>.host_network`, so the exporter listens on port 9633 of the node's address |
| `resources` | `<c>.resources` |
| `podAnnotations`, `podLabels` | `<c>.pod_annotations`, `<c>.pod_labels` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `service.type`, `service.port` | `generators.kubernetes.services.smartctl-exporter-prometheus-smartctl-exporter.type` and `.ports.http.service_port` |

The exporter does not call the Kubernetes API. As in the chart, the
ServiceAccount and the pod keep the API default and mount a token. A
target that does not want it sets
`<c>.automount_service_account_token: false`.

Any list set in the target is appended to the recipe's list. To replace
one, such as `tolerations`, set the key to `~` in a class included after
the recipe and the new list in the target.

## Left out

The chart binds its ServiceAccount to the ClusterRole `unrestricted-psp`,
a name for a PodSecurityPolicy role that the chart does not render and that
Kubernetes stopped using with the removal of PodSecurityPolicy in 1.25.
`tests/values.yaml` sets `rbac.create: false`, so the recipe has no
`RoleBinding/smartctl-exporter-prometheus-smartctl-exporter`.

The chart's ServiceMonitor and PrometheusRule are off by default and not
part of the recipe. They need the CRDs of the Prometheus Operator, which
`check` does not install. Further instances (`extraInstances`) and a
drive database (`drivedb`) are not offered. A second instance is a second
component of the same shape with its own `idx` label.

## Proof

`check smartctl-exporter --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind for each Kubernetes minor CI tests. The three
objects differ in three classes:

- Selector scheme: the DaemonSet and the Service select on `name`, the
  chart on `app.kubernetes.io/name`, `app.kubernetes.io/instance` and, for
  the DaemonSet, `idx`, and both select the same pods.
- Explicit default: the pod and the ServiceAccount set
  `automountServiceAccountToken: true`, which the chart leaves unset.
- Derived name: the container is named after the component, the chart's
  `main`.

`tests/smoke` reads `/metrics` through the Service and requires
`smartctl_exporter_build_info` with the version of the DaemonSet's image,
`smartctl_devices` above 0, and `smartctl_device_smartctl_exit_status` for
each disk found. A kind node sees the devices of the host it runs on.
Without `privileged` the exporter finds no disk and the test fails.

## Replacing a Helm release

Not tested. A release named `smartctl-exporter` has the same object names.

1. Delete the DaemonSet `smartctl-exporter-prometheus-smartctl-exporter-0`
   with `--cascade=orphan`, because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.smartctl-exporter.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pods are ready, delete the orphaned pods of the old
   DaemonSet and the RoleBinding `smartctl-exporter-prometheus-smartctl-exporter`.
   With `hostNetwork`, the orphaned pods hold port 9633 of the node, and
   the recipe's pods stay `Pending` until they are gone.
