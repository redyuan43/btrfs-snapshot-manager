# Btrfs Automatic Snapshot Manager

自动监控指定目录的文件变化并创建 Btrfs 快照的 Python 工具，提供完整的 REST API 接口支持前端开发。

## 功能特性

### 核心功能
- 🔍 **实时监控**: 使用 watchdog/inotify 监控目录变化
- 📸 **自动快照**: 文件变化时自动创建 Btrfs 快照
- 🧹 **智能清理**: 支持按数量或时间自动清理旧快照
- ⏱️ **防抖动**: 内置冷却时间和防抖机制，避免频繁快照
- 📝 **详细日志**: 完整的操作日志记录
- 🛡️ **错误处理**: 优雅的错误处理和恢复机制

### API 接口
- 🌐 **REST API**: 完整的 HTTP API 接口
- 🔗 **CORS 支持**: 支持跨域请求，便于前端集成
- 📊 **实时统计**: 系统资源和快照统计信息
- 🎛️ **远程控制**: 通过 API 远程管理快照和监控

## 系统要求

- Linux 系统（支持 Btrfs）
- Python 3.6+
- btrfs-progs
- root 权限（Btrfs 操作需要）

## 快速安装

### 方法1: 用户安装（推荐，无需sudo）
```bash
# 1. 下载项目
cd /home/ivan/COW

# 2. 用户安装（不需要sudo，不安装systemd服务）
bash install.sh --user

# 3. 编辑配置文件
nano ~/.config/btrfs-snapshot-manager/config.yaml

# 4. 手动运行测试
~/.local/btrfs-snapshot-manager/btrfs-snapshot-manager --test-mode \
  --watch-dir /tmp/test --snapshot-dir /tmp/snapshots
```

### 方法2: 系统安装（需要sudo，包含systemd服务）
```bash
# 1. 下载项目
cd /home/ivan/COW

# 2. 系统安装（需要sudo，安装systemd服务）
sudo bash install.sh

# 3. 编辑配置文件
sudo nano /etc/btrfs-snapshot-manager/config.yaml

# 4. 启动服务
sudo systemctl enable btrfs-snapshot-manager
sudo systemctl start btrfs-snapshot-manager
```

## 配置说明

编辑 `config.yaml` 文件：

```yaml
watch_dir: /data/mydir          # 监控目录（必须是 Btrfs 子卷）
snapshot_dir: /data/snapshots   # 快照存储目录
max_snapshots: 50               # 最大快照数量
cleanup_mode: count             # 清理模式: count 或 time
retention_days: 7               # 保留天数（time 模式）
cooldown_seconds: 60            # 快照间隔冷却时间
debounce_seconds: 5             # 文件变化防抖时间
```

## 使用方法

### 方式1: 作为系统服务运行

```bash
# 启动服务
sudo systemctl start btrfs-snapshot-manager

# 查看状态
sudo systemctl status btrfs-snapshot-manager

# 查看日志
sudo journalctl -u btrfs-snapshot-manager -f

# 停止服务
sudo systemctl stop btrfs-snapshot-manager
```

### 方式2: 命令行直接运行

```bash
# 基本运行
source venv/bin/activate
sudo python btrfs_snapshot_manager.py

# 指定配置文件
sudo python btrfs_snapshot_manager.py -c /path/to/config.yaml

# 测试模式（不需要 root，不创建真实快照）
python3 btrfs_snapshot_manager.py --test-mode \
    --watch-dir /tmp/test_dir \
    --snapshot-dir /tmp/snapshots

# 立即创建快照
sudo python3 btrfs_snapshot_manager.py --snapshot-now

# 列出现有快照
sudo python3 btrfs_snapshot_manager.py --list

# 手动清理旧快照
sudo python3 btrfs_snapshot_manager.py --cleanup

# 调试模式
sudo python3 btrfs_snapshot_manager.py --log-level DEBUG
```

### 命令行参数

- `-c, --config`: 配置文件路径
- `--test-mode`: 测试模式运行
- `--watch-dir`: 覆盖配置中的监控目录
- `--snapshot-dir`: 覆盖配置中的快照目录
- `--max-snapshots`: 覆盖配置中的最大快照数
- `--list`: 列出快照并退出
- `--cleanup`: 执行清理并退出
- `--snapshot-now`: 立即创建快照并退出
- `--log-level`: 日志级别 (DEBUG/INFO/WARNING/ERROR)

