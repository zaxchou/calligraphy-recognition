"""
补跑 LLM 元数据提取（针对上次失败的文献）
改进：更大的采样 + 更好的 JSON 解析
"""
import os, sys, asyncio, logging, json, re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from app.modules.pantianshou_composition.database import SessionLocal
from app.modules.pantianshou_composition.models import PdfBook
from app.modules.pantianshou_composition.metadata_extractor import extract_metadata

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

UUID_RE = re.compile(r'^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

def has_issues(b):
    if not b.title or UUID_RE.match(b.title.strip()):
        return True
    return not b.author or not b.journal or not b.publish_year or not b.keywords or not b.abstract or len((b.abstract or '')) < 20 or not b.source_type

async def main():
    db = SessionLocal()
    try:
        books = db.query(PdfBook).filter(
            PdfBook.document_type == 'literature',
            PdfBook.status == 'completed',
        ).all()

        todo = [b for b in books if has_issues(b)]
        logger.info(f"需要补提: {len(todo)}/{len(books)}")

        ok = 0
        for i, b in enumerate(todo):
            logger.info(f"[{i+1}/{len(todo)}] {b.file_name}")

            if not b.full_md or len(b.full_md) < 50:
                logger.warning(f"  无内容")
                continue

            meta = await extract_metadata(b.full_md, filename=b.file_name)
            if not meta:
                logger.warning(f"  提取失败")
                continue

            changed = []
            if (not b.title or UUID_RE.match(b.title.strip())) and meta.get('title'):
                b.title = meta['title']
                changed.append('title')
            if not b.author and meta.get('authors'):
                a = meta['authors']
                b.author = a[0] if isinstance(a, list) else a
                changed.append('author')
            if not b.journal and meta.get('journal'):
                b.journal = meta['journal']
                changed.append('journal')
            if not b.publish_year and meta.get('publish_year'):
                b.publish_year = meta['publish_year']
                changed.append('year')
            if not b.abstract and meta.get('abstract'):
                b.abstract = meta['abstract']
                changed.append('abstract')
            if not b.keywords and meta.get('keywords'):
                b.keywords = json.dumps(meta['keywords'], ensure_ascii=False)
                changed.append('keywords')
            if not b.source_type and meta.get('source_type'):
                b.source_type = meta['source_type']
                changed.append('source_type')

            if changed:
                ok += 1
                logger.info(f"  ✅ 更新: {changed}")
            else:
                logger.info(f"  无变化")
            db.commit()

        logger.info(f"\n完成: {ok}/{len(todo)}")

        # 最终验证
        remaining = [b for b in db.query(PdfBook).filter(PdfBook.document_type == 'literature', PdfBook.status == 'completed').all() if has_issues(b)]
        if remaining:
            logger.warning(f"仍然有 {len(remaining)} 篇不完整:")
            for b in remaining[:5]:
                logger.warning(f"  {b.file_name}: title={b.title} author={b.author} journal={b.journal}")
        else:
            logger.info("✅ 全部完整!")
    finally:
        db.close()

if __name__ == '__main__':
    asyncio.run(main())
