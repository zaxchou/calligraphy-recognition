"""
对已有的 composition 报告 JSON 重新运行 _postprocess_text()，
修复 <em>/<strong> HTML 标签泄漏等问题，无需重新上传图片。

用法：
  python reprocess_llm_text.py              # 预览模式，只打印需要修改的报告
  python reprocess_llm_text.py --apply       # 实际修改报告 JSON
  python reprocess_llm_text.py --task-id XXX # 只处理指定 task_id
"""
import json
import os
import re
import sys


def _normalize_html_to_markdown(text: str) -> str:
    """将 LLM 输出中的 HTML 标签归一化回 Markdown。

    这与 composition_llm.py 中 _postprocess_text() 的逻辑一致。
    """
    t = text
    t = re.sub(r'<strong>([\s\S]*?)</strong>', r'**\1**', t)
    t = re.sub(r'<em>([\s\S]*?)</em>', r'*\1*', t)
    t = re.sub(r'<bold>([\s\S]*?)</bold>', r'**\1**', t)
    t = re.sub(r'<b>([\s\S]*?)</b>', r'**\1**', t)
    t = re.sub(r'<i>([\s\S]*?)</i>', r'*\1*', t)
    return t


def needs_fix(text: str) -> bool:
    """检查文本是否包含需要修复的 HTML 标签。"""
    if not text:
        return False
    patterns = [r'<strong>', r'</strong>', r'<em>', r'</em>', r'<bold>', r'</bold>', r'<b>', r'</b>', r'<i>', r'</i>']
    return any(re.search(p, text) for p in patterns)


def main():
    apply = "--apply" in sys.argv
    specific_task = None
    for arg in sys.argv:
        if arg.startswith("--task-id="):
            specific_task = arg.split("=", 1)[1]
        elif arg == "--task-id" and sys.argv.index(arg) + 1 < len(sys.argv):
            specific_task = sys.argv[sys.argv.index(arg) + 1]

    # 定位 reports 目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(script_dir, "data", "composition", "reports")

    if not os.path.isdir(reports_dir):
        print(f"[ERROR] reports dir not found: {reports_dir}")
        sys.exit(1)

    # 收集所有报告文件
    report_files = []
    for fname in os.listdir(reports_dir):
        if fname.endswith(".json") and not fname.endswith("_meta.json"):
            task_id = fname[:-5]  # strip .json
            if specific_task and task_id != specific_task:
                continue
            report_files.append(os.path.join(reports_dir, fname))

    if not report_files:
        print("No report files found.")
        return

    print(f"Found {len(report_files)} report(s). {'APPLY mode' if apply else 'PREVIEW mode'}")
    print("-" * 60)

    fixed_count = 0
    for rpath in sorted(report_files):
        task_id = os.path.basename(rpath)[:-5]
        try:
            with open(rpath, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception as e:
            print(f"  [{task_id}] SKIP - cannot read: {e}")
            continue

        llm = report.get("llm", {})
        text = llm.get("text", "")
        if not text:
            continue

        if not needs_fix(text):
            continue

        # 统计有多少 HTML 标签
        tag_counts = {}
        for tag in ["strong", "em", "bold", "b", "i"]:
            opens = len(re.findall(f'<{tag}>', text))
            closes = len(re.findall(f'</{tag}>', text))
            if opens > 0 or closes > 0:
                tag_counts[tag] = opens

        new_text = _normalize_html_to_markdown(text)
        changed = (new_text != text)

        if changed:
            fixed_count += 1
            tags_str = ", ".join(f"<{t}>:{c}" for t, c in tag_counts.items())
            print(f"  [{task_id}] FIX ({tags_str})")

            if apply:
                report["llm"]["text"] = new_text
                with open(rpath, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                print(f"    -> Saved")
            else:
                # 显示一处示例差异
                for i, (old_line, new_line) in enumerate(zip(text.split('\n'), new_text.split('\n'))):
                    if old_line != new_line:
                        print(f"    BEFORE: {old_line[:100]}")
                        print(f"    AFTER:  {new_line[:100]}")
                        break

    print("-" * 60)
    if apply:
        print(f"Done. Fixed {fixed_count} report(s).")
    else:
        print(f"Found {fixed_count} report(s) needing fix. Run with --apply to apply changes.")


if __name__ == "__main__":
    main()
