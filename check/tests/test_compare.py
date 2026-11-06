"""AC-2: the comparison on fixtures, without a cluster (RCP-9 to RCP-12)."""

import copy
import unittest
from pathlib import Path

import yaml

import compare

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return [o for o in yaml.safe_load_all((FIXTURES / name).read_text()) if o]


def find(objs, kind):
    return next(o for o in objs if o["kind"] == kind)


class Compare(unittest.TestCase):
    def setUp(self):
        self.chart, self.recipe = load("chart.yaml"), load("recipe.yaml")

    def run_compare(self):
        return compare.compare(self.chart, self.recipe)

    def unaccepted(self, result):
        return [str(d) for d in result["differences"] if not d.cls]

    def test_each_accepted_class(self):
        result = self.run_compare()
        self.assertEqual(self.unaccepted(result), [])
        self.assertEqual(result["selector_errors"], [])
        self.assertEqual((result["only_chart"], result["only_recipe"]), ([], []))
        found = {(d.cls, d.where()) for d in result["differences"]}
        for expected in [
            (compare.SELECTOR_SCHEME, "spec.selector.matchLabels.name"),
            (compare.SELECTOR_SCHEME, "spec.selector.name"),
            (compare.EXPLICIT_DEFAULT, "spec.template.spec.automountServiceAccountToken"),
            (compare.PORT_BY_NAME, "spec.ports[0].targetPort"),
            (compare.DERIVED_NAME, "spec.template.spec.containers[0].name"),
            (compare.DERIVED_NAME, "spec.template.spec.containers[0].ports"),
            (compare.DERIVED_NAME, "metadata.name"),
        ]:
            self.assertIn(expected, found)

    def test_dropped_label_fails(self):
        labels = find(self.recipe, "Deployment")["spec"]["template"]["metadata"]["labels"]
        del labels["sidecar.istio.io/inject"]
        self.assertEqual(
            self.unaccepted(self.run_compare()),
            [
                "NOT ACCEPTED: Deployment.apps/demo/demo spec.template.metadata.labels: "
                'chart {"sidecar.istio.io/inject": "false"}, recipe <unset>'
            ],
        )

    def test_unchanged_selector_that_no_longer_matches_fails(self):
        # The recipe keeps the chart's Service selector, but its pods carry
        # only the name label.
        find(self.recipe, "Service")["spec"]["selector"] = copy.deepcopy(find(self.chart, "Service")["spec"]["selector"])
        result = self.run_compare()
        self.assertEqual(
            result["selector_errors"],
            ["Service/demo/demo: selects [], the chart's ['Deployment.apps/demo/demo']"],
        )
        self.assertIn("NOT ACCEPTED", " ".join(map(str, result["differences"])))

    def test_workload_selector_that_misses_its_pods_fails(self):
        find(self.recipe, "Deployment")["spec"]["selector"]["matchLabels"]["name"] = "other"
        result = self.run_compare()
        self.assertIn("Deployment.apps/demo/demo: selector does not select its own pods", result["selector_errors"])
        self.assertTrue(self.unaccepted(result))

    def test_explicit_default_needs_the_service_account_default(self):
        find(self.chart, "ServiceAccount")["automountServiceAccountToken"] = False
        self.assertIn(
            "spec.template.spec.automountServiceAccountToken",
            " ".join(self.unaccepted(self.run_compare())),
        )

    def test_explicit_default_false_needs_the_service_account_false(self):
        for objs in (self.chart, self.recipe):
            find(objs, "ServiceAccount")["automountServiceAccountToken"] = False
        find(self.recipe, "Deployment")["spec"]["template"]["spec"]["automountServiceAccountToken"] = False
        found = {(d.cls, d.where()) for d in self.run_compare()["differences"]}
        self.assertIn((compare.EXPLICIT_DEFAULT, "spec.template.spec.automountServiceAccountToken"), found)
        find(self.chart, "ServiceAccount")["automountServiceAccountToken"] = True
        self.assertIn(
            "spec.template.spec.automountServiceAccountToken",
            " ".join(self.unaccepted(self.run_compare())),
        )

    def test_empty_container_security_context_is_an_explicit_default(self):
        container = find(self.recipe, "Deployment")["spec"]["template"]["spec"]["containers"][0]
        container["securityContext"] = {}
        find(self.chart, "Deployment")["spec"]["template"]["spec"]["containers"][0].pop("securityContext", None)
        found = {(d.cls, d.where()) for d in self.run_compare()["differences"]}
        self.assertIn((compare.EXPLICIT_DEFAULT, "spec.template.spec.containers[0].securityContext"), found)
        container["securityContext"] = {"runAsNonRoot": True}
        self.assertIn("containers[0].securityContext", " ".join(self.unaccepted(self.run_compare())))

    def test_certificate_rotation_policy_always_is_an_explicit_default(self):
        cert = {"apiVersion": "cert-manager.io/v1", "kind": "Certificate", "metadata": {"name": "demo", "namespace": "demo"},
                "spec": {"secretName": "demo-tls", "issuerRef": {"kind": "Issuer", "name": "demo"}}}
        recipe = copy.deepcopy(cert)
        recipe["spec"]["privateKey"] = {"rotationPolicy": "Always"}
        self.chart.append(cert)
        self.recipe.append(recipe)
        found = {(d.cls, d.where()) for d in self.run_compare()["differences"]}
        self.assertIn((compare.EXPLICIT_DEFAULT, "spec.privateKey"), found)
        cert["spec"]["privateKey"] = {"algorithm": "ECDSA"}
        recipe["spec"]["privateKey"]["algorithm"] = "ECDSA"
        found = {(d.cls, d.where()) for d in self.run_compare()["differences"]}
        self.assertIn((compare.EXPLICIT_DEFAULT, "spec.privateKey.rotationPolicy"), found)
        recipe["spec"]["privateKey"]["rotationPolicy"] = "Never"
        self.assertIn("spec.privateKey.rotationPolicy", " ".join(self.unaccepted(self.run_compare())))

    def test_port_by_name_must_resolve_to_the_same_port(self):
        find(self.chart, "Service")["spec"]["ports"][0]["targetPort"] = 10250
        self.assertIn("spec.ports[0].targetPort", " ".join(self.unaccepted(self.run_compare())))

    def test_derived_names_follow_the_generator(self):
        find(self.recipe, "Deployment")["spec"]["template"]["spec"]["containers"][0]["name"] = "other"
        find(self.recipe, "ValidatingWebhookConfiguration")["metadata"]["name"] = "other-demo-webhook"
        unaccepted = " ".join(self.unaccepted(self.run_compare()))
        self.assertIn("containers[0].name", unaccepted)
        self.assertIn("metadata.name", unaccepted)

    def test_job_labels_of_the_api_server(self):
        # A Job as a server-side dry run on kind returns it, one UID per side.
        def job(uid):
            generated = {"batch.kubernetes.io/controller-uid": uid, "batch.kubernetes.io/job-name": "demo-admin",
                         "controller-uid": uid, "job-name": "demo-admin"}
            return {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": "demo-admin", "namespace": "demo", "uid": uid},
                    "spec": {"selector": {"matchLabels": {"batch.kubernetes.io/controller-uid": uid}},
                             "template": {"metadata": {"labels": {"app.kubernetes.io/name": "demo", **generated}},
                                          "spec": {"containers": [{"name": "demo-admin", "image": "registry.example.org/demo:v1.0.0"}]}}}}

        chart, recipe = job("0750ca74-1829-4852-a622-0d607b323de5"), job("a27962b7-5d82-42e6-beb0-bb425bad1bb0")
        result = compare.compare([chart], [recipe])
        self.assertEqual(self.unaccepted(result), [])
        self.assertEqual(
            [(d.cls, d.where()) for d in result["differences"]],
            [(compare.SELECTOR_SCHEME, "spec.selector.matchLabels.batch.kubernetes.io/controller-uid")],
        )
        # A Job without labels of its own gets those of its pod template.
        chart["metadata"]["labels"] = dict(chart["spec"]["template"]["metadata"]["labels"])
        recipe["metadata"]["labels"] = {"name": "demo-admin"}
        self.assertEqual(self.unaccepted(compare.compare([chart], [recipe])), [])
        # A job-name label the Job sets itself stays.
        chart["metadata"]["labels"] = {"job-name": "demo-admin"}
        self.assertEqual(
            self.unaccepted(compare.compare([chart], [recipe])),
            ['NOT ACCEPTED: Job.batch/demo/demo-admin metadata.labels: chart {"job-name": "demo-admin"}, recipe <unset>'],
        )
        del chart["metadata"]["labels"]
        recipe["spec"]["template"]["metadata"]["labels"]["sidecar.istio.io/inject"] = "false"
        self.assertEqual(
            self.unaccepted(compare.compare([chart], [recipe])),
            ["NOT ACCEPTED: Job.batch/demo/demo-admin spec.template.metadata: "
             'chart <unset>, recipe {"labels": {"sidecar.istio.io/inject": "false"}}'],
        )

    def test_lost_group_role_binding_is_found(self):
        self.recipe = [o for o in self.recipe if o["kind"] != "RoleBinding"]
        subjects = compare.rbac_subjects(self.chart) | compare.rbac_subjects(self.recipe)
        self.assertEqual(subjects, {("Group", "", "demo-readers")})
        self.assertEqual(compare.rbac_namespaces(self.chart + self.recipe, subjects, "other"), {"demo"})
        # helm template leaves out a namespace the chart's template does not set.
        for o in self.chart:
            o["metadata"].pop("namespace", None)
        self.assertEqual(compare.rbac_namespaces(self.chart, subjects, "demo"), {"demo"})
        self.assertEqual(
            compare.impersonation(("Group", "", "demo-readers")),
            ["--as", "check-group-member", "--as-group", "demo-readers"],
        )
        # can-i --list in namespace demo, as the group on each side.
        chart_out = (
            "Resources   Non-Resource URLs   Resource Names   Verbs\n"
            "pods        []                  []               [watch list get]\n"
            "            [/api/*]            []               [get]\n"
        )
        recipe_out = "Resources   Non-Resource URLs   Resource Names   Verbs\n            [/api/*]            []               [get]\n"
        key = "Group demo-readers in demo"
        self.assertEqual(
            compare.diff_permissions(
                {key: compare.normalize_can_i(chart_out)}, {key: compare.normalize_can_i(recipe_out)}
            ),
            [f"{key}: only chart: pods [] [] [get list watch]"],
        )


