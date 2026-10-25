"""AC-19: check downloads a release manifest and fails unless its SHA-256 is the one of the Source line (RCP-23).
AC-15: null fields, the order of prerequisites and the owner of an object, which need no cluster."""

import hashlib
import io
import shutil
import tempfile
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


if __name__ == "__main__":
    unittest.main()
