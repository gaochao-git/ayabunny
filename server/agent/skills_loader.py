"""
Agent Skills 加载器

实现渐进加载模式：
1. 启动时只加载技能元数据（SKILL.md 的前几行）
2. LLM 判断需要时调用 load_skill 工具加载完整内容
3. 动态将技能信息注入到系统提示词

参考：https://agentskills.io/
"""

import os
import re
from dataclasses import dataclass
from typing import Optional
from config import get_settings

settings = get_settings()


@dataclass
class SkillMetadata:
    """技能元数据（轻量级，启动时加载）"""
    id: str
    name: str
    version: str
    icon: str
    keywords: list[str]
    triggers: list[str]  # 触发条件摘要
    tools: list[str]     # 可用工具名
    path: str            # SKILL.md 文件路径
    content_dir: str = "stories"  # 内容目录名称，默认 stories


@dataclass
class SkillContent:
    """技能完整内容（按需加载）"""
    metadata: SkillMetadata
    full_content: str    # SKILL.md 完整内容
    loaded: bool = True


# 全局技能注册表
_skill_registry: dict[str, SkillMetadata] = {}
_skill_content_cache: dict[str, SkillContent] = {}


def get_skills_root() -> str:
    """获取技能根目录"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")


def parse_skill_metadata(skill_path: str) -> Optional[SkillMetadata]:
    """
    解析 SKILL.md 文件，只提取元数据部分（快速解析）

    Args:
        skill_path: SKILL.md 文件路径

    Returns:
        SkillMetadata 或 None
    """
    if not os.path.exists(skill_path):
        return None

    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 解析标题（第一个 # 标题）
        name_match = re.search(r"^#\s+(.+?)(?:\s*技能)?$", content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else "未命名技能"

        # 解析 ID
        id_match = re.search(r"\*\*ID\*\*:\s*(\w+)", content)
        skill_id = id_match.group(1) if id_match else os.path.basename(os.path.dirname(skill_path))

        # 解析版本
        version_match = re.search(r"\*\*版本\*\*:\s*([\d.]+)", content)
        version = version_match.group(1) if version_match else "1.0.0"

        # 解析图标
        icon_match = re.search(r"\*\*图标\*\*:\s*(\S+)", content)
        icon = icon_match.group(1) if icon_match else "🔧"

        # 解析关键词
        keywords_match = re.search(r"\*\*关键词\*\*:\s*(.+)", content)
        keywords = []
        if keywords_match:
            keywords = [k.strip() for k in keywords_match.group(1).split(",")]

        # 解析触发条件（提取触发条件部分的列表项）
        triggers = []
        trigger_section = re.search(r"##\s*触发条件\s*\n([\s\S]*?)(?=\n##|\Z)", content)
        if trigger_section:
            trigger_items = re.findall(r"^-\s*(.+)$", trigger_section.group(1), re.MULTILINE)
            triggers = [t.strip() for t in trigger_items]

        # 解析工具列表（从 ### 工具名 提取）
        tools = re.findall(r"^###\s+(\w+)\s*$", content, re.MULTILINE)

        # 解析内容目录名称
        content_dir_match = re.search(r"\*\*内容目录\*\*:\s*(\S+)", content)
        content_dir = content_dir_match.group(1) if content_dir_match else "stories"

        return SkillMetadata(
            id=skill_id,
            name=name,
            version=version,
            icon=icon,
            keywords=keywords,
            triggers=triggers,
            tools=tools,
            path=skill_path,
            content_dir=content_dir,
        )

    except Exception as e:
        print(f"[Skills] 解析技能元数据失败 {skill_path}: {e}")
        return None


def discover_skills() -> dict[str, SkillMetadata]:
    """
    发现所有可用技能（只加载元数据）

    Returns:
        技能ID -> 元数据的映射
    """
    global _skill_registry

    skills_root = get_skills_root()
    if not os.path.exists(skills_root):
        print(f"[Skills] 技能目录不存在: {skills_root}")
        return {}

    skills = {}

    # 遍历技能目录
    for item in os.listdir(skills_root):
        skill_dir = os.path.join(skills_root, item)
        if not os.path.isdir(skill_dir):
            continue

        skill_md = os.path.join(skill_dir, "SKILL.md")
        if not os.path.exists(skill_md):
            # 兼容旧格式：尝试 index.json
            index_json = os.path.join(skill_dir, "index.json")
            if os.path.exists(index_json):
                # 创建基础元数据
                import json
                with open(index_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                skills[item] = SkillMetadata(
                    id=data.get("id", item),
                    name=data.get("name", item),
                    version=data.get("version", "1.0.0"),
                    icon=data.get("icon", "🔧"),
                    keywords=[],
                    triggers=[],
                    tools=data.get("tools", []),
                    path=index_json,
                )
            continue

        metadata = parse_skill_metadata(skill_md)
        if metadata:
            skills[metadata.id] = metadata
            print(f"[Skills] 发现技能: {metadata.icon} {metadata.name} (v{metadata.version})")

    _skill_registry = skills
    return skills


def load_skill_content(skill_id: str) -> Optional[SkillContent]:
    """
    加载技能完整内容（按需调用）

    Args:
        skill_id: 技能 ID

    Returns:
        SkillContent 或 None
    """
    global _skill_content_cache

    # 检查缓存
    if skill_id in _skill_content_cache:
        return _skill_content_cache[skill_id]

    # 检查技能是否存在
    if skill_id not in _skill_registry:
        return None

    metadata = _skill_registry[skill_id]

    try:
        with open(metadata.path, "r", encoding="utf-8") as f:
            full_content = f.read()

        content = SkillContent(
            metadata=metadata,
            full_content=full_content,
        )

        _skill_content_cache[skill_id] = content
        print(f"[Skills] 加载技能内容: {metadata.name}")
        return content

    except Exception as e:
        print(f"[Skills] 加载技能内容失败 {skill_id}: {e}")
        return None


def get_skills_summary() -> str:
    """
    生成技能摘要（用于系统提示词）

    Returns:
        技能摘要文本
    """
    if not _skill_registry:
        discover_skills()

    if not _skill_registry:
        return "当前没有可用的技能。"

    lines = ["## 可用技能\n"]

    for skill in _skill_registry.values():
        lines.append(f"### {skill.icon} {skill.name}")
        lines.append(f"ID: `{skill.id}`")
        if skill.keywords:
            lines.append(f"关键词: {', '.join(skill.keywords)}")
        if skill.triggers:
            lines.append("触发条件:")
            for trigger in skill.triggers[:3]:  # 只显示前3个
                lines.append(f"  - {trigger}")
        if skill.tools:
            lines.append(f"工具: {', '.join(skill.tools)}")
        lines.append("")

    return "\n".join(lines)


def get_skill_registry() -> dict[str, SkillMetadata]:
    """获取技能注册表"""
    if not _skill_registry:
        discover_skills()
    return _skill_registry


def get_skill_by_id(skill_id: str) -> Optional[SkillMetadata]:
    """根据 ID 获取技能元数据"""
    if not _skill_registry:
        discover_skills()
    return _skill_registry.get(skill_id)
