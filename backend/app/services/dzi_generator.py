"""
Deep Zoom Image (DZI) generator using PIL.
Generates tile pyramid compatible with OpenSeadragon.
"""
import os
import math
import logging
from PIL import Image

# Allow very large images (e.g. 200MB scans)
Image.MAX_IMAGE_PIXELS = None

logger = logging.getLogger(__name__)

TILE_SIZE = 256
TILE_OVERLAP = 1
IMAGE_FORMAT = "jpg"
QUALITY = 85


def _get_num_levels(width: int, height: int) -> int:
    """Calculate number of pyramid levels needed"""
    max_dim = max(width, height)
    return math.ceil(math.log2(max_dim)) + 1


def generate_dzi(filepath: str, dzi_dir: str) -> str | None:
    """
    Generate DZI tiles from an image file.
    
    Args:
        filepath: Path to source image
        dzi_dir: Output directory for DZI files (e.g. backend/data/dzi/{name}/)
    
    Returns:
        Path to .dzi descriptor file, or None on failure
    """
    try:
        base_name = os.path.splitext(os.path.basename(filepath))[0]
        out_dir = os.path.join(dzi_dir, f"{base_name}_files")
        os.makedirs(out_dir, exist_ok=True)
        
        with Image.open(filepath) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            width, height = img.size
        
        num_levels = _get_num_levels(width, height)
        
        # Build pyramid from top (smallest) to bottom (full size)
        for level in range(num_levels):
            scale = 1.0 / (2 ** (num_levels - 1 - level))
            level_w = max(1, int(width * scale))
            level_h = max(1, int(height * scale))
            
            level_dir = os.path.join(out_dir, str(level))
            os.makedirs(level_dir, exist_ok=True)
            
            with Image.open(filepath) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                resampled = img.resize((level_w, level_h), Image.Resampling.LANCZOS)
            
            cols = math.ceil(level_w / TILE_SIZE)
            rows = math.ceil(level_h / TILE_SIZE)
            
            for row in range(rows):
                for col in range(cols):
                    left = col * TILE_SIZE
                    top = row * TILE_SIZE
                    right = min(left + TILE_SIZE + TILE_OVERLAP, level_w)
                    bottom = min(top + TILE_SIZE + TILE_OVERLAP, level_h)
                    
                    tile = resampled.crop((left, top, right, bottom))
                    tile_path = os.path.join(level_dir, f"{col}_{row}.{IMAGE_FORMAT}")
                    tile.save(tile_path, "JPEG", quality=QUALITY)
                    
                    tile.close()
            
            resampled.close()
        
        # Generate DZI descriptor XML
        dzi_path = os.path.join(dzi_dir, f"{base_name}.dzi")
        with open(dzi_path, "w", encoding="utf-8") as f:
            f.write(f'''<?xml version="1.0" encoding="utf-8"?>
<Image xmlns="http://schemas.microsoft.com/deepzoom/2008"
       TileSize="{TILE_SIZE}"
       Overlap="{TILE_OVERLAP}"
       Format="{IMAGE_FORMAT}">
  <Size Width="{width}" Height="{height}"/>
</Image>''')
        
        logger.info("DZI generated: %s (%d levels, %dx%d)", dzi_path, num_levels, width, height)
        return dzi_path
    
    except Exception as e:
        logger.error("DZI generation failed for %s: %s", filepath, e)
        return None
