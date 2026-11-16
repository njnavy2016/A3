# ============================================================
# PdM Agent Dockerfile
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# 系统依赖：numpy/scipy 需要编译
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先安装科学计算依赖（大体积，单独层缓存）
RUN pip install --no-cache-dir numpy scipy scikit-learn

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8100

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
