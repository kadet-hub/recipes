"""AC-1, AC-5, AC-8, AC-9, AC-10, AC-12, AC-13, AC-19 and AC-21: check lint on the cert-manager, miniflux and mysql recipes and on broken copies of them."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

import lint

RECIPE = Path(__file__).resolve().parents[2] / "cert-manager"
COMPOSE_RECIPE = RECIPE.parent / "miniflux"
DESIGN_RECIPE = RECIPE.parent / "mysql"
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

    def test_anchor_and_alias(self):
        errors = self.errors_with(
            "parameters:\n  applications:\n    cert-manager:\n      a: &probe\n        port: 1\n      b: *probe\n"
        )
        self.assertIn("broken.yml:4: YAML anchor &probe (RCP-4a)", errors)
        self.assertIn("broken.yml:6: YAML alias *probe (RCP-4a)", errors)

    def test_merge_key(self):
        errors = self.errors_with("parameters:\n  applications:\n    cert-manager:\n      <<: {port: 1}\n")
        self.assertIn("broken.yml:4: YAML merge key << (RCP-4a)", errors)

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

    def test_image_tag_from_interpolation(self):  # RCP-66
        image = "quay.io/jetstack/cert-manager-controller:${applications.cert-manager.version}@" + DIGEST
        errors = self.errors_with(f"parameters:\n  components:\n    cert-manager-extra:\n      application: cert-manager\n      image: {image}\n")
        self.assertIn("broken.yml:5: image reference takes its tag from an interpolation (RCP-66)", errors)
        literal = f"parameters:\n  components:\n    cert-manager-extra:\n      application: cert-manager\n      image: quay.io/x:v1@{DIGEST}\n"
        self.assertNotIn("RCP-66", self.errors_with(literal))

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

    def test_forbidden_resolvers(self):
        for resolver, call in [
            ("from_file", "${from_file:/etc/passwd}"),
            ("write", "${write:components.x,applications.cert-manager}"),
            ("oc.env", "${oc.decode:${oc.env:GITHUB_TOKEN}}"),
            ("filename", "${filename:}"),
            ("parent_filename", "${parent_filename:}"),
            ("path", "${path:}"),
            ("parent_path", "${parent_path:}"),
        ]:
            with self.subTest(resolver):
                errors = self.errors_with(f"parameters:\n  applications:\n    cert-manager:\n      key: {call}\n")
                self.assertIn(f"uses the resolver {resolver} (RCP-17)", errors)

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

    # AC-9

    def nested_errors(self, text):
        """Errors after adding vendor/x.yml with the given text, included as .vendor.x."""
        (self.recipe / "vendor/x.yml").write_text(text)
        return self.errors_with("classes:\n  - .vendor.x\n")

    def test_nested_external_entry(self):
        errors = self.nested_errors("parameters:\n  kapitan:\n    compile:\n      - input_type: external\n        input_paths:\n          - /bin/sh\n")
        self.assertIn("vendor/x.yml: compile entry of input_type external (RCP-17)", errors)

    def test_nested_env_resolver(self):
        errors = self.nested_errors("parameters:\n  applications:\n    cert-manager:\n      key: ${oc.env:GITHUB_TOKEN}\n")
        self.assertIn("vendor/x.yml: uses the resolver oc.env (RCP-17)", errors)

    def test_include_outside_the_linted_files(self):
        errors = self.errors_with("classes:\n  - .tests.target\n")
        self.assertIn("broken.yml: class .tests.target resolves to cert-manager/tests/target.yml, which is not linted (RCP-36)", errors)

    def test_python_file(self):
        (self.recipe / "vendor/x.py").write_text("")
        self.assertIn("vendor/x.py: a recipe contains no Python (RCP-33)", "\n".join(lint.lint_files(self.recipe)))

    # AC-8

    def test_copy_without_license(self):
        (self.recipe / "vendor/cert-manager.crds.yaml.LICENSE").unlink()
        self.assertIn("has no cert-manager.crds.yaml.LICENSE (RCP-35)", "\n".join(lint.lint_files(self.recipe)))

    def test_readme_fields(self):
        readme = self.recipe / "README.md"
        readme.write_text(readme.read_text().replace("Level: `deploys`", "Level: deploys"))
        self.assertIn("README.md has no line Level:", "\n".join(lint.lint_files(self.recipe)))

    # AC-21

    def test_http_repository_source(self):
        readme = self.recipe / "README.md"
        source = f"https://charts.jetstack.io/cert-manager:v1.21.2@{DIGEST}"
        readme.write_text(lint.SOURCE_LINE.sub(f"Source: `{source}`", readme.read_text()))
        self.assertEqual(lint.readme_fields(self.recipe)[0], ("http", ("https://charts.jetstack.io", "cert-manager", "v1.21.2", DIGEST)))
        self.assertEqual(lint.lint_files(self.recipe), [])
        (self.recipe / "tests/values.yaml").unlink()
        self.assertIn("tests/values.yaml is missing (RCP-1)", lint.lint_files(self.recipe))


    def test_required_parameters(self):
        readme = self.recipe / "README.md"
        text = readme.read_text()
        for broken in (text.replace("## Required parameters", "## Required"),
                       text.replace("No parameter has to be set.", "")):
            readme.write_text(broken)
            self.assertIn('README.md has no section "Required parameters"', "\n".join(lint.lint_files(self.recipe)))

    def rcp32_errors(self, readme=None):
        """The RCP-32 errors, after writing the README if one is given."""
        if readme is not None:
            (self.recipe / "README.md").write_text(readme)
        return [e for e in lint.lint_files(self.recipe) if "(RCP-32)" in e]

    def description_errors(self, paragraph):
        """The RCP-32 errors after replacing the README's first paragraph."""
        readme = self.recipe / "README.md"
        heading, _, rest = readme.read_text().split("\n\n", 2)
        return self.rcp32_errors(f"{heading}\n\n{paragraph}\n\n{rest}")

    def test_description_length(self):
        self.assertEqual(self.description_errors("x" * 300), [])
        self.assertEqual(
            self.description_errors("x" * 301),
            ["README.md: the first paragraph is 301 characters, at most 300 (RCP-32)"],
        )

    def test_description_length_counts_collapsed_whitespace(self):
        self.assertEqual(self.description_errors("x" * 150 + "\n   \t" + "y" * 149), [])
        self.assertEqual(len(self.description_errors("x" * 150 + "\n   \t" + "y" * 150)), 1)

    def test_description_is_the_first_block_after_the_heading(self):
        readme = "x" * 400 + "\n\n# cert-manager\n\n\nOne\nparagraph.\n\n" + "x" * 400 + "\n"
        self.assertEqual(self.rcp32_errors(readme), [])
        readme = "Short.\n\n# cert-manager\n\n\n" + "x" * 301 + "\n\nShort.\n"
        self.assertEqual(len(self.rcp32_errors(readme)), 1)

    def test_description_control_character(self):
        self.assertEqual(self.description_errors("Two\tlines\nof text"), [])
        for char in ("\x00", "\x1b", "\x7f", "\x85"):
            self.assertEqual(
                self.description_errors(f"A{char}B"),
                [f"README.md: the first paragraph contains U+{ord(char):04X}, a control or bidirectional formatting character (RCP-32)"],
            )

    def test_description_bidirectional_character(self):
        self.assertEqual(self.description_errors("Caf\u00e9 \u201cquoted\u201d"), [])
        for char in ("\u061c", "\u200e", "\u202e", "\u2066"):
            self.assertEqual(len(self.description_errors(f"A{char}B")), 1, char)

    def test_description_trailing_colon(self):
        self.assertEqual(self.description_errors("Derived from: the chart."), [])
        for paragraph in ("Derived from the chart:", "Derived from\nthe chart: "):
            self.assertEqual(self.description_errors(paragraph), ["README.md: the first paragraph ends with a colon (RCP-32)"])

    def test_description_missing(self):
        for readme in ("# cert-manager\n", "# cert-manager\n\n\n \t\n", "no heading\n\ntext\n"):
            self.assertEqual(self.rcp32_errors(readme), ["README.md has no paragraph after the heading (RCP-32)"], readme)

    # AC-12

    def test_args_list_warns(self):
        (self.recipe / "broken.yml").write_text(
            "parameters:\n  components:\n    cert-manager-extra:\n      application: cert-manager\n"
            "      args:\n        - --v=2\n      init_containers:\n        wait:\n          args:\n            - --once\n"
        )
        self.assertEqual(lint.lint_files(self.recipe), [])
        self.assertEqual(lint.lint_warnings(self.recipe), [
            "broken.yml: components.cert-manager-extra.args is a list, write it as a mapping (RCP-43)",
            "broken.yml: components.cert-manager-extra.init_containers.wait.args is a list, write it as a mapping (RCP-43)",
        ])
        init = self.recipe / "init.yml"
        init.write_text(init.read_text().replace("kubernetes:1.14.0@", "kubernetes:1.6.0@"))
        self.assertEqual(lint.lint_warnings(self.recipe), [])

    def test_args_mappings_do_not_warn(self):
        self.assertEqual(lint.lint_warnings(self.recipe), [])
        self.assertEqual(lint.lint_warnings(RECIPE.parent / "valkey"), [])


