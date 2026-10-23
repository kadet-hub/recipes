"""AC-1 and AC-5: check lint on the cert-manager recipe and on broken copies of it."""

import shutil
import tempfile
import unittest
from pathlib import Path

import lint

RECIPE = Path(__file__).resolve().parents[2] / "cert-manager"
DIGEST = "sha256:" + "0" * 64


class Lint(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.recipe = self.tmp / "cert-manager"
        shutil.copytree(RECIPE, self.recipe)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors_with(self, text):
        """Errors after adding a class file with the given text."""
        (self.recipe / "broken.yml").write_text(text)
        return "\n".join(lint.lint_files(self.recipe))

    def test_cert_manager_passes(self):
        self.assertEqual(lint.lint_files(self.recipe), [])

    # AC-1

    def test_default_config(self):
        errors = self.errors_with("parameters:\n  generators:\n    manifest:\n      default_config:\n        replicas: 2\n")
        self.assertIn("generators.manifest.default_config is merged into every component of a target (RCP-2)", errors)

    def test_component_without_application(self):
        errors = self.errors_with("parameters:\n  components:\n    cert-manager-extra:\n      image: x\n")
        self.assertIn("components.cert-manager-extra does not set application: cert-manager (RCP-2)", errors)

    def test_manifests_pass_through(self):
        errors = self.errors_with(
            "parameters:\n  generators:\n    kubernetes:\n      manifests:\n        cert-manager-extra:\n          kind: Foo\n"
        )
        self.assertIn("generators.kubernetes.manifests copies whole objects through (RCP-7)", errors)

    def test_long_flow_line(self):
        rule = "{apiGroups: [cert-manager.io], resources: [certificates, certificaterequests], verbs: [get]}"
        errors = self.errors_with(f"parameters:\n  applications:\n    cert-manager:\n      rule: {rule}\n")
        self.assertIn("broken.yml:4: flow style on a line longer than 80 characters (RCP-4)", errors)

    def test_image_without_digest(self):
        deployment = {
            "kind": "Deployment",
            "metadata": {"name": "cert-manager"},
            "spec": {"template": {"spec": {"containers": [{
                "image": "quay.io/jetstack/cert-manager-controller:v1.21.2",
                "args": [f"--acme-http01-solver-image=quay.io/jetstack/cert-manager-acmesolver:v1.21.2@{DIGEST}"],
            }]}}},
        }
        self.assertEqual(
            lint.lint_output("cert-manager", [deployment], set()),
            ["Deployment/cert-manager: image quay.io/jetstack/cert-manager-controller:v1.21.2 is not pinned by digest (RCP-6)"],
        )
        deployment["spec"]["template"]["spec"]["containers"][0]["image"] += f"@{DIGEST}"
        deployment["spec"]["template"]["spec"]["containers"][0]["args"] = ["--acme-http01-solver-image=quay.io/x:v1"]
        self.assertIn("image quay.io/x:v1 is not pinned", lint.lint_output("cert-manager", [deployment], set())[0])

    def test_rendered_name_outside_the_recipe(self):
        objs = [{"kind": "ClusterRole", "metadata": {"name": "admin-extra"}}, {"kind": "Role", "metadata": {"name": "chart-role"}}]
        self.assertEqual(
            lint.lint_output("cert-manager", objs, {"chart-role"}),
            ["ClusterRole/admin-extra: name neither starts with cert-manager nor is one the chart uses (RCP-3)"],
        )

    # AC-5

    def test_external_entry(self):
        errors = self.errors_with("parameters:\n  kapitan:\n    compile:\n      - input_type: external\n        input_paths:\n          - /bin/sh\n")
        self.assertIn("compile entry of input_type external (RCP-17)", errors)

    def test_jinja2_entry(self):
        errors = self.errors_with("parameters:\n  kapitan:\n    compile:\n      - input_type: jinja2\n        input_paths:\n          - templates\n")
        self.assertIn("compile entry of input_type jinja2 (RCP-17)", errors)

    def test_from_file(self):
        errors = self.errors_with("parameters:\n  applications:\n    cert-manager:\n      key: ${from_file:/etc/passwd}\n")
        self.assertIn("uses the resolver from_file (RCP-17)", errors)

    def test_unpinned_dependency(self):
        errors = self.errors_with(
            "parameters:\n  kapitan:\n    dependencies:\n      - type: oci\n        source: ghcr.io/kadet-hub/kubernetes:1.7.0\n        output_path: lib/k\n"
        )
        self.assertIn("dependency ghcr.io/kadet-hub/kubernetes:1.7.0 is not an oci artifact of ghcr.io/kadet-hub/ pinned by digest (RCP-17)", errors)

    def test_foreign_dependency(self):
        errors = self.errors_with(
            f"parameters:\n  kapitan:\n    dependencies:\n      - type: oci\n        source: ghcr.io/example/kubernetes@{DIGEST}\n        output_path: lib/k\n"
        )
        self.assertIn(f"dependency ghcr.io/example/kubernetes@{DIGEST} is not an oci artifact", errors)

    def test_copy_without_matching_hash(self):
        crds = self.recipe / "crds.yml"
        crds.write_text(crds.read_text().replace("SHA-256 262f", "SHA-256 162f"))
        self.assertIn("vendor/cert-manager.crds.yaml has no matching SHA-256 comment (RCP-17)", "\n".join(lint.lint_files(self.recipe)))

    def test_key_under_another_applications_component(self):
        errors = self.errors_with("parameters:\n  components:\n    ingress-nginx:\n      image: evil\n")
        self.assertIn("components.ingress-nginx is not below the recipe's name (RCP-18)", errors)

    def test_rbac_entry_named_after_something_else(self):
        errors = self.errors_with(
            "parameters:\n  generators:\n    kubernetes:\n      rbac:\n        kube-system-admin:\n          cluster_role: cluster-admin\n"
        )
        self.assertIn("generators.kubernetes.rbac.kube-system-admin is not below the recipe's name (RCP-18)", errors)

    def test_ref_backend(self):
        errors = self.errors_with("parameters:\n  applications:\n    cert-manager:\n      password: ?{base64:cert-manager/password}\n")
        self.assertIn("names a ref backend with ?{ (RCP-19)", errors)

    def test_readme_fields(self):
        readme = self.recipe / "README.md"
        readme.write_text(readme.read_text().replace("Level: `deploys`", "Level: deploys"))
        self.assertIn("README.md has no line Level:", "\n".join(lint.lint_files(self.recipe)))


if __name__ == "__main__":
    unittest.main()
