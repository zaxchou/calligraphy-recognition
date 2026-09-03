#!/usr/bin/env python3
"""
设置作品的 page_role（封面/封底/附件）。

用法示例:
  # 按 ID 设置
  python backend/migrate_page_role.py --ids 802,803 --role cover

  # 按标题模糊匹配，交互确认
  python backend/migrate_page_role.py --title "扇骨" --role accessory --dry-run

  # 列出库中所有可设置 page_role 的记录
  python backend/migrate_page_role.py --list --library-id 10
"""
import argparse, sqlite3, sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "calligraphy.db"
VALID_ROLES = {"cover": "封面", "back_cover": "封底", "accessory": "附件", "inscription": "题跋页", "other": "其他页", None: "正文(清除角色)"}


def parse_args():
    p = argparse.ArgumentParser(description="设置作品 page_role")
    p.add_argument("--ids", help="逗号分隔的作品ID列表")
    p.add_argument("--title", help="标题模糊匹配（需配合 --role）")
    p.add_argument("--library-id", type=int, help="限定库")
    p.add_argument("--role", choices=["cover", "back_cover", "accessory", "clear"],
                   help="角色: cover/back_cover/accessory/clear(重置)")
    p.add_argument("--list", action="store_true", help="列出可设置的作品")
    p.add_argument("--dry-run", action="store_true", help="只预览，不修改")
    return p.parse_args()


def main():
    args = parse_args()
    if not DB_PATH.exists():
        print(f"ERROR: DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    role_val = None if args.role == "clear" else args.role

    if args.list:
        where = "WHERE library_id = ?" if args.library_id else ""
        params = (args.library_id,) if args.library_id else ()
        cur = conn.execute(
            f"SELECT id, library_id, title, artist, page_role FROM tubi_analyses {where} ORDER BY library_id, id",
            params,
        )
        for r in cur.fetchall():
            role = r["page_role"] or "正文"
            print(f"  id={r['id']:<6} Lib#{r['library_id']:<3} [{role:<6}] {r['artist']} 《{r['title']}》")
        conn.close()
        return

    if not args.role:
        print("ERROR: 需要 --role 或 --list")
        sys.exit(1)

    # Collect IDs
    ids = []
    if args.ids:
        ids = [int(x.strip()) for x in args.ids.split(",") if x.strip()]

    if args.title:
        like = f"%{args.title}%"
        params = (like,)
        where = "WHERE title LIKE ?"
        if args.library_id:
            where += " AND library_id = ?"
            params = (like, args.library_id)
        cur = conn.execute(f"SELECT id, title, artist, library_id FROM tubi_analyses {where}", params)
        matched = cur.fetchall()
        if not matched:
            print(f"没有匹配「{args.title}」的作品")
            conn.close()
            return
        print(f"匹配 {len(matched)} 条:")
        for r in matched:
            print(f"  id={r['id']} Lib#{r['library_id']} {r['artist']} 《{r['title']}》")
        if not args.dry_run:
            ans = input(f"\n确认设置 page_role='{args.role}'? (y/N): ")
            if ans.lower() != "y":
                print("已取消")
                conn.close()
                return
        ids.extend(r["id"] for r in matched)

    if not ids:
        print("ERROR: 没有指定作品ID（用 --ids 或 --title）")
        sys.exit(1)

    role_name = VALID_ROLES.get(role_val, str(role_val))
    for rid in ids:
        if args.dry_run:
            cur = conn.execute("SELECT title FROM tubi_analyses WHERE id=?", (rid,))
            r = cur.fetchone()
            print(f"  [DRY RUN] id={rid} 《{r['title']}》 → {role_name}")
        else:
            conn.execute("UPDATE tubi_analyses SET page_role=? WHERE id=?", (role_val, rid))
            print(f"  id={rid} → {role_name}")

    if not args.dry_run:
        conn.commit()
        print(f"\n已更新 {len(ids)} 条记录")

    conn.close()


if __name__ == "__main__":
    main()
