#!/bin/bash

# Btrfs快照管理器系统监控脚本
# 定期收集系统指标并生成报告

DEPLOY_DIR="/opt/btrfs-snapshot-manager"
MONITOR_DATA_DIR="/var/lib/btrfs-monitor"
LOG_FILE="/var/log/btrfs-snapshot-manager/monitor.log"

# 创建监控数据目录
mkdir -p "$MONITOR_DATA_DIR"

# 日志函数
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 收集系统指标
collect_system_metrics() {
    local timestamp=$(date -Iseconds)
    local metrics_file="$MONITOR_DATA_DIR/system_metrics_$(date +%Y%m%d).json"

    # CPU使用率
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//' | sed 's/\..*//')

    # 内存使用率
    local mem_total=$(free -b | awk '/^Mem:/ {print $2}')
    local mem_used=$(free -b | awk '/^Mem:/ {print $3}')
    local mem_usage=$((mem_used * 100 / mem_total))

    # 磁盘使用率
    local disk_usage=$(df /data | awk 'NR==2 {print $5}' | sed 's/%//')

    # 负载平均值
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')

    # 生成JSON格式的指标数据
    cat >> "$metrics_file" << EOF
{
  "timestamp": "$timestamp",
  "system": {
    "cpu_usage": $cpu_usage,
    "memory_usage": $mem_usage,
    "memory_total": $mem_total,
    "memory_used": $mem_used,
    "disk_usage": $disk_usage,
    "load_average": $load_avg
  }
},
EOF

    log "系统指标收集完成: CPU=${cpu_usage}%, 内存=${mem_usage}%, 磁盘=${disk_usage}%"
}

