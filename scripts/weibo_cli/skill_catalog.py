"""Skill 发现与输出。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SkillDefinition:
    name: str
    description: str
    location: str
    directory: str
    title: str
    body: str
    raw_content: str
    compatibility: str | None


def discover_skill_files(repo_root: Path) -> list[Path]:
    skill_files: list[Path] = []
    root_skill = repo_root / "SKILL.md"
    if root_skill.exists():
        skill_files.append(root_skill)

    search_roots = [repo_root / ".agents" / "skills"]
    if not root_skill.exists():
        search_roots.insert(0, repo_root / "skills")

    for root in search_roots:
        if not root.exists():
            continue
        for child in root.iterdir():
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                skill_files.append(skill_md)
    return sorted({path.resolve() for path in skill_files})


def parse_frontmatter(raw_content: str) -> tuple[dict[str, str], str]:
    if not raw_content.startswith("---"):
        raise RuntimeError("SKILL.md 缺少有效的 YAML frontmatter。")
    parts = raw_content.split("---", 2)
    if len(parts) < 3:
        raise RuntimeError("SKILL.md frontmatter 未正确闭合。")
    metadata_block = parts[1].strip("\r\n")
    body = parts[2].lstrip("\r\n")
    metadata: dict[str, Any] = {}
    current_map: dict[str, str] | None = None
    current_key: str | None = None
    for line in metadata_block.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and current_map is not None and current_key == "metadata":
            key, value = [part.strip() for part in line.strip().split(":", 1)]
            current_map[key] = value.strip().strip('"')
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        if key == "metadata":
            metadata[key] = {}
            current_map = metadata[key]
            current_key = key
            continue
        metadata[key] = value.strip().strip('"')
        current_map = None
        current_key = key
    return metadata, body


def validate_skill(skill_path: Path, metadata: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    directory_name = skill_path.parent.name
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not name:
        errors.append("frontmatter 必须包含非空字符串字段 name")
    elif skill_path.parent != repo_root and name != directory_name:
        errors.append(f"name 必须与父目录同名，当前目录为 {directory_name}")
    if not description:
        errors.append("frontmatter 必须包含非空字符串字段 description")
    return errors


def load_skills(repo_root: Path) -> tuple[list[SkillDefinition], list[tuple[str, list[str]]]]:
    skills: list[SkillDefinition] = []
    issues: list[tuple[str, list[str]]] = []
    for skill_path in discover_skill_files(repo_root):
        raw_content = skill_path.read_text(encoding="utf-8")
        try:
            metadata, body = parse_frontmatter(raw_content)
            errors = validate_skill(skill_path, metadata, repo_root)
            if errors:
                issues.append((str(skill_path), errors))
                continue
            title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), metadata["name"])
            skills.append(
                SkillDefinition(
                    name=str(metadata["name"]),
                    description=str(metadata["description"]),
                    location=str(skill_path),
                    directory=str(skill_path.parent),
                    title=title,
                    body=body.strip(),
                    raw_content=raw_content,
                    compatibility=str(metadata.get("compatibility") or "") or None,
                )
            )
        except Exception as error:  # noqa: BLE001
            issues.append((str(skill_path), [str(error)]))
    return sorted(skills, key=lambda item: item.name), issues


def format_skill_list(skills: list[SkillDefinition]) -> str:
    if not skills:
        return "当前仓库没有可用的 skills。\n"
    lines = ["可用 skills:"]
    for skill in skills:
        lines.append(f"- {skill.name}: {skill.title}")
        lines.append(f"  {skill.description}")
        lines.append(f"  位置: {skill.location}")
        if skill.compatibility:
            lines.append(f"  兼容性: {skill.compatibility}")
    return "\n".join(lines) + "\n"


def format_skill_document(skill: SkillDefinition) -> str:
    return f"# {skill.name}\n位置: {skill.location}\n\n{skill.raw_content.rstrip()}\n"


def format_skill_prompt_xml(skills: list[SkillDefinition]) -> str:
    if not skills:
        return "<available_skills>\n</available_skills>\n"
    lines = ["<available_skills>"]
    for skill in skills:
        lines.extend([
            "<skill>",
            "<name>",
            escape_xml(skill.name),
            "</name>",
            "<description>",
            escape_xml(skill.description),
            "</description>",
            "<location>",
            escape_xml(skill.location),
            "</location>",
            "</skill>",
        ])
    lines.append("</available_skills>")
    return "\n".join(lines) + "\n"


def format_skill_validation(issues: list[tuple[str, list[str]]]) -> str:
    if not issues:
        return "所有 skills 均通过校验。\n"
    lines = ["skills 校验失败:"]
    for skill_path, messages in issues:
        lines.append(f"- {skill_path}")
        for message in messages:
            lines.append(f"  - {message}")
    return "\n".join(lines) + "\n"


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )