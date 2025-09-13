#!/bin/bash

# 修复部署脚本 - 解决Git分支冲突问题
# 在服务器上运行此脚本来修复部署问题

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

DEPLOY_DIR="/opt/btrfs-snapshot-manager"

log "🔧 修复部署问题..."

# 检查是否在部署目录
if [[ ! -d "$DEPLOY_DIR" ]]; then
    error "部署目录不存在: $DEPLOY_DIR"
    log "重新创建部署目录..."
    mkdir -p "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
    git clone https://github.com/redyuan43/btrfs-snapshot-manager.git .
else
    cd "$DEPLOY_DIR"

    # 检查Git状态
    log "检查Git状态..."
    git status

    # 保存本地更改（如果有）
    if ! git diff --quiet || ! git diff --cached --quiet; then
        warning "检测到本地更改，正在保存..."
        git stash push -m "部署脚本自动保存 $(date)"
    fi

    # 重置到干净状态
    log "重置Git仓库状态..."
    git reset --hard HEAD

    # 设置Git配置以使用merge策略
    git config pull.rebase false

    # 强制拉取最新代码
    log "拉取最新代码..."
    git fetch origin master
    git reset --hard origin/master
fi

log "✅ Git问题已修复"

# 继续部署流程
log "继续部署流程..."

# 创建必要目录
mkdir -p /data/{monitored,snapshots}
mkdir -p /var/log/btrfs-snapshot-manager

# 创建生产环境配置
log "配置生产环境..."
mkdir -p config

cat > config/production.yaml << EOF
# 生产环境配置 - 由修复脚本生成
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

# 确保Docker Compose使用正确的数据目录挂载
# (docker-compose.yml 已经正确配置了 /data:/data)

# 停止现有服务
log "停止现有服务..."
docker-compose down --remove-orphans 2>/dev/null || true

# 构建镜像
log "构建Docker镜像..."
docker-compose build

# 启动服务
log "启动服务..."
docker-compose up -d

# 等待服务启动
log "等待服务启动..."
sleep 15

# 验证部署
log "验证部署状态..."

# 检查容器状态
if docker-compose ps | grep -q "Up"; then
    log "✅ 容器启动成功"
else
    error "❌ 容器启动失败"
    echo "容器状态:"
    docker-compose ps
    echo "容器日志:"
    docker-compose logs
    exit 1
fi

# 检查API健康状态
for i in {1..30}; do
    if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
        log "✅ API服务健康检查通过"
        break
    fi

    if [[ $i -eq 30 ]]; then
        error "❌ API服务健康检查失败"
        exit 1
    fi

    log "等待API服务启动... ($i/30)"
    sleep 2
done

# 检查Web界面
if curl -s http://localhost:8080 > /dev/null 2>&1; then
    log "✅ Web界面访问正常"
else
    warning "⚠️ Web界面可能存在问题"
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

# 显示部署信息
echo
echo "=================================================="
echo -e "${GREEN}🎉 Btrfs快照管理器部署成功！${NC}"
echo "=================================================="
echo
echo "访问信息："
echo "  Web管理界面: http://$(hostname -I | awk '{print $1}'):8080"
echo "  API接口:     http://$(hostname -I | awk '{print $1}'):5000/api"
echo "  容器管理:    http://$(hostname -I | awk '{print $1}'):9000 (Portainer)"
echo
echo "重要路径："
echo "  部署目录: $DEPLOY_DIR"
echo "  监控目录: /data/monitored"
echo "  快照目录: /data/snapshots"
echo "  日志文件: /var/log/btrfs-snapshot-manager/"
echo
echo "管理命令："
echo "  查看状态: cd $DEPLOY_DIR && docker-compose ps"
echo "  查看日志: cd $DEPLOY_DIR && docker-compose logs -f"
echo "  重启服务: cd $DEPLOY_DIR && docker-compose restart"
echo "  停止服务: cd $DEPLOY_DIR && docker-compose down"

log "🎉 部署修复完成！"