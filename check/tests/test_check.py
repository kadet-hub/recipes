"""AC-19 and AC-21: check downloads a release manifest, and a chart from an HTTP repository served on localhost,
and fails unless the SHA-256 is the one of the Source line (RCP-23).
AC-15: null fields, the order of prerequisites, the owner of an object and the wait for Established CRDs, which need no cluster.
AC-414: the steps of a migration, their order and verdict, without a cluster (RCP-14 to RCP-14b).
RCP-34: check at renders on a given compiled output and chart render, without Kapitan, helm or a cluster."""

import contextlib
import functools
import hashlib
import http.server
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import check

MANIFEST = b"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: rabbitmq-system\n---\n"
DIGEST = "sha256:" + hashlib.sha256(MANIFEST).hexdigest()
SOURCE = ("rabbitmq/cluster-operator", "v2.23.1", "cluster-operator.yml")


class FetchManifest(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.urlopen = mock.patch("urllib.request.urlopen", return_value=io.BytesIO(MANIFEST)).start()
        self.addCleanup(mock.patch.stopall)

    def tearDown(self):
        shutil.rmtree(self.work)

    def test_matching_digest(self):
        objs = check.fetch_manifest((*SOURCE, DIGEST), self.work)
        self.assertEqual(objs, [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "rabbitmq-system"}}])
        self.assertEqual((self.work / "manifest.yaml").read_bytes(), MANIFEST)
        self.assertEqual(
            self.urlopen.call_args.args[0],
            "https://github.com/rabbitmq/cluster-operator/releases/download/v2.23.1/cluster-operator.yml",
        )

    def test_other_digest_fails(self):
        other = "sha256:" + "0" * 64
        with self.assertRaises(check.Failed) as e:
            check.fetch_manifest((*SOURCE, other), self.work)
        self.assertEqual(
            str(e.exception),
            f"cluster-operator.yml of rabbitmq/cluster-operator release v2.23.1 has {DIGEST}, the README names {other}",
        )
        self.assertFalse((self.work / "manifest.yaml").exists())


def archive(name, version):
    """A chart archive as helm package writes it: <name>/Chart.yaml in a gzipped tar."""
    data = f"apiVersion: v2\nname: {name}\nversion: {version}\n".encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(f"{name}/Chart.yaml")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class HttpChart(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        # The index names the archive relative to the repository, as helm repo index writes it.
        self.repo.joinpath("index.yaml").write_text(
            "apiVersion: v1\nentries:\n  demo:\n    - name: demo\n      version: 1.2.0\n"
            "      urls:\n        - demo-1.2.0.tgz\n"
        )
        self.serve(archive("demo", "1.2.0"))
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.repo))
        handler.log_message = lambda *args: None
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.work = self.tmp / "work"
        self.work.mkdir()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.tmp)

    def serve(self, data):
        self.repo.joinpath("demo-1.2.0.tgz").write_bytes(data)
        self.digest = "sha256:" + hashlib.sha256(data).hexdigest()

    def test_archive_with_its_digest(self):
        tgz = check.fetch_http_chart((self.url, "demo", "1.2.0", self.digest), self.work)
        self.assertEqual("sha256:" + hashlib.sha256(tgz.read_bytes()).hexdigest(), self.digest)

    def test_archive_with_another_digest_fails(self):
        with self.assertRaisesRegex(check.Failed, "demo-1.2.0.tgz has sha256:.*, the README names sha256:0{64}"):
            check.fetch_http_chart((self.url, "demo", "1.2.0", "sha256:" + "0" * 64), self.work)

    def test_chart_yaml_with_another_version_fails(self):
        self.serve(archive("demo", "1.3.0"))
        with self.assertRaisesRegex(check.Failed, "is demo 1.3.0, the README names demo 1.2.0"):
            check.fetch_http_chart((self.url, "demo", "1.2.0", self.digest), self.work)

    def test_version_the_index_does_not_list_fails(self):
        with self.assertRaisesRegex(check.Failed, "index.yaml lists no archive of demo 1.1.0"):
            check.fetch_http_chart((self.url, "demo", "1.1.0", self.digest), self.work)


RECIPES = Path(__file__).resolve().parents[2]


