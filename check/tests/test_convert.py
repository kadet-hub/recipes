"""AC-142: kadet-convert without helm and without a cluster (docs/specs/converter.md)."""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml

import convert


def deployment(**pod):
    container = {"name": "web", "image": "example.org/web:1.0", "ports": [{"name": "http", "containerPort": 8080}],
                 "readinessProbe": {"httpGet": {"path": "/ready", "port": "http"}}}
    return {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "web", "namespace": "ns"},
            "spec": {"selector": {"matchLabels": {"app": "web"}},
                     "template": {"metadata": {"labels": {"app": "web"}}, "spec": {"containers": [container], **pod}}}}


def mapped(*objs):
    m = convert.Mapper("web", "ns")
    m.map(list(objs))
    return m


class Escape(unittest.TestCase):
    def test_resolver_or_backslashes(self):
        """CNV-7: ${escape:...} where it can emit the text, backslashes for a nested or unclosed ${."""
        self.assertEqual(convert.escape("a ${B:-x,y} c"), "a ${escape:'B:-x,y'} c")
        seven = "\\" * 7  # three escape passes: 0 backslashes become 1, 3, 7
        self.assertEqual(convert.escape("${ID_${INDEX}}"), f"{seven}${{ID_{seven}${{INDEX}}}}")

    def test_kapitan_reads_text_back(self):
        """CNV-7 with the Kapitan of the lock."""
        texts = {"plain": "echo ${HOME}", "nested": 'echo "(\\${ID_${INDEX}})"', "default": "${VAR:-x}",
                 "comma": "${VAR:-a,b}", "quotes": "${VAR:-'x' \"y\"}", "quote after backslash": "${a\\'b}",
                 "trailing backslash": "${VAR:-x\\}", "bash": "${#arr[@]} ${v//a/b}", "brace": "${a{b}",
                 "backslashes": "x \\\\${y}", "dollars": "$${x}", "unclosed": "echo ${", "two": "${A}${B}",
                 "none": "no interpolation \\d"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "inventory/classes").mkdir(parents=True)
            (root / "inventory/targets").mkdir(parents=True)
            (root / ".kapitan").write_text("global:\n  inventory-backend: omegaconf\n")
            (root / "inventory/classes/text.yml").write_text(yaml.safe_dump({"parameters": {"texts": convert.escape(texts)}}))
            (root / "inventory/targets/t.yml").write_text("classes:\n  - text\nparameters:\n  kapitan:\n    vars:\n      target: t\n")
            out = subprocess.run([str(Path(sys.executable).parent / "kapitan"), "inventory", "-t", "t"], cwd=root,
                                 capture_output=True, text=True, check=True).stdout
        self.assertEqual(yaml.safe_load(out)["parameters"]["texts"], texts)


class Render(unittest.TestCase):
    def test_generated_fields(self):
        """CNV-3: a field that differs between two renders is reported, an equal one is not."""
        first = [{"kind": "Secret", "metadata": {"name": "s"}, "data": {"password": "YQ==", "user": "dQ=="}}]
        second = [{"kind": "Secret", "metadata": {"name": "s"}, "data": {"password": "Yg==", "user": "dQ=="}}]
        self.assertEqual(convert.generated(first, second), ["Secret/s data.password"])


