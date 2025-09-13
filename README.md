# Btrfs Automatic Snapshot Manager

自动监控指定目录的文件变化并创建 Btrfs 快照的 Python 工具。

## 功能特性

- 🔍 **实时监控**: 使用 watchdog/inotify 监控目录变化
- 📸 **自动快照**: 文件变化时自动创建 Btrfs 快照
- 🧹 **智能清理**: 支持按数量或时间自动清理旧快照
- ⏱️ **防抖动**: 内置冷却时间和防抖机制，避免频繁快照
- 📝 **详细日志**: 完整的操作日志记录
- 🛡️ **错误处理**: 优雅的错误处理和恢复机制

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

### 作为系统服务运行

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

### 命令行直接运行

```bash
# 基本运行
sudo python3 btrfs_snapshot_manager.py

# 指定配置文件
sudo python3 btrfs_snapshot_manager.py -c /path/to/config.yaml

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

## 测试

```bash
# 运行测试套件
python3 -m pytest tests/

# 或使用 unittest
python3 -m unittest discover tests/
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

## 注意事项

1. **磁盘空间**: 快照会占用磁盘空间，请确保有足够的存储
2. **性能影响**: 频繁的快照可能影响系统性能，建议设置合理的冷却时间
3. **文件系统**: 仅支持 Btrfs 文件系统
4. **权限要求**: Btrfs 操作需要 root 权限

## 许可证

MIT License