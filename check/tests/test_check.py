"""AC-21: check fetches a chart from an HTTP repository, served on localhost, by the SHA-256 of its archive."""

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

import check


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


if __name__ == "__main__":
    unittest.main()
