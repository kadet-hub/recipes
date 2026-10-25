"""AC-19 and AC-21: check downloads a release manifest, and a chart from an HTTP repository served on localhost,
and fails unless the SHA-256 is the one of the Source line (RCP-23).
AC-15: null fields, the order of prerequisites and the owner of an object, which need no cluster.
RCP-34: check at renders on a given compiled output and chart render, without Kapitan, helm or a cluster."""

import contextlib
import functools
import hashlib
import http.server
import io
import shutil
import tarfile
import tempfile
import threading
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


if __name__ == "__main__":
    unittest.main()
