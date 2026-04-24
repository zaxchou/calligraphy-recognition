"""
处理《扬州画派书画全集·李鱓》书页图片
- 用 Qwen VL Plus 识别每页内容（文字/画作/混合）
- 裁切画作区域，去除书页边距、页码等
- 横向图片旋转90°
- 命名规则：清_李鱓_作品名_创作时间.jpg
"""
import os
import sys
import json
import base64
import time
import re
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import dashscope
from dashscope import MultiModalConversation

dashscope.api_key = os.getenv("QWEN_API_KEY")

# 目录配置
SRC_DIR = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"
OUT_DIR = r"E:\李鱓全集\修改版"

# 结果缓存
RESULT_FILE = Path(__file__).parent / "data" / "book_page_analysis.json"

ANALYSIS_PROMPT = """你是一位中国画专家，正在分析《扬州画派书画全集·李鱓》的扫描书页。

请仔细观察这张图片，判断其内容并返回严格的JSON格式信息（不要加markdown代码块）：

{
  "page_type": "text" | "artwork" | "artwork_with_text" | "multi_page_spread",
  "artwork_info": {
    "title": "作品名称，从画面上的题款/印章/文字中识别。如无法确定写'未知'",
    "creation_date": "创作时间（如乾隆某年等），如无法确定写空字符串",
    "orientation": "portrait" | "landscape",
    "is_detail": false,
    "spread_part": null | "left" | "center" | "right",
    "spread_total": null | 2 | 3
  },
  "crop_box": {
    "x_percent": 0.0,
    "y_percent": 0.0, 
    "w_percent": 1.0,
    "h_percent": 1.0
  },
  "description": "简要描述画面内容"
}

关键规则：
1. page_type:
   - "text": 纯文字页面（序言、目录、文章等），这些页面将被跳过
   - "artwork": 单页完整画作
   - "artwork_with_text": 页面左侧/上方有文字说明，右侧/下方是画作
   - "multi_page_spread": 一幅画跨两页或三页展开

2. artwork_info:
   - title: 从画面题款中识别作品名。如果是多个局部图，写同一个作品名
   - orientation: 画作本身的方向。横向长卷是landscape，立轴是portrait
   - is_detail: 是否为局部放大图
   - spread_part: 如果是跨页画作，标记这是左/中/右部分
   - spread_total: 跨页总共几页

3. crop_box: 裁切框（百分比坐标0-1），尽量精确地框住画作区域，去除：
   - 书页边距和灰色背景
   - 页码
   - 左侧的文字说明（如果有）
   - 但保留画作上的题款和印章

4. 对于横向的画作(landscape)，crop_box应框住画作实际区域（可能是横向的矩形）

请确保返回纯JSON，不要加```json```包裹。"""


def get_page_files(start_page=23):
    """获取所有书页文件（排除(1)重复），按页码排序"""
    files = []
    for f in os.listdir(SRC_DIR):
        if '(1)' in f:
            continue
        match = re.search(r'第(\d+)页', f)
        if match:
            page_num = int(match.group(1))
            if page_num >= start_page:
                files.append((page_num, os.path.join(SRC_DIR, f)))
    files.sort(key=lambda x: x[0])
    return files


def encode_image_to_base64(image_path, max_size=2048):
    """将图片编码为base64，如果太大则缩放"""
    img = Image.open(image_path)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    # 缩放到合理大小
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    
    import io
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def analyze_page(image_path, page_num):
    """用 Qwen VL Plus 分析单页"""
    print(f"  分析第{page_num}页: {os.path.basename(image_path)}")
    
    b64 = encode_image_to_base64(image_path)
    
    messages = [
        {
            "role": "user",
            "content": [
                {"image": f"data:image/jpeg;base64,{b64}"},
                {"text": ANALYSIS_PROMPT}
            ]
        }
    ]
    
    for attempt in range(3):
        try:
            response = MultiModalConversation.call(
                model='qwen-vl-plus',
                messages=messages,
                result_format='message'
            )
            
            if response.status_code == 200:
                text = response.output.choices[0].message.content[0]['text']
                # 清理可能的markdown包裹
                text = text.strip()
                if text.startswith('```'):
                    text = re.sub(r'^```\w*\n?', '', text)
                    text = re.sub(r'\n?```$', '', text)
                    text = text.strip()
                
                result = json.loads(text)
                result['page_num'] = page_num
                result['source_file'] = os.path.basename(image_path)
                return result
            else:
                print(f"    API错误: {response.code} - {response.message}")
                time.sleep(2)
        except json.JSONDecodeError as e:
            print(f"    JSON解析失败: {e}")
            print(f"    原始返回: {text[:200]}")
            time.sleep(1)
        except Exception as e:
            print(f"    异常: {e}")
            time.sleep(3)
    
    return None