class LintCompose(unittest.TestCase):
    """AC-10: a recipe derived from a compose file."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.recipe = self.tmp / "miniflux"
        shutil.copytree(COMPOSE_RECIPE, self.recipe)
        self.readme = self.recipe / "README.md"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_miniflux_passes_without_values_yaml(self):
        self.assertFalse((self.recipe / "tests/values.yaml").exists())
        self.assertEqual(lint.lint_files(self.recipe), [])
        self.assertEqual(lint.readme_fields(self.recipe)[0][0], "compose")

    def test_level_renders(self):
        self.readme.write_text(self.readme.read_text().replace("Level: `deploys`", "Level: `renders`"))
        self.assertIn("a compose source is proven at level deploys, not renders (RCP-38)", lint.lint_files(self.recipe))

    def test_source_without_full_commit(self):
        self.readme.write_text(self.readme.read_text().replace("/blob/238c5614e584ebc87894e7d9f10bc91373a0b2c2/", "/blob/2.3.4/"))
        self.assertIn("README.md has no line Source:", "\n".join(lint.lint_files(self.recipe)))

    def test_output(self):
        pod = {"metadata": {"labels": {"name": "miniflux"}}}
        deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "miniflux", "namespace": "miniflux"},
                      "spec": {"selector": {"matchLabels": {"name": "miniflux"}}, "template": pod}}
        service = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "miniflux", "namespace": "miniflux"},
                   "spec": {"selector": {"name": "miniflux"}}}
        self.assertEqual(lint.lint_compose_output([deployment, service]), [])
        stray = {**service, "metadata": {"name": "miniflux-db", "namespace": "miniflux"}, "spec": {"selector": {"name": "db"}}}
        binding = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
                   "metadata": {"name": "miniflux", "namespace": "miniflux"}}
        self.assertEqual(
            lint.lint_compose_output([deployment, service, stray, binding]),
            [
                "RoleBinding.rbac.authorization.k8s.io/miniflux/miniflux: RBAC object, the source grants no API access (RCP-38)",
                "Service/miniflux/miniflux-db: selector selects no pods (RCP-38)",
            ],
        )


class LintManifest(unittest.TestCase):
    """AC-19: a recipe from a release manifest needs no tests/values.yaml (RCP-23)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.recipe = self.tmp / "cert-manager"
        shutil.copytree(RECIPE, self.recipe)
        (self.recipe / "tests/values.yaml").unlink()
        self.readme = self.recipe / "README.md"
        self.line = re.search(r"^Source: .*$", self.readme.read_text(), re.M).group(0)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def source(self, url):
        self.readme.write_text(self.readme.read_text().replace(self.line, f"Source: `{url}@{DIGEST}`"))
        return lint.readme_fields(self.recipe)[0]

    def test_release_asset(self):
        url = "https://github.com/rabbitmq/cluster-operator/releases/download/v2.23.1/cluster-operator.yml"
        self.assertEqual(self.source(url), ("manifest", ("rabbitmq/cluster-operator", "v2.23.1", "cluster-operator.yml", DIGEST)))
        self.assertEqual(lint.lint_files(self.recipe), [])

    def test_not_a_release_asset(self):
        self.assertIsNone(self.source("https://github.com/rabbitmq/cluster-operator/releases/v2.23.1/cluster-operator.yml"))
        self.assertIn("README.md has no line Source:", "\n".join(lint.lint_files(self.recipe)))


