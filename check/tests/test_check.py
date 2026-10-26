"""AC-15: null fields, the order of prerequisites and the owner of an object, which need no cluster.
AC-24: check validates only the Kapitan output (DEC-19). Every recipe kind at renders, on a given compiled output
(RCP-34) or its own compile, is linted and applied once on one cluster, with no helm run and no download of its
Source (RCP-8, RCP-26)."""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check

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



def deployment(name, namespace, image="docker.io/library/busybox:1.37.0@sha256:" + "0" * 64):
    labels = {"name": name}
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": name, "namespace": namespace},
            "spec": {"selector": {"matchLabels": labels},
                     "template": {"metadata": {"labels": labels}, "spec": {"containers": [{"name": name, "image": image}]}}}}


MYSQL = ("container-registry.oracle.com/mysql/community-server:9.7.4"
         "@sha256:cb9cfddeccbbd9922bf927cd67bdb58067b357a1fc75d132988d1f5cc4cb17bb")


class Renders(unittest.TestCase):
    """AC-24: a chart (nextcloud, which includes postgresql and valkey and requires cnpg and gateway-api), a chart
    from an HTTP repository (external-dns-powerdns, which includes powerdns), a release manifest
    (rabbitmq-cluster-operator, which requires cert-manager), a compose (miniflux) and a designed recipe (mysql)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.out, self.report = self.tmp / "out", self.tmp / "report.txt"
        self.ran = []
        for target in ("check.run", "subprocess.run", "subprocess.Popen", "urllib.request.urlopen"):
            mock.patch(target, side_effect=lambda *a, **kw: self.ran.append(a)).start()
        mock.patch("check.GatewayProvider").start()
        mock.patch("check.Cluster.delete").start()
        self.apply = mock.patch("check.apply_renders").start()
        self.deploy = mock.patch("check.deploy").start()
        self.addCleanup(mock.patch.stopall)
        cluster = obj("Cluster", "postgresql-cluster", api="postgresql.cnpg.io/v1")
        secret = obj("Secret", "valkey-auth")
        powerdns = deployment("powerdns", "dns")
        self.compiled("nextcloud", deployment("nextcloud", "nextcloud"), cluster, secret)
        self.compiled("postgresql", cluster)
        self.compiled("valkey", secret)
        self.compiled("cnpg", {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "cnpg-system"}})
        self.compiled("external-dns-powerdns", deployment("external-dns-powerdns", "dns"), powerdns)
        self.compiled("powerdns", powerdns)
        # RCP-3: a release manifest's own names, as the Issuer of the RabbitMQ Cluster Operator's.
        self.compiled("rabbitmq-cluster-operator", deployment("rabbitmq-cluster-operator", "rabbitmq-system"),
                      {"apiVersion": "cert-manager.io/v1", "kind": "Issuer",
                       "metadata": {"name": "selfsigned-issuer", "namespace": "rabbitmq-system"}})
        self.compiled("cert-manager", {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "cert-manager"}})
        self.compiled("miniflux", deployment("miniflux", "miniflux"))
        self.compiled("mysql", deployment("mysql", "mysql", MYSQL))

    def compiled(self, name, *objs):
        write_all(self.out / f"compiled/{name}/manifests.yml", *objs)

    def main(self, name, *args):
        self.report.unlink(missing_ok=True)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            status = check.main([str(RECIPES / name), "--report", str(self.report), *args])
        return status, self.report.read_text().splitlines() if self.report.exists() else err.getvalue()

    def test_every_kind_once_on_one_cluster(self):
        for name, objects in (("nextcloud", 3), ("external-dns-powerdns", 2), ("rabbitmq-cluster-operator", 2),
                              ("miniflux", 1), ("mysql", 1)):
            with self.subTest(name=name):
                self.apply.reset_mock()
                status, lines = self.main(name, "--compiled", str(self.out))
                self.assertEqual(status, 0, lines)
                self.assertEqual(lines[-1], "renders: passed")
                (call,) = self.apply.call_args_list
                self.assertEqual(call.args[0].name, f"check-{name}-{os.getpid()}"[:50])
                self.assertEqual(len(call.args[1]), objects)
        self.deploy.assert_not_called()
        self.assertEqual(self.ran, [])

    def test_report_of_a_parent(self):
        _, lines = self.main("nextcloud", "--compiled", str(self.out))
        for line in [
            "compiled: given in " + str(self.out) + ", generators not verified by check",
            "requires: gateway-api, cloud-provider-kind with the Gateway gateway/gateway, installed before the proof",
            "requires: cnpg, 1 objects, installed before the proof",
            "included valkey: `Secret/valkey-auth`",
            "included postgresql: `Cluster/postgresql-cluster`",
        ]:
            self.assertIn(line, lines)

    def test_own_compile_fetches_no_source(self):
        mock.patch("check.fetch_generators", return_value=[]).start()
        mock.patch("check.compile_recipe", side_effect=lambda project, out: write_all(
            out / "compiled/valkey/manifests.yml", deployment("valkey", "valkey"))).start()
        mock.patch("check.compile_next", return_value="not run in this test").start()
        status, lines = self.main("valkey")
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines[-1], "renders: passed")
        self.apply.assert_called_once()
        self.assertEqual(self.ran, [])

    def test_lint_fails_on_rbac_of_a_compose_recipe(self):
        self.compiled("miniflux", deployment("miniflux", "miniflux"),
                      {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": {"name": "miniflux", "namespace": "miniflux"}})
        status, lines = self.main("miniflux", "--compiled", str(self.out))
        self.assertEqual(status, 1)
        self.assertIn("lint: Role.rbac.authorization.k8s.io/miniflux/miniflux: RBAC object, the source grants no API access (RCP-38)", lines)
        self.apply.assert_not_called()

    def test_names_without_the_prefix(self):
        """RCP-3: a compose recipe's names start with its own, a chart recipe's may be the chart's."""
        self.compiled("miniflux", deployment("miniflux", "miniflux"), deployment("db", "miniflux"))
        status, lines = self.main("miniflux", "--compiled", str(self.out))
        self.assertEqual(status, 1)
        self.assertIn("lint: Deployment/db: name neither starts with miniflux nor is one the chart uses (RCP-3)", lines)
        self.compiled("valkey", deployment("valkey", "valkey"), deployment("db", "valkey"))
        status, lines = self.main("valkey", "--compiled", str(self.out))
        self.assertEqual(status, 0, lines)

    def test_missing_compile_of_an_included_recipe_fails(self):
        shutil.rmtree(self.out / "compiled/valkey")
        status, err = self.main("nextcloud", "--compiled", str(self.out))
        self.assertEqual(status, 2)
        self.assertIn("no compiled output of valkey", err)
        self.assertEqual(self.ran, [])

    def test_compiled_only_at_renders_and_no_rendered(self):
        for args in (["--compiled", str(self.out), "--level", "deploys"],
                     ["--compiled", str(self.out), "--rendered", str(self.tmp / "chart.yaml")]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.main("valkey", *args)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            check.main(["lint", str(RECIPES / "valkey"), "--compiled", str(self.out)])
        self.assertEqual(self.ran, [])

    def test_deploys_on_one_cluster_without_the_renders_apply(self):
        objs = [deployment("valkey", "valkey")]
        prepare = mock.patch("check.prepare").start()
        self.deploy.return_value = "smoke passed\n"
        lines = []
        for level, failed in (("deploys", False), ("migrates", True)):
            with self.subTest(level=level):
                self.assertEqual(check.proof(RECIPES / "valkey", level, self.tmp, False, lines.append, "valkey", objs, [], self.out), failed)
        self.assertEqual([c.args[0].name for c in prepare.call_args_list], [f"check-valkey-{os.getpid()}"] * 2)
        self.assertEqual([c.args[1] for c in self.deploy.call_args_list], [objs, objs])
        self.apply.assert_not_called()
        self.assertEqual(lines.count("deploys: passed"), 2)
        self.assertEqual(lines[-1], "migrates: not implemented in this version of check")


if __name__ == "__main__":
    unittest.main()
