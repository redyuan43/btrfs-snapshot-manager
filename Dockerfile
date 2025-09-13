FROM python:3.11-slim-bookworm

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    btrfs-progs \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/logs /app/data

# 设置环境变量
ENV PYTHONPATH=/app
ENV FLASK_APP=api_server.py
ENV FLASK_ENV=production

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

# 启动命令
CMD ["python", "api_server.py", "-c", "/app/config/production.yaml", "--host", "0.0.0.0", "--port", "5000"]