Python 脚本需求文档（Btrfs 自动快照管理器）
1. 背景

使用环境：飞牛OS（基于 Linux，支持 Btrfs 文件系统），Intel N100 + 16GB 内存。

需求：在某个指定的目录（如 /data/mydir）发生文件更新时，自动执行 Btrfs 快照，并管理快照的数量/生命周期，实现类似“实时版本管理”的功能。

2. 功能目标

目录监控

使用 inotify 或 watchdog 库，实时监听指定目录下的文件/子目录变化事件（新增、修改、删除）。

一旦发生变化，触发快照操作。

自动快照

调用 Btrfs 命令生成快照：

btrfs subvolume snapshot /data/mydir /data/snapshots/mydir_YYYYMMDD_HHMMSS


快照命名规则：基于时间戳，保证唯一性。

快照清理

保留最新 N 个快照（如 50 个），删除更早的快照。

或者支持基于时间的清理策略（比如只保留最近 7 天的快照）。

日志记录

每次快照生成/删除的操作要写入日志文件（如 /var/log/btrfs_snapshot.log）。

日志内容包括：时间、触发事件、快照路径、删除操作等。

错误处理

如果快照失败（磁盘满 / 权限问题），写入日志并跳过。

不允许因为一次失败就中断整个服务。

3. 输入与输出
输入

配置文件 / 参数：

watch_dir：监控的目录（必须是 Btrfs 子卷）。

snapshot_dir：存放快照的目录。

max_snapshots：最大快照数（超过则删除旧快照）。

mode：清理模式（按数量 or 按时间）。

输出

快照目录结构：

/data/snapshots/mydir_2025-09-13_10-30-45
/data/snapshots/mydir_2025-09-13_10-45-12
...


日志文件：

[2025-09-13 10:30:45] EVENT: modify file1.txt → Snapshot created: /data/snapshots/mydir_2025-09-13_10-30-45
[2025-09-13 11:00:12] CLEANUP: Deleted snapshot /data/snapshots/mydir_2025-09-12_08-00-00

4. 流程逻辑

启动程序 → 加载配置 → 初始化日志。

使用 inotify 监听 watch_dir 的文件系统事件。

检测到事件（如 IN_MODIFY、IN_CREATE、IN_DELETE）：

检查上一次快照时间，如果间隔过短（比如 1 分钟内已有快照），则忽略（避免频繁快照）。

否则创建新快照。

检查快照目录数量：

如果超过 max_snapshots，删除最旧的快照。

写日志。

程序持续运行（systemd service 守护）。

5. 边界条件

非 Btrfs 子卷：如果监控目录不是子卷，脚本需提示错误。

磁盘不足：快照失败时写入日志并跳过。

频繁写入：需要加“冷却时间阈值”，避免文件写入频繁导致快照过多。

权限不足：必须 root 权限运行。

6. 扩展功能（可选）

支持配置文件（YAML/JSON），方便修改监控目录/策略。

提供命令行参数（--list、--cleanup、--snapshot-now）。

Web 界面简单展示当前快照列表（可选）。
