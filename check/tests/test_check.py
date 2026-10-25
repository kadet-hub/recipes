"""AC-19: check downloads a release manifest and fails unless its SHA-256 is the one of the Source line (RCP-23)."""

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


if __name__ == "__main__":
    unittest.main()
