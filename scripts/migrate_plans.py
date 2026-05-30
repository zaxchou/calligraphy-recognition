"""
迁移所有 plan 文档到 docs/plans/ 按月归档
"""
import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PLANS_DIR = PROJECT_ROOT / "docs" / "plans"

# ── 来源定义 ──
SOURCES = [
    # (源目录, 文件名模式说明)
    (PROJECT_ROOT / ".workbuddy" / "plans", "workbuddy"),
    (PROJECT_ROOT / ".trae" / "documents", "trae"),
    (PROJECT_ROOT / "docs", "docs"),
    (PROJECT_ROOT / "reports", "reports"),
]


def clean_filename(original_name: str, source: str, date_str: str) -> str:
    """清理文件名：去掉 hash 后缀，加日期前缀"""
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix  # .md

    # workbuddy 文件名格式: name_hashhash(未完成).md
    if source == "workbuddy":
        # 去掉 (未完成) 标记
        stem = stem.replace("(未完成)", "").rstrip("_").rstrip()
        # 去掉末尾的 _8位hex hash
        stem = re.sub(r'_[0-9a-f]{8}$', '', stem)

    # docs 中只有 plan 开头的文件才迁移，名字不变
    # reports 中 plan_ 开头的文件，保留原名
    # trae 文件名已经是干净的

    # 确保文件名对文件系统安全
    # 替换不安全字符但保留中文
    stem = stem.replace("/", "-").replace("\\", "-").replace(":", "-")
    stem = stem.replace(" ", "-")
    # 合并连续的 -
    stem = re.sub(r'-{2,}', '-', stem)
    stem = stem.strip('-')

    return f"{date_str}_{stem}{suffix}"


def extract_title(filepath: Path) -> str:
    """从文件内容提取标题"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return filepath.stem

    # 尝试从 frontmatter 的 overview 或 name 字段提取
    if content.startswith('---'):
        fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            # 优先用 overview
            overview = re.search(r'overview:\s*(.+)', fm)
            if overview:
                return overview.group(1).strip()
            name = re.search(r'^name:\s*(.+)', fm, re.MULTILINE)
            if name:
                return name.group(1).strip()

    # 尝试从第一个 # 标题提取
    title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
    if title_match:
        return title_match.group(1).strip()

    # 尝试从第一个 > 引用提取
    quote_match = re.search(r'^>\s*(.+)', content, re.MULTILINE)
    if quote_match:
        return quote_match.group(1).strip()

    return filepath.stem


def extract_overview(filepath: Path) -> str:
    """从文件提取简要概述"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return ""

    if content.startswith('---'):
        fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            overview = re.search(r'overview:\s*(.+)', fm)
            if overview:
                return overview.group(1).strip()[:120]

    # 从内容提取第一段非标题非空行
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('---') and not line.startswith('>') and len(line) > 10:
            return line[:120]

    return ""


def is_incomplete(filepath: Path) -> bool:
    """检查计划是否标记为未完成"""
    name = filepath.name
    if "(未完成)" in name:
        return True
    try:
        content = filepath.read_text(encoding='utf-8')
        if content.startswith('---'):
            fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
            if fm_match:
                fm = fm_match.group(1)
                # 检查 todos 中是否有非 completed 的
                if 'status: pending' in fm or 'status: in_progress' in fm:
                    return True
    except:
        pass
    return False


