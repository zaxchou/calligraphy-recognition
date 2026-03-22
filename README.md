# 书法碑帖字体认证系统

基于深度学习的书法碑帖字体认证系统，用户上传书法图片，系统识别出自哪个碑帖，并显示相似度百分比。

## 功能特点

- **智能识别**：基于深度学习和图像处理技术，精准识别书法字体
- **碑帖匹配**：匹配数据库中的碑帖字形，返回相似度百分比
- **多字体支持**：支持楷、行、草、隶、篆等多种字体风格
- **可视化界面**：友好的Web界面，支持图片上传和结果展示

## 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   前端界面   │────▶│   API服务   │────▶│  图像处理   │
│  (Vue3)     │     │  (FastAPI)  │     │  (OpenCV)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                       ┌─────────────┐         │
                       │  数据库     │◀────────┤
                       │ (PostgreSQL)│         │
                       └─────────────┘         │
                                                │
                       ┌─────────────┐         │
                       │  特征匹配   │◀────────┘
                       │  (FAISS)    │
                       └─────────────┘
```

## 技术栈

### 后端
- **FastAPI**: 高性能Web框架
- **SQLAlchemy**: ORM数据库操作
- **OpenCV**: 图像处理
- **PyTorch**: 深度学习（可选）
- **FAISS**: 向量相似度搜索
- **PostgreSQL**: 主数据库

### 前端
- **Vue 3**: 前端框架
- **Element Plus**: UI组件库
- **Axios**: HTTP客户端
- **Vite**: 构建工具

## 快速开始

### 1. 克隆项目

```bash
cd calligraphy-recognition
```

### 2. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 配置数据库

修改 `backend/app/core/config.py` 中的数据库连接字符串：

```python
DATABASE_URL = "postgresql://username:password@localhost:5432/calligraphy"
```

### 4. 初始化数据

```bash
cd backend
python scripts/init_data.py
```

### 5. 启动后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 安装前端依赖

```bash
cd frontend
npm install
```

### 7. 启动前端服务

```bash
cd frontend
npm run dev
```

### 8. 访问系统

打开浏览器访问 http://localhost:3000

## API接口

### 识别接口

**POST** `/api/v1/recognize`

上传图片进行识别

**请求参数**:
- `file`: 图片文件 (multipart/form-data)

**响应示例**:
```json
{
  "success": true,
  "data": {
    "recognized_character": "大",
    "similarity": 92.5,
    "best_match": {
      "stele": {
        "name": "雁塔圣教序",
        "calligrapher": "褚遂良",
        "style": "楷书"
      }
    },
    "top_matches": [...]
  }
}
```

### 碑帖接口

**GET** `/api/v1/steles`

获取碑帖列表

**GET** `/api/v1/steles/{id}`

获取碑帖详情

**GET** `/api/v1/steles/{id}/characters`

获取碑帖字形列表

## 项目结构

```
calligraphy-recognition/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   │   ├── image_processor.py    # 图像处理
│   │   │   ├── feature_extractor.py  # 特征提取
│   │   │   └── matcher.py            # 相似度匹配
│   │   └── main.py         # 入口文件
│   ├── scripts/            # 脚本工具
│   └── requirements.txt    # 依赖列表
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/           # API接口
│   │   ├── views/         # 页面视图
│   │   └── router/        # 路由配置
│   └── package.json
├── data/                   # 数据文件
│   ├── uploads/           # 上传图片
│   └── static/            # 静态资源
└── README.md
```

## 核心算法

### 图像预处理流程

1. **灰度化**: 将彩色图像转换为灰度图
2. **去噪**: 使用高斯滤波去除噪声
3. **二值化**: 自适应阈值二值化
4. **倾斜校正**: 基于矩的倾斜校正
5. **ROI提取**: 提取感兴趣区域
6. **归一化**: 统一尺寸为128x128

### 特征提取

- **CNN特征**: 使用ResNet50提取深度特征
- **笔画特征**: HOG方向梯度直方图
- **结构特征**: Hu矩、投影特征、区域密度
- **融合策略**: 加权融合多层级特征

### 相似度匹配

- **余弦相似度**: 计算向量夹角余弦值
- **FAISS索引**: 高效向量检索
- **Top-K搜索**: 返回最相似的K个结果

## 演示数据

系统预置了《雁塔圣教序》作为演示碑帖，包含10个示例汉字：
- 大、唐、三、藏、圣、教、序、皇、帝、文

## 扩展开发

### 添加新碑帖

1. 在数据库中添加碑帖记录
2. 准备碑帖字形图片
3. 运行特征提取脚本
4. 重建FAISS索引

### 优化识别精度

1. 收集更多训练数据
2. 微调深度学习模型
3. 调整特征权重
4. 优化相似度阈值

## 许可证

MIT License

## 联系方式

如有问题或建议，欢迎提交Issue。