def crop_and_save(image_path, analysis, output_dir):
    """根据分析结果裁切并保存图片"""
    page_type = analysis.get('page_type', 'text')
    
    # 跳过纯文字页
    if page_type == 'text':
        print(f"    -> 跳过文字页")
        return None
    
    img = Image.open(image_path)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    w, h = img.size
    
    # 获取裁切框
    crop = analysis.get('crop_box', {})
    x_pct = crop.get('x_percent', 0)
    y_pct = crop.get('y_percent', 0)
    w_pct = crop.get('w_percent', 1)
    h_pct = crop.get('h_percent', 1)
    
    # 计算像素坐标
    left = int(w * x_pct)
    top = int(h * y_pct)
    right = int(w * (x_pct + w_pct))
    bottom = int(h * (y_pct + h_pct))
    
    # 确保裁切区域有效
    left = max(0, left)
    top = max(0, top)
    right = min(w, right)
    bottom = min(h, bottom)
    
    if right - left < 100 or bottom - top < 100:
        print(f"    -> 裁切区域太小，跳过")
        return None
    
    cropped = img.crop((left, top, right, bottom))
    
    # 检查是否需要旋转（横向画作）
    info = analysis.get('artwork_info', {})
    orientation = info.get('orientation', 'portrait')
    
    cw, ch = cropped.size
    rotated = False
    if orientation == 'landscape' and ch > cw:
        # 横向画作但图片是竖的，旋转90°
        cropped = cropped.rotate(-90, expand=True)
        rotated = True
        print(f"    -> 旋转90°（横向画作）")
    
    # 生成文件名
    title = info.get('title', '未知')
    creation_date = info.get('creation_date', '')
    spread_part = info.get('spread_part')
    spread_total = info.get('spread_total')
    is_detail = info.get('is_detail', False)
    
    # 清理标题中的非法字符
    title_clean = re.sub(r'[\\/:*?"<>|]', '', title).strip()
    if not title_clean:
        title_clean = '未知'
    
    # 构建文件名
    name_parts = ['清', '李鱓', title_clean]
    if creation_date:
        name_parts.append(creation_date)
    
    # 跨页标记
    if spread_part and spread_total:
        part_idx = {'left': 1, 'center': 2, 'right': 2 if spread_total == 2 else 3}
        name_parts.append(f"第{part_idx.get(spread_part, 1)}部分")
    
    # 局部图标记
    if is_detail:
        name_parts.append('局部')
    
    filename = '_'.join(name_parts) + '.jpg'
    filepath = os.path.join(output_dir, filename)
    
    # 避免重名
    counter = 1
    while os.path.exists(filepath):
        name_parts_base = name_parts[:-1] if counter == 1 else name_parts[:-1]
        filepath = os.path.join(output_dir, '_'.join(name_parts) + f'_{counter}.jpg')
        counter += 1
    
    # 保存
    cropped.save(filepath, 'JPEG', quality=92)
    print(f"    -> 保存: {filename} ({cropped.size[0]}x{cropped.size[1]})")
    
    return filepath


def run_analysis(pages, force=False):
    """分析指定页码范围"""
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # 加载已有结果
    all_results = {}
    if RESULT_FILE.exists() and not force:
        with open(RESULT_FILE, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
    
    page_files = get_page_files(start_page=23)
    
    # 过滤指定页码
    target_files = [(pn, fp) for pn, fp in page_files if pn in pages]
    
    results = []
    for page_num, filepath in target_files:
        # 跳过已分析的
        if str(page_num) in all_results and not force:
            print(f"  第{page_num}页已有分析结果，跳过")
            results.append(all_results[str(page_num)])
            continue
        
        analysis = analyze_page(filepath, page_num)
        if analysis:
            all_results[str(page_num)] = analysis
            results.append(analysis)
            # 每次分析后保存
            with open(RESULT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
        else:
            print(f"  第{page_num}页分析失败")
        
        time.sleep(1)  # 避免API限速
    
    return results


def process_results(results):
    """处理分析结果：裁切、旋转、保存"""
    os.makedirs(OUT_DIR, exist_ok=True)
    
    saved = []
    for r in results:
        page_num = r.get('page_num')
        # 找到源文件
        page_files = get_page_files(start_page=23)
        filepath = None
        for pn, fp in page_files:
            if pn == page_num:
                filepath = fp
                break
        
        if not filepath:
            print(f"  第{page_num}页: 找不到源文件")
            continue
        
        print(f"  处理第{page_num}页:")
        result = crop_and_save(filepath, r, OUT_DIR)
        if result:
            saved.append(result)
    
    return saved


def main():
    import argparse
    parser = argparse.ArgumentParser(description='处理扬州画派书画全集李鱓书页')
    parser.add_argument('--start', type=int, default=23, help='起始页码')
    parser.add_argument('--end', type=int, default=32, help='结束页码')
    parser.add_argument('--analyze-only', action='store_true', help='仅分析不裁切')
    parser.add_argument('--process-only', action='store_true', help='仅裁切（用已有分析结果）')
    parser.add_argument('--force', action='store_true', help='强制重新分析')
    args = parser.parse_args()
    
    pages = list(range(args.start, args.end + 1))
    print(f"处理页码: {pages}")
    
    if not args.process_only:
        print("\n=== 阶段1: VL分析 ===")
        results = run_analysis(pages, force=args.force)
        print(f"\n分析完成: {len(results)} 页")
    
    if not args.analyze_only:
        print("\n=== 阶段2: 裁切保存 ===")
        # 加载结果
        if args.process_only:
            with open(RESULT_FILE, 'r', encoding='utf-8') as f:
                all_results = json.load(f)
            results = [all_results[str(p)] for p in pages if str(p) in all_results]
        
        saved = process_results(results)
        print(f"\n保存完成: {len(saved)} 个文件")
        print(f"输出目录: {OUT_DIR}")


if __name__ == '__main__':
    main()
