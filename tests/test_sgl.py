"""Tests for the runner, gates and hook. Run: python -m unittest discover -s tests"""

import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sgl import gates  # noqa: E402
from sgl.runner import PipelineError, load, run  # noqa: E402

PY = sys.executable


def pipeline(tmp: Path, body: str) -> Path:
    p = tmp / "pipeline.yaml"
    p.write_text(textwrap.dedent(body))
    return p


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.tmp = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    def test_all_pass(self):
        p = pipeline(self.tmp, f"""
            stages:
              - name: a
                run: echo hi > a.txt
                gates: ["test -s a.txt"]
              - name: b
                gates: ["true"]
        """)
        r = run(load(str(p)), quiet=True)
        self.assertTrue(r["ok"])
        self.assertEqual(r["passed"], ["a", "b"])

    def test_stops_at_first_failed_gate_and_never_runs_downstream(self):
        p = pipeline(self.tmp, """
            stages:
              - name: a
                gates: ["true"]
              - name: b
                gates:
                  - {name: must-fail, run: "echo broken; exit 1"}
              - name: c
                run: touch c-ran
        """)
        r = run(load(str(p)), quiet=True)
        self.assertFalse(r["ok"])
        self.assertEqual(r["stopped_at"], "b")
        self.assertIn("must-fail", r["feedback"])
        self.assertIn("broken", r["feedback"])
        self.assertFalse((self.tmp / "c-ran").exists(), "downstream stage must not run")

    def test_retry_gets_feedback_and_only_failed_stage_reruns(self):
        p = pipeline(self.tmp, f"""
            stages:
              - name: first
                run: echo x >> first-count
              - name: flaky
                retries: 2
                run: >-
                  {PY} -c "import os; open('flaky-count','a').write('x');
                  open('ok','w').write('1' if 'needs-fix' in os.environ['SGL_FEEDBACK'] else '0')"
                gates:
                  - {{name: check, run: "grep -q 1 ok || (echo needs-fix; exit 1)"}}
        """)
        r = run(load(str(p)), quiet=True)
        self.assertTrue(r["ok"])
        self.assertEqual((self.tmp / "first-count").read_text().count("x"), 1)
        self.assertEqual((self.tmp / "flaky-count").read_text(), "xx")

    def test_stage_command_failure_stops(self):
        p = pipeline(self.tmp, """
            stages:
              - name: a
                run: exit 3
                gates: ["touch gate-ran"]
        """)
        r = run(load(str(p)), quiet=True)
        self.assertFalse(r["ok"])
        self.assertIn("exit 3", r["feedback"])
        self.assertFalse((self.tmp / "gate-ran").exists())

    def test_resume_skips_passed_stages(self):
        p = pipeline(self.tmp, """
            stages:
              - name: a
                run: echo x >> a-count
              - name: b
                gates: ["test -f fixed"]
        """)
        self.assertFalse(run(load(str(p)), quiet=True)["ok"])
        (self.tmp / "fixed").touch()
        r = run(load(str(p)), resume=True, quiet=True)
        self.assertTrue(r["ok"])
        self.assertEqual((self.tmp / "a-count").read_text().count("x"), 1)
        self.assertFalse((self.tmp / ".sgl" / "pipeline.state.json").exists())

    def test_gates_only_skips_stage_commands(self):
        p = pipeline(self.tmp, """
            stages:
              - name: a
                run: touch ran
                gates: ["true"]
        """)
        self.assertTrue(run(load(str(p)), gates_only=True, quiet=True)["ok"])
        self.assertFalse((self.tmp / "ran").exists())

    def test_timeout_is_a_failure(self):
        p = pipeline(self.tmp, """
            stages:
              - name: a
                gates: [{name: slow, run: "sleep 5", timeout: 1}]
        """)
        r = run(load(str(p)), quiet=True)
        self.assertFalse(r["ok"])
        self.assertIn("timed out", r["feedback"])

    def test_log_is_jsonl(self):
        p = pipeline(self.tmp, "stages:\n  - name: a\n    gates: ['true']\n")
        r = run(load(str(p)), quiet=True)
        events = [json.loads(line)["event"] for line in Path(r["log"]).read_text().splitlines()]
        self.assertEqual(events, ["run_start", "gate", "run_end"])

    def test_invalid_pipelines(self):
        for body in ["{}", "stages: []", "stages:\n  - run: x\n",
                     "stages:\n  - name: a\n", "stages:\n  - name: a\n    gates: [{name: g}]\n",
                     "stages:\n  - {name: a, run: x}\n  - {name: a, run: y}\n"]:
            with self.assertRaises(PipelineError, msg=body):
                load(str(pipeline(self.tmp, body)))


