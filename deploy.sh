#!/bin/bash

# Btrfs快照管理器 - 一键部署脚本
# 适用于Debian系统，自动化Docker容器部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置变量
APP_NAME="btrfs-snapshot-manager"
GITHUB_REPO="https://github.com/redyuan43/btrfs-snapshot-manager.git"
DEPLOY_DIR="/opt/btrfs-snapshot-manager"
DATA_DIR="/data"
LOG_FILE="/var/log/btrfs-deploy.log"

# 日志函数
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
    echo "[ERROR] $1" >> "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
    echo "[WARNING] $1" >> "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
    echo "[INFO] $1" >> "$LOG_FILE"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "此脚本需要root权限运行"
        error "请使用: sudo bash deploy.sh"
        exit 1
    fi
}

# 检查系统环境
check_system() {
    log "检查系统环境..."

    # 检查操作系统
    if ! grep -q "Debian\|Ubuntu" /etc/os-release; then
        warning "检测到非Debian/Ubuntu系统，脚本可能需要调整"
    fi

    # 检查Docker
    if ! command -v docker &> /dev/null; then
        error "Docker未安装，请先安装Docker"
        info "安装命令: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi

    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        warning "Docker Compose未安装，正在安装..."
        curl -L "https://github.com/docker/compose/releases/download/v2.12.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi

    # 检查Btrfs工具
    if ! command -v btrfs &> /dev/null; then
        warning "Btrfs工具未安装，正在安装..."
        apt-get update
        apt-get install -y btrfs-progs
    fi

    log "系统环境检查完成"
}

# 创建必要目录
create_directories() {
    log "创建必要目录..."

    # 部署目录
    mkdir -p "$DEPLOY_DIR"

    # 数据目录
    mkdir -p "$DATA_DIR"/{monitored,snapshots}

    # 日志目录
    mkdir -p /var/log/btrfs-snapshot-manager

    log "目录创建完成"
}

# 下载或更新代码
update_code() {
    log "更新应用代码..."

    if [[ -d "$DEPLOY_DIR/.git" ]]; then
        info "检测到现有代码，正在更新..."
        cd "$DEPLOY_DIR"
        git pull origin master
    else
        info "下载最新代码..."
        rm -rf "$DEPLOY_DIR"
        git clone "$GITHUB_REPO" "$DEPLOY_DIR"
        cd "$DEPLOY_DIR"
    fi

    log "代码更新完成"
}

# 配置环境
configure_environment() {
    log "配置部署环境..."

    cd "$DEPLOY_DIR"

    # 创建生产环境配置
    cat > config/production.yaml << EOF
# 生产环境配置 - 由部署脚本生成
watch_dir: $DATA_DIR/monitored
snapshot_dir: $DATA_DIR/snapshots
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
    sed -i "s|/data:/data|$DATA_DIR:$DATA_DIR|g" docker-compose.yml

    log "环境配置完成"
}

# 构建和启动服务
deploy_services() {
    log "构建和启动服务..."

    cd "$DEPLOY_DIR"

    # 停止现有服务
    docker-compose down --remove-orphans 2>/dev/null || true

    # 构建镜像
    info "构建Docker镜像..."
    docker-compose build

    # 启动服务
    info "启动服务..."
    docker-compose up -d

    # 等待服务启动
    sleep 10

    log "服务部署完成"
}

# 验证部署
verify_deployment() {
    log "验证部署状态..."

    # 检查容器状态
    if ! docker-compose ps | grep -q "Up"; then
        error "部分服务未正常启动"
        docker-compose logs
        exit 1
    fi

    # 检查API健康状态
    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
            log "API服务健康检查通过"
            break
        fi

        if [[ $attempt -eq $max_attempts ]]; then
            error "API服务健康检查失败"
            exit 1
        fi

        info "等待API服务启动... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    # 检查Web界面
    if curl -s http://localhost:8080 > /dev/null 2>&1; then
        log "Web界面访问正常"
    else
        warning "Web界面可能存在问题"
    fi

    log "部署验证完成"
}

# 设置开机自启
setup_autostart() {
    log "设置开机自启动..."

    # 创建systemd服务
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

    log "自启动设置完成"
}

# 显示部署信息
show_deployment_info() {
    echo
    echo "=================================================="
    echo -e "${GREEN}🎉 Btrfs快照管理器部署成功！${NC}"
    echo "=================================================="
    echo
    echo -e "${BLUE}访问信息：${NC}"
    echo "  Web管理界面: http://$(hostname -I | awk '{print $1}'):8080"
    echo "  API接口:     http://$(hostname -I | awk '{print $1}'):5000/api"
    echo "  容器管理:    http://$(hostname -I | awk '{print $1}'):9000 (Portainer)"
    echo
    echo -e "${BLUE}重要路径：${NC}"
    echo "  部署目录: $DEPLOY_DIR"
    echo "  监控目录: $DATA_DIR/monitored"
    echo "  快照目录: $DATA_DIR/snapshots"
    echo "  日志文件: /var/log/btrfs-snapshot-manager/"
    echo
    echo -e "${BLUE}管理命令：${NC}"
    echo "  查看状态: cd $DEPLOY_DIR && docker-compose ps"
    echo "  查看日志: cd $DEPLOY_DIR && docker-compose logs -f"
    echo "  重启服务: cd $DEPLOY_DIR && docker-compose restart"
    echo "  停止服务: cd $DEPLOY_DIR && docker-compose down"
    echo
    echo -e "${YELLOW}注意事项：${NC}"
    echo "  1. 请确保监控目录 $DATA_DIR/monitored 是Btrfs子卷"
    echo "  2. 首次使用请在Web界面配置监控路径"
    echo "  3. 建议定期备份配置文件: $DEPLOY_DIR/config/"
    echo
}

# 清理函数
cleanup() {
    if [[ $? -ne 0 ]]; then
        error "部署过程中发生错误，请检查日志: $LOG_FILE"
    fi
}

# 主函数
main() {
    trap cleanup EXIT

    echo -e "${GREEN}"
    echo "=========================================="
    echo "  Btrfs快照管理器 - 一键部署脚本"
    echo "=========================================="
    echo -e "${NC}"

    # 执行部署步骤
    check_root
    check_system
    create_directories
    update_code
    configure_environment
    deploy_services
    verify_deployment
    setup_autostart
    show_deployment_info

    log "部署完成！"
}

# 处理命令行参数
case "${1:-}" in
    "update")
        log "执行更新模式..."
        cd "$DEPLOY_DIR"
        git pull origin master
        docker-compose build
        docker-compose up -d
        log "更新完成"
        ;;
    "stop")
        log "停止服务..."
        cd "$DEPLOY_DIR"
        docker-compose down
        log "服务已停止"
        ;;
    "start")
        log "启动服务..."
        cd "$DEPLOY_DIR"
        docker-compose up -d
        log "服务已启动"
        ;;
    "logs")
        cd "$DEPLOY_DIR"
        docker-compose logs -f
        ;;
    *)
        main
        ;;
esac