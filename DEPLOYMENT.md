# Btrfs快照管理器 - 生产环境部署指南

## 🚀 一键部署

在你的Debian服务器 `192.168.100.97` 上执行以下命令：

```bash
# 1. 下载部署脚本
curl -O https://raw.githubusercontent.com/redyuan43/btrfs-snapshot-manager/master/deploy.sh

# 2. 设置执行权限
chmod +x deploy.sh

# 3. 执行一键部署
sudo ./deploy.sh
```

## 📋 部署流程

部署脚本会自动完成以下步骤：

1. **环境检查**
   - 检查Debian系统
   - 验证Docker安装
   - 安装Docker Compose（如果需要）
   - 安装Btrfs工具

2. **目录设置**
   - 创建 `/opt/btrfs-snapshot-manager` (部署目录)
   - 创建 `/data/monitored` (监控目录)
   - 创建 `/data/snapshots` (快照目录)

3. **代码部署**
   - 从GitHub拉取最新代码
   - 配置生产环境参数

4. **服务启动**
   - 构建Docker镜像
   - 启动服务容器
   - 配置健康检查

5. **监控配置**
   - 设置系统监控
   - 配置日志轮转
   - 安装定时任务

## 🖥️ 访问界面

部署成功后，可通过以下地址访问：

- **Web管理界面**: http://192.168.100.97
- **API接口**: http://192.168.100.97:5000/api
- **容器管理**: http://192.168.100.97:9000 (Portainer)

## ⚙️ 配置快照监控

1. 打开Web管理界面
2. 在"监控配置"部分设置：
   - **监控路径**: 你想监控的Btrfs子卷路径
   - **快照目录**: 快照存储路径（默认 `/data/snapshots`）
   - **最大快照数**: 建议50个
   - **冷却时间**: 建议300秒（5分钟）

3. 点击"保存配置"
4. 点击"启动监控"

## 📊 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web浏览器     │────│   Nginx容器     │────│   API容器       │
│  (端口 80)      │    │  (反向代理)     │    │  (端口 5000)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
                                           ┌─────────────────┐
                                           │  主机Btrfs      │
                                           │  文件系统       │
                                           └─────────────────┘
```

## 🛠️ 管理命令

### 服务管理
```bash
cd /opt/btrfs-snapshot-manager

# 查看服务状态
docker-compose ps

# 查看实时日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 启动服务
docker-compose up -d
```

### 更新系统
```bash
# 更新到最新版本
sudo /opt/btrfs-snapshot-manager/deploy.sh update

# 或者手动更新
cd /opt/btrfs-snapshot-manager
git pull
docker-compose build
docker-compose up -d
```

### 备份和恢复
```bash
# 备份配置
tar -czf btrfs-backup-$(date +%Y%m%d).tar.gz /opt/btrfs-snapshot-manager/config

# 恢复配置
tar -xzf btrfs-backup-20250913.tar.gz -C /
```

## 📈 监控和告警

### 自动监控
系统会自动执行以下监控任务：

- **每5分钟**: 健康检查
- **每10分钟**: 系统指标收集
- **每小时**: 自动重启不健康容器
- **每天**: 生成监控报告
- **每周**: 检查系统更新

### 告警配置

编辑 `/opt/btrfs-snapshot-manager/monitoring/monitoring.yaml`：

```yaml
alerting:
  email:
    enabled: true
    smtp_server: "your-smtp-server.com"
    recipients:
      - "admin@yourdomain.com"
```

### 查看监控报告
```bash
# 查看最新监控报告
ls -la /var/lib/btrfs-monitor/daily_report_*.html

# 在浏览器中查看
firefox /var/lib/btrfs-monitor/daily_report_$(date +%Y%m%d).html
```

## 🔧 故障排除

### 常见问题

1. **容器无法启动**
   ```bash
   # 查看详细错误日志
   docker-compose logs

   # 检查磁盘空间
   df -h

   # 检查Docker服务
   systemctl status docker
   ```

2. **快照创建失败**
   ```bash
   # 检查Btrfs子卷
   btrfs subvolume show /data/monitored

   # 检查权限
   ls -la /data/

   # 手动测试快照
   btrfs subvolume snapshot /data/monitored /data/snapshots/test
   ```

3. **Web界面无法访问**
   ```bash
   # 检查容器状态
   docker-compose ps

   # 检查端口占用
   netstat -tlnp | grep :80

   # 重启Web容器
   docker-compose restart btrfs-web
   ```

### 日志位置

- **应用日志**: `/var/log/btrfs-snapshot-manager/`
- **部署日志**: `/var/log/btrfs-deploy.log`
- **容器日志**: `docker-compose logs`
- **监控日志**: `/var/log/btrfs-snapshot-manager/monitor.log`

## 🔐 安全建议

1. **防火墙配置**
   ```bash
   # 只允许内网访问
   ufw allow from 192.168.100.0/24 to any port 80
   ufw allow from 192.168.100.0/24 to any port 5000
   ```

2. **定期备份**
   - 配置文件备份
   - 关键快照备份
   - 数据库备份（如果使用）

3. **访问控制**
   - 考虑添加认证机制
   - 限制API访问来源
   - 定期更新系统

## 📞 支持

如有问题，请：

1. 查看 `/var/log/btrfs-deploy.log` 日志
2. 运行健康检查: `bash /opt/btrfs-snapshot-manager/monitoring/health_check.sh`
3. 提交Issue到GitHub仓库

## 📝 更新记录

- **v2.0**: 添加Docker容器化支持
- **v2.1**: 添加Web管理界面
- **v2.2**: 添加完整监控系统