class Mapping(unittest.TestCase):
    def test_api_defaults(self):
        """CNV-6: the API's defaults where the chart leaves fields unset."""
        sa = {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "web"}}
        svc = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "web"},
               "spec": {"selector": {"app": "web"}, "ports": [{"name": "http", "port": 80, "targetPort": "http"}]}}
        latest = deployment()
        latest["spec"]["template"]["spec"]["containers"][0]["image"] = "example.org/web"
        m = mapped(latest, sa, svc)
        web = m.p["components"]["web"]
        self.assertEqual(web["healthcheck"]["readiness"]["timeout_seconds"], 1)
        self.assertIs(web["automount_service_account_token"], True)
        self.assertEqual(web["pull_policy"], "Always")
        kubernetes = m.p["generators"]["kubernetes"]
        self.assertIs(kubernetes["service_accounts"]["web"]["service_account"]["automount_service_account_token"], True)
        self.assertEqual(kubernetes["services"]["web"]["ports"]["http"]["app_protocol"], "")

    def test_not_mappable_fields(self):
        """CNV-5: the keys of generator 1.15.0 are mapped, an empty value that it leaves out is not mappable."""
        sts = deployment(shareProcessNamespace=True, affinity={}, tolerations=[{"operator": "Exists"}])
        sts["kind"] = "StatefulSet"
        sts["spec"]["serviceName"] = "web"
        self.assertNotIn("statefulset_service_name", mapped(sts).p["components"]["web"])
        sts["spec"]["serviceName"] = "other"
        sts["spec"]["template"]["spec"]["containers"][0].update(workingDir="/srv", lifecycle={}, command=[])
        sts["spec"]["template"]["spec"]["containers"][0]["ports"] += [
            {"containerPort": 9090}, {"containerPort": 9090, "protocol": "UDP"}, {"containerPort": 8080}, {"name": "port-8080", "containerPort": 8081}]
        self.assertNotIn("volume_claim_name_label", mapped(sts).p["components"]["web"])
        sts["spec"]["volumeClaimTemplates"] = [{"metadata": {"name": "data"}, "spec": {"accessModes": ["ReadWriteOnce"]}}]
        svc = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "web"},
               "spec": {"selector": {"app": "web"}, "ipFamilyPolicy": "PreferDualStack", "ipFamilies": ["IPv4"],
                        "ports": [{"port": 80}]}}
        m = mapped(sts, svc)
        web = m.p["components"]["web"]
        self.assertEqual(web["statefulset_service_name"], "other")
        self.assertIs(web["volume_claim_name_label"], False)
        self.assertEqual((web["working_dir"], web["share_process_namespace"]), ("/srv", True))
        self.assertEqual(web["ports"]["port-9090"], {"container_port": 9090, "unnamed": True})
        self.assertEqual(web["ports"]["port-9090-udp"], {"container_port": 9090, "protocol": "UDP", "unnamed": True})
        self.assertEqual(web["tolerations"], [{"operator": "Exists"}])
        self.assertFalse({"affinity", "lifecycle", "command"} & set(web))
        services = m.p["generators"]["kubernetes"]["services"]
        self.assertEqual((services["web"]["ip_family_policy"], services["web"]["ip_families"]), ("PreferDualStack", ["IPv4"]))
        self.assertEqual(sorted(m.not_mappable["StatefulSet/ns/web"]), [
            "spec.template.spec.affinity: {}",
            "spec.template.spec.containers[web].command: []",
            "spec.template.spec.containers[web].lifecycle: {}",
            "spec.template.spec.containers[web].ports[port-8080] more than once",
        ])
        self.assertEqual(m.not_mappable["Service/web"], ["spec.ports[80] without name"])

    def test_unmapped_kind(self):
        """CNV-4"""
        pdb = {"apiVersion": "policy/v1", "kind": "PodDisruptionBudget", "metadata": {"name": "web"}, "spec": {}}
        self.assertEqual(mapped(pdb).rows, [("PodDisruptionBudget/web", "", False, "the converter does not map PodDisruptionBudget")])

    def test_rbac(self):
        """CNV-8: the binding joins its role's entry, `:` becomes `-`."""
        role = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "ClusterRole", "metadata": {"name": "web:view"},
                "rules": [{"apiGroups": [""], "resources": ["pods"], "verbs": ["get"]}]}
        binding = {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "ClusterRoleBinding", "metadata": {"name": "web:view"},
                   "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole", "name": "web:view"},
                   "subjects": [{"kind": "ServiceAccount", "name": "web", "namespace": "ns"}]}
        m = mapped(role, binding)
        self.assertEqual(m.p["generators"]["kubernetes"]["rbac"], {"web-view": {
            "rules": role["rules"], "service_accounts": ["ns/web"], "cluster_wide": True}})
        self.assertEqual(m.renamed, [("web:view", "web-view")])


