from typing import List, Optional
import os
import tempfile

from fastapi import APIRouter, Query, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.services.image_search import get_search_engine, SearchHit

router = APIRouter()


class SearchResult(BaseModel):
    id: int
    title: str
    artist: str
    score: float
    thumbnail_url: str
    year: Optional[int] = None
    album_name: Optional[str] = None
    inscription_percent: Optional[float] = None


class DuplicatePairItem(BaseModel):
    id: Optional[int] = None
    title: str
    artist: str
    thumbnail_url: str
    year: Optional[int] = None


class DuplicatePair(BaseModel):
    score: float
    a: DuplicatePairItem
    b: DuplicatePairItem


class SearchResponse(BaseModel):
    hits: List[SearchResult]
    total_indexed: int


class RebuildResponse(BaseModel):
    ok: bool
    total: int
    skipped: int
    elapsed: float


@router.post("/search", response_model=SearchResponse)
async def search_similar(
    image: UploadFile = File(...),
    top_k: int = Query(default=10, le=20),
):
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="未收到图片数据")

    suffix = ".jpg"
    if image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            suffix = ext

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(contents)
        tmp.close()

        engine = get_search_engine()
        hits = engine.search(tmp.name, top_k=top_k)
    finally:
        os.unlink(tmp.name)

    return SearchResponse(
        hits=[SearchResult(**{k: v for k, v in h.__dict__.items() if k in SearchResult.model_fields}) for h in hits],
        total_indexed=engine.total_indexed,
    )


@router.get("/duplicates", response_model=List[DuplicatePair])
async def find_duplicates(
    threshold: float = Query(default=0.95, ge=0.80, le=1.0),
):
    engine = get_search_engine()
    pairs = engine.find_duplicates(threshold=threshold)
    return pairs


@router.post("/rebuild-index", response_model=RebuildResponse)
async def rebuild_index(
    artist: str = Query(default="all"),
):
    engine = get_search_engine()
    result = engine.build_index(artist=artist)
    return result