class ReferencedSecret(unittest.TestCase):
    """RCP-243: a Secret only in the recipe that the chart side's pods read by name."""

    SECRET = "Secret/demo/demo-login"

    def setUp(self):
        self.chart, self.recipe = load("chart.yaml"), load("recipe.yaml")
        self.secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "demo-login", "namespace": "demo"},
            "type": "Opaque",
            "data": {"username": "", "password": ""},
        }
        self.recipe.append(self.secret)

    def pods(self, *sides):
        return [find(objs, "Deployment")["spec"]["template"]["spec"] for objs in sides]

    def read_keys(self, *sides, keys=("username", "password")):
        for pod in self.pods(*sides):
            pod["containers"][0]["env"] = [
                {"name": key.upper(), "valueFrom": {"secretKeyRef": {"name": "demo-login", "key": key}}} for key in keys
            ]

    def assertAccepted(self):
        result = compare.compare(self.chart, self.recipe)
        self.assertEqual(result["referenced_secrets"], [self.SECRET])
        self.assertEqual(result["only_recipe"], [])
        self.assertEqual([str(d) for d in result["differences"] if not d.cls], [])

    def assertDenied(self):
        result = compare.compare(self.chart, self.recipe)
        self.assertEqual(result["referenced_secrets"], [])
        self.assertEqual(result["only_recipe"], [self.SECRET])

    def test_secret_key_refs_with_exactly_their_keys(self):
        self.read_keys(self.chart, self.recipe)
        self.assertAccepted()

    def test_env_from_reads_every_key(self):
        for pod in self.pods(self.chart, self.recipe):
            pod["containers"][0]["envFrom"] = [{"secretRef": {"name": "demo-login"}}]
        self.assertAccepted()

    def test_secret_volume_reads_its_items(self):
        for pod in self.pods(self.chart, self.recipe):
            pod["volumes"] = [{
                "name": "login",
                "secret": {"secretName": "demo-login", "items": [{"key": "username", "path": "u"}, {"key": "password", "path": "p"}]},
            }]
        self.assertAccepted()

    def test_unreferenced_secret_fails(self):
        self.assertDenied()

    def test_extra_key_fails(self):
        self.read_keys(self.chart, self.recipe, keys=("password",))
        self.assertDenied()

    def test_missing_key_fails(self):
        self.read_keys(self.chart, self.recipe, keys=("username", "password", "totp"))
        self.assertDenied()

    def test_reference_on_the_recipe_side_only_fails(self):
        self.read_keys(self.recipe)
        self.assertDenied()

    def test_secret_in_another_namespace_fails(self):
        self.read_keys(self.chart, self.recipe)
        self.secret["metadata"]["namespace"] = "other"
        self.SECRET = "Secret/other/demo-login"
        self.assertDenied()

    def test_only_secrets(self):
        self.read_keys(self.chart, self.recipe)
        self.secret["kind"] = "ConfigMap"
        self.SECRET = "ConfigMap/demo/demo-login"
        self.assertDenied()