class Output(unittest.TestCase):
    def write(self, *objs, crds=()):
        m = mapped(*objs)
        self.tmp = tempfile.TemporaryDirectory()
        project = Path(self.tmp.name)
        classes = convert.write_project(project, "web", "ns", m, list(crds))
        return project, classes

    def tearDown(self):
        self.tmp.cleanup()

    def test_secret_data(self):
        """CNV-10: data only in the git-ignored secrets class, interpolated into the converted class."""
        secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "web"}, "data": {"tls.key": "c2VjcmV0"}}
        project, classes = self.write(secret)
        self.assertNotIn("c2VjcmV0", (classes / "init.yml").read_text())
        init = yaml.safe_load((classes / "init.yml").read_text())["parameters"]
        self.assertEqual(init["generators"]["kubernetes"]["secrets"]["web"]["data"]["tls.key"],
                         {"value": "${applications.web.secrets.web__tls_key}", "b64_encode": False})
        secrets = yaml.safe_load((classes / "secrets.yml").read_text())["parameters"]
        self.assertEqual(secrets, {"applications": {"web": {"secrets": {"web__tls_key": "c2VjcmV0"}}}})
        self.assertEqual((project / ".gitignore").read_text(), "inventory/classes/converted/web/secrets.yml\n")
        target = yaml.safe_load((project / "inventory/targets/web.yml").read_text())
        self.assertEqual(target["classes"], ["converted.web", "converted.web.secrets"])

    def test_crds(self):
        """CNV-9: one vendored file per CRD, compiled by a copy entry."""
        crd = {"apiVersion": "apiextensions.k8s.io/v1", "kind": "CustomResourceDefinition", "metadata": {"name": "a.example.org"}}
        _, classes = self.write(deployment(), crds=[crd])
        self.assertEqual(yaml.safe_load((classes / "vendor/a.example.org.yaml").read_text()), crd)
        compile_entries = yaml.safe_load((classes / "init.yml").read_text())["parameters"]["kapitan"]["compile"]
        self.assertIn({"input_type": "copy", "input_paths": ["inventory/classes/converted/web/vendor/a.example.org.yaml"],
                       "output_path": "crds/"}, compile_entries)


class ValueMap(unittest.TestCase):
    def test_classes(self):
        """CNV-12"""
        values = {"replicas": 2, "image": {"tag": "1.0"}, "metrics": {"enabled": False, "port": 9090}}
        leaf = ("leaf", ("components", "web", "replicas"), 2, 7921)
        embedded = ("leaf", ("components", "web", "image"), "example.org/web:1.0", "example.org/web:1.0zq9")
        added = ("structural", ("components", "web", "ports", "metrics"), None, {"container_port": 9090})
        other = ("leaf", ("components", "web", "args", 0), "--x=1", "--y")
        self.assertEqual(convert.classify(values, ("replicas",), 2, [leaf]), "reached")
        self.assertEqual(convert.classify(values, ("image", "tag"), "1.0", [embedded]), "reached")
        self.assertEqual(convert.classify(values, ("metrics", "enabled"), False, [added]), "switch")
        self.assertEqual(convert.classify(values, ("metrics", "port"), 9090, []), "no effect, below a switch that is off")
        self.assertEqual(convert.classify(values, ("replicas",), 2, []), "no effect")
        self.assertEqual(convert.classify(values, ("image", "tag"), "1.0", [other]), "derived")


class Cli(unittest.TestCase):
    ARGS = ("oauth2-proxy", "--repo", "https://charts.example.org", "--version", "1.0.0",
            "--name", "oauth2-proxy", "--namespace", "ns", "--out")

    def main(self, out, existing=False):
        """convert.main in a new directory, with every command it runs failing; returns status, stderr, commands."""
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp), contextlib.redirect_stderr(err), \
                unittest.mock.patch.object(convert.check, "run", side_effect=convert.check.Failed("stub")) as run:
            if existing:
                Path(out).mkdir()
            try:
                status = convert.main([*self.ARGS, out])
            except SystemExit as e:
                status = f"exit {e.code}"
            created = Path(out).exists()
        return status, err.getvalue(), [c.args[0] for c in run.call_args_list], created

    def test_out_named_like_the_chart(self):
        """CNV-20: an --out that names a repository chart is rejected before it is created or a command runs."""
        for existing in (False, True):
            with self.subTest(existing=existing):
                status, err, commands, created = self.main("oauth2-proxy", existing)
                self.assertEqual((status, commands, created), ("exit 2", [], existing))
                self.assertIn("--out oauth2-proxy", err)
        status, _, commands, created = self.main("converted")
        self.assertEqual((status, commands[0][:3], created), (2, ["helm", "pull", "oauth2-proxy"], True))


if __name__ == "__main__":
    unittest.main()
