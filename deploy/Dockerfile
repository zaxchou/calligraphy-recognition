FROM python:3.12-slim

# Chinese mirrors for both apt and pip
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

RUN pip install --no-cache-dir \
    fastapi==0.104.1 uvicorn[standard]==0.24.0 \
    sqlalchemy==2.0.23 redis==5.0.1 celery==5.3.6 \
    python-multipart==0.0.6 pillow httpx==0.25.2 \
    opencv-python-headless==4.8.1.78 numpy==1.26.2 \
    PyMuPDF==1.25.5 scikit-learn==1.3.2 scipy==1.11.4 \
    pydantic==2.5.2 pydantic-settings==2.1.0 \
    alembic==1.12.1 python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 dashscope>=1.20.0

RUN pip install --no-cache-dir torch==2.1.1 torchvision==0.16.1 --index-url https://download.pytorch.org/whl/cpu

WORKDIR /app
COPY backend/ /app/

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