class DropNulls(unittest.TestCase):
    def test_nulls_go_at_every_depth(self):
        cluster = {"spec": {"bootstrap": {"initdb": None}, "postgresql": None, "instances": 3,
                            "env": [{"name": "A", "value": None}]}}
        self.assertEqual(
            check.drop_nulls(cluster),
            {"spec": {"bootstrap": {}, "instances": 3, "env": [{"name": "A"}]}},
        )

    def test_falsy_values_stay(self):
        value = {"a": 0, "b": "", "c": [], "d": {}, "e": False}
        self.assertEqual(check.drop_nulls(value), value)


class Established(unittest.TestCase):
    """RCP-55: a CRD whose status.conditions is still null is waited for, not failed on."""

    def crd(self, conditions):
        return json.dumps({"kind": "CustomResourceDefinition", "metadata": {"name": "a.example.org"},
                           "status": {"conditions": conditions}})

    def established(self, *answers, timeout=60):
        cluster = check.Cluster("c", Path("/nonexistent"))
        with mock.patch.object(cluster, "kubectl", side_effect=answers), mock.patch("time.sleep"):
            return cluster.established(["crd/a.example.org"], timeout=timeout)

    def test_null_conditions_then_established(self):
        crds = self.established(self.crd(None), self.crd([{"type": "Established", "status": "True"}]))
        self.assertEqual(crds[0]["metadata"]["name"], "a.example.org")

    def test_never_established_fails(self):
        with self.assertRaisesRegex(check.Failed, "not Established"):
            self.established(self.crd(None), self.crd(None), timeout=-1)


