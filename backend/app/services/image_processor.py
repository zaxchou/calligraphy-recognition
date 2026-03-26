import cv2
import numpy as np
from PIL import Image
import io
from typing import Tuple, Optional


def binarize_image(gray: np.ndarray, threshold: int = 127) -> np.ndarray:
    """
    统一的图像二值化函数。

    自动检测背景颜色：深色背景用 THRESH_BINARY（保留浅色笔画），
    浅色背景用 THRESH_BINARY_INV（反转深色笔画为白色）。

    Args:
        gray: 灰度图像 (H, W)
        threshold: 固定阈值（默认 127）

    Returns:
        二值化图像 (H, W)，笔画区域为白色(255)，背景为黑色(0)
    """
    mean_val = np.mean(gray)
    if mean_val < threshold:
        return cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)[1]
    else:
        return cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]


class ImageProcessor:
    """图像预处理服务"""
    
    def __init__(self, target_size: Tuple[int, int] = (128, 128)):
        self.target_size = target_size
    
    def process(self, image_bytes: bytes) -> np.ndarray:
        """
        完整的图像预处理流程
        
        Args:
            image_bytes: 原始图像字节
            
        Returns:
            预处理后的图像数组 (H, W, C)
        """
        # 1. 读取图像
        image = self._load_image(image_bytes)
        
        # 2. 灰度化
        gray = self._to_grayscale(image)
        
        # 3. 去噪
        denoised = self._denoise(gray)
        
        # 4. 二值化
        binary = self._binarize(denoised)
        
        # 5. 倾斜校正
        aligned = self._deskew(binary)
        
        # 6. 提取ROI
        roi = self._extract_roi(aligned)
        
        # 7. 归一化尺寸
        normalized = self._normalize_size(roi)
        
        # 8. 转换为3通道（用于深度学习模型）
        result = cv2.cvtColor(normalized, cv2.COLOR_GRAY2RGB)
        
        return result
    
    def _load_image(self, image_bytes: bytes) -> np.ndarray:
        """加载图像"""
        image = Image.open(io.BytesIO(image_bytes))
        # 转换为RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return np.array(image)
    
    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """灰度化"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return image
    
    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """去噪处理 - 使用高斯滤波"""
        return cv2.GaussianBlur(image, (5, 5), 0)
    
    def _binarize(self, image: np.ndarray) -> np.ndarray:
        """自适应二值化 - 自动检测背景颜色"""
        # 判断背景颜色
        mean_val = np.mean(image)
        
        if mean_val < 127:
            # 深色背景（黑色背景，浅色笔画）
            # 使用THRESH_BINARY，保持浅色笔画为白色
            binary = cv2.adaptiveThreshold(
                image, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,  # 不反转：浅色笔画变为白色
                11, 2
            )
        else:
            # 浅色背景（白色背景，深色笔画）
            # 使用THRESH_BINARY_INV，将深色笔画变为白色
            binary = cv2.adaptiveThreshold(
                image, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,  # 反转：深色笔画变为白色
                11, 2
            )
        
        return binary
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """倾斜校正"""
        # 计算图像矩
        coords = np.column_stack(np.where(image > 0))
        
        if len(coords) < 10:
            return image
        
        # 计算角度
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # 如果角度很小，不需要旋转
        if abs(angle) < 0.5:
            return image
        
        # 旋转图像
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )
        
        return rotated
    
    def _extract_roi(self, image: np.ndarray) -> np.ndarray:
        """提取感兴趣区域（去除空白边框）"""
        # 查找非零像素的坐标
        coords = cv2.findNonZero(image)
        
        if coords is None:
            return image
        
        # 计算边界框
        x, y, w, h = cv2.boundingRect(coords)
        
        # 添加一些边距
        padding = 10
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        
        # 裁剪
        roi = image[y:y+h, x:x+w]
        
        return roi
    
    def _normalize_size(self, image: np.ndarray) -> np.ndarray:
        """归一化尺寸，保持纵横比"""
        h, w = image.shape[:2]
        target_h, target_w = self.target_size
        
        # 计算缩放比例
        scale = min(target_w / w, target_h / h)
        
        # 缩放
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # 创建画布并居中放置
        result = np.zeros(self.target_size, dtype=np.uint8)
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return result
    
    def get_stroke_features(self, image: np.ndarray) -> np.ndarray:
        """
        提取笔画特征（用于传统方法）
        
        Returns:
            笔画特征向量
        """
        # 骨架提取
        skeleton = self._skeletonize(image)
        
        # 计算笔画方向直方图
        hog_features = self._compute_hog(skeleton)
        
        return hog_features
    
    def _skeletonize(self, image: np.ndarray) -> np.ndarray:
        """骨架提取"""
        # 使用形态学操作提取骨架
        size = np.size(image)
        skel = np.zeros(image.shape, np.uint8)
        
        ret, img = cv2.threshold(image, 127, 255, 0)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        
        done = False
        while not done:
            eroded = cv2.erode(img, element)
            temp = cv2.dilate(eroded, element)
            temp = cv2.subtract(img, temp)
            skel = cv2.bitwise_or(skel, temp)
            img = eroded.copy()
            
            zeros = size - cv2.countNonZero(img)
            if zeros == size:
                done = True
        
        return skel
    
    def _compute_hog(self, image: np.ndarray) -> np.ndarray:
        """计算HOG特征"""
        # 简化版HOG
        gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
        
        mag, ang = cv2.cartToPolar(gx, gy)
        
        # 将角度量化为9个bin
        bins = np.int32(9 * ang / (2 * np.pi))
        
        # 计算直方图
        hist = np.zeros(9)
        for i in range(9):
            hist[i] = np.sum(mag[bins == i])
        
        # 归一化
        hist = hist / (np.linalg.norm(hist) + 1e-7)
        
        return hist
