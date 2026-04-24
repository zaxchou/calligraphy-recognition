"""
裁切书页图片：彻底去除白色边框，保留所有画作+题跋内容
命名规则：清_李鱓_作品名_年份.jpg（年份只取数字如1715，无年份写0000）
横向图片旋转90°
纯OCR + 正则提取（不用VL降级）
"""
import os
import sys
import json
import base64
import re
import time
from pathlib import Path
from PIL import Image
import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import dashscope
from dashscope import MultiModalConversation

dashscope.api_key = os.getenv("QWEN_API_KEY")

# 目录
SRC_DIR = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"
OUT_DIR = r"E:\李鱓全集\修改版"
ANALYSIS_FILE = Path(__file__).parent / "data" / "book_page_analysis.json"


def get_page_files(start_page=23):
    """获取排序后的页面文件列表（跳过(1)副本）"""
    files = []
    for f in os.listdir(SRC_DIR):
        if f.upper().endswith(('.JPG', '.JPEG', '.PNG')):
            if '(1)' in f:
                continue
            try:
                num = int(f.split('页')[0].replace('第', ''))
                if num >= start_page:
                    files.append((num, f))
            except (ValueError, IndexError):
                continue
    files.sort(key=lambda x: x[0])
    return files


def trim_white_borders(img, threshold=225, min_white_ratio=0.80):
    """彻底去除图片四周的白色边框"""
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    is_white = (arr[:, :, 0] > threshold) & (arr[:, :, 1] > threshold) & (arr[:, :, 2] > threshold)
    
    top = 0
    for row in range(h):
        if np.sum(is_white[row, :]) / w < min_white_ratio:
            top = row
            break
    
    bottom = h
    for row in range(h - 1, -1, -1):
        if np.sum(is_white[row, :]) / w < min_white_ratio:
            bottom = row + 1
            break
    
    left = 0
    for col in range(w):
        if np.sum(is_white[:, col]) / h < min_white_ratio:
            left = col
            break
    
    right = w
    for col in range(w - 1, -1, -1):
        if np.sum(is_white[:, col]) / h < min_white_ratio:
            right = col + 1
            break
    
    # 第二轮微调
    if right > left and bottom > top:
        arr2 = arr[top:bottom, left:right]
        h2, w2 = arr2.shape[:2]
        is_white2 = (arr2[:, :, 0] > threshold) & (arr2[:, :, 1] > threshold) & (arr2[:, :, 2] > threshold)
        
        for row in range(min(20, h2)):
            if np.sum(is_white2[row, :]) / w2 < min_white_ratio:
                top = top + row
                break
        for row in range(min(20, h2)):
            if np.sum(is_white2[h2 - 1 - row, :]) / w2 < min_white_ratio:
                bottom = bottom - row
                break
        for col in range(min(20, w2)):
            if np.sum(is_white2[:, col]) / h2 < min_white_ratio:
                left = left + col
                break
        for col in range(min(20, w2)):
            if np.sum(is_white2[:, w2 - 1 - col]) / h2 < min_white_ratio:
                right = right - col
                break
    
    if right <= left:
        left, right = 0, w
    if bottom <= top:
        top, bottom = 0, h
    
    return (left, top, right, bottom)


def is_landscape(img):
    w, h = img.size
    return w > h