class Normalize(unittest.TestCase):
    def test_drops_exactly_the_listed_fields(self):
        chart, recipe = load("chart.yaml"), load("recipe.yaml")
        deploy = compare.normalize(find(chart, "Deployment"), "chart")
        self.assertNotIn("resourceVersion", deploy["metadata"])
        self.assertNotIn("labels", deploy["metadata"])
        self.assertNotIn("status", deploy)
        template = deploy["spec"]["template"]["metadata"]
        self.assertEqual(template["labels"], {"sidecar.istio.io/inject": "false"})
        self.assertEqual(template["annotations"], {"prometheus.io/port": "9402"})
        self.assertEqual(compare.normalize(find(chart, "ServiceAccount"), "chart")["metadata"], {"name": "demo", "namespace": "demo"})

    def test_drops_the_release_labels_of_strimzis_chart(self):
        labels = {"chart": "strimzi-kafka-operator-1.3.0", "release": "strimzi", "heritage": "Helm",
                  "component": "service-account", "strimzi.io/kind": "cluster-operator"}
        sa = {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "s", "labels": labels}}
        self.assertEqual(compare.normalize(sa, "chart")["metadata"]["labels"], {"strimzi.io/kind": "cluster-operator"})

    def test_digests_only_on_the_recipe_side(self):
        recipe = find(load("recipe.yaml"), "Deployment")
        container = compare.normalize(recipe, "recipe")["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["image"], "registry.example.org/demo:v1.0.0")
        self.assertEqual(container["args"], ["--solver-image=registry.example.org/solver:v1.0.0"])
        container = compare.normalize(recipe, "chart")["spec"]["template"]["spec"]["containers"][0]
        self.assertIn("@sha256:", container["image"])

    def test_secrets_by_key(self):
        secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "s"}, "data": {"password": "c2VjcmV0"}}
        self.assertEqual(compare.normalize(secret, "chart")["data"], {"password": ""})

    def test_can_i_sorts_verbs_and_lines(self):
        out = "Resources   Non-Resource URLs   Resource Names   Verbs\nsecrets   []   [ca]   [update get]\nevents   []   []   [patch create]\n"
        self.assertEqual(compare.normalize_can_i(out), ["events [] [] [create patch]", "secrets [] [ca] [get update]"])


if __name__ == "__main__":
    unittest.main()