# 收集容器指标
collect_container_metrics() {
    local timestamp=$(date -Iseconds)
    local metrics_file="$MONITOR_DATA_DIR/container_metrics_$(date +%Y%m%d).json"

    cd "$DEPLOY_DIR" 2>/dev/null || return 1

    # 获取容器统计信息
    docker-compose ps --format json 2>/dev/null | while read -r container_info; do
        local container_name=$(echo "$container_info" | jq -r '.Name' 2>/dev/null)
        local container_status=$(echo "$container_info" | jq -r '.State' 2>/dev/null)

        if [[ -n "$container_name" && "$container_name" != "null" ]]; then
            # 获取容器详细统计
            local stats=$(docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" "$container_name" 2>/dev/null | tail -1)

            if [[ -n "$stats" ]]; then
                local cpu_perc=$(echo "$stats" | awk '{print $1}' | sed 's/%//')
                local mem_usage=$(echo "$stats" | awk '{print $2}')
                local net_io=$(echo "$stats" | awk '{print $3}')
                local block_io=$(echo "$stats" | awk '{print $4}')

                cat >> "$metrics_file" << EOF
{
  "timestamp": "$timestamp",
  "container": {
    "name": "$container_name",
    "status": "$container_status",
    "cpu_percent": "$cpu_perc",
    "memory_usage": "$mem_usage",
    "network_io": "$net_io",
    "block_io": "$block_io"
  }
},
EOF
            fi
        fi
    done

    log "容器指标收集完成"
}

# 收集快照统计
collect_snapshot_metrics() {
    local timestamp=$(date -Iseconds)
    local metrics_file="$MONITOR_DATA_DIR/snapshot_metrics_$(date +%Y%m%d).json"

    # 通过API获取快照信息
    local api_response=$(curl -s http://localhost:5000/api/snapshots 2>/dev/null)

    if [[ $? -eq 0 ]] && [[ -n "$api_response" ]]; then
        local snapshot_count=$(echo "$api_response" | jq '.snapshots | length' 2>/dev/null)
        local total_size=0

        # 计算总大小（如果API提供）
        if echo "$api_response" | jq -e '.snapshots[0].size' >/dev/null 2>&1; then
            total_size=$(echo "$api_response" | jq '[.snapshots[].size] | add' 2>/dev/null)
        fi

        cat >> "$metrics_file" << EOF
{
  "timestamp": "$timestamp",
  "snapshots": {
    "count": $snapshot_count,
    "total_size": $total_size
  }
},
EOF

        log "快照指标收集完成: 数量=${snapshot_count}, 总大小=${total_size}"
    else
        log "无法获取快照指标"
    fi
}

# 收集API性能指标
collect_api_metrics() {
    local timestamp=$(date -Iseconds)
    local metrics_file="$MONITOR_DATA_DIR/api_metrics_$(date +%Y%m%d).json"

    # 测试API响应时间
    local start_time=$(date +%s%N)
    local response=$(curl -s -w "%{http_code}" -o /dev/null http://localhost:5000/api/health 2>/dev/null)
    local end_time=$(date +%s%N)

    local response_time=$(((end_time - start_time) / 1000000))  # 转换为毫秒

    cat >> "$metrics_file" << EOF
{
  "timestamp": "$timestamp",
  "api": {
    "health_check_response_time_ms": $response_time,
    "health_check_status_code": "$response",
    "is_healthy": $([ "$response" = "200" ] && echo "true" || echo "false")
  }
},
EOF

    log "API指标收集完成: 响应时间=${response_time}ms, 状态=${response}"
}

# 生成监控报告
generate_report() {
    local report_file="$MONITOR_DATA_DIR/daily_report_$(date +%Y%m%d).html"
    local today=$(date +%Y%m%d)

    cat > "$report_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Btrfs快照管理器 - 监控报告 $(date +%Y-%m-%d)</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background: #f4f4f4; padding: 20px; border-radius: 5px; }
        .metric { margin: 10px 0; padding: 10px; border-left: 4px solid #007cba; }
        .critical { border-left-color: #dc3545; }
        .warning { border-left-color: #ffc107; }
        .good { border-left-color: #28a745; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Btrfs快照管理器 - 监控报告</h1>
        <p>报告日期: $(date)</p>
    </div>

    <h2>系统指标摘要</h2>
EOF

    # 分析今天的指标数据
    if [[ -f "$MONITOR_DATA_DIR/system_metrics_${today}.json" ]]; then
        local avg_cpu=$(grep -o '"cpu_usage": [0-9]*' "$MONITOR_DATA_DIR/system_metrics_${today}.json" | awk -F': ' '{sum+=$2; count++} END {print int(sum/count)}')
        local avg_mem=$(grep -o '"memory_usage": [0-9]*' "$MONITOR_DATA_DIR/system_metrics_${today}.json" | awk -F': ' '{sum+=$2; count++} END {print int(sum/count)}')
        local max_disk=$(grep -o '"disk_usage": [0-9]*' "$MONITOR_DATA_DIR/system_metrics_${today}.json" | awk -F': ' '{if($2>max) max=$2} END {print max}')

        cat >> "$report_file" << EOF
    <div class="metric $([ $avg_cpu -gt 80 ] && echo "warning" || echo "good")">
        <strong>平均CPU使用率:</strong> ${avg_cpu}%
    </div>
    <div class="metric $([ $avg_mem -gt 80 ] && echo "warning" || echo "good")">
        <strong>平均内存使用率:</strong> ${avg_mem}%
    </div>
    <div class="metric $([ $max_disk -gt 80 ] && echo "warning" || echo "good")">
        <strong>最大磁盘使用率:</strong> ${max_disk}%
    </div>
EOF
    fi

    cat >> "$report_file" << EOF
    <h2>服务状态</h2>
    <table>
        <tr><th>检查项</th><th>状态</th><th>最后检查时间</th></tr>
EOF

    # 运行健康检查并添加到报告
    if bash "$DEPLOY_DIR/monitoring/health_check.sh" containers >/dev/null 2>&1; then
        echo "<tr><td>容器状态</td><td style='color: green;'>正常</td><td>$(date)</td></tr>" >> "$report_file"
    else
        echo "<tr><td>容器状态</td><td style='color: red;'>异常</td><td>$(date)</td></tr>" >> "$report_file"
    fi

    if bash "$DEPLOY_DIR/monitoring/health_check.sh" api >/dev/null 2>&1; then
        echo "<tr><td>API服务</td><td style='color: green;'>正常</td><td>$(date)</td></tr>" >> "$report_file"
    else
        echo "<tr><td>API服务</td><td style='color: red;'>异常</td><td>$(date)</td></tr>" >> "$report_file"
    fi

    cat >> "$report_file" << EOF
    </table>

    <h2>建议</h2>
    <ul>
        <li>定期检查磁盘空间使用情况</li>
        <li>监控快照数量，避免超过限制</li>
        <li>确保Btrfs子卷配置正确</li>
        <li>定期备份重要配置文件</li>
    </ul>

    <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666;">
        <p>此报告由Btrfs快照管理器监控系统自动生成</p>
    </footer>
</body>
</html>
EOF

    log "监控报告生成完成: $report_file"
}

# 清理旧数据
cleanup_old_data() {
    log "清理7天前的监控数据..."

    find "$MONITOR_DATA_DIR" -name "*.json" -mtime +7 -delete 2>/dev/null
    find "$MONITOR_DATA_DIR" -name "*.html" -mtime +30 -delete 2>/dev/null

    log "数据清理完成"
}

# 主函数
main() {
    case "${1:-collect}" in
        "collect")
            log "开始收集监控数据..."
            collect_system_metrics
            collect_container_metrics
            collect_snapshot_metrics
            collect_api_metrics
            log "监控数据收集完成"
            ;;
        "report")
            log "生成监控报告..."
            generate_report
            ;;
        "cleanup")
            cleanup_old_data
            ;;
        "all")
            collect_system_metrics
            collect_container_metrics
            collect_snapshot_metrics
            collect_api_metrics
            generate_report
            cleanup_old_data
            ;;
        *)
            echo "用法: $0 [collect|report|cleanup|all]"
            exit 1
            ;;
    esac
}

main "$@"