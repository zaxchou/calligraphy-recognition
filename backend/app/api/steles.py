from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.stele import Stele
from app.models.character import Character

router = APIRouter()


@router.get("/steles")
def get_steles(
    skip: int = 0,
    limit: int = 100,
    style: str = None,
    db: Session = Depends(get_db)
):
    """
    获取碑帖列表
    
    - **skip**: 分页偏移量
    - **limit**: 每页数量
    - **style**: 按字体风格筛选（楷/行/草/隶/篆）
    """
    query = db.query(Stele)
    
    if style:
        query = query.filter(Stele.style == style)
    
    steles = query.offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "data": [
            {
                "id": s.id,
                "name": s.name,
                "dynasty": s.dynasty,
                "calligrapher": s.calligrapher,
                "style": s.style,
                "description": s.description
            }
            for s in steles
        ],
        "total": query.count()
    }


@router.get("/steles/{stele_id}")
def get_stele(stele_id: int, db: Session = Depends(get_db)):
    """获取单个碑帖详情"""
    stele = db.query(Stele).filter(Stele.id == stele_id).first()
    
    if not stele:
        raise HTTPException(status_code=404, detail="碑帖不存在")
    
    return {
        "success": True,
        "data": {
            "id": stele.id,
            "name": stele.name,
            "dynasty": stele.dynasty,
            "calligrapher": stele.calligrapher,
            "style": stele.style,
            "description": stele.description
        }
    }


@router.get("/steles/{stele_id}/characters")
def get_stele_characters(
    stele_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取碑帖包含的所有字形"""
    stele = db.query(Stele).filter(Stele.id == stele_id).first()
    
    if not stele:
        raise HTTPException(status_code=404, detail="碑帖不存在")
    
    characters = db.query(Character).filter(
        Character.stele_id == stele_id
    ).offset(skip).limit(limit).all()
    
    return {
        "success": True,
        "data": {
            "stele": {
                "id": stele.id,
                "name": stele.name
            },
            "characters": [
                {
                    "id": c.id,
                    "character": c.character,
                    "unicode": c.unicode,
                    "image_path": c.image_path,
                    "stroke_count": c.stroke_count
                }
                for c in characters
            ],
            "total": db.query(Character).filter(Character.stele_id == stele_id).count()
        }
    }


@router.get("/characters/{character_id}")
def get_character(character_id: int, db: Session = Depends(get_db)):
    """获取单个字形详情"""
    character = db.query(Character).filter(Character.id == character_id).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="字形不存在")
    
    stele = db.query(Stele).filter(Stele.id == character.stele_id).first()
    
    return {
        "success": True,
        "data": {
            "id": character.id,
            "character": character.character,
            "unicode": character.unicode,
            "image_path": character.image_path,
            "stroke_count": character.stroke_count,
            "bounding_box": character.bounding_box,
            "metadata": character.metadata,
            "stele": {
                "id": stele.id,
                "name": stele.name,
                "calligrapher": stele.calligrapher
            } if stele else None
        }
    }
