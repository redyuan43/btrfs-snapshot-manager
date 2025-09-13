#!/bin/bash

# Btrfs快照管理器健康检查脚本
# 用于监控系统状态并发送告警

DEPLOY_DIR="/opt/btrfs-snapshot-manager"
LOG_FILE="/var/log/btrfs-snapshot-manager/health_check.log"
ALERT_EMAIL="${ALERT_EMAIL:-admin@example.com}"
WEBHOOK_URL="${WEBHOOK_URL:-}"

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 告警函数
send_alert() {
    local subject="$1"
    local message="$2"
    local severity="${3:-WARNING}"

    log "[$severity] $subject: $message"

    # 邮件告警
    if command -v mail &> /dev/null && [[ -n "$ALERT_EMAIL" ]]; then
        echo "$message" | mail -s "[$severity] Btrfs快照管理器: $subject" "$ALERT_EMAIL"
    fi

    # Webhook告警
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -X POST "$WEBHOOK_URL" \
             -H "Content-Type: application/json" \
             -d "{\"severity\":\"$severity\",\"subject\":\"$subject\",\"message\":\"$message\",\"timestamp\":\"$(date -Iseconds)\"}" \
             2>/dev/null || true
    fi
}

# 检查Docker容器状态
check_containers() {
    log "检查Docker容器状态..."

    cd "$DEPLOY_DIR" 2>/dev/null || {
        send_alert "部署目录不存在" "无法找到部署目录: $DEPLOY_DIR" "CRITICAL"
        return 1
    }

    local unhealthy_containers=$(docker-compose ps --filter "health=unhealthy" -q 2>/dev/null)
    if [[ -n "$unhealthy_containers" ]]; then
        send_alert "容器健康检查失败" "发现不健康的容器: $unhealthy_containers" "CRITICAL"
        return 1
    fi

    local stopped_containers=$(docker-compose ps --filter "status=exited" -q 2>/dev/null)
    if [[ -n "$stopped_containers" ]]; then
        send_alert "容器意外停止" "发现停止的容器: $stopped_containers" "CRITICAL"
        return 1
    fi

    log "容器状态检查通过"
    return 0
}

# 检查API服务
check_api() {
    log "检查API服务..."

    local api_url="http://localhost:5000/api/health"
    local response=$(curl -s -w "%{http_code}" -o /tmp/api_response "$api_url" 2>/dev/null)

    if [[ "$response" != "200" ]]; then
        send_alert "API服务不可用" "API健康检查失败，HTTP状态码: $response" "CRITICAL"
        return 1
    fi

    local status=$(jq -r '.status' /tmp/api_response 2>/dev/null)
    if [[ "$status" != "ok" ]]; then
        send_alert "API服务异常" "API返回状态: $status" "WARNING"
        return 1
    fi

    log "API服务检查通过"
    return 0
}

# 检查Web界面
check_web() {
    log "检查Web界面..."

    local web_url="http://localhost:80"
    local response=$(curl -s -w "%{http_code}" -o /dev/null "$web_url" 2>/dev/null)

    if [[ "$response" != "200" ]]; then
        send_alert "Web界面不可用" "Web界面检查失败，HTTP状态码: $response" "WARNING"
        return 1
    fi

    log "Web界面检查通过"
    return 0
}

# 检查磁盘空间
check_disk_space() {
    log "检查磁盘空间..."

    local data_dir="/data"
    local usage=$(df "$data_dir" | awk 'NR==2 {print $5}' | sed 's/%//')

    if [[ "$usage" -gt 90 ]]; then
        send_alert "磁盘空间不足" "数据目录 $data_dir 使用率: ${usage}%" "CRITICAL"
        return 1
    elif [[ "$usage" -gt 80 ]]; then
        send_alert "磁盘空间警告" "数据目录 $data_dir 使用率: ${usage}%" "WARNING"
    fi

    log "磁盘空间检查通过 (使用率: ${usage}%)"
    return 0
}

# 检查Btrfs子卷
check_btrfs() {
    log "检查Btrfs子卷状态..."

    if ! command -v btrfs &> /dev/null; then
        send_alert "Btrfs工具缺失" "btrfs命令不可用" "CRITICAL"
        return 1
    fi

    local watch_dir="/data/monitored"
    if [[ -d "$watch_dir" ]]; then
        if ! btrfs subvolume show "$watch_dir" &>/dev/null; then
            send_alert "Btrfs子卷错误" "$watch_dir 不是有效的Btrfs子卷" "WARNING"
        fi
    fi

    log "Btrfs检查完成"
    return 0
}

# 检查系统资源
check_resources() {
    log "检查系统资源..."

    # CPU使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    cpu_usage=${cpu_usage%.*}  # 取整数部分

    if [[ "$cpu_usage" -gt 80 ]]; then
        send_alert "CPU使用率过高" "当前CPU使用率: ${cpu_usage}%" "WARNING"
    fi

    # 内存使用率
    local mem_usage=$(free | awk '/^Mem:/ {printf "%.0f", $3/$2 * 100}')

    if [[ "$mem_usage" -gt 90 ]]; then
        send_alert "内存使用率过高" "当前内存使用率: ${mem_usage}%" "WARNING"
    fi

    log "系统资源检查完成 (CPU: ${cpu_usage}%, 内存: ${mem_usage}%)"
    return 0
}

# 主函数
main() {
    log "开始健康检查..."

    local failed_checks=0

    check_containers || ((failed_checks++))
    check_api || ((failed_checks++))
    check_web || ((failed_checks++))
    check_disk_space || ((failed_checks++))
    check_btrfs || ((failed_checks++))
    check_resources || ((failed_checks++))

    if [[ $failed_checks -eq 0 ]]; then
        log "所有健康检查通过"
    else
        log "健康检查发现 $failed_checks 个问题"
        send_alert "健康检查完成" "发现 $failed_checks 个问题，请查看日志" "INFO"
    fi

    log "健康检查完成"
}

# 清理临时文件
cleanup() {
    rm -f /tmp/api_response
}

trap cleanup EXIT

# 根据参数执行不同检查
case "${1:-all}" in
    "containers")
        check_containers
        ;;
    "api")
        check_api
        ;;
    "web")
        check_web
        ;;
    "disk")
        check_disk_space
        ;;
    "btrfs")
        check_btrfs
        ;;
    "resources")
        check_resources
        ;;
    "all")
        main
        ;;
    *)
        echo "用法: $0 [containers|api|web|disk|btrfs|resources|all]"
        exit 1
        ;;
esac