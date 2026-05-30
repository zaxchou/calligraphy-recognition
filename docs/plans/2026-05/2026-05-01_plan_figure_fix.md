# Plan: 插图查找链路彻底修复

## 审计结论（完整事实）

| 数据源 | 状态 | 备注 |
|--------|------|------|
| `extracted/` 目录 | **不存在** | `_build_cache()` 永远返回空 |
| `figure_metadata.json` | 109条目，98有`image_path` | 路径指向已删除的旧PDF文件，全部`exists=False` |
| Qdrant `knowledge_images` | **611条，全部`source=pdf_upload`** | figure_id=`img_pXX`，有`image_path`字段(= `/api/v1/knowledge/images/{book_id}/{filename}`) |
| Qdrant `source=pan.md` | **0条** | PDF重传后collection重建，旧数据丢失 |
| Qdrant `source=bird_flower_tutorial` | **0条** | 同上 |
| SQLite `composition_rules` | 202条，`reference_figures`=`["图一","图二"...]` | 中文图号，与Qdrant `img_pXX` 无法直接匹配 |

**根因链**：`reference_figures=图一/图二` → `figure_image_url()` 查 `extracted/mapping.json`(不存在)→None → `figure_image_url_from_qdrant()` 查 Qdrant filter `figure_id=图一`(0条pan.md)→Miss → `_build_qdrant_cache` fallback 读 `image_url/stored_url`(不存在)→读 `image_path`(最新修复)→**500点但有ID无法匹配**→最终返回 `__fallback__`

## 修复方案

**不匹配就不匹配**——PDF提取的611张图本身就是潘天寿《关于构图问题》的插图。用本地文件路径生成 `/static/` URL，绕过 Qdrant `image_path` 的 API 路径。

### 单文件改动：figure_assets.py

```python
def _build_qdrant_cache():
    # 1. 从 Qdrant 取全部 points（已有）
    # 2. 对每个 point，取 figure_id + book_id，然后查本地磁盘
    #    disk_path = data/knowledge/books/images/{book_id}/
    #    取第一个 .png/.jpg → build_static_url(relative_path)
    # 3. 生成 {figure_id: url} 缓存
    # 4. 精确匹配 → 中文数字模糊匹配 → 随机 fallback

def _build_qdrant_cache() -> Dict[str, str]:
    from app.modules.pantianshou_composition.qdrant_client import scroll_by_filter, KNOWLEDGE_IMAGES_COLLECTION
    from app.modules.pantianshou_composition.storage import build_static_url
    pts = scroll_by_filter(KNOWLEDGE_IMAGES_COLLECTION, {}, limit=500)
    out = {}
    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    images_base = os.path.join(base_data_dir, "knowledge", "books", "images")
    
    for pt in (pts or []):
        p = pt.get("payload") or {}
        fid = p.get("figure_id", "")
        book_id = p.get("book_id", "")
        # Try to find actual file on disk
        book_img_dir = os.path.join(images_base, book_id)
        files = []
        if os.path.isdir(book_img_dir):
            files = [f for f in os.listdir(book_img_dir) if f.endswith(('.png','.jpg','.jpeg'))]
        if files:
            img_path = os.path.join(book_img_dir, files[0])
            rel = os.path.relpath(img_path, base_data_dir)
            url = build_static_url(rel)
            out[str(fid)] = url
        else:
            # Fallback: use Qdrant image_path as last resort
            url = p.get("image_path") or ""
            if fid and url:
                out[str(fid)] = url
    
    _plog(f"qdrant_cache: {len(pts)} pts, {len(out)} with url")
    return out
```

**效果**：
- 每条 `img_pXX` 映射到本地磁盘图片 → `/static/knowledge/books/images/{book_id}/page_X_img_Y.png`
- 中文数字模糊匹配(图二→匹配含"二"的key) + 最终 fallback 返回任意图
- URL 是 `/static/...` 格式，生产和开发模式都可用

### 代码量
~40 行，只改 `figure_assets.py` 一个文件
