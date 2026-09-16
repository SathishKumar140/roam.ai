"""
Skills Loader module conforming to the LangChain DeepAgents and Agent Skills Specification.
Handles progressive disclosure, YAML frontmatter parsing, validation, and subagent skill isolation.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, TypedDict
from langchain_core.tools import tool

MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024


class SkillMetadata(TypedDict, total=False):
    name: str
    description: str
    path: str
    parent_dir: str
    license: Optional[str]
    compatibility: Optional[str]
    metadata: Dict[str, str]
    allowed_tools: List[str]


def validate_skill_name(name: str, directory_name: str) -> tuple[bool, str]:
    """
    Validates skill name per Agent Skills specification:
    - 1-64 characters
    - Lowercase alphanumeric and hyphens only
    - Must not start/end with hyphen or contain '--'
    - Must match the parent folder name containing SKILL.md
    """
    if not name:
        return False, "Skill name is required"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, f"Skill name exceeds {MAX_SKILL_NAME_LENGTH} characters"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False, "Skill name must not start/end with hyphen or have consecutive hyphens"
    if not re.match(r"^[a-z0-9-]+$", name):
        return False, "Skill name must contain only lowercase alphanumeric characters and hyphens"
    if name != directory_name:
        return False, f"Skill name '{name}' must match directory name '{directory_name}'"
    return True, ""


def parse_skill_md(file_path: Path) -> Optional[SkillMetadata]:
    """
    Reads a SKILL.md file and extracts its YAML frontmatter and metadata.
    """
    if not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if not match:
        return None

    frontmatter_raw, _ = match.groups()
    try:
        fm = yaml.safe_load(frontmatter_raw)
        if not isinstance(fm, dict):
            return None
    except Exception:
        return None

    skill_name = str(fm.get("name", "")).strip()
    dir_name = file_path.parent.name

    is_valid, err = validate_skill_name(skill_name, dir_name)
    if not is_valid:
        return None

    allowed_tools = fm.get("allowed_tools", [])
    if isinstance(allowed_tools, str):
        allowed_tools = [t.strip() for t in allowed_tools.split(",") if t.strip()]
    elif not isinstance(allowed_tools, list):
        allowed_tools = []

    metadata = fm.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    return SkillMetadata(
        name=skill_name,
        description=str(fm.get("description", "")).strip(),
        path=str(file_path.resolve()),
        parent_dir=str(file_path.parent.resolve()),
        license=fm.get("license"),
        compatibility=fm.get("compatibility"),
        metadata={str(k): str(v) for k, v in metadata.items()},
        allowed_tools=[str(t) for t in allowed_tools]
    )


class SkillsLoader:
    """
    Loads skills from configured parent directory sources according to DeepAgents progressive disclosure.
    """

    @classmethod
    def load_skills_from_sources(cls, sources: List[str], base_dir: Optional[Path] = None) -> Dict[str, SkillMetadata]:
        """
        Scans a list of parent directories for child skill folders containing SKILL.md.
        Sources are loaded in order; later sources override earlier ones with the same skill name.
        """
        skills: Dict[str, SkillMetadata] = {}
        if base_dir is None:
            base_dir = Path.cwd()

        for source in sources:
            source_path = Path(source)
            if not source_path.is_absolute():
                source_path = (base_dir / source_path).resolve()

            if not source_path.is_dir():
                continue

            for child in sorted(source_path.iterdir()):
                if child.is_dir():
                    skill_file = child / "SKILL.md"
                    if skill_file.is_file():
                        meta = parse_skill_md(skill_file)
                        if meta:
                            skills[meta["name"]] = meta

        return skills

    @classmethod
    def format_skills_system_prompt(cls, skills: Dict[str, SkillMetadata], sources: List[str]) -> str:
        """
        Generates the progressive disclosure skills system prompt section.
        """
        if not skills:
            return ""

        sources_str = ", ".join(sources)
        skills_lines = []
        for name, meta in skills.items():
            line = f"- **`{name}`**: {meta['description']}\n  - Location: `{meta['path']}`"
            if meta.get("allowed_tools"):
                line += f"\n  - Recommended Tools: {', '.join(meta['allowed_tools'])}"
            if meta.get("compatibility"):
                line += f"\n  - Compatibility: {meta['compatibility']}"
            skills_lines.append(line)

        skills_list = "\n".join(skills_lines)

        return f"""
## 🧠 Skills System (Progressive Disclosure)

You have access to specialized domain skills loaded from: `{sources_str}`.
Skills follow a **progressive disclosure** pattern: you see their summary below, and can inspect their complete workflow instructions on demand when relevant.

**Available Skills:**
{skills_list}

**How to Use Skills:**
1. **Identify Relevant Skill**: Match incoming user requests to the skill descriptions above.
2. **Inspect Full Skill Instructions**: Call `read_skill_instructions(skill_name)` if you need the detailed multi-step workflow, decision tree, or edge cases.
3. **Execute Skill Workflow**: Follow the guidelines and invoke the associated tools.
"""

    @classmethod
    def read_skill_full_markdown(cls, skill_path: str) -> str:
        """
        Reads and returns the complete markdown content of a skill.
        """
        path = Path(skill_path)
        if not path.is_file():
            return f"Error: Skill file not found at {skill_path}"
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading skill file: {e}"

    @classmethod
    def create_skill_inspection_tool(cls, skills: Dict[str, SkillMetadata]):
        """
        Creates a LangChain tool allowing agents to view full skill workflows on demand.
        """
        @tool
        def read_skill_instructions(skill_name: str) -> str:
            """
            Reads the complete instructions, workflow steps, and guidelines for a specific skill.
            Use this when you need detailed domain instructions to execute a user's task.
            """
            if skill_name not in skills:
                available = ", ".join(skills.keys())
                return f"Error: Skill '{skill_name}' not found. Available skills: {available}"
            return cls.read_skill_full_markdown(skills[skill_name]["path"])

        return read_skill_instructions
