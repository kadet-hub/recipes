# node-exporter

The Prometheus node exporter 1.12.1 as a DaemonSet on every node's host
network, reading the node's `/proc`, `/sys` and root file system, rendered
by the kadet-hub `kubernetes` generator 1.14.0 from the prometheus-community
Helm chart `prometheus-node-exporter` 5.1.0 with its default values.

Source: `oci://ghcr.io/prometheus-community/charts/prometheus-node-exporter:5.1.0@sha256:3001c54dd6248a0a31d25bb963f3d3f95ba9b7fbccd5d366f910461acf039f48`

Level: `deploys`

The chart comes from [prometheus-community/helm-charts](https://github.com/prometheus-community/helm-charts),
tag `prometheus-node-exporter-5.1.0`. Its HTTP repository
`https://prometheus-community.github.io/helm-charts` serves the same
archive, SHA-256
`908fb55ede2c340c64cd643bc6352ce46f3cbc94663014033b0b321a5013a0b8`. The
chart and the exporter are Apache-2.0. The image is a multi-arch index for
amd64, arm64, arm/v7, ppc64le, riscv64 and s390x.

The chart names its objects `<release>-prometheus-node-exporter`, so with
the release name `node-exporter` the DaemonSet, Service and ServiceAccount
are all `node-exporter-prometheus-node-exporter`.

The pod uses the node's network and process namespaces and mounts the
node's `/proc`, `/sys` and `/` read-only below `/host`. Pod Security
`baseline` forbids all three, so the namespace needs the level
`privileged`. The exporter listens on port 9100 of every node's address.

## Include

```yaml
classes:
  - recipes.node-exporter
parameters:
  namespace: node-exporter
  kapitan:
    vars:
      target: node-exporter
```

## Required parameters

No parameter has to be set.

## Settings

`<c>` stands for `components.node-exporter-prometheus-node-exporter`.

| Chart value | Inventory |
|---|---|
| `image.tag` | `<c>.image`, tag and digest |
| `extraArgs` | `<c>.args.<key>`, such as `textfile: --collector.textfile.directory=/host/root/var/lib/node-exporter` |
| `service.port`, `service.targetPort` | `<c>.ports.metrics.service_port` and `<c>.args.listen-address` |
| `resources` | `<c>.resources` |
| `hostNetwork`, `hostPID` | `<c>.host_network`, `<c>.host_pid` |
| `hostRootFsMount.enabled: false` | `~` for `<c>.volumes.root`, `<c>.volume_mounts.root`, `<c>.args.rootfs` and `<c>.args.udev` |
| `podAnnotations` | `<c>.pod_annotations` |
| `nodeSelector`, `tolerations`, `affinity` | `<c>.node_selector`, `<c>.tolerations`, `<c>.affinity` |
| `securityContext` | `<c>.workload_security_context` |
| `containerSecurityContext` | `<c>.security_context` |

The exporter runs as UID 65534, as in the chart. The `rapl` collector
reports CPU package power from `energy_uj` below `/sys/class/powercap`,
which the kernel makes readable by root only since CVE-2020-8694. To read
it, a target runs the pod as root:

```yaml
components:
  node-exporter-prometheus-node-exporter:
    workload_security_context:
      runAsNonRoot: false
      runAsUser: 0
      runAsGroup: 0
```

Any list set in the target is appended to the recipe's list. To replace
one, such as `tolerations`, set the key to `~` in a class included after
the recipe and the new list in the target.

## Left out

The chart's ServiceMonitor, PodMonitor, NetworkPolicy,
VerticalPodAutoscaler, kube-rbac-proxy with its ClusterRole, binding and
ConfigMap, Endpoints and extra manifests are off by default and not part
of the recipe. A ServiceMonitor or PodMonitor needs the CRDs of the
Prometheus Operator, which `check` does not install.

## Proof

`check node-exporter --level deploys` with `tests/values.yaml`, the
chart's defaults, and `tests/target.yml`, on kind for each Kubernetes
minor CI tests. The three objects differ in three classes:

- Selector scheme: the DaemonSet and the Service select on `name`, the
  chart on `app.kubernetes.io/name` and `app.kubernetes.io/instance`, and
  both select the same pods.
- Derived name: the container is named after the component, the chart's
  `node-exporter`.
- Port by name: the Service targets the port `metrics`, the chart the
  number 9100.

The chart binds no role. `tests/smoke` reads `/metrics` through the
Service and requires `node_exporter_build_info` with the version of the
DaemonSet's image. On every node it reads port 9100 of the node's address
through the API server's node proxy and requires `node_uname_info` with
the node's name and at least one `node_filesystem_size_bytes`. Without
`hostNetwork` the node's port refuses the connection and the test fails.

## Replacing a Helm release

Not tested. A release named `node-exporter` has the same object names.

1. Delete the DaemonSet `node-exporter-prometheus-node-exporter` with
   `--cascade=orphan`, because its selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.node-exporter.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Delete the orphaned pods of the old DaemonSet. They hold port 9100 of
   the node, so the recipe's pods stay `Pending` until then.
