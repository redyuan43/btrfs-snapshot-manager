#!/bin/bash

# 强制重新部署脚本 - 完全重新开始
# 解决Git和Docker缓存问题

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

DEPLOY_DIR="/opt/btrfs-snapshot-manager"
GITHUB_REPO="https://github.com/redyuan43/btrfs-snapshot-manager.git"

log "🚀 强制重新部署Btrfs快照管理器..."

# 检查root权限
if [[ $EUID -ne 0 ]]; then
    error "此脚本需要root权限运行"
    error "请使用: sudo bash force_deploy.sh"
    exit 1
fi

# 停止并删除所有相关容器
log "停止所有相关服务..."
cd "$DEPLOY_DIR" 2>/dev/null && docker-compose down --remove-orphans 2>/dev/null || true
docker stop $(docker ps -q --filter "name=btrfs") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=btrfs") 2>/dev/null || true

# 清理Docker资源
log "清理Docker资源..."
docker system prune -f
docker volume prune -f

# 完全删除旧部署目录
log "删除旧部署目录..."
rm -rf "$DEPLOY_DIR"

# 重新克隆代码
log "重新克隆最新代码..."
git clone "$GITHUB_REPO" "$DEPLOY_DIR"
cd "$DEPLOY_DIR"

# 确保使用main分支的最新代码
git checkout main
git pull origin main

log "当前代码版本:"
git log --oneline -1

# 验证关键文件存在
log "验证关键文件..."
required_files=(
    "requirements.txt"
    "Dockerfile"
    "docker-compose.yml"
    "api_server.py"
    "btrfs_snapshot_manager.py"
)

for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
        info "✅ $file 存在"
    else
        error "❌ $file 缺失"
        exit 1
    fi
done

# 创建必要目录
log "创建必要目录..."
mkdir -p /data/{monitored,snapshots}
mkdir -p /var/log/btrfs-snapshot-manager
mkdir -p logs config

# 创建生产环境配置
log "创建生产环境配置..."
cat > config/production.yaml << 'EOF'
# 生产环境配置
watch_dir: /data/monitored
snapshot_dir: /data/snapshots
max_snapshots: 50
cleanup_mode: count
retention_days: 30
cooldown_seconds: 300
debounce_seconds: 10
log_file: /var/log/btrfs-snapshot-manager/snapshot.log
log_level: INFO
test_mode: false

# API服务配置
api:
  host: 0.0.0.0
  port: 5000
  debug: false
  cors_origins: ["*"]

# 安全配置
security:
  api_key_required: false
  max_snapshots_per_hour: 12

# 监控配置
monitoring:
  enable_metrics: true
  metrics_retention_hours: 72
EOF

# 验证Docker Compose配置
log "验证Docker Compose配置..."
docker-compose config > /dev/null

# 构建镜像（不使用缓存）
log "构建Docker镜像（不使用缓存）..."
docker-compose build --no-cache --pull

# 启动服务
log "启动服务..."
docker-compose up -d

# 等待服务启动
log "等待服务启动..."
sleep 20

# 验证部署
log "验证部署状态..."

# 检查容器状态
if docker-compose ps | grep -q "Up"; then
    log "✅ 容器启动成功"
    docker-compose ps
else
    error "❌ 容器启动失败"
    echo "容器状态:"
    docker-compose ps
    echo "容器日志:"
    docker-compose logs
    exit 1
fi

# 检查API健康状态
info "检查API健康状态..."
for i in {1..60}; do
    if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
        log "✅ API服务健康检查通过"
        break
    fi

    if [[ $i -eq 60 ]]; then
        error "❌ API服务健康检查失败"
        echo "API容器日志:"
        docker-compose logs btrfs-api
        exit 1
    fi

    if [[ $((i % 10)) -eq 0 ]]; then
        info "等待API服务启动... ($i/60)"
    fi
    sleep 2
done

# 检查Web界面
info "检查Web界面..."
if curl -s http://localhost:8080 > /dev/null 2>&1; then
    log "✅ Web界面访问正常"
else
    warning "⚠️ Web界面可能存在问题"
    echo "Web容器日志:"
    docker-compose logs btrfs-web
fi

# 设置开机自启
log "设置开机自启动..."
cat > /etc/systemd/system/btrfs-snapshot-manager.service << EOF
[Unit]
Description=Btrfs Snapshot Manager
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable btrfs-snapshot-manager

# 显示最终信息
echo
echo "=================================================="
echo -e "${GREEN}🎉 Btrfs快照管理器强制部署成功！${NC}"
echo "=================================================="
echo
echo -e "${BLUE}访问信息：${NC}"
echo "  Web管理界面: http://$(hostname -I | awk '{print $1}'):8080"
echo "  API接口:     http://$(hostname -I | awk '{print $1}'):5000/api"
echo "  容器管理:    http://$(hostname -I | awk '{print $1}'):9000 (Portainer)"
echo
echo -e "${BLUE}重要路径：${NC}"
echo "  部署目录: $DEPLOY_DIR"
echo "  监控目录: /data/monitored"
echo "  快照目录: /data/snapshots"
echo "  日志文件: /var/log/btrfs-snapshot-manager/"
echo
echo -e "${BLUE}管理命令：${NC}"
echo "  查看状态: cd $DEPLOY_DIR && docker-compose ps"
echo "  查看日志: cd $DEPLOY_DIR && docker-compose logs -f"
echo "  重启服务: cd $DEPLOY_DIR && docker-compose restart"
echo "  停止服务: cd $DEPLOY_DIR && docker-compose down"
echo
echo -e "${YELLOW}注意事项：${NC}"
echo "  1. 请确保监控目录 /data/monitored 是Btrfs子卷"
echo "  2. 首次使用请在Web界面配置监控路径"
echo "  3. 建议定期备份配置文件"

log "🎉 强制部署完成！"