class LintDesign(unittest.TestCase):
    """AC-13: a recipe designed on the project's image."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.recipe = self.tmp / "mysql"
        shutil.copytree(DESIGN_RECIPE, self.recipe)
        self.readme = self.recipe / "README.md"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_mysql_passes_without_values_yaml(self):
        self.assertFalse((self.recipe / "tests/values.yaml").exists())
        self.assertEqual(lint.lint_files(self.recipe), [])
        self.assertEqual(lint.readme_fields(self.recipe)[0][0], "design")

    def test_level_renders(self):
        self.readme.write_text(self.readme.read_text().replace("Level: `deploys`", "Level: `renders`"))
        self.assertIn("a designed recipe is proven at level deploys, not renders (RCP-44)", lint.lint_files(self.recipe))

    def test_output(self):
        source = ("container-registry.oracle.com/mysql/community-server", "9.7.4", DIGEST)
        image = f"container-registry.oracle.com/mysql/community-server:9.7.4@{DIGEST}"
        container = {"name": "mysql", "image": image}
        pod = {"metadata": {"labels": {"name": "mysql"}}, "spec": {"containers": [container]}}
        statefulset = {"apiVersion": "apps/v1", "kind": "StatefulSet", "metadata": {"name": "mysql", "namespace": "mysql"},
                       "spec": {"selector": {"matchLabels": {"name": "mysql"}}, "template": pod}}
        service = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "mysql", "namespace": "mysql"},
                   "spec": {"selector": {"name": "mysql"}}}
        self.assertEqual(lint.lint_design_output([statefulset, service], source), [])
        container["image"] = image.replace(":9.7.4@", ":9.7.3@")
        binding = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding",
                   "metadata": {"name": "mysql", "namespace": "mysql"}, "roleRef": {"kind": "ClusterRole", "name": "edit"}}
        self.assertEqual(
            lint.lint_design_output([statefulset, service, binding], source),
            [
                "RoleBinding.rbac.authorization.k8s.io/mysql/mysql: binds ClusterRole/edit, which the recipe does not render (RCP-308)",
                f"no container runs the Source image {image} (RCP-23)",
            ],
        )

    def test_read_only_rbac(self):
        """RCP-308: a designed recipe may bind its own roles that only read, and nothing else."""
        rbac = "rbac.authorization.k8s.io/v1"
        reads = {"apiGroups": ["", "networking.k8s.io"], "resources": ["pods", "ingresses"], "verbs": ["get", "list", "watch"]}
        cluster_role = {"apiVersion": rbac, "kind": "ClusterRole", "metadata": {"name": "homepage"}, "rules": [reads]}
        role = {"apiVersion": rbac, "kind": "Role", "metadata": {"name": "homepage", "namespace": "homepage"}, "rules": [reads]}
        subjects = [{"kind": "ServiceAccount", "name": "homepage", "namespace": "homepage"}]
        cluster_binding = {"apiVersion": rbac, "kind": "ClusterRoleBinding", "metadata": {"name": "homepage"},
                           "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole", "name": "homepage"},
                           "subjects": subjects}
        binding = {"apiVersion": rbac, "kind": "RoleBinding", "metadata": {"name": "homepage", "namespace": "homepage"},
                   "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "homepage"}, "subjects": subjects}
        self.assertEqual(lint.read_only_rbac_errors([cluster_role, role, cluster_binding, binding]), [])
        # A ClusterRole is cluster-scoped: a namespace in its metadata does not hide it from its binding.
        namespaced = {**cluster_role, "metadata": {"name": "homepage", "namespace": "homepage"}}
        self.assertEqual(lint.read_only_rbac_errors([namespaced, cluster_binding]), [])
        # A Role rendered without a namespace lands in the binding's, the target namespace.
        unnamespaced = {**role, "metadata": {"name": "homepage"}}
        self.assertEqual(lint.read_only_rbac_errors([unnamespaced, binding]), [])
        writes = {**cluster_role, "rules": [reads, {"apiGroups": [""], "resources": ["configmaps"], "verbs": ["get", "update"]}]}
        secrets = {**role, "rules": [{"apiGroups": [""], "resources": ["secrets", "secrets/status"], "verbs": ["get"]},
                                     {"apiGroups": ["*"], "resources": ["pods"], "verbs": ["list"]}]}
        urls = {**cluster_role, "metadata": {"name": "homepage-urls"}, "rules": [{"nonResourceURLs": ["/metrics"], "verbs": ["get"]}],
                "aggregationRule": {"clusterRoleSelectors": []}}
        admin = {**cluster_binding, "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole", "name": "cluster-admin"}}
        elsewhere = {**binding, "metadata": {"name": "homepage", "namespace": "other"}}
        self.assertEqual(
            lint.read_only_rbac_errors([writes, secrets, urls, admin, elsewhere]),
            [
                "ClusterRole.rbac.authorization.k8s.io/homepage: verbs update, a designed recipe only reads (RCP-308)",
                "Role.rbac.authorization.k8s.io/homepage/homepage: secrets, secrets/status, a designed recipe reads no Secret (RCP-308)",
                "Role.rbac.authorization.k8s.io/homepage/homepage: *, a designed recipe names the groups and resources it reads (RCP-308)",
                "ClusterRole.rbac.authorization.k8s.io/homepage-urls: aggregationRule, a designed recipe grants only the rules it lists (RCP-308)",
                "ClusterRole.rbac.authorization.k8s.io/homepage-urls: nonResourceURLs, a designed recipe reads only resources (RCP-308)",
                "ClusterRoleBinding.rbac.authorization.k8s.io/homepage: binds ClusterRole/cluster-admin, which the recipe does not render (RCP-308)",
                "RoleBinding.rbac.authorization.k8s.io/other/homepage: binds Role/homepage, which the recipe does not render (RCP-308)",
            ],
        )
        # A compose recipe still renders no RBAC object at all (RCP-38).
        self.assertEqual(
            lint.lint_compose_output([cluster_role]),
            ["ClusterRole.rbac.authorization.k8s.io/homepage: RBAC object, the source grants no API access (RCP-38)"],
        )

    def test_output_on_an_operator(self):
        source = ("quay.io/keycloak/keycloak", "26.8.1", DIGEST)
        resource = {"apiVersion": "k8s.keycloak.org/v2beta1", "kind": "Keycloak",
                    "metadata": {"name": "keycloak", "namespace": "keycloak"},
                    "spec": {"image": f"quay.io/keycloak/keycloak:26.8.1@{DIGEST}"}}
        self.assertEqual(lint.lint_design_output([resource], source), [])
        resource["spec"]["image"] = f"quay.io/keycloak/keycloak:26.8.0@{DIGEST}"
        self.assertEqual(
            lint.lint_design_output([resource], source),
            [f"no container runs the Source image quay.io/keycloak/keycloak:26.8.1@{DIGEST} (RCP-23)"],
        )

    def test_output_on_an_operator_per_part(self):
        """AC-22: a Strimzi Kafka names its image as spec.kafka.image; deeper parts do not count (RCP-58)."""
        source = ("quay.io/strimzi/kafka", "1.3.0-kafka-4.3.1", DIGEST)
        image = f"quay.io/strimzi/kafka:1.3.0-kafka-4.3.1@{DIGEST}"
        resource = {"apiVersion": "kafka.strimzi.io/v1", "kind": "Kafka", "metadata": {"name": "kafka", "namespace": "kafka"},
                    "spec": {"kafka": {"image": image}}}
        self.assertEqual(lint.lint_design_output([resource], source), [])
        resource["spec"] = {"kafka": {}, "entityOperator": {"topicOperator": {"image": image}}}
        self.assertEqual(lint.lint_design_output([resource], source), [f"no container runs the Source image {image} (RCP-23)"])


class LintIncludesAndRequires(unittest.TestCase):
    """AC-14: RCP-47, RCP-48 and RCP-54 on a parent built from copies of valkey and cert-manager."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for name in ("valkey", "cert-manager", "miniflux"):
            shutil.copytree(RECIPE.parent / name, self.tmp / name)
        # The parent: valkey's own files under another name, which includes valkey.
        self.parent = self.tmp / "valkeyparent"
        shutil.copytree(RECIPE.parent / "valkey", self.parent)
        (self.parent / "valkey.yml").unlink()
        init = (self.parent / "init.yml").read_text().replace("  - .valkey\n", "  - recipes.valkey\n")
        (self.parent / "init.yml").write_text(init.replace("    valkey:\n", "    valkeyparent:\n"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors(self, recipe=None):
        return "\n".join(lint.lint_files(recipe or self.parent))

    def requires(self, recipe, line):
        readme = recipe / "README.md"
        readme.write_text(readme.read_text().replace("Level: `deploys`", f"Level: `deploys`\n\n{line}"))

    def test_parent_with_same_pins_passes(self):
        errors = self.errors()
        self.assertNotIn("RCP-47", errors)
        self.assertNotIn("RCP-48", errors)
        self.assertNotIn("RCP-54", errors)

    def test_included_recipe_that_includes_fails(self):
        init = self.tmp / "valkey" / "init.yml"
        init.write_text(init.read_text().replace("  - .valkey\n", "  - .valkey\n  - recipes.cert-manager\n"))
        self.assertIn("includes valkey, which includes cert-manager itself (RCP-47)", self.errors())

    def test_different_pins_fail(self):
        init = self.parent / "init.yml"
        init.write_text(re.sub(r"kubernetes:[0-9.]+@", "kubernetes:1.6.0@", init.read_text()))
        self.assertIn("lib/kubernetes is pinned at different sources", self.errors())

    def test_other_recipe_with_another_pin_fails(self):
        pin = re.search(r"ghcr\.io/kadet-hub/kubernetes:\S+", (self.tmp / "cert-manager/init.yml").read_text()).group(0)
        other = re.sub(r"kubernetes:[0-9.]+@", "kubernetes:1.6.0@", pin)
        init = self.tmp / "miniflux/init.yml"
        init.write_text(init.read_text().replace(pin, other))
        # lint lists the sources sorted as strings, whatever the version of the pin.
        listed = ", ".join(f"{s} ({n})" for s, n in sorted({other: "miniflux", pin: "cert-manager, valkey, valkeyparent"}.items()))
        self.assertIn(
            f"lib/kubernetes is pinned at different sources: {listed} (RCP-48)",
            self.errors(self.tmp / "cert-manager"),
        )

    def test_other_recipes_with_the_same_pin_pass(self):
        self.assertNotIn("RCP-48", self.errors(self.tmp / "cert-manager"))

    def test_recipe_alone_passes(self):
        init = self.tmp / "cert-manager/init.yml"
        init.write_text(re.sub(r"kubernetes:[0-9.]+@", "kubernetes:1.6.0@", init.read_text()))
        self.assertIn("RCP-48", self.errors(self.tmp / "cert-manager"))
        for name in ("valkey", "miniflux", "valkeyparent"):
            shutil.rmtree(self.tmp / name)
        self.assertNotIn("RCP-48", self.errors(self.tmp / "cert-manager"))

    def test_requires_entries(self):
        self.requires(self.parent, "Requires: `cert-manager`, `gateway-api`")
        self.assertNotIn("RCP-54", self.errors())
        self.requires(self.parent, "Requires: `nosuchrecipe`")
        self.assertIn("Requires nosuchrecipe, which is neither another recipe of this repository nor gateway-api (RCP-54)", self.errors())

    def test_requires_what_it_includes_fails(self):
        self.requires(self.parent, "Requires: `valkey`")
        self.assertIn("Requires valkey, which the recipe also includes (RCP-54)", self.errors())

    def test_malformed_requires_line_fails(self):
        self.requires(self.parent, "Requires: cert-manager")
        self.assertIn("the Requires line is not", self.errors())

    def test_cycle_through_prerequisites_fails(self):
        self.requires(self.parent, "Requires: `cert-manager`")
        self.requires(self.tmp / "cert-manager", "Requires: `miniflux`")
        self.requires(self.tmp / "miniflux", "Requires: `valkeyparent`")
        self.assertIn("requires itself through valkeyparent -> cert-manager -> miniflux -> valkeyparent (RCP-54)", self.errors())



class Meta(unittest.TestCase):
    """RCP-260, RCP-261: recipe.yaml of a copy of valkey, its keys and its match with the README."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.recipe = self.tmp / "valkey"
        shutil.copytree(RECIPE.parent / "valkey", self.recipe)
        self.meta = self.recipe / lint.META
        self.readme = self.recipe / "README.md"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def errors(self):
        return "\n".join(lint.lint_files(self.recipe))

    def edit(self, path, old, new):
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_valkey_passes(self):
        self.assertEqual(lint.lint_files(self.recipe), [])

    def test_missing_file_fails(self):
        self.meta.unlink()
        self.assertIn("recipe.yaml is missing (RCP-260)", self.errors())

    def test_keys(self):
        for text, error in [
            ("backends:\n  - omegaconf\n", "has the keys backends and required and no other (RCP-260)"),
            ("backends:\n  - omegaconf\nrequired: []\nlevel: deploys\n", "has the keys backends and required and no other"),
            ("backends:\n  - reclass\nrequired: []\n", "backends lists omegaconf and may list reclass and reclass-rs, each once"),
            ("backends:\n  - omegaconf\n  - kadet\nrequired: []\n", "backends lists omegaconf"),
            ("backends:\n  - omegaconf\n  - omegaconf\nrequired: []\n", "backends lists omegaconf"),
            ("backends:\n  - omegaconf\nrequired:\n  - path: applications.valkey.password\n    secret: true\n",
             "required[0] has path, description, secret and, for an option, option (RCP-260)"),
            ("backends:\n  - omegaconf\nrequired:\n  - path: applications..password\n    description: x\n    secret: true\n",
             "path applications..password is no dotted parameter path"),
            ("backends:\n  - omegaconf\nrequired:\n  - path: applications.valkey.password\n    description: x\n    secret: yes please\n",
             "required[0]: secret is true or false"),
            ("backends:\n  - omegaconf\nrequired:\n  - path: applications.valkey.password\n    description: \"a\\nb\"\n    secret: true\n",
             "description is one line of at most 300 characters"),
        ]:
            with self.subTest(text):
                self.meta.write_text(text)
                self.assertIn(error, self.errors())

    def test_anchor_fails(self):
        self.meta.write_text("backends: &b\n  - omegaconf\nrequired: []\nx: *b\n")
        self.assertIn("recipe.yaml:1: YAML anchor &b (RCP-4a)", self.errors())

    def test_path_the_readme_does_not_name_fails(self):
        self.edit(self.readme, "`applications.valkey.password` must be set", "The password must be set")
        self.assertIn("Required parameters does not name applications.valkey.password in backticks (RCP-261)", self.errors())

    def test_path_the_file_does_not_list_fails(self):
        self.meta.write_text("backends:\n  - omegaconf\nrequired: []\n")
        errors = self.errors()
        self.assertIn("Required parameters names applications.valkey.password, which recipe.yaml does not list (RCP-261)", errors)
        self.assertIn('says "No parameter has to be set." exactly when recipe.yaml lists no parameter (RCP-261)', errors)

    def test_secret_follows_the_snippet(self):
        self.edit(self.meta, "secret: true", "secret: false")
        self.assertIn("the Include snippet sets applications.valkey.password to <ref>, and recipe.yaml has secret: False (RCP-261)",
                      self.errors())

    def test_path_the_snippet_does_not_set_fails(self):
        self.edit(self.readme, "      password: <ref>\n", "      storage: 1Gi\n")
        self.assertIn("the Include snippet does not set applications.valkey.password (RCP-261)", self.errors())

    def test_option_the_snippet_does_not_include_fails(self):
        self.edit(self.meta, "    secret: true\n", "    secret: true\n    option: tls\n")
        self.assertIn("the Include snippet does not include recipes.valkey.tls (RCP-261)", self.errors())

    def test_no_class(self):
        self.assertNotIn(self.meta, lint.class_files(self.recipe))


if __name__ == "__main__":
    unittest.main()