def collect_files():
    """收集所有需要迁移的文件"""
    files = []

    # workbuddy/plans - 全部
    wb_dir = PROJECT_ROOT / ".workbuddy" / "plans"
    if wb_dir.exists():
        for f in wb_dir.glob("*.md"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            files.append({
                "path": f,
                "source": "workbuddy",
                "date": mtime,
                "title": extract_title(f),
                "overview": extract_overview(f),
                "incomplete": is_incomplete(f),
            })

    # trae/documents - 全部
    trae_dir = PROJECT_ROOT / ".trae" / "documents"
    if trae_dir.exists():
        for f in trae_dir.glob("*.md"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            files.append({
                "path": f,
                "source": "trae",
                "date": mtime,
                "title": extract_title(f),
                "overview": extract_overview(f),
                "incomplete": is_incomplete(f),
            })

    # docs/ - 只选 plan 相关的
    docs_dir = PROJECT_ROOT / "docs"
    if docs_dir.exists():
        plan_keywords = ['plan', 'PLAN', '方案', '规划', '重构']
        for f in docs_dir.glob("*.md"):
            fname = f.name.lower()
            if any(kw.lower() in fname for kw in plan_keywords):
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                files.append({
                    "path": f,
                    "source": "docs",
                    "date": mtime,
                    "title": extract_title(f),
                    "overview": extract_overview(f),
                    "incomplete": is_incomplete(f),
                })

    # reports/ - 全部 (都是 plan/report)
    reports_dir = PROJECT_ROOT / "reports"
    if reports_dir.exists():
        for f in reports_dir.glob("*.md"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            files.append({
                "path": f,
                "source": "reports",
                "date": mtime,
                "title": extract_title(f),
                "overview": extract_overview(f),
                "incomplete": is_incomplete(f),
            })

    # backend/ 根目录的 plan 文件
    be_dir = PROJECT_ROOT / "backend"
    if be_dir.exists():
        for f in be_dir.glob("*.md"):
            fname = f.name.lower()
            if 'plan' in fname or 'review' in fname:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                files.append({
                    "path": f,
                    "source": "backend",
                    "date": mtime,
                    "title": extract_title(f),
                    "overview": extract_overview(f),
                    "incomplete": is_incomplete(f),
                })

    # 按日期排序
    files.sort(key=lambda x: x["date"])
    return files


def migrate(files):
    """执行迁移"""
    migrated = []
    seen_filenames = {}  # 处理同名冲突

    for info in files:
        f = info["path"]
        source = info["source"]
        date = info["date"]
        date_str = date.strftime("%Y-%m-%d")
        month_dir = date.strftime("%Y-%m")

        # 确定目标月目录
        target_dir = PLANS_DIR / month_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 清理文件名
        new_name = clean_filename(f.name, source, date_str)

        # 处理同名冲突
        if new_name in seen_filenames:
            seen_filenames[new_name] += 1
            base = Path(new_name).stem
            ext = Path(new_name).suffix
            new_name = f"{base}_v{seen_filenames[new_name]}{ext}"
        else:
            seen_filenames[new_name] = 1

        target_path = target_dir / new_name

        # 复制文件（不删除原文件）
        shutil.copy2(f, target_path)

        info["new_name"] = new_name
        info["new_path"] = target_path
        info["month"] = month_dir
        migrated.append(info)

    return migrated


def generate_month_index(month: str, files: list):
    """生成月度索引"""
    lines = [f"# {month} 开发计划索引\n"]
    lines.append(f"> 共 {len(files)} 个计划文档\n")
    lines.append("| 日期 | 状态 | 计划名称 | 来源 |")
    lines.append("|------|------|----------|------|")

    for info in sorted(files, key=lambda x: x["date"]):
        date_str = info["date"].strftime("%m-%d")
        status = "🔴 未完成" if info["incomplete"] else "✅ 已完成"
        title = info["title"][:50]
        fname = info["new_name"]
        source = info["source"]
        lines.append(f"| {date_str} | {status} | [{title}]({fname}) | {source} |")

    lines.append("")
    index_path = PLANS_DIR / month / "_index.md"
    index_path.write_text("\n".join(lines), encoding='utf-8')


def generate_readme(all_files: list):
    """生成主 README"""
    months = {}
    for info in all_files:
        m = info["month"]
        if m not in months:
            months[m] = []
        months[m].append(info)

    total = len(all_files)
    completed = sum(1 for f in all_files if not f["incomplete"])
    incomplete = total - completed

    lines = [
        "# 书法识别项目 · 开发计划文档库\n",
        "",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d')} | 共 {total} 个计划 | ✅ {completed} 已完成 | 🔴 {incomplete} 未完成\n",
        "",
        "## 文档结构\n",
        "```",
        "docs/plans/",
        "├── README.md          ← 你在这里",
    ]

    for month in sorted(months.keys()):
        count = len(months[month])
        lines.append(f"├── {month}/              ← {count} 个计划")

    lines.extend([
        "│   └── _index.md      ← 月度索引",
        "└── templates/",
        "    └── plan-template.md",
        "```\n",
        "",
        "## 月度索引\n",
    ])

    for month in sorted(months.keys()):
        files = months[month]
        completed_m = sum(1 for f in files if not f["incomplete"])
        lines.append(f"### [{month}]({month}/_index.md) — {len(files)} 个计划（✅ {completed_m} 已完成）\n")
        lines.append("| 日期 | 状态 | 计划 |")
        lines.append("|------|------|------|")

        for info in sorted(files, key=lambda x: x["date"]):
            date_str = info["date"].strftime("%m-%d")
            status = "🔴" if info["incomplete"] else "✅"
            title = info["title"][:60]
            fname = info["new_name"]
            lines.append(f"| {date_str} | {status} | [{title}]({month}/{fname}) |")

        lines.append("")

    lines.extend([
        "---\n",
        "## 开发管理规范\n",
        "",
        "### 创建新计划\n",
        "1. 复制 `templates/plan-template.md`",
        "2. 命名格式: `YYYY-MM-DD_功能名称.md`",
        "3. 放入对应的月份文件夹",
        "4. 更新月度 `_index.md`\n",
        "",
        "### 状态标记\n",
        "- `✅ 已完成` — 所有 todo 已完成",
        "- `🔴 未完成` — 仍有 pending/in_progress 的 todo\n",
        "",
        "### 来源说明\n",
        "本文档库整合了以下工具生成的计划文档：\n",
        "| 来源 | 说明 | 时间范围 | 数量 |",
        "|------|------|----------|------|",
        "| workbuddy | WorkBuddy agent 生成的详细执行计划 | 2026-04 ~ 2026-04 | 71 |",
        "| trae | Trae IDE 生成的设计方案 | 2026-04 ~ 2026-05 | 17 |",
        "| docs | 项目 docs/ 目录的 plan 文档 | 2026-04 ~ 2026-05 | 5 |",
        "| reports | 项目 reports/ 目录的规划报告 | 2026-04 ~ 2026-05 | 11 |",
        "| backend | 后端相关审查文档 | 2026-05 | 1 |",
        "",
        "原始文件保留在原位置未删除，本目录是整合后的副本。\n",
    ])

    readme_path = PLANS_DIR / "README.md"
    readme_path.write_text("\n".join(lines), encoding='utf-8')


if __name__ == "__main__":
    print("📋 收集文件...")
    files = collect_files()
    print(f"   找到 {len(files)} 个 plan 文件")

    print("\n📦 迁移文件...")
    migrated = migrate(files)
    print(f"   已迁移 {len(migrated)} 个文件")

    print("\n📝 生成月度索引...")
    months = {}
    for info in migrated:
        m = info["month"]
        if m not in months:
            months[m] = []
        months[m].append(info)

    for month, month_files in months.items():
        generate_month_index(month, month_files)
        print(f"   {month}: {len(month_files)} 个文件")

    print("\n📖 生成主索引...")
    generate_readme(migrated)

    # 输出迁移清单供验证
    manifest = []
    for info in migrated:
        manifest.append({
            "source": str(info["path"].relative_to(PROJECT_ROOT)),
            "target": str(info["new_path"].relative_to(PROJECT_ROOT)),
            "date": info["date"].isoformat(),
            "title": info["title"],
        })

    manifest_path = PLANS_DIR / "_manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！迁移清单保存到 {manifest_path.relative_to(PROJECT_ROOT)}")

    # 统计
    print(f"\n📊 统计:")
    print(f"   总计: {len(migrated)} 个计划文档")
    for month in sorted(months.keys()):
        print(f"   {month}: {len(months[month])} 个")
