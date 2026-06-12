"""
迁移脚本：将 pan.md / panplus.md 中的构图规则导入数据库

用法：
    cd backend
    python -m scripts.migrate_rules_to_db [--dry-run]

导入后，rule_matcher.py 将从数据库加载规则，不再依赖文件解析。
"""

import os
import sys
import argparse
from datetime import date

# 确保能导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.modules.pantianshou_composition.models import Base, CompositionRule, CompositionFigure
from app.modules.pantianshou_composition.knowledge_ingest import (
    parse_pan_rules,
    parse_pan_figure_index,
    parse_panplus_supplement_rules,
    load_panplus_rules,
    _read_text,
    PanRule,
    PanFigureIndex,
)


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _db_path() -> str:
    return os.path.join(_repo_root(), "backend", "data", "knowledge.db")


def _parse_weight_to_int(w: float) -> int:
    """将 0.0-1.0 的权重转为 0-100 整数"""
    return int(round(w * 100))


def migrate_rules(session, dry_run: bool = False) -> dict:
    """解析 pan.md + panplus.md 并导入 composition_rules 表"""
    repo = _repo_root()
    pan_md = os.path.join(repo, "archive", "training-docs", "pan.md")
    panplus_md = os.path.join(repo, "archive", "training-docs", "panplus.md")
    
    if not os.path.exists(pan_md):
        print(f"[ERROR] pan.md 不存在: {pan_md}")
        return {"ok": False, "error": "pan.md not found"}
    
    # 解析 pan.md
    pan_text = _read_text(pan_md)
    pan_rules = parse_pan_rules(pan_text)
    print(f"[pan.md] 解析到 {len(pan_rules)} 条规则")
    
    # 解析 panplus.md
    panplus_rules = []
    if os.path.exists(panplus_md):
        panplus_text = _read_text(panplus_md)
        # 主规则（JH/CC/BJ 维度）
        main_rules = parse_pan_rules(panplus_text)
        # 补充规则（KH/XS/SM/QS/FZ 维度的新增）
        supplement_rules = parse_panplus_supplement_rules(panplus_text)
        panplus_rules = main_rules + supplement_rules
        print(f"[panplus.md] 解析到 {len(panplus_rules)} 条规则（主规则 {len(main_rules)} + 补充 {len(supplement_rules)}）")
    
    # 合并去重（panplus 优先）
    seen: dict[str, PanRule] = {}
    for r in pan_rules:
        seen[r.rule_id] = r
    for r in panplus_rules:
        seen[r.rule_id] = r  # 覆盖 pan.md 中的同 ID 规则
    
    all_rules = list(seen.values())
    print(f"[合并] 去重后共 {len(all_rules)} 条规则")
    
    if dry_run:
        print("[DRY RUN] 不写入数据库")
        for r in all_rules[:5]:
            print(f"  - {r.rule_id}: {r.rule_name} ({r.category_code})")
        if len(all_rules) > 5:
            print(f"  ... 还有 {len(all_rules) - 5} 条")
        return {"ok": True, "rules_count": len(all_rules), "dry_run": True}
    
    # 写入数据库
    today = date.today().isoformat()
    imported = 0
    updated = 0
    
    for r in all_rules:
        existing = session.query(CompositionRule).filter_by(rule_id=r.rule_id).first()
        if existing:
            # 更新已有记录
            existing.rule_name = r.rule_name
            existing.condition = r.condition
            existing.quantitative_standard = r.quantitative_standard
            existing.weight = _parse_weight_to_int(r.weight)
            existing.category_name = r.category_name
            existing.category_code = r.category_code
            existing.subcategory_name = r.subcategory_name
            existing.reference_figures = r.reference_figures
            existing.ruleset_version = today
            updated += 1
        else:
            # 新增
            rule = CompositionRule(
                rule_id=r.rule_id,
                rule_name=r.rule_name,
                condition=r.condition,
                quantitative_standard=r.quantitative_standard,
                weight=_parse_weight_to_int(r.weight),
                category_name=r.category_name,
                category_code=r.category_code,
                subcategory_name=r.subcategory_name,
                reference_figures=r.reference_figures,
                source="panplus.md" if r.rule_id.startswith(("JH-", "CC-", "BJ-")) else "pan.md",
                ruleset_version=today,
            )
            session.add(rule)
            imported += 1
    
    session.commit()
    print(f"[DB] 导入完成：新增 {imported}，更新 {updated}")
    return {"ok": True, "imported": imported, "updated": updated, "total": len(all_rules)}


def migrate_figures(session, dry_run: bool = False) -> dict:
    """解析 pan.md 中的插图索引并导入 composition_figures 表"""
    repo = _repo_root()
    pan_md = os.path.join(repo, "archive", "training-docs", "pan.md")
    
    if not os.path.exists(pan_md):
        return {"ok": False, "error": "pan.md not found"}
    
    pan_text = _read_text(pan_md)
    figures = parse_pan_figure_index(pan_text)
    print(f"[pan.md] 解析到 {len(figures)} 个插图索引")
    
    if dry_run:
        print("[DRY RUN] 不写入数据库")
        for f in figures[:5]:
            print(f"  - {f.figure_id}: {f.figure_type} (score={f.score_ref})")
        return {"ok": True, "figures_count": len(figures), "dry_run": True}
    
    today = date.today().isoformat()
    imported = 0
    updated = 0
    
    for f in figures:
        existing = session.query(CompositionFigure).filter_by(figure_id=f.figure_id).first()
        if existing:
            existing.figure_type = f.figure_type
            existing.score_ref = int(round(f.score_ref * 100)) if f.score_ref is not None else None
            existing.description = f.description
            existing.ruleset_version = today
            updated += 1
        else:
            fig = CompositionFigure(
                figure_id=f.figure_id,
                figure_type=f.figure_type,
                score_ref=int(round(f.score_ref * 100)) if f.score_ref is not None else None,
                description=f.description,
                source="pan.md",
                ruleset_version=today,
            )
            session.add(fig)
            imported += 1
    
    session.commit()
    print(f"[DB] 导入完成：新增 {imported}，更新 {updated}")
    return {"ok": True, "imported": imported, "updated": updated, "total": len(figures)}


def main():
    parser = argparse.ArgumentParser(description="迁移构图规则到数据库")
    parser.add_argument("--dry-run", action="store_true", help="只解析不写入")
    args = parser.parse_args()
    
    db_path = _db_path()
    print(f"[DB] 数据库路径: {db_path}")
    
    if not os.path.exists(db_path):
        print("[ERROR] 数据库文件不存在，请先启动后端服务初始化数据库")
        sys.exit(1)
    
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    # 确保表存在
    Base.metadata.create_all(bind=engine, tables=[
        CompositionRule.__table__,
        CompositionFigure.__table__,
    ])
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("\n=== 迁移构图规则 ===")
        rules_result = migrate_rules(session, dry_run=args.dry_run)
        
        print("\n=== 迁移插图索引 ===")
        figures_result = migrate_figures(session, dry_run=args.dry_run)
        
        print("\n=== 迁移完成 ===")
        print(f"规则: {rules_result}")
        print(f"插图: {figures_result}")
        
    except Exception as e:
        print(f"[ERROR] 迁移失败: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
