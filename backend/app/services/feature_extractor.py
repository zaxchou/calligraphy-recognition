import numpy as np
from PIL import Image
from typing import List, Union
import cv2

# 尝试导入PyTorch，如果失败则使用简化版
try:
    import torch
    import torch.nn as nn
    import torchvision.models as models
    import torchvision.transforms as transforms
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    print("警告: PyTorch未安装，使用简化版特征提取器")


class CalligraphyFeatureExtractor:
    """书法特征提取器 - 基于笔画结构特征"""
    
    def __init__(self, feature_dim: int = 512):
        self.feature_dim = feature_dim
    
    def extract(self, image: np.ndarray) -> np.ndarray:
        """提取图像特征"""
        return self._extract_structure_features(image)
    
    def _extract_structure_features(self, image: np.ndarray) -> np.ndarray:
        """
        提取结构特征 - 专门用于区分不同汉字的笔画结构
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        h, w = gray.shape
        
        # 确保是白色笔画在黑色背景
        mean_val = np.mean(gray)
        if mean_val > 127:
            # 如果是黑色笔画在白色背景，反转
            gray = 255 - gray
        
        # 二值化
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        features = []
        
        # 1. 笔画密度 (1维)
        stroke_pixels = np.sum(binary > 0)
        total_pixels = binary.size
        density = stroke_pixels / total_pixels
        features.append(density)
        
        # 2. 笔画分布 - 16x16 网格 (256维)
        grid_size = 16
        cell_h, cell_w = h // grid_size, w // grid_size
        for i in range(grid_size):
            for j in range(grid_size):
                cell = binary[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
                cell_density = np.sum(cell > 0) / (cell.size + 1e-7)
                features.append(cell_density)
        
        # 3. 水平投影 - 32个采样点 (32维)
        h_proj = np.sum(binary, axis=1) / 255.0
        h_proj_normalized = h_proj / (w + 1e-7)
        h_samples = np.linspace(0, len(h_proj)-1, 32, dtype=int)
        features.extend(h_proj_normalized[h_samples])
        
        # 4. 垂直投影 - 32个采样点 (32维)
        w_proj = np.sum(binary, axis=0) / 255.0
        w_proj_normalized = w_proj / (h + 1e-7)
        w_samples = np.linspace(0, len(w_proj)-1, 32, dtype=int)
        features.extend(w_proj_normalized[w_samples])
        
        # 5. 轮廓特征
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        features.append(len(contours) / 10.0)  # 轮廓数量
        
        if contours:
            areas = [cv2.contourArea(c) for c in contours]
            perimeters = [cv2.arcLength(c, True) for c in contours]
            
            features.append(np.mean(areas) / (h * w))
            features.append(np.std(areas) / (h * w) if len(areas) > 1 else 0)
            features.append(np.mean(perimeters) / (h + w))
        else:
            features.extend([0, 0, 0])
        
        # 6. 方向特征 - 检测主要笔画方向 (8维)
        gx = cv2.Sobel(binary, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(binary, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy)
        
        # 8个方向直方图
        direction_hist = np.zeros(8)
        for i in range(8):
            mask = ((ang >= i * np.pi / 4) & (ang < (i + 1) * np.pi / 4))
            direction_hist[i] = np.sum(mag[mask])
        
        if np.sum(direction_hist) > 0:
            direction_hist = direction_hist / np.sum(direction_hist)
        features.extend(direction_hist)
        
        # 7. 角点特征 (4维)
        corners = cv2.goodFeaturesToTrack(binary, 100, 0.01, 10)
        if corners is not None:
            features.append(len(corners) / 100.0)
            
            # 角点分布
            corner_y = corners[:, 0, 1]
            corner_x = corners[:, 0, 0]
            features.append(np.mean(corner_y) / h)
            features.append(np.mean(corner_x) / w)
            features.append(np.std(corner_y) / h + np.std(corner_x) / w)
        else:
            features.extend([0, 0.5, 0.5, 0])
        
        # 8. 连通域特征 (4维)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        features.append((num_labels - 1) / 10.0)  # 减去背景
        
        if num_labels > 1:
            areas = stats[1:, cv2.CC_STAT_AREA]
            features.append(np.mean(areas) / (h * w))
            features.append(np.max(areas) / (h * w))
            
            # 连通域位置方差
            lefts = stats[1:, cv2.CC_STAT_LEFT] / w
            tops = stats[1:, cv2.CC_STAT_TOP] / h
            features.append(np.std(lefts) + np.std(tops))
        else:
            features.extend([0, 0, 0])
        
        # 9. 边缘密度 - 4个象限 (4维)
        edges = cv2.Canny(binary, 50, 150)
        for i in range(2):
            for j in range(2):
                quadrant = edges[i*h//2:(i+1)*h//2, j*w//2:(j+1)*w//2]
                features.append(np.sum(quadrant > 0) / (quadrant.size + 1e-7))
        
        # 10. 骨架特征 - 细化后的笔画 (16维)
        skeleton = self._skeletonize(binary)
        # 骨架的4x4网格密度
        for i in range(4):
            for j in range(4):
                cell = skeleton[i*h//4:(i+1)*h//4, j*w//4:(j+1)*w//4]
                features.append(np.sum(cell > 0) / (cell.size + 1e-7))
        
        # 11. 对称性特征 (4维)
        # 水平对称性
        h_sym = np.sum(binary[:, :w//2] == np.fliplr(binary[:, w//2:])) / binary.size
        features.append(h_sym)
        
        # 垂直对称性
        v_sym = np.sum(binary[:h//2, :] == np.flipud(binary[h//2:, :])) / binary.size
        features.append(v_sym)
        
        # 对角线对称性
        diag1_sym = np.sum(binary == binary.T) / binary.size
        features.append(diag1_sym)
        
        # 反对角线对称性
        flipped = np.fliplr(binary)
        diag2_sym = np.sum(binary == flipped.T) / binary.size
        features.append(diag2_sym)
        
        # 12. 笔画端点特征 (8维)
        endpoints = self._find_endpoints(skeleton)
        features.append(len(endpoints) / 20.0)
        
        if endpoints:
            endpoint_y = [e[0] for e in endpoints]
            endpoint_x = [e[1] for e in endpoints]
            features.append(np.mean(endpoint_y) / h)
            features.append(np.mean(endpoint_x) / w)
            features.append(np.std(endpoint_y) / h)
            features.append(np.std(endpoint_x) / w)
            
            # 端点分布 - 上下左右
            top_endpoints = sum(1 for y, x in endpoints if y < h / 3)
            bottom_endpoints = sum(1 for y, x in endpoints if y > 2 * h / 3)
            left_endpoints = sum(1 for y, x in endpoints if x < w / 3)
            right_endpoints = sum(1 for y, x in endpoints if x > 2 * w / 3)
            
            total = len(endpoints) + 1e-7
            features.extend([
                top_endpoints / total,
                bottom_endpoints / total,
                left_endpoints / total,
                right_endpoints / total
            ])
        else:
            features.extend([0.5, 0.5, 0, 0, 0, 0, 0, 0])
        
        # 转换为numpy数组
        features = np.array(features, dtype=np.float32)
        
        # 如果特征维度不够，补零
        if len(features) < self.feature_dim:
            features = np.pad(features, (0, self.feature_dim - len(features)), 'constant')
        elif len(features) > self.feature_dim:
            features = features[:self.feature_dim]
        
        return features
    
    def _skeletonize(self, binary: np.ndarray) -> np.ndarray:
        """图像细化（骨架提取）"""
        # 使用OpenCV的形态学操作进行细化
        size = np.size(binary)
        skel = np.zeros(binary.shape, np.uint8)
        
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        done = False
        
        while not done:
            eroded = cv2.erode(binary, element)
            temp = cv2.dilate(eroded, element)
            temp = cv2.subtract(binary, temp)
            skel = cv2.bitwise_or(skel, temp)
            binary = eroded.copy()
            
            zeros = size - cv2.countNonZero(binary)
            if zeros == size:
                done = True
        
        return skel
    
    def _find_endpoints(self, skeleton: np.ndarray) -> List[tuple]:
        """找到骨架的端点"""
        endpoints = []
        h, w = skeleton.shape
        
        for y in range(1, h-1):
            for x in range(1, w-1):
                if skeleton[y, x] > 0:
                    # 计算8邻域内的笔画像素数
                    neighbors = 0
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dy == 0 and dx == 0:
                                continue
                            if skeleton[y+dy, x+dx] > 0:
                                neighbors += 1
                    
                    # 端点只有一个邻居
                    if neighbors == 1:
                        endpoints.append((y, x))
        
        return endpoints
    
    def extract_batch(self, images: List[np.ndarray]) -> np.ndarray:
        """批量提取特征"""
        features_list = []
        for image in images:
            features = self.extract(image)
            features_list.append(features)
        return np.array(features_list)
    
    def extract_description(self, image: np.ndarray) -> str:
        """提取特征描述（用于 AI 分析）"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # 确保是白色笔画在黑色背景
        mean_val = np.mean(gray)
        if mean_val > 127:
            gray = 255 - gray
        
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        h, w = binary.shape
        
        description = []
        description.append(f"图像尺寸: {w}x{h}")
        
        # 笔画密度
        density = np.sum(binary > 0) / binary.size
        description.append(f"笔画密度: {density:.2%}")
        
        # 轮廓分析
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        description.append(f"轮廓数量: {len(contours)}")
        
        # 九宫格区域密度
        description.append("九宫格区域笔画密度:")
        cell_h, cell_w = h // 3, w // 3
        for i in range(3):
            for j in range(3):
                cell = binary[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
                cell_density = np.sum(cell > 0) / cell.size
                pos = ["上", "中", "下"][i] + ["左", "中", "右"][j]
                description.append(f"  {pos}: {cell_density:.2%}")
        
        # 方向分析
        gx = cv2.Sobel(binary, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(binary, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy)
        
        directions = []
        for i in range(4):
            mask = ((ang >= i * np.pi / 4) & (ang < (i + 1) * np.pi / 4))
            strength = np.sum(mag[mask])
            if strength > mag.sum() * 0.15:
                directions.append(["水平", "右上-左下", "垂直", "左上-右下"][i])
        
        if directions:
            description.append(f"主要笔画方向: {', '.join(directions)}")
        
        # 角点检测
        corners = cv2.goodFeaturesToTrack(binary, 100, 0.01, 10)
        corner_count = len(corners) if corners is not None else 0
        description.append(f"角点数量: {corner_count}")
        
        # 对称性
        h_sym = np.sum(binary[:, :w//2] == np.fliplr(binary[:, w//2:])) / binary.size
        v_sym = np.sum(binary[:h//2, :] == np.flipud(binary[h//2:, :])) / binary.size
        description.append(f"对称性: 水平{h_sym:.2%}, 垂直{v_sym:.2%}")
        
        return "\n".join(description)


class SimpleFeatureExtractor:
    """简化版特征提取器"""
    
    def __init__(self, feature_dim: int = 512):
        self.feature_dim = feature_dim
        self.extractor = CalligraphyFeatureExtractor(feature_dim)
    
    def extract(self, image: np.ndarray) -> np.ndarray:
        """提取特征"""
        return self.extractor.extract(image)
    
    def extract_description(self, image: np.ndarray) -> str:
        """提取特征描述"""
        return self.extractor.extract_description(image)
