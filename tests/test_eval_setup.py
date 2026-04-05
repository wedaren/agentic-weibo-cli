"""评估 workspace 初始化测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from weibo_cli.eval_setup import initialize_workspace, load_eval_config


class EvalSetupTests(unittest.TestCase):
    def test_initialize_workspace_creates_case_structure_and_tasks(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        config = load_eval_config(repo_root / "evals" / "evals.json")

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir) / "agentic-weibo-cli-workspace"
            initialize_workspace(
                workspace_root=workspace_root,
                iteration_number=1,
                config=config,
                skill_root=repo_root,
                baseline="without_skill",
                force=False,
                snapshot_path=None,
            )

            iteration_dir = workspace_root / "iteration-1"
            self.assertTrue((iteration_dir / "benchmark.json").exists())
            self.assertTrue((iteration_dir / "feedback.json").exists())
            self.assertTrue((iteration_dir / "eval-login-guidance" / "with_skill" / "task.md").exists())
            self.assertTrue((iteration_dir / "eval-login-guidance" / "without_skill" / "task.md").exists())

            feedback = json.loads((iteration_dir / "feedback.json").read_text(encoding="utf-8"))
            self.assertIn("eval-login-guidance", feedback)
            self.assertIn("eval-list-recent-weibos", feedback)
            self.assertIn("eval-inspect-reposts", feedback)

            with_skill_task = (iteration_dir / "eval-inspect-reposts" / "with_skill" / "task.md").read_text(encoding="utf-8")
            without_skill_task = (iteration_dir / "eval-inspect-reposts" / "without_skill" / "task.md").read_text(encoding="utf-8")
            self.assertIn("- Skill path:", with_skill_task)
            self.assertIn("Save outputs to:", with_skill_task)
            self.assertIn("不提供任何 skill", without_skill_task)


if __name__ == "__main__":
    unittest.main()
