"""评估 workspace 初始化工具。"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ZERO_METRIC_TEMPLATE = {
    "pass_rate": {"mean": 0.0, "stddev": 0.0},
    "time_seconds": {"mean": 0.0, "stddev": 0.0},
    "tokens": {"mean": 0.0, "stddev": 0.0},
}

SNAPSHOT_IGNORE_NAMES = {
    ".git",
    ".venv",
    ".local",
    "node_modules",
    "__pycache__",
}


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: int
    slug: str
    prompt: str
    expected_output: str
    files: tuple[str, ...]
    assertions: tuple[str, ...]

    @property
    def case_dir_name(self) -> str:
        return f"eval-{self.slug}"


@dataclass(frozen=True, slots=True)
class EvalConfig:
    skill_name: str
    evals: tuple[EvalCase, ...]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="初始化 agentskills 风格的评估 workspace")
    parser.add_argument("--workspace", required=True, help="评估 workspace 根目录路径")
    parser.add_argument("--iteration", default="1", help="迭代编号，默认 1")
    parser.add_argument("--baseline", choices=("without_skill", "old_skill"), default="without_skill")
    parser.add_argument("--evals-file", help="evals.json 路径；默认使用仓库下 evals/evals.json")
    parser.add_argument("--skill-path", help="skill 根目录；默认自动推断为当前仓库根目录")
    parser.add_argument("--force", action="store_true", help="允许覆盖已生成的说明与模板文件")
    parser.add_argument(
        "--snapshot-old-skill",
        action="store_true",
        help="当 baseline=old_skill 时，把当前 skill 快照复制到 workspace/skill-snapshot",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    skill_root = resolve_skill_root(args.skill_path)
    evals_path = Path(args.evals_file).expanduser().resolve() if args.evals_file else skill_root / "evals" / "evals.json"
    workspace_root = Path(args.workspace).expanduser().resolve()
    iteration_number = parse_positive_int(args.iteration, "--iteration")
    config = load_eval_config(evals_path)

    if config.skill_name != skill_root.name:
        raise RuntimeError(
            f"evals.json 中的 skill_name={config.skill_name} 与目录名 {skill_root.name} 不一致。"
        )

    snapshot_path = None
    if args.baseline == "old_skill" and args.snapshot_old_skill:
        snapshot_path = snapshot_skill(skill_root, workspace_root, force=args.force)

    initialize_workspace(
        workspace_root=workspace_root,
        iteration_number=iteration_number,
        config=config,
        skill_root=skill_root,
        baseline=args.baseline,
        force=args.force,
        snapshot_path=snapshot_path,
    )

    print(render_summary(workspace_root, iteration_number, config, args.baseline, snapshot_path))
    return 0


def resolve_skill_root(skill_path: str | None) -> Path:
    if skill_path:
        return Path(skill_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def parse_positive_int(raw_value: str, option_name: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{option_name} 必须是大于 0 的整数。") from error
    if value <= 0:
        raise RuntimeError(f"{option_name} 必须是大于 0 的整数。")
    return value


def load_eval_config(evals_path: Path) -> EvalConfig:
    try:
        payload = json.loads(evals_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"未找到 evals.json：{evals_path}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"evals.json 不是合法 JSON：{error}") from error

    skill_name = normalize_required_string(payload.get("skill_name"), "skill_name")
    raw_evals = payload.get("evals")
    if not isinstance(raw_evals, list) or not raw_evals:
        raise RuntimeError("evals.json 必须包含非空的 evals 数组。")

    cases: list[EvalCase] = []
    seen_slugs: set[str] = set()
    for index, row in enumerate(raw_evals, start=1):
        if not isinstance(row, dict):
            raise RuntimeError(f"evals[{index}] 必须是对象。")
        slug = normalize_required_string(row.get("slug"), f"evals[{index}].slug")
        if slug in seen_slugs:
            raise RuntimeError(f"eval slug 重复：{slug}")
        seen_slugs.add(slug)
        files = tuple(normalize_string_list(row.get("files"), f"evals[{index}].files"))
        assertions = tuple(normalize_string_list(row.get("assertions"), f"evals[{index}].assertions"))
        cases.append(
            EvalCase(
                id=parse_required_int(row.get("id"), f"evals[{index}].id"),
                slug=slug,
                prompt=normalize_required_string(row.get("prompt"), f"evals[{index}].prompt"),
                expected_output=normalize_required_string(
                    row.get("expected_output"), f"evals[{index}].expected_output"
                ),
                files=files,
                assertions=assertions,
            )
        )
    return EvalConfig(skill_name=skill_name, evals=tuple(cases))


def parse_required_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise RuntimeError(f"{field_name} 必须是整数。")
    if isinstance(value, int):
        return value
    raise RuntimeError(f"{field_name} 必须是整数。")


def normalize_required_string(value: Any, field_name: str) -> str:
    normalized = str(value).strip() if value is not None else ""
    if not normalized:
        raise RuntimeError(f"{field_name} 不能为空。")
    return normalized


def normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuntimeError(f"{field_name} 必须是字符串数组。")
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        result.append(normalize_required_string(item, f"{field_name}[{index}]") )
    return result


def initialize_workspace(
    *,
    workspace_root: Path,
    iteration_number: int,
    config: EvalConfig,
    skill_root: Path,
    baseline: str,
    force: bool,
    snapshot_path: Path | None,
) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    iteration_dir = workspace_root / f"iteration-{iteration_number}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    write_text_file(
        iteration_dir / "README.md",
        render_iteration_readme(iteration_number, config, baseline, skill_root, workspace_root, snapshot_path),
        force=force,
    )
    write_json_file(iteration_dir / "benchmark.json", create_benchmark_payload(baseline), force=force)
    write_json_file(iteration_dir / "feedback.json", create_feedback_payload(config), force=force)

    for case in config.evals:
        case_dir = iteration_dir / case.case_dir_name
        case_dir.mkdir(parents=True, exist_ok=True)
        write_text_file(case_dir / "README.md", render_case_readme(case, baseline), force=force)

        write_run_bundle(
            case=case,
            config_name="with_skill",
            skill_root=skill_root,
            case_dir=case_dir,
            workspace_root=workspace_root,
            iteration_number=iteration_number,
            baseline=baseline,
            snapshot_path=snapshot_path,
            force=force,
        )
        write_run_bundle(
            case=case,
            config_name=baseline,
            skill_root=skill_root,
            case_dir=case_dir,
            workspace_root=workspace_root,
            iteration_number=iteration_number,
            baseline=baseline,
            snapshot_path=snapshot_path,
            force=force,
        )


def write_run_bundle(
    *,
    case: EvalCase,
    config_name: str,
    skill_root: Path,
    case_dir: Path,
    workspace_root: Path,
    iteration_number: int,
    baseline: str,
    snapshot_path: Path | None,
    force: bool,
) -> None:
    run_dir = case_dir / config_name
    outputs_dir = run_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    write_text_file(
        outputs_dir / ".gitkeep",
        "",
        force=force,
    )
    write_text_file(
        run_dir / "task.md",
        render_task_instructions(
            case=case,
            config_name=config_name,
            skill_root=skill_root,
            workspace_root=workspace_root,
            iteration_number=iteration_number,
            baseline=baseline,
            snapshot_path=snapshot_path,
        ),
        force=force,
    )


def write_text_file(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json_file(path: Path, payload: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_benchmark_payload(baseline: str) -> dict[str, Any]:
    return {
        "run_summary": {
            "with_skill": dict(ZERO_METRIC_TEMPLATE),
            baseline: dict(ZERO_METRIC_TEMPLATE),
            "delta": {"pass_rate": 0.0, "time_seconds": 0.0, "tokens": 0.0},
        }
    }


def create_feedback_payload(config: EvalConfig) -> dict[str, str]:
    return {case.case_dir_name: "" for case in config.evals}


def render_iteration_readme(
    iteration_number: int,
    config: EvalConfig,
    baseline: str,
    skill_root: Path,
    workspace_root: Path,
    snapshot_path: Path | None,
) -> str:
    lines = [
        f"# Iteration {iteration_number}",
        "",
        "这个目录由 `scripts/setup-evals` 自动生成，用于执行一整轮 agentskills 风格评估。",
        "",
        f"- Skill: `{config.skill_name}`",
        f"- Skill path: `{skill_root}`",
        f"- Workspace: `{workspace_root}`",
        f"- Baseline: `{baseline}`",
    ]
    if snapshot_path is not None:
        lines.append(f"- Old skill snapshot: `{snapshot_path}`")
    lines.extend(
        [
            "",
            "## Cases",
            "",
        ]
    )
    for case in config.evals:
        lines.append(f"- `{case.case_dir_name}`: {case.expected_output}")
    lines.extend(
        [
            "",
            "每个 case 目录下都已经生成了 `with_skill/task.md` 和基线配置的 `task.md`，可直接复制给评估 agent 运行。",
        ]
    )
    return "\n".join(lines) + "\n"


def render_case_readme(case: EvalCase, baseline: str) -> str:
    lines = [
        f"# {case.case_dir_name}",
        "",
        f"- Eval ID: `{case.id}`",
        f"- Prompt: `{case.prompt}`",
        f"- Expected output: {case.expected_output}",
        f"- Baseline config: `{baseline}`",
    ]
    if case.files:
        lines.append(f"- Input files: {', '.join(case.files)}")
    if case.assertions:
        lines.extend(["", "## Assertions", ""])
        for assertion in case.assertions:
            lines.append(f"- {assertion}")
    return "\n".join(lines) + "\n"


def render_task_instructions(
    *,
    case: EvalCase,
    config_name: str,
    skill_root: Path,
    workspace_root: Path,
    iteration_number: int,
    baseline: str,
    snapshot_path: Path | None,
) -> str:
    case_output_dir = workspace_root / f"iteration-{iteration_number}" / case.case_dir_name / config_name / "outputs"
    timing_path = workspace_root / f"iteration-{iteration_number}" / case.case_dir_name / config_name / "timing.json"
    mode_line = render_skill_path_line(config_name, skill_root, baseline, snapshot_path)
    lines = [
        "执行这个任务。",
        "",
    ]
    if mode_line:
        lines.append(mode_line)
    lines.extend(
        [
            f"- Task: {case.prompt}",
            f"- Save outputs to: {case_output_dir}",
        ]
    )
    if case.files:
        lines.append(f"- Input files: {', '.join(case.files)}")
    lines.extend(
        [
            "",
            "要求：",
            "- 在干净上下文中运行",
            "- 把最终回答原文保存到 outputs/response.md",
            f"- 记录 total_tokens 和 duration_ms 到 {timing_path}",
        ]
    )
    if config_name == "without_skill":
        lines.append("- 不提供任何 skill")
    if config_name == "old_skill":
        lines.append("- 使用旧版 skill 快照作为基线")
    return "\n".join(lines) + "\n"


def render_skill_path_line(config_name: str, skill_root: Path, baseline: str, snapshot_path: Path | None) -> str | None:
    if config_name == "with_skill":
        return f"- Skill path: {skill_root}"
    if config_name == "old_skill":
        if snapshot_path is None:
            return "- Skill path: <请先提供旧版 skill 快照路径，或使用 --snapshot-old-skill 自动生成>"
        return f"- Skill path: {snapshot_path}"
    if baseline == "without_skill":
        return None
    return None


def snapshot_skill(skill_root: Path, workspace_root: Path, *, force: bool) -> Path:
    snapshot_path = workspace_root / "skill-snapshot"
    if snapshot_path.exists():
        if not force:
            return snapshot_path
        shutil.rmtree(snapshot_path)
    shutil.copytree(skill_root, snapshot_path, ignore=ignore_snapshot_entries)
    return snapshot_path


def ignore_snapshot_entries(_: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in SNAPSHOT_IGNORE_NAMES}
    ignored.update({name for name in names if name.endswith(".pyc")})
    return ignored


def render_summary(
    workspace_root: Path,
    iteration_number: int,
    config: EvalConfig,
    baseline: str,
    snapshot_path: Path | None,
) -> str:
    lines = [
        f"评估 workspace 已初始化：{workspace_root / f'iteration-{iteration_number}'}",
        f"用例数量：{len(config.evals)}",
        f"基线配置：{baseline}",
    ]
    if snapshot_path is not None:
        lines.append(f"旧版快照：{snapshot_path}")
    lines.append("已生成每个 case 的 task.md，可直接用于 with_skill / baseline 对照运行。")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