def ocr_image_text(image_path):
    """用 Qwen-OCR text_recognition 识别页面所有文字"""
    try:
        with open(image_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')

        ext = os.path.splitext(image_path)[1].lower()
        mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'

        response = MultiModalConversation.call(
            model='qwen-vl-ocr',
            messages=[{
                'role': 'user',
                'content': [
                    {'image': f'data:{mime};base64,{img_b64}'},
                    {'text': '请识别图中所有文字'}
                ]
            }],
            result_format='message',
            ocr_options={'task': 'text_recognition'}
        )

        if response.status_code == 200:
            text = response.output.choices[0].message.content[0]['text']
            return text
        else:
            print(f"  OCR error: {response.code} - {response.message}")
            return None
    except Exception as e:
        print(f"  OCR识别失败: {e}")
        return None


def detect_text_orientation(image_path):
    """用 advanced_recognition 检测文字方向，返回是否需要旋转90°"""
    try:
        with open(image_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')

        ext = os.path.splitext(image_path)[1].lower()
        mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'

        response = MultiModalConversation.call(
            model='qwen-vl-ocr',
            messages=[{
                'role': 'user',
                'content': [
                    {'image': f'data:{mime};base64,{img_b64}'},
                    {'text': '请识别图中所有文字及其位置'}
                ]
            }],
            result_format='message',
            ocr_options={'task': 'advanced_recognition'}
        )

        if response.status_code != 200:
            return False, None

        raw = response.output.choices[0].message.content[0]['text']

        # 尝试解析 JSON
        try:
            if '```json' in raw:
                raw = raw.split('```json')[1].split('```')[0].strip()
            data = json.loads(raw)
        except json.JSONDecodeError:
            return False, None

        # 提取所有文字块的方向信息
        # advanced_recognition 返回结构化数据，遍历找到文本条目
        text_blocks = []

        def find_texts(obj):
            if isinstance(obj, dict):
                # 检查是否是文字条目（有文本内容）
                if 'text' in obj and obj['text'] and len(obj['text']) > 1:
                    # 尝试获取位置信息
                    bbox = obj.get('bbox') or obj.get('position') or {}
                    if bbox:
                        x = bbox.get('x', 0) or 0
                        y = bbox.get('y', 0) or 0
                        w = bbox.get('width', 0) or bbox.get('w', 0) or 0
                        h = bbox.get('height', 0) or bbox.get('h', 0) or 0
                        if w > 0 and h > 0:
                            text_blocks.append({'x': x, 'y': y, 'w': w, 'h': h})
                for v in obj.values():
                    find_texts(v)
            elif isinstance(obj, list):
                for item in obj:
                    find_texts(item)

        find_texts(data)

        if not text_blocks:
            return False, None

        # 判断文字方向：统计宽高比
        # 如果文字块普遍是 高 > 宽（竖排文字），说明文字是竖排的
        # 此时如果图片本身是横向的，则需要旋转
        portrait_text = 0  # 高 > 宽 的块数
        landscape_text = 0  # 宽 > 高 的块数

        for block in text_blocks:
            if block['h'] > block['w']:
                portrait_text += 1
            else:
                landscape_text += 1

        # 简单判断：如果竖排文字块占多数，说明文字是竖排的
        text_is_portrait = portrait_text > landscape_text

        # 旋转逻辑：只有当图片是横向(宽>高) 且 文字是竖排时，才旋转
        img = Image.open(image_path)
        img_is_landscape = img.size[0] > img.size[1]

        should_rotate = img_is_landscape and text_is_portrait

        if should_rotate:
            print(f"  [方向检测] 图片横向+竖排文字 → 需旋转90°")
        else:
            print(f"  [方向检测] 无需旋转（文字{'竖排' if text_is_portrait else '横排'}，图片{'横向' if img_is_landscape else '竖向'}）")

        return should_rotate, raw

    except Exception as e:
        print(f"  方向检测失败: {e}")
        return False, None


def extract_info_from_text(ocr_text):
    """步骤2: 用正则从 OCR 文字中提取作品名和年份（免费、快速、稳定）
    
    图注格式规律：
    - "1.石畔秋英图 轴绢 118.9cm×56.6cm 1715年 南京博物院藏"
    - "4.花卉卷局部之一"
    - "7.相对二君子 轴纸 140.9cm×51.5cm 年代不详 南京博物院藏"
    """
    result = {"page_type": "artwork", "title": "", "year": ""}
    
    # 检测是否为纯文字页（序言/目录/论文特征）
    text_markers = ['目录', '序言', '前言', '后记', '论文', '图版', '绪论', '附录', '参考']
    text_line_count = sum(1 for line in ocr_text.split('\n') if any(m in line for m in text_markers))
    long_lines = sum(1 for line in ocr_text.split('\n') if len(line.strip()) > 40)
    if text_line_count >= 2 or long_lines >= 5:
        result["page_type"] = "text"
        return result
    
    # 提取图注格式："数字.作品名"
    # 匹配如 "1.石畔秋英图"、"2. 萱花"、"4.花卉卷局部之一"
    match = re.search(r'\d+[\.\s]+(.+?)(?:\s+(?:轴|卷|扇|册|镜|屏|横|立|绢|纸|绫|本))', ocr_text)
    if match:
        result["title"] = match.group(1).strip()
    else:
        # 备选：匹配 "数字.作品名" 到行尾或空格
        match = re.search(r'\d+[\.\s]+(\S+)', ocr_text)
        if match:
            result["title"] = match.group(1).strip()
    
    # 提取年份：4位数字 + "年"
    year_match = re.search(r'(1[6-7]\d{2}|18\d{2})\s*年', ocr_text)
    if year_match:
        result["year"] = year_match.group(1)
    
    # 如果图注包含"局部"，标记为detail
    if result["title"] and '局部' in result["title"]:
        result["page_type"] = "detail"
    
    # 如果没有提取到图注格式的标题，检查是否只有零星文字（画作上的题跋）
    # 这种页面OCR结果通常是画作上的题跋文字，没有图注
    if not result["title"] and not year_match:
        # 检查OCR文字是否很短（只有画作上的零星文字）
        lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
        if len(lines) <= 3 and all(len(l) < 10 for l in lines):
            result["title"] = ""  # 未命名
        else:
            # 可能有图注但格式不标准，尝试其他提取方式
            # 找第一个看起来像作品名的短语（2-8个汉字，不含常见非作品名词）
            for line in lines:
                clean = re.sub(r'[\d\.\s]', '', line)
                if 2 <= len(clean) <= 12 and not any(w in clean for w in ['轴', '卷', '册', '博物院', '博物馆', '藏', '纸', '绢', '绫']):
                    result["title"] = clean
                    break
    
    return result


def extract_numeric_year(date_str):
    """从日期字符串中提取4位数字年份"""
    if not date_str:
        return "0000"
    match = re.search(r'(1[6-7]\d{2}|18\d{2})', str(date_str))
    if match:
        return match.group(1)
    return "0000"


def process_page(page_num, filename, analyze=True):
    """处理单页：文字方向检测 → 旋转 → 去白边 → OCR提取 → 保存"""
    src_path = os.path.join(SRC_DIR, filename)
    print(f"\n处理第{page_num}页: {filename}")
    
    # 1. 打开原图
    img = Image.open(src_path)
    original_size = img.size
    print(f"  原始: {original_size[0]}x{original_size[1]}")
    
    # 2. 用原图检测文字方向
    should_rotate = False
    ocr_raw_text = None
    
    if analyze:
        tmp_path = os.path.join(OUT_DIR, f"_tmp_p{page_num}.jpg")
        vl_img = img.copy()
        max_dim = 2000
        ow, oh = vl_img.size
        if max(ow, oh) > max_dim:
            ratio = max_dim / max(ow, oh)
            vl_img = vl_img.resize((int(ow * ratio), int(oh * ratio)), Image.LANCZOS)
        vl_img.save(tmp_path, quality=90)
        
        should_rotate, ocr_raw_text = detect_text_orientation(tmp_path)
        
        # 步骤1: OCR识别文字（用于提取标题和时间）
        ocr_text = ocr_image_text(tmp_path)
        if ocr_text:
            print(f"  OCR文字: {ocr_text[:100].replace(chr(10), ' ')}")
            # 步骤2: 正则提取
            result = extract_info_from_text(ocr_text)
            page_type = result.get('page_type', 'artwork')
            title = str(result.get('title', '') or '').strip()
            raw_year = str(result.get('year', '') or '').strip()
            year = extract_numeric_year(raw_year) if raw_year else "0000"
            print(f"  [正则提取] type={page_type}, title={title or '(空)'}, year={year}")
        else:
            page_type, title, year = "artwork", "", "0000"
        
        try:
            os.remove(tmp_path)
        except:
            pass
    else:
        page_type, title, year = "artwork", "", "0000"
    
    # 3. 根据文字方向旋转（原图先旋转，再去白边）
    rotated = False
    if should_rotate:
        img = img.rotate(-90, expand=True)
        rotated = True
        print(f"  旋转90°后: {img.size[0]}x{img.size[1]}")
    
    # 4. 去白边
    bbox = trim_white_borders(img)
    cropped = img.crop(bbox)
    print(f"  裁切后: {cropped.size[0]}x{cropped.size[1]}")
    
    # 5. 生成文件名
    # 如果OCR文字是年表（纪事表），也跳过
    if page_type == 'text' or (ocr_text and (
        ('年号' in ocr_text[:50] and '干支' in ocr_text[:50]) or
        '纪事与出处' in ocr_text[:80]
    )):
        print(f"  跳过文字页(年表/纪事表)")
        return {'page': page_num, 'type': 'text', 'title': '', 'year': year, 'saved': False}
    
    # 清理文件名中的非法字符
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title)
    
    # 过滤无效标题
    invalid_titles = ['作品名称未在图中显示', '作品名称未在页面中明确标注', '李鱓', '李鳝', '李鱼']
    if not safe_title or safe_title in invalid_titles:
        safe_title = f"未命名_p{page_num}"
    
    # Windows 文件名最长 255 字符，超长截断
    fname = f"清_李鱓_{safe_title}_{year}.jpg"
    if len(fname) > 200:
        safe_title = safe_title[:80]
        fname = f"清_李鱓_{safe_title}_{year}.jpg"
    
    # 5. 保存
    out_path = os.path.join(OUT_DIR, fname)
    
    # 如果同名文件存在，加编号
    if os.path.exists(out_path):
        base, ext = os.path.splitext(fname)
        counter = 2
        while os.path.exists(os.path.join(OUT_DIR, f"{base}_{counter}{ext}")):
            counter += 1
        fname = f"{base}_{counter}{ext}"
        out_path = os.path.join(OUT_DIR, fname)
    
    cropped.save(out_path, quality=95)
    print(f"  保存: {fname} ({cropped.size[0]}x{cropped.size[1]})")
    
    return {
        'page': page_num,
        'type': page_type,
        'title': title,
        'year': year,
        'filename': fname,
        'size': list(cropped.size),
        'rotated': rotated,
        'saved': True
    }


def main():
    start_page = 23
    max_pages = None
    skip_to = None
    
    # 参数: max_pages 或 --from=N
    for arg in sys.argv[1:]:
        if arg.startswith('--from='):
            skip_to = int(arg.split('=')[1])
        else:
            max_pages = int(arg)
    
    pages = get_page_files(start_page)
    if skip_to:
        pages = [(n, f) for n, f in pages if n >= skip_to]
    if max_pages:
        pages = pages[:max_pages]
    
    print(f"共找到 {len(pages)} 页待处理")
    print(f"提取方案: OCR(text_recognition) + 正则提取")
    print("=" * 60)
    
    results = {}
    if ANALYSIS_FILE.exists():
        with open(ANALYSIS_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
    
    for page_num, filename in pages:
        try:
            r = process_page(page_num, filename, analyze=True)
            results[str(page_num)] = r
            with open(ANALYSIS_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            time.sleep(0.5)
        except Exception as e:
            print(f"  错误: {e}")
            results[str(page_num)] = {'page': page_num, 'error': str(e)}
    
    # 打印汇总
    print("\n" + "=" * 60)
    print("处理汇总:")
    saved = [r for r in results.values() if r.get('saved')]
    skipped = [r for r in results.values() if r.get('type') == 'text']
    errors = [r for r in results.values() if r.get('error')]
    print(f"  保存: {len(saved)} 张")
    print(f"  跳过(文字页): {len(skipped)} 张")
    print(f"  错误: {len(errors)} 张")


if __name__ == '__main__':
    main()
