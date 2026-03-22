from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import time
import os
import uuid

from app.core.database import get_db
from app.core.config import get_settings
from app.core.path_utils import get_static_url, get_full_file_path
from app.services.image_processor import ImageProcessor
from app.services.feature_extractor import SimpleFeatureExtractor
from app.services.simple_matcher import SimpleMatcher
from app.services.enhanced_matcher import get_enhanced_matcher
from app.services.siliconflow_recognition_service import get_siliconflow_recognition_service
from app.services.ocr_service import get_ocr_service
from app.models.recognition_log import RecognitionLog

router = APIRouter()
settings = get_settings()

# 初始化服务
image_processor = ImageProcessor(target_size=(128, 128))
feature_extractor = SimpleFeatureExtractor(feature_dim=512)
matcher = SimpleMatcher()
enhanced_matcher = get_enhanced_matcher()
ocr_service = get_ocr_service()
siliconflow_service = get_siliconflow_recognition_service()


@router.post("/recognize")
async def recognize_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    识别上传的书法图片（使用 SiliconFlow AI + Kimi-K2.5 模型）
    
    - **file**: 书法图片文件（支持jpg、png等格式）
    
    返回识别结果，包括最匹配的碑帖、相似度百分比等
    """
    start_time = time.time()
    
    # 验证文件类型
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/bmp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="不支持的文件类型，请上传图片文件")
    
    try:
        # 读取上传的图片
        contents = await file.read()
        
        # 保存上传的图片
        upload_dir = settings.UPLOAD_DIR
        os.makedirs(upload_dir, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1] or '.jpg'
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)

        with open(file_path, 'wb') as f:
            f.write(contents)
        
        # 图像预处理
        processed_image = image_processor.process(contents)
        
        # 提取特征
        feature_vector = feature_extractor.extract(processed_image)

        # 特征匹配 - 使用简单匹配器获取候选字符
        match_result = matcher.match(
            feature_vector, 
            db, 
            top_k=5,
            threshold=settings.SIMILARITY_THRESHOLD
        )
        
        # 获取候选字符列表
        candidates = []
        if match_result.get('top_matches'):
            candidates = [m['character'] for m in match_result['top_matches'][:5]]
        
        print(f"特征匹配结果: {match_result.get('recognized_character')}, 相似度: {match_result.get('similarity')}")
        print(f"Top 5 候选: {candidates}")
        
        # SiliconFlow AI 识别（使用 Kimi-K2.5 模型，直接图像输入）
        ai_result = None
        final_character = None
        final_confidence = 0
        recognition_method = "feature_match"
        
        try:
            # 使用 SiliconFlow 进行图像识别
            ai_result = siliconflow_service.recognize_character(
                image_bytes=contents,
                candidates=candidates if candidates else None
            )
            
            print(f"SiliconFlow AI 识别结果: {ai_result}")
            
            if ai_result.get('success'):
                ai_character = ai_result.get('character', '').strip()
                ai_confidence = ai_result.get('confidence', 0)
                
                # 优先使用 AI 结果（如果 AI 置信度较高）
                if ai_confidence >= 60:
                    final_character = ai_character
                    final_confidence = ai_confidence
                    recognition_method = "ai_primary"
                else:
                    # AI 置信度不高，使用特征匹配结果
                    final_character = match_result.get('recognized_character', '')
                    final_confidence = match_result.get('similarity', 0)
                    recognition_method = "feature_primary"
                
                # 更新识别结果
                match_result['recognized_character'] = final_character
                match_result['ai_confidence'] = ai_confidence
                match_result['ai_reason'] = ai_result.get('reason', '')
                match_result['similarity'] = final_confidence
                
                # 重新查找最佳匹配的字形信息
                from app.models.character import Character
                from app.models.stele import Stele
                
                correct_char_record = db.query(Character).filter(
                    Character.character == final_character
                ).first()
                
                if correct_char_record:
                    stele = db.query(Stele).filter(
                        Stele.id == correct_char_record.stele_id
                    ).first()
                    
                    match_result['best_match'] = {
                        'character_id': correct_char_record.id,
                        'character': correct_char_record.character,
                        'image_path': correct_char_record.image_path,
                        'unicode': correct_char_record.unicode,
                        'stele': {
                            'id': stele.id,
                            'name': stele.name,
                            'dynasty': stele.dynasty,
                            'calligrapher': stele.calligrapher,
                            'style': stele.style
                        } if stele else None
                    }
            else:
                print(f"AI 识别失败: {ai_result.get('error')}")
                # AI 失败，使用特征匹配结果
                final_character = match_result.get('recognized_character', '')
                final_confidence = match_result.get('similarity', 0)
                
        except Exception as e:
            print(f"SiliconFlow AI 识别失败: {e}")
            import traceback
            traceback.print_exc()
            match_result['ai_error'] = str(e)
            # AI 失败，使用特征匹配结果
            final_character = match_result.get('recognized_character', '')
            final_confidence = match_result.get('similarity', 0)
        
        # OCR识别（作为辅助信息）
        ocr_result = None
        try:
            ocr_result = ocr_service.recognize_single_char(contents)
            print(f"OCR识别结果: {ocr_result}")
        except Exception as e:
            print(f"OCR识别失败: {e}")
        
        # 计算处理时间
        processing_time = int((time.time() - start_time) * 1000)
        
        # 保存识别记录（只要有识别结果就保存，不管特征匹配是否成功）
        if final_character:
            # 获取碑帖ID
            matched_stele_id = None
            if match_result.get('best_match') and match_result['best_match'].get('stele'):
                matched_stele_id = match_result['best_match']['stele']['id']
            
            # 存储标准化路径到数据库（使用正斜杠）
            from app.core.path_utils import normalize_path
            log = RecognitionLog(
                uploaded_image_path=normalize_path(file_path),
                recognized_character=final_character,
                matched_stele_id=matched_stele_id,
                similarity_score=final_confidence,
                top_matches=match_result.get('top_matches', []),
                processing_time_ms=processing_time
            )
            db.add(log)
            db.commit()
            print(f"识别记录已保存: {final_character}, 相似度: {final_confidence}")
        
        # 组装返回结果 - 使用跨平台路径处理
        result = {
            "success": True,
            "data": {
                **match_result,
                "processing_time_ms": processing_time,
                "uploaded_image_url": get_static_url(f"uploads/{unique_filename}"),
                "recognition_method": recognition_method,
                "ocr_result": ocr_result,
                "ai_result": ai_result
            }
        }
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@router.post("/search")
async def search_similar(
    file: UploadFile = File(...),
    top_k: int = 5,
    db: Session = Depends(get_db)
):
    """
    搜索相似字形（不指定具体碑帖）
    
    - **file**: 书法图片文件
    - **top_k**: 返回结果数量（默认5个）
    """
    try:
        # 读取图片
        contents = await file.read()
        
        # 预处理
        processed_image = image_processor.process(contents)
        
        # 提取特征
        feature_vector = feature_extractor.extract(processed_image)
        
        # 特征匹配
        result = matcher.match(feature_vector, db, top_k=top_k)
        
        return {
            "success": True,
            "data": {
                "results": result.get('top_matches', []),
                "total": len(result.get('top_matches', []))
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")


@router.get("/recognition/history")
async def get_recognition_history(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
):
    """
    获取识别历史记录
    
    - **page**: 页码（从1开始）
    - **page_size**: 每页数量
    """
    try:
        from app.models.stele import Stele
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 查询总数
        total = db.query(RecognitionLog).count()
        
        # 查询记录
        logs = db.query(RecognitionLog).order_by(
            RecognitionLog.created_at.desc()
        ).offset(offset).limit(page_size).all()
        
        # 组装结果
        results = []
        for log in logs:
            result_item = {
                "id": log.id,
                "uploaded_image_path": log.uploaded_image_path,
                "recognized_character": log.recognized_character,
                "similarity_score": log.similarity_score,
                "processing_time_ms": log.processing_time_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "top_matches": log.top_matches
            }
            
            # 查询碑帖信息
            if log.matched_stele_id:
                stele = db.query(Stele).filter(Stele.id == log.matched_stele_id).first()
                if stele:
                    result_item["best_match"] = {
                        "stele": {
                            "id": stele.id,
                            "name": stele.name,
                            "dynasty": stele.dynasty,
                            "calligrapher": stele.calligrapher,
                            "style": stele.style
                        }
                    }
            
            results.append(result_item)
        
        return {
            "success": True,
            "data": results,
            "total": total,
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")


@router.delete("/recognition/history/{log_id}")
async def delete_recognition_history(
    log_id: int,
    db: Session = Depends(get_db)
):
    """
    删除识别历史记录
    
    - **log_id**: 记录ID
    """
    try:
        log = db.query(RecognitionLog).filter(RecognitionLog.id == log_id).first()
        
        if not log:
            raise HTTPException(status_code=404, detail="记录不存在")
        
        # 删除关联的图片文件 - 使用跨平台路径处理
        if log.uploaded_image_path:
            # 将存储的路径转换为本地路径
            file_path = get_full_file_path(log.uploaded_image_path, settings.UPLOAD_DIR)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"删除图片文件失败: {e}")
        
        db.delete(log)
        db.commit()
        
        return {
            "success": True,
            "message": "删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