class RolloutFailure(unittest.TestCase):
    """RCP-270: a failed rollout reports describe and logs of each pod that is neither ready nor completed."""

    PODS = json.dumps({"items": [
        {"metadata": {"namespace": "app", "name": "web-0"},
         "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "False"}]}},
        {"metadata": {"namespace": "app", "name": "db-0"},
         "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]}},
        {"metadata": {"namespace": "app", "name": "token-x"}, "status": {"phase": "Succeeded"}},
        {"metadata": {"namespace": "other", "name": "pull-0"}, "status": {"phase": "Pending"}},
    ]})

    def wait(self, *answers):
        cluster = check.Cluster("c", Path("/nonexistent"))
        sts = {"kind": "StatefulSet", "metadata": {"name": "web", "namespace": "app"}}
        self.ran = []

        def kubectl(cmd, **kw):
            self.ran.append(" ".join(cmd[3:]))
            return subprocess.CompletedProcess(cmd, 1, "", f"{' '.join(cmd[3:5])} output\n")

        with mock.patch.object(cluster, "kubectl", side_effect=answers), mock.patch("subprocess.run", side_effect=kubectl):
            check.wait_rollouts(cluster, [sts])

    def test_timeout_reports_unready_pods(self):
        with self.assertRaises(check.Failed) as failed:
            self.wait(check.Failed("error: timed out waiting for the condition"), self.PODS)
        logs = "logs --all-containers --prefix --timestamps --tail 100"
        self.assertEqual(self.ran, ["describe pod -n app web-0", f"{logs} -n app web-0",
                                    "describe pod -n other pull-0", f"{logs} -n other pull-0"])
        message = str(failed.exception)
        self.assertTrue(message.startswith("error: timed out waiting for the condition\n"))
        self.assertIn("kubectl describe pod -n app web-0:\ndescribe pod output", message)
        self.assertIn(f"kubectl {logs} -n other pull-0:\nlogs --all-containers output", message)

    def test_rollout_passes_without_report(self):
        self.wait("statefulset rolling update complete")
        self.assertEqual(self.ran, [])


class RequirementOrder(unittest.TestCase):
    """RCP-55: each prerequisite once, after those it requires, also through an included recipe."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("valkey", "cert-manager", "miniflux"):
            shutil.copytree(RECIPES / name, self.tmp / name)
        parent = self.tmp / "valkeyparent"
        shutil.copytree(RECIPES / "valkey", parent)
        init = (parent / "init.yml").read_text()
        (parent / "init.yml").write_text(init.replace("  - .valkey\n", "  - .valkey\n  - recipes.miniflux\n"))
        self.parent = parent

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def requires(self, name, line):
        readme = self.tmp / name / "README.md"
        readme.write_text(readme.read_text().replace("Level: `deploys`", f"Level: `deploys`\n\n{line}"))

    def test_order(self):
        self.requires("valkeyparent", "Requires: `cert-manager`, `gateway-api`")
        self.requires("miniflux", "Requires: `valkey`")
        self.requires("valkey", "Requires: `cert-manager`")
        self.assertEqual(check.requirement_order(self.parent), ["cert-manager", "gateway-api", "valkey"])

    def test_none(self):
        self.assertEqual(check.requirement_order(self.parent), [])


class Partition(unittest.TestCase):
    """RCP-49: an object belongs to the included recipe whose own compile renders its kind and name."""

    def test_by_kind_and_name(self):
        objs = [
            {"kind": "Deployment", "metadata": {"name": "nextcloud"}},
            {"kind": "Cluster", "metadata": {"name": "app-db"}},
            {"kind": "Secret", "metadata": {"name": "valkey-auth"}},
            {"kind": "Service", "metadata": {"name": "app-db"}},
        ]
        own, parts = check.partition(objs, {"postgresql": {("Cluster", "app-db")}, "valkey": {("Secret", "valkey-auth")}})
        self.assertEqual([o["kind"] for o in own], ["Deployment", "Service"])
        self.assertEqual({n: [o["kind"] for o in p] for n, p in parts.items()}, {"postgresql": ["Cluster"], "valkey": ["Secret"]})


def write_all(path, *objs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(check.dump_all(list(objs)))


def obj(kind, name, api="v1", **fields):
    return {"apiVersion": api, "kind": kind, "metadata": {"name": name, "namespace": "nextcloud"}, **fields}


class MigrationPlan(unittest.TestCase):
    """RCP-14b: the chart's Deployments whose selector changes, and its objects under names the recipe does not use,
    without those whose deletion takes data with them."""

    def test_plan(self):
        def deployment(name, labels):
            return {**obj("Deployment", name), "spec": {"selector": {"matchLabels": labels}}}

        role = obj("Role", "web:leader")
        chart = [deployment("web", {"app.kubernetes.io/name": "web"}), deployment("worker", {"name": "worker"}),
                 {**role, "metadata": {**role["metadata"], "namespace": "kube-system"}},
                 {"kind": "ServiceAccount", "metadata": {"name": "web"}},
                 {"kind": "CustomResourceDefinition", "metadata": {"name": "a.example.org"}}, obj("PersistentVolumeClaim", "data")]
        recipe = [deployment("web", {"name": "web"}), deployment("worker", {"name": "worker"}), obj("ServiceAccount", "web")]
        changed, leftovers, kept = check.migration_plan(chart, recipe, "nextcloud")
        names = [[f"{o['kind']}/{o['metadata']['name']}" for o in objs] for objs in (changed, leftovers, kept)]
        self.assertEqual(names, [["Deployment/web"], ["Role/web:leader"],
                                 ["CustomResourceDefinition/a.example.org", "PersistentVolumeClaim/data"]])


class Migrate(unittest.TestCase):
    """RCP-14: the steps of Migration in their order with tests/smoke before, during and after; RCP-14a."""

    CHART = [{**obj("Deployment", "web"), "spec": {"selector": {"matchLabels": {"app.kubernetes.io/name": "web"}}}},
             obj("Service", "web"), obj("Role", "web:leader"), obj("PersistentVolumeClaim", "data")]
    RECIPE = [{**obj("Deployment", "web"), "spec": {"selector": {"matchLabels": {"name": "web"}}}},
              obj("Service", "web"), obj("Role", "web-leader")]

    def migrate(self, failing_run=None, error=check.Failed("smoke failed"), labelled=(), smoke_wait=0.001, failing_step=None):
        self.steps, self.report, calls = [], [], []
        replicasets = {"items": [{"metadata": {"name": "web-1", "ownerReferences": [{"kind": "Deployment", "name": "web"}]}},
                                 {"metadata": {"name": "other-1"}}]}

        def kubectl(*args, input=None, **kw):
            names = [o["metadata"]["name"] for o in check.load_all(input)] if input else []
            self.steps.append(" ".join(args) + (f" {names}" if names else ""))
            if args[:1] == (failing_step,):
                raise check.Failed(f"kubectl {failing_step} failed")
            return json.dumps(replicasets) if args[:2] == ("get", "replicasets") else ""

        def smoke(cluster, recipe):
            calls.append(None)
            threading.Event().wait(smoke_wait if len(calls) > 1 else 0.001)  # the run before step 1 is quick
            if len(calls) == failing_run:
                raise error
            return "ok"

        cluster = mock.Mock(kubeconfig=Path("/nonexistent"))
        cluster.kubectl.side_effect = kubectl
        cluster.apply_for_real.side_effect = lambda objs, *f: self.steps.append(f"apply_for_real {[o['kind'] for o in objs]} {f}")
        cluster.apply.side_effect = lambda objs, *f: self.steps.append(f"apply {[o['kind'] for o in objs]} {f}")
        for target in ("check.prepare", "check.install"):
            mock.patch(target).start()
        mock.patch("check.run", return_value="v4.3.1+gc0d08d0").start()
        mock.patch("check.smoke", side_effect=smoke).start()
        mock.patch("check.wait_rollouts", side_effect=lambda c, objs: self.steps.append("rollout")).start()
        mock.patch("time.sleep", side_effect=lambda s: self.steps.append(f"sleep {s}")).start()
        mock.patch("check.helm_labelled", return_value=list(labelled)).start()
        self.addCleanup(mock.patch.stopall)
        return check.migrate(cluster, Path("web.tgz"), self.CHART, self.RECIPE, Path("/recipes/web"), "nextcloud",
                             {"nextcloud"}, (), self.report.append)

    def test_steps_in_order(self):
        self.assertFalse(self.migrate())
        self.assertEqual(self.steps, [
            "delete secret -n nextcloud -l owner=helm,name=web",
            "get replicasets -n nextcloud -o json",
            "delete deployment web -n nextcloud --cascade=orphan",
            "apply_for_real ['Deployment', 'Role'] ('--force-conflicts',)",
            "rollout",
            "apply ['Service'] ('--force-conflicts',)",
            "apply --server-side --field-manager helm -f - ['web', 'web', 'web-leader', 'data']",
            "rollout",
            f"sleep {check.SERVICE_SWITCH_WAIT}",
            "delete replicaset web-1 -n nextcloud --cascade=foreground",
            "delete --ignore-not-found -f - ['web:leader']",
        ])
        self.assertEqual(self.report[:4], ["migrates: selector changed: Deployment/web", "migrates: leftover: Role/web:leader",
                                           "migrates: leftover kept, it holds data: PersistentVolumeClaim/data",
                                           "migrates: chart installed with helm v4.3.1+gc0d08d0, smoke before: ok"])
        self.assertRegex(self.report[4], r"^migrates: smoke during the steps: \d+ runs passed$")
        self.assertEqual(self.report[5:], ["migrates: smoke after: ok", "migrates: no object labelled app.kubernetes.io/managed-by: Helm"])

    def test_failed_run_during_the_steps_fails(self):
        self.assertTrue(self.migrate(failing_run=2))
        self.assertRegex(self.report[4], r"^migrates: smoke during the steps failed in 1 of \d+ runs, first: Failed: smoke failed$")

    def test_timed_out_run_during_the_steps_fails(self):
        self.assertTrue(self.migrate(failing_run=2, error=subprocess.TimeoutExpired(["tests/smoke"], 600)))
        self.assertRegex(self.report[4], r"failed in 1 of \d+ runs, first: TimeoutExpired: Command '\['tests/smoke'\]' timed out")

    def test_failed_step_does_not_wait_for_smoke(self):
        start = time.monotonic()
        with self.assertRaisesRegex(check.Failed, "kubectl delete failed"):
            self.migrate(smoke_wait=5, failing_step="delete")
        self.assertLess(time.monotonic() - start, 4)

    def test_object_labelled_by_helm_fails(self):
        self.assertTrue(self.migrate(labelled=["serviceaccount/web"]))
        self.assertEqual(self.report[-1], "migrates: labelled app.kubernetes.io/managed-by: Helm: serviceaccount/web")


class GivenOutputs(unittest.TestCase):
    """RCP-34: nextcloud, which includes postgresql and valkey and requires cnpg (through postgresql) and
    gateway-api, at renders on outputs the caller compiled and rendered."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.out, self.rendered = self.tmp / "out", self.tmp / "rendered.yaml"
        config = obj("ConfigMap", "nextcloud-config", data={"a": "1"})
        secret = obj("Secret", "valkey-auth", stringData={"password": "x"})
        cluster = obj("Cluster", "postgresql-cluster", api="postgresql.cnpg.io/v1", spec={"instances": 1})
        write_all(self.rendered, obj("ServiceAccount", "nextcloud"),
                  {**config, "metadata": {**config["metadata"], "labels": {"helm.sh/chart": "nextcloud-9.4.1"}}})
        write_all(self.out / "compiled/nextcloud/manifests.yml", obj("ServiceAccount", "nextcloud"), config, secret, cluster)
        write_all(self.out / "compiled/valkey/manifests.yml", secret)
        write_all(self.out / "compiled/postgresql/manifests.yml", cluster)
        write_all(self.out / "compiled/cnpg/manifests.yml", obj("Namespace", "cnpg-system"))
        self.ran = []
        for target in ("check.run", "subprocess.run", "subprocess.Popen", "urllib.request.urlopen"):
            mock.patch(target, side_effect=lambda *a, **kw: self.ran.append(a)).start()
        mock.patch("check.GatewayProvider").start()
        mock.patch("check.Cluster.delete").start()
        self.prove = mock.patch("check.prove_side", side_effect=lambda cluster, objs, *a: (objs, {})).start()
        self.addCleanup(mock.patch.stopall)

    def main(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            status = check.main([str(RECIPES / "nextcloud"), *args])
        return status, err.getvalue()

    def test_compares_the_given_outputs(self):
        report = self.tmp / "report.txt"
        status, _ = self.main("--compiled", str(self.out), "--rendered", str(self.rendered), "--report", str(report))
        lines = report.read_text().splitlines()
        self.assertEqual(self.ran, [])
        self.assertEqual(status, 0, lines)
        for line in [
            "requires: gateway-api, cloud-provider-kind with the Gateway gateway/gateway, installed before the proof",
            "requires: cnpg, 1 objects, installed before the proof",
            "included valkey: `Secret/valkey-auth`",
            "included postgresql: `Cluster/postgresql-cluster`",
            "renders: passed",
        ]:
            self.assertIn(line, lines)
        sides = {tuple(o["metadata"]["name"] for o in c.args[1]) for c in self.prove.call_args_list}
        self.assertEqual(sides, {("nextcloud", "nextcloud-config")})

    def test_base_is_not_compiled(self):
        """RCP-21, RCP-34: with the compiled output given, check runs no Kapitan for the base either."""
        report = self.tmp / "report.txt"
        status, _ = self.main("--compiled", str(self.out), "--rendered", str(self.rendered), "--report", str(report),
                              "--base", str(RECIPES))
        self.assertEqual(status, 0)
        self.assertIn("base: not compared, the compiled output is given (RCP-34)", report.read_text().splitlines())
        self.assertEqual(self.ran, [])

    def test_missing_compile_of_an_included_recipe_fails(self):
        shutil.rmtree(self.out / "compiled/valkey")
        status, err = self.main("--compiled", str(self.out), "--rendered", str(self.rendered))
        self.assertEqual(status, 2)
        self.assertIn("no compiled output of valkey", err)
        self.assertEqual(self.ran, [])

    def test_flags_only_together_and_at_renders(self):
        both = ["--compiled", str(self.out), "--rendered", str(self.rendered)]
        for args in (both[:2], both[2:], [*both, "--level", "deploys"]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.main(*args)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            check.main(["lint", str(RECIPES / "nextcloud"), *both])
        self.assertEqual(self.ran, [])


class GivenCompile(unittest.TestCase):
    """RCP-34, RCP-38, RCP-44: a compose recipe (miniflux) and a designed one (mysql) at renders on a given
    compiled output: lint, then the apply of RCP-26 on one cluster, and nothing compared."""

    IMAGES = {
        "miniflux": "docker.io/miniflux/miniflux:2.3.4@sha256:" + "0" * 64,
        "mysql": "container-registry.oracle.com/mysql/community-server:9.7.4"
                 "@sha256:cb9cfddeccbbd9922bf927cd67bdb58067b357a1fc75d132988d1f5cc4cb17bb",
    }

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.ran = []
        for target in ("check.run", "subprocess.run", "subprocess.Popen", "urllib.request.urlopen"):
            mock.patch(target, side_effect=lambda *a, **kw: self.ran.append(a)).start()
        mock.patch("check.Cluster.delete").start()
        self.prove = mock.patch("check.prove_side", return_value=([], {})).start()
        self.compare = mock.patch("compare.compare").start()
        self.deploy = mock.patch("check.deploy").start()
        self.addCleanup(mock.patch.stopall)

    def main(self, name, *objs, args=()):
        labels = {"name": name}
        deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": name, "namespace": name},
                      "spec": {"selector": {"matchLabels": labels}, "template": {
                          "metadata": {"labels": labels}, "spec": {"containers": [{"name": name, "image": self.IMAGES[name]}]}}}}
        write_all(self.tmp / f"out/compiled/{name}/manifests.yml", deployment, *objs)
        report = self.tmp / "report.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            status = check.main([str(RECIPES / name), "--compiled", str(self.tmp / "out"), "--report", str(report), *args])
        return status, report.read_text().splitlines()

    def test_applies_and_compares_nothing(self):
        for name in self.IMAGES:
            with self.subTest(name=name):
                self.prove.reset_mock()
                status, lines = self.main(name)
                self.assertEqual(status, 0, lines)
                self.assertIn("renders: passed", lines)
                (call,) = self.prove.call_args_list
                self.assertEqual(([o["metadata"]["name"] for o in call.args[1]], call.args[4]), ([name], set()))
        self.compare.assert_not_called()
        self.deploy.assert_not_called()
        self.assertEqual(self.ran, [])

    def test_lint_fails_on_rbac(self):
        role = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": {"name": "miniflux", "namespace": "miniflux"}}
        status, lines = self.main("miniflux", role)
        self.assertEqual(status, 1)
        self.assertIn("lint: Role.rbac.authorization.k8s.io/miniflux/miniflux: RBAC object, the source grants no API access (RCP-38)", lines)
        self.prove.assert_not_called()

    def test_rendered_is_rejected(self):
        for name in self.IMAGES:
            with self.subTest(name=name), self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.main(name, args=("--rendered", str(self.tmp / "rendered.yaml")))
        self.prove.assert_not_called()

    def test_node_image(self):
        """RCP-70: kind creates the cluster from the node image given, from its default without one."""
        image = "kindest/node:v1.35.8@sha256:" + "0" * 64
        for args, line in (((), "node image: kind default"), (("--node-image", image), f"node image: {image}")):
            with self.subTest(args=args):
                self.prove.reset_mock()
                status, lines = self.main("mysql", args=args)
                self.assertEqual(status, 0, lines)
                self.assertIn(line, lines)
                self.prove.call_args.args[0].create()
                cmd = self.ran[-1][0]
                if args:
                    self.assertEqual(cmd[cmd.index("--image") + 1], image)
                else:
                    self.assertNotIn("--image", cmd)


class BaseChanges(unittest.TestCase):
    """RCP-21: check compiles the recipe of the base checkout and lists what changed against it."""

    IMAGE = "docker.io/valkey/valkey:9.0.0@sha256:" + "0" * 64

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.fetch = mock.patch("check.fetch_generators", return_value=[]).start()
        self.addCleanup(mock.patch.stopall)
        self.new = [obj("Pod", "valkey", spec={"containers": [{"name": "valkey", "image": self.IMAGE}]})]

    def changes(self, compiled_objs, base=RECIPES):
        def compile_recipe(project, out):
            write_all(out / "compiled/valkey/manifests.yml", *compiled_objs)

        with mock.patch("check.compile_recipe", side_effect=compile_recipe):
            return check.base_changes(RECIPES / "valkey", base, self.new, "valkey", self.tmp)

    def test_same(self):
        self.assertEqual(self.changes(self.new), ["same images, permissions, webhooks and host access"])
        (call,) = self.fetch.call_args_list
        self.assertEqual(call.args[0], RECIPES / "valkey")

    def test_changed_image(self):
        old = [obj("Pod", "valkey", spec={"containers": [{"name": "valkey", "image": self.IMAGE.replace("9.0.0", "8.1.0")}]})]
        self.assertEqual(self.changes(old), [f"image: {self.IMAGE.replace('9.0.0', '8.1.0')} -> {self.IMAGE}"])

    def test_new_recipe(self):
        self.assertEqual(self.changes([], base=self.tmp / "empty"), ["no recipe valkey in the base"])
        self.fetch.assert_not_called()

    def test_base_without_an_included_recipe(self):
        """A pull request that adds a recipe and the recipe it includes: the base has only one of them."""
        shutil.copytree(RECIPES / "authentik", self.tmp / "base/authentik")
        lines = check.base_changes(RECIPES / "authentik", self.tmp / "base", self.new, "authentik", self.tmp)
        self.assertEqual(lines, ["not compared, the base has no recipe postgresql that it includes"])
        self.fetch.assert_not_called()

    def test_base_that_does_not_compile(self):
        """The cause, not Kapitan's last line, as Kapitan 0.36.3 reports a failed kadet input."""
        failed = check.Failed("kapitan compile exited 1:\nError compiling valkey: Could not load Kadet module: kubernetes\n"
                              "Compile error: failed to compile target: valkey\n")
        with mock.patch("check.compile_recipe", side_effect=failed):
            lines = check.base_changes(RECIPES / "valkey", RECIPES, self.new, "valkey", self.tmp)
        self.assertEqual(lines, ["not compared, the base does not compile: Error compiling valkey: Could not load Kadet module: kubernetes"])


class NextAttestation(unittest.TestCase):
    """RCP-29a: the next image runs only after gh attestation verify accepted it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_verified_before_it_runs(self):
        with mock.patch("check.run") as run:
            self.assertIsNone(check.compile_next(self.tmp, self.tmp / "next"))
        verify, docker = (c.args[0] for c in run.call_args_list)
        digest = check.KAPITAN_NEXT.partition("@")[2]
        self.assertEqual(verify, ["gh", "attestation", "verify", f"oci://ghcr.io/kadet-hub/kapitan@{digest}",
                                  "--owner", "kadet-hub", "--cert-identity", check.NEXT_IDENTITY])
        self.assertEqual(docker[:2], ["docker", "run"])

    def test_unverified_image_does_not_run(self):
        with mock.patch("check.run", side_effect=check.Failed("no attestation")) as run, \
                self.assertRaises(check.Failed):
            check.compile_next(self.tmp, self.tmp / "next")
        self.assertEqual(run.call_count, 1)



class Meta(unittest.TestCase):
    """RCP-262, RCP-263: kapitan inventory proves recipe.yaml on copies of valkey and memcached."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def copy(self, name):
        recipe = self.tmp / "recipes" / name
        shutil.copytree(Path(__file__).resolve().parents[2] / name, recipe)
        return recipe

    def errors(self, recipe):
        work = self.tmp / "work"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir()
        return check.meta_errors(recipe, work)

    def edit(self, path, old, new):
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_valkey_passes(self):
        self.assertEqual(self.errors(self.copy("valkey")), [])

    def test_key_that_is_not_required_fails(self):
        recipe = self.copy("valkey")
        self.edit(recipe / "README.md", "      password: <ref>\n", "      password: <ref>\n      extra: <ref>\n")
        self.edit(recipe / "recipe.yaml", "required:\n", "required:\n  - path: applications.valkey.extra\n    description: x\n    secret: true\n")
        self.assertEqual(self.errors(recipe), [
            "applications.valkey.extra is not required: the Include snippet without it resolves (RCP-262)"])

    def test_backend_that_does_not_resolve_fails(self):
        recipe = self.copy("valkey")
        self.edit(recipe / "recipe.yaml", "  - omegaconf\n", "  - omegaconf\n  - reclass-rs\n")
        errors = self.errors(recipe)
        self.assertEqual(len(errors), 1)
        # reclass-rs resolves .valkey of valkey/init.yml to recipes.valkey itself (DEC-191).
        self.assertRegex(errors[0], r"^tests/target.yml does not resolve on reclass-rs: .+ \(RCP-263\)$")

    def test_backend_that_resolves_passes(self):
        recipe = self.copy("memcached")
        self.edit(recipe / "init.yml", "  - .memcached\n", "  - recipes.memcached.memcached\n")
        self.edit(recipe / "recipe.yaml", "  - omegaconf\n", "  - omegaconf\n  - reclass\n  - reclass-rs\n")
        self.assertEqual(self.errors(recipe), [])

    def test_option_that_does_not_need_the_key_fails(self):
        recipe = self.copy("valkey")
        (recipe / "tls.yml").write_text("parameters: {}\n")
        self.edit(recipe / "README.md", "  - recipes.valkey\n", "  - recipes.valkey\n  - recipes.valkey.tls\n")
        self.edit(recipe / "recipe.yaml", "    secret: true\n", "    secret: true\n    option: tls\n")
        errors = self.errors(recipe)
        self.assertEqual(len(errors), 1)
        self.assertRegex(errors[0], r"^the Include snippet without the option tls and applications.valkey.password does not resolve: "
                                    r".*Interpolation key 'applications.valkey.password' not found.* \(RCP-262\)$")


if __name__ == "__main__":
    unittest.main()