def g(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = gates.main(list(argv))
    return code, buf.getvalue()


class GateTests(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.tmp = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    def f(self, name, text):
        p = self.tmp / name
        p.write_text(text)
        return str(p)

    def test_exists(self):
        self.assertEqual(g("exists", self.f("a", "hello"))[0], 0)
        self.assertEqual(g("exists", str(self.tmp / "nope"))[0], 1)
        self.assertEqual(g("exists", self.f("b", "hi"), "--min-bytes", "10")[0], 1)

    def test_no_pattern(self):
        p = self.f("p.md", "fine line\nbad — dash\n")
        code, out = g("no-pattern", p, "-p", "—")
        self.assertEqual(code, 1)
        self.assertIn(":2:", out)
        self.assertEqual(g("no-pattern", p, "-p", "delve")[0], 0)
        self.assertEqual(g("no-pattern", p, "-i", "-p", "FINE")[0], 1)

    def test_words_ignores_frontmatter(self):
        p = self.f("w.md", "---\ntitle: a b c d e f\n---\none two three\n")
        self.assertEqual(g("words", p, "--min", "3", "--max", "3")[0], 0)
        self.assertEqual(g("words", p, "--min", "4")[0], 1)

    def test_frontmatter(self):
        p = self.f("f.md", "---\ntitle: x\ndate: 2026-01-01\n---\nbody\n")
        self.assertEqual(g("frontmatter", p, "--require", "title,date")[0], 0)
        self.assertEqual(g("frontmatter", p, "--require", "title,description")[0], 1)
        self.assertEqual(g("frontmatter", self.f("n.md", "no fm"), "--require", "title")[0], 1)

    def test_schema(self):
        schema = self.f("s.json", json.dumps({
            "type": "object", "required": ["n", "tags"],
            "properties": {"n": {"type": "integer", "minimum": 1},
                           "tags": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                           "url": {"type": "string", "pattern": "^https://"}}}))
        good = self.f("g.json", json.dumps({"n": 2, "tags": ["a"], "url": "https://x"}))
        self.assertEqual(g("schema", good, "--schema", schema)[0], 0)
        for bad in [{"n": 0, "tags": ["a"]}, {"n": 2, "tags": []}, {"n": True, "tags": ["a"]},
                    {"n": 2, "tags": [1]}, {"tags": ["a"]}, {"n": 2, "tags": ["a"], "url": "http://x"}]:
            self.assertEqual(g("schema", self.f("b.json", json.dumps(bad)), "--schema", schema)[0], 1, bad)
        self.assertEqual(g("schema", self.f("j.json", "{not json"), "--schema", schema)[0], 1)

    def test_preflight_never_prints_env_values(self):
        with mock.patch.dict(os.environ, {"SGL_TEST_SECRET": "s3cr3t-value"}):
            code, out = g("preflight", "--cmd", "python3", "--env", "SGL_TEST_SECRET")
        self.assertEqual(code, 0)
        self.assertNotIn("s3cr3t-value", out)
        self.assertEqual(g("preflight", "--cmd", "definitely-not-a-cmd-xyz")[0], 1)
        self.assertEqual(g("preflight", "--env", "SGL_UNSET_VAR_XYZ")[0], 1)

    def test_cap(self):
        led = str(self.tmp / "ledger.tsv")
        for _ in range(2):
            self.assertEqual(g("cap", "--ledger", led, "--key", "k", "--max", "2", "--record")[0], 0)
        self.assertEqual(g("cap", "--ledger", led, "--key", "k", "--max", "2", "--record")[0], 1)
        self.assertEqual(g("cap", "--ledger", led, "--key", "other", "--max", "2")[0], 0)


class HookTests(unittest.TestCase):
    def _hook(self, pipeline_body, event):
        with tempfile.TemporaryDirectory() as d:
            p = pipeline(Path(d), pipeline_body)
            return subprocess.run([PY, "-m", "sgl", "hook", "claude-code", str(p)],
                                  input=json.dumps(event), capture_output=True, text=True,
                                  env={**os.environ, "PYTHONPATH": str(ROOT / "src")})

    def test_pass_allows_stop(self):
        r = self._hook("stages:\n  - name: a\n    gates: ['true']\n", {"stop_hook_active": False})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")

    def test_fail_blocks_stop_with_reason(self):
        r = self._hook("stages:\n  - name: tests\n    gates: ['echo 2 failed; exit 1']\n",
                       {"stop_hook_active": False})
        out = json.loads(r.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("2 failed", out["reason"])

    def test_bad_config_never_wedges_session(self):
        r = self._hook("stages: []\n", {})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
