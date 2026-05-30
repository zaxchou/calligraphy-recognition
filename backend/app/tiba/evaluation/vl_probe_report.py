"""
生成 VL 探针测试的 HTML 可视化报告（支持 Hybrid 对比）
"""
import json
import os
import base64
from pathlib import Path


def image_to_base64(image_path: str) -> str:
    """将图片转为 base64 data URL"""
    with open(image_path, "rb") as f:
        data = f.read()
    ext = Path(image_path).suffix.lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64," + base64.b64encode(data).decode()


def generate_html_report(report_dir: str, output_path: str):
    """生成 HTML 报告"""
    report_json = os.path.join(report_dir, "report.json")
    with open(report_json, "r", encoding="utf-8") as f:
        report = json.load(f)

    is_hybrid = report.get("mode") == "hybrid"
    bbox_summary = report.get("bbox_summary", report.get("summary", {}))
    hybrid_summary = report.get("hybrid_summary", {})
    improvement = report.get("improvement", {})

    images_html = []
    for result in report["results"]:
        if not result.get("success"):
            continue

        image_id = result["image_id"]
        title = result.get("title", image_id)
        vl = result["vl_result"]

        bbox_iou = result.get("bbox_iou", {})
        hybrid_iou = result.get("hybrid_iou", {})

        # 可视化图
        vis_baseline_path = os.path.join(report_dir, f"vis_{image_id}_baseline.jpg")
        vis_hybrid_path = os.path.join(report_dir, f"vis_{image_id}_hybrid.jpg")

        vis_html = ""
        if os.path.exists(vis_baseline_path):
            vis_b64 = image_to_base64(vis_baseline_path)
            vis_html += f'<div class="vis-block"><div class="vis-label">VL BBox Baseline</div><img src="{vis_b64}" alt="baseline"></div>'
        if is_hybrid and os.path.exists(vis_hybrid_path):
            vis_b64_h = image_to_base64(vis_hybrid_path)
            vis_html += f'<div class="vis-block"><div class="vis-label">VL + CV Hybrid</div><img src="{vis_b64_h}" alt="hybrid"></div>'

        # 区域列表
        insc_items = []
        for r in vl.get("inscription_regions", []):
            coords = f"[{r.get('x1',0):.2f},{r.get('y1',0):.2f},{r.get('x2',0):.2f},{r.get('y2',0):.2f}]"
            insc_items.append(f"<li><b>{coords}</b> {r.get('note','')}</li>")

        paint_items = []
        for r in vl.get("painting_regions", []):
            coords = f"[{r.get('x1',0):.2f},{r.get('y1',0):.2f},{r.get('x2',0):.2f},{r.get('y2',0):.2f}]"
            paint_items.append(f"<li><b>{coords}</b> {r.get('note','')}</li>")

        # Hybrid 区域（如果有）
        hybrid_regions_html = ""
        if "hybrid_regions" in result:
            h_insc = result["hybrid_regions"].get("inscription_regions", [])
            h_paint = result["hybrid_regions"].get("painting_regions", [])
            hybrid_regions_html = f"""
            <div class="hybrid-info">
                <b>Hybrid 多边形区域：</b>
                题跋 {len(h_insc)} 个，绘画 {len(h_paint)} 个
            </div>
            """

        images_html.append(f"""
        <div class="image-card">
            <h2>{title} <span class="dim">{result['width']}×{result['height']}</span></h2>
            <div class="metrics-row">
                <div class="metric-group">
                    <div class="group-label">BBox Baseline</div>
                    <div class="metrics">
                        <div class="metric insc"><div class="metric-label">题跋</div><div class="metric-value">{bbox_iou.get('inscription_iou',0):.3f}</div></div>
                        <div class="metric paint"><div class="metric-label">绘画</div><div class="metric-value">{bbox_iou.get('painting_iou',0):.3f}</div></div>
                        <div class="metric overall"><div class="metric-label">综合</div><div class="metric-value">{bbox_iou.get('overall_iou',0):.3f}</div></div>
                    </div>
                </div>
                {f"""
                <div class="metric-group">
                    <div class="group-label">Hybrid</div>
                    <div class="metrics">
                        <div class="metric insc"><div class="metric-label">题跋</div><div class="metric-value">{hybrid_iou.get('inscription_iou',0):.3f}</div></div>
                        <div class="metric paint"><div class="metric-label">绘画</div><div class="metric-value">{hybrid_iou.get('painting_iou',0):.3f}</div></div>
                        <div class="metric overall"><div class="metric-label">综合</div><div class="metric-value">{hybrid_iou.get('overall_iou',0):.3f}</div></div>
                    </div>
                    <div class="delta">
                        dI={hybrid_iou.get('inscription_iou',0)-bbox_iou.get('inscription_iou',0):+.3f}
                        dP={hybrid_iou.get('painting_iou',0)-bbox_iou.get('painting_iou',0):+.3f}
                        dO={hybrid_iou.get('overall_iou',0)-bbox_iou.get('overall_iou',0):+.3f}
                    </div>
                </div>
                """ if hybrid_iou else ""}
                <div class="metric time"><div class="metric-label">API</div><div class="metric-value">{vl.get('elapsed_sec',0):.1f}s</div></div>
            </div>
            <div class="visualizations">{vis_html}</div>
            {hybrid_regions_html}
            <div class="vl-output">
                <div class="desc"><b>VL描述：</b>{vl.get('description','')}</div>
                <div class="regions">
                    <div class="region-col">
                        <h4>题跋区域 ({len(vl.get('inscription_regions',[]))}个)</h4>
                        <ul>{''.join(insc_items)}</ul>
                    </div>
                    <div class="region-col">
                        <h4>绘画区域 ({len(vl.get('painting_regions',[]))}个)</h4>
                        <ul>{''.join(paint_items)}</ul>
                    </div>
                </div>
            </div>
        </div>
        """)

    # Summary 对比
    summary_boxes = f"""
        <div class="summary-box">
            <div class="label">BBox 题跋 IoU</div>
            <div class="value">{bbox_summary.get('avg_insc_iou',0):.3f}</div>
            <div class="compare">vs CV-First 0.155 (+{((bbox_summary.get('avg_insc_iou',0)-0.155)/0.155*100):.0f}%)</div>
        </div>
        <div class="summary-box">
            <div class="label">BBox 绘画 IoU</div>
            <div class="value">{bbox_summary.get('avg_paint_iou',0):.3f}</div>
            <div class="compare">vs CV-First 0.526 (+{((bbox_summary.get('avg_paint_iou',0)-0.526)/0.526*100):.0f}%)</div>
        </div>
        <div class="summary-box">
            <div class="label">BBox 综合 IoU</div>
            <div class="value">{bbox_summary.get('avg_overall_iou',0):.3f}</div>
            <div class="compare">vs CV-First 0.397 (+{((bbox_summary.get('avg_overall_iou',0)-0.397)/0.397*100):.0f}%)</div>
        </div>
    """

    if is_hybrid and hybrid_summary:
        summary_boxes += f"""
        <div class="summary-box hybrid-box">
            <div class="label">Hybrid 综合 IoU</div>
            <div class="value">{hybrid_summary.get('avg_overall_iou',0):.3f}</div>
            <div class="compare" style="color:{'#27ae60' if improvement.get('overall_delta',0) >= 0 else '#e74c3c'}">
                dO={improvement.get('overall_delta',0):+.3f}
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VL 语义分割探针报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f4ed;
            color: #141413;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}

        h1 {{
            text-align: center;
            margin-bottom: 8px;
            font-size: 28px;
            color: #c96442;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }}

        .summary {{
            display: flex;
            justify-content: center;
            gap: 16px;
            margin-bottom: 40px;
            flex-wrap: wrap;
        }}
        .summary-box {{
            background: white;
            border-radius: 12px;
            padding: 20px 28px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            min-width: 130px;
        }}
        .summary-box.hybrid-box {{
            border: 2px solid #b8a47e;
            background: #fdfcfa;
        }}
        .summary-box .label {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
        .summary-box .value {{ font-size: 28px; font-weight: bold; color: #c96442; }}
        .summary-box .compare {{ font-size: 11px; color: #999; margin-top: 4px; }}

        .image-card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 32px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }}
        .image-card h2 {{
            font-size: 20px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .image-card .dim {{
            font-size: 12px;
            color: #999;
            font-weight: normal;
        }}

        .metrics-row {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            align-items: flex-start;
        }}
        .metric-group {{
            background: #f8f8f5;
            border-radius: 10px;
            padding: 14px 18px;
        }}
        .group-label {{
            font-size: 11px;
            color: #888;
            margin-bottom: 8px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metrics {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .metric {{
            background: white;
            border-radius: 8px;
            padding: 10px 16px;
            text-align: center;
            min-width: 70px;
        }}
        .metric.insc {{ border-left: 3px solid #e74c3c; }}
        .metric.paint {{ border-left: 3px solid #3498db; }}
        .metric.overall {{ border-left: 3px solid #c96442; }}
        .metric.time {{ border-left: 3px solid #95a5a6; }}
        .metric-label {{ font-size: 10px; color: #888; }}
        .metric-value {{ font-size: 18px; font-weight: bold; color: #333; }}
        .delta {{
            font-size: 11px;
            color: #666;
            margin-top: 6px;
            font-family: monospace;
        }}

        .visualizations {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .vis-block {{
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .vis-label {{
            background: #141413;
            color: #f5f4ed;
            font-size: 11px;
            padding: 6px 12px;
            text-align: center;
        }}
        .vis-block img {{
            width: 100%;
            height: auto;
            display: block;
        }}

        .hybrid-info {{
            background: #fdf8f0;
            border-left: 3px solid #b8a47e;
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 16px;
            font-size: 12px;
            color: #666;
        }}

        .vl-output {{
            background: #fafaf8;
            border-radius: 8px;
            padding: 16px;
        }}
        .vl-output .desc {{
            font-size: 13px;
            color: #555;
            margin-bottom: 16px;
            line-height: 1.7;
        }}
        .regions {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        @media (max-width: 768px) {{
            .regions {{ grid-template-columns: 1fr; }}
            .visualizations {{ grid-template-columns: 1fr; }}
        }}
        .region-col h4 {{
            font-size: 13px;
            color: #888;
            margin-bottom: 8px;
            padding-bottom: 4px;
            border-bottom: 1px solid #eee;
        }}
        .region-col ul {{
            list-style: none;
            font-size: 12px;
            color: #555;
        }}
        .region-col li {{
            padding: 4px 0;
            border-bottom: 1px dotted #eee;
        }}
        .region-col li:last-child {{ border-bottom: none; }}

        .legend {{
            display: flex;
            justify-content: center;
            gap: 24px;
            margin: 20px 0;
            font-size: 12px;
            color: #666;
            flex-wrap: wrap;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>VL 语义分割探针报告</h1>
        <p class="subtitle">模型：{report['model']} | 模式：{report.get('mode','bbox').upper()} | 测试时间：{report['timestamp']}</p>

        <div class="summary">
            {summary_boxes}
        </div>

        <div class="legend">
            <div class="legend-item"><div class="legend-dot" style="background:#e74c3c"></div>GT 题跋区域</div>
            <div class="legend-item"><div class="legend-dot" style="background:#3498db"></div>GT 绘画区域</div>
            <div class="legend-item"><div class="legend-dot" style="background:#2ecc71"></div>预测正确 (TP)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#f1c40f"></div>漏检 (FN)</div>
            <div class="legend-item"><div class="legend-dot" style="background:#e84393"></div>误检 (FP)</div>
        </div>

        {''.join(images_html)}

        <div style="text-align:center; padding: 30px; color: #999; font-size: 12px;">
            生成时间：{report['timestamp']} | 书法碑帖字体认证系统
        </div>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML report saved: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        report_dir = sys.argv[1]
    else:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "evaluation_reports", "vl_probe")
        dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        if not dirs:
            print("No report directories found")
            exit(1)
        report_dir = os.path.join(base_dir, sorted(dirs)[-1])

    out = os.path.join(report_dir, "report.html")
    generate_html_report(report_dir, out)