### 方式3: API服务器模式

```bash
# 启动API服务器
source venv/bin/activate
python api_server.py

# 指定配置和端口
python api_server.py -c config.yaml --host 0.0.0.0 --port 8080

# 开启调试模式
python api_server.py --debug
```

## REST API 接口

本系统提供完整的REST API接口，方便前端开发和远程管理。

### 启动API服务器

```bash
source venv/bin/activate
python api_server.py
```

服务器将在 `http://127.0.0.1:5000` 启动。

### 主要API端点

#### 快照管理
- `GET /api/snapshots` - 获取快照列表
- `POST /api/snapshots` - 创建新快照
- `DELETE /api/snapshots/<name>` - 删除快照
- `POST /api/snapshots/cleanup` - 清理旧快照
- `GET /api/snapshots/info` - 获取快照统计

#### 文件监控
- `GET /api/monitoring` - 获取监控状态
- `POST /api/monitoring/start` - 启动监控
- `POST /api/monitoring/stop` - 停止监控

#### 系统信息
- `GET /api/health` - 健康检查
- `GET /api/config` - 获取配置
- `GET /api/files` - 列出监控目录文件
- `GET /api/stats` - 获取系统统计

### 前端集成示例

#### JavaScript/React
```javascript
// 获取快照列表
const response = await fetch('/api/snapshots');
const data = await response.json();
console.log('快照列表:', data.snapshots);

// 创建快照
await fetch('/api/snapshots', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ description: '手动快照' })
});

// 启动监控
await fetch('/api/monitoring/start', { method: 'POST' });
```

### API演示

```bash
# 运行完整API演示
source venv/bin/activate
python demo_api.py

# 测试API接口
python tests/test_api.py
```

## 测试

```bash
# 运行所有测试
source venv/bin/activate
python -m pytest tests/

# 综合功能测试
python tests/comprehensive_test.py

# API接口测试
python tests/test_api.py
```

## 日志位置

- 默认日志: `/var/log/btrfs_snapshot.log`
- Systemd 日志: `journalctl -u btrfs-snapshot-manager`

## 快照命名规则

快照按以下格式命名：
```
{目录名}_{YYYYMMDD}_{HHMMSS}
```

例如：`mydir_20250913_143022`

## 故障排除

### 1. 权限错误
```bash
# 确保以 root 运行
sudo python3 btrfs_snapshot_manager.py
```

### 2. Btrfs 子卷检查
```bash
# 检查目录是否为 Btrfs 子卷
sudo btrfs subvolume show /data/mydir
```

### 3. 查看详细日志
```bash
# 启用调试日志
sudo python3 btrfs_snapshot_manager.py --log-level DEBUG
```

### 4. 手动创建快照测试
```bash
# 测试 Btrfs 命令
sudo btrfs subvolume snapshot /data/mydir /data/snapshots/test_snapshot
```

## 卸载

```bash
sudo bash uninstall.sh
```

## 文档

- 📖 **[API文档](API_DOCUMENTATION.md)** - 完整的REST API使用指南
- 📊 **[测试报告](COMPREHENSIVE_TEST_REPORT.md)** - 详细的测试结果和性能指标
- 🛠️ **[开发指南](CLAUDE.md)** - 开发环境设置和架构说明

## 性能指标

基于综合测试结果：

- **API响应时间**: <200ms
- **快照创建**: <0.15s (真实Btrfs) / <0.01s (测试模式)
- **文件监控延迟**: <100ms
- **内存使用**: ~70MB (含API服务器)
- **CPU使用**: <3%
- **测试成功率**: 95%+ (核心功能100%)

## 注意事项

1. **磁盘空间**: 快照会占用磁盘空间，请确保有足够的存储
2. **性能影响**: 频繁的快照可能影响系统性能，建议设置合理的冷却时间
3. **文件系统**: 仅支持 Btrfs 文件系统
4. **权限要求**: Btrfs 操作需要 root 权限
5. **API安全**: 生产环境建议添加认证和HTTPS

## 许可证

MIT License