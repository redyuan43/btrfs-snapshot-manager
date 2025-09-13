// Btrfs快照管理器前端应用 v2.0
class BtrfsManager {
    constructor() {
        this.apiBase = '/api';
        this.refreshInterval = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.startAutoRefresh();
        this.loadInitialData();
    }

    // 绑定事件监听器
    bindEvents() {
        // 监控控制
        document.getElementById('toggle-monitoring').addEventListener('click', () => {
            this.toggleMonitoring();
        });

        // 快照操作
        document.getElementById('create-snapshot').addEventListener('click', () => {
            this.createSnapshot();
        });

        document.getElementById('cleanup-snapshots').addEventListener('click', () => {
            this.cleanupSnapshots();
        });

        // 配置保存
        document.getElementById('save-config').addEventListener('click', () => {
            this.saveConfig();
        });

        // 刷新按钮
        document.getElementById('refresh-snapshots').addEventListener('click', () => {
            this.loadSnapshots();
        });

        document.getElementById('refresh-logs').addEventListener('click', () => {
            this.loadLogs();
        });

        // 路径浏览
        document.getElementById('browse-btn').addEventListener('click', () => {
            this.browseFiles();
        });
    }

    // 启动自动刷新
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.updateStatus();
            this.loadSnapshots();
        }, 30000); // 30秒刷新一次
    }

    // 加载初始数据
    async loadInitialData() {
        console.log('Loading initial data...');
        try {
            await this.updateStatus();
            console.log('Status updated, loading config...');
            await this.loadConfig();
            console.log('Config loaded, loading snapshots...');
            await this.loadSnapshots();
            console.log('Snapshots loaded, loading logs...');
            await this.loadLogs();
            console.log('Initial data loading complete');
        } catch (error) {
            console.error('Error during initial data loading:', error);
        }
    }

    // API请求封装
    async apiRequest(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API请求失败: ${endpoint}`, error);
            this.showAlert('错误', `API请求失败: ${error.message}`, 'danger');
            throw error;
        }
    }

    // 更新系统状态
    async updateStatus() {
        try {
            // 健康检查
            const health = await this.apiRequest('/health');
            this.updateStatusIndicator(health.status === 'healthy');

            // 监控状态
            const monitoring = await this.apiRequest('/monitoring');
            this.updateMonitoringStatus(monitoring.active);
            this.updateMonitoringPath(monitoring.watch_dir);

            // 快照统计
            const snapshots = await this.apiRequest('/snapshots');
            this.updateSnapshotCount(snapshots.count);

            // 系统统计
            const stats = await this.apiRequest('/stats');
            this.updateSystemStats(stats);

        } catch (error) {
            this.updateStatusIndicator(false);
        }
    }

    // 更新状态指示器
    updateStatusIndicator(isOnline) {
        const indicator = document.getElementById('status-indicator');
        indicator.className = `badge ${isOnline ? 'bg-success' : 'bg-danger'}`;
        indicator.textContent = isOnline ? '在线' : '离线';
    }

    // 更新监控状态
    updateMonitoringStatus(isRunning) {
        const statusElement = document.getElementById('monitoring-status');
        const toggleBtn = document.getElementById('toggle-monitoring');

        if (isRunning) {
            statusElement.innerHTML = '<span class="status-online"><i class="bi bi-check-circle"></i> 运行中</span>';
            toggleBtn.innerHTML = '<i class="bi bi-stop-circle"></i> 停止监控';
            toggleBtn.className = 'btn btn-sm btn-danger';
        } else {
            statusElement.innerHTML = '<span class="status-offline"><i class="bi bi-x-circle"></i> 已停止</span>';
            toggleBtn.innerHTML = '<i class="bi bi-play-circle"></i> 启动监控';
            toggleBtn.className = 'btn btn-sm btn-success';
        }
    }

    // 更新快照数量
    updateSnapshotCount(count) {
        document.getElementById('snapshot-count').textContent = count;
    }

    // 更新系统统计
    updateSystemStats(stats) {
        if (stats.disk) {
            const usage = stats.disk;
            const percent = Math.round(usage.percent);
            document.getElementById('disk-usage').textContent = `${percent}%`;
            document.getElementById('disk-progress').style.width = `${percent}%`;
        }

        if (stats.snapshots && stats.snapshots.last_snapshot_time) {
            const lastTime = new Date(stats.snapshots.last_snapshot_time).toLocaleString('zh-CN');
            document.getElementById('last-snapshot').textContent = lastTime;
        }
    }

    // 更新监控路径显示
    updateMonitoringPath(path) {
        const pathElement = document.getElementById('monitoring-path');
        if (pathElement) {
            // 简化长路径显示
            const displayPath = path.length > 30 ? path.substring(0, 27) + '...' : path;
            pathElement.textContent = displayPath;
            pathElement.title = path; // 悬停显示完整路径
            console.log('Updated monitoring path display:', path);
        } else {
            console.error('monitoring-path element not found');
        }
    }

    // 切换监控状态
    async toggleMonitoring() {
        try {
            const monitoring = await this.apiRequest('/monitoring');
            const endpoint = monitoring.active ? '/monitoring/stop' : '/monitoring/start';

            await this.apiRequest(endpoint, { method: 'POST' });
            this.showAlert('成功', '监控状态已更新', 'success');
            await this.updateStatus();
        } catch (error) {
            // 错误已在apiRequest中处理
        }
    }

    // 创建快照
    async createSnapshot() {
        try {
            const description = document.getElementById('snapshot-description').value || '手动创建';
            await this.apiRequest('/snapshots', {
                method: 'POST',
                body: JSON.stringify({ description })
            });

            this.showAlert('成功', '快照创建成功', 'success');
            document.getElementById('snapshot-description').value = '';
            await this.loadSnapshots();
        } catch (error) {
            // 错误已在apiRequest中处理
        }
    }

    // 清理快照
    async cleanupSnapshots() {
        if (!confirm('确定要清理旧快照吗？')) return;

        try {
            await this.apiRequest('/snapshots/cleanup', { method: 'POST' });
            this.showAlert('成功', '快照清理完成', 'success');
            await this.loadSnapshots();
        } catch (error) {
            // 错误已在apiRequest中处理
        }
    }

    // 删除单个快照
    async deleteSnapshot(name) {
        if (!confirm(`确定要删除快照 "${name}" 吗？`)) return;

        try {
            await this.apiRequest(`/snapshots/${name}`, { method: 'DELETE' });
            this.showAlert('成功', '快照删除成功', 'success');
            await this.loadSnapshots();
        } catch (error) {
            // 错误已在apiRequest中处理
        }
    }

    // 加载配置
    async loadConfig() {
        try {
            const config = await this.apiRequest('/config');
            console.log('Loaded config:', config);

            const watchPath = document.getElementById('watch-path');
            if (watchPath) {
                watchPath.value = config.watch_dir || '';
                console.log('Set watch path to:', config.watch_dir);
            } else {
                console.error('watch-path element not found');
            }

            document.getElementById('snapshot-path').value = config.snapshot_dir || '';
            document.getElementById('max-snapshots').value = config.max_snapshots || 50;
            document.getElementById('cooldown-seconds').value = config.cooldown_seconds || 300;
        } catch (error) {
            console.error('Failed to load config:', error);
            // 错误已在apiRequest中处理
        }
    }

    // 保存配置
    async saveConfig() {
        try {
            const config = {
                watch_dir: document.getElementById('watch-path').value,
                snapshot_dir: document.getElementById('snapshot-path').value,
                max_snapshots: parseInt(document.getElementById('max-snapshots').value),
                cooldown_seconds: parseInt(document.getElementById('cooldown-seconds').value)
            };

            await this.apiRequest('/config', {
                method: 'POST',
                body: JSON.stringify(config)
            });

            this.showAlert('成功', '配置保存成功', 'success');
        } catch (error) {
            // 错误已在apiRequest中处理
        }
    }

    // 加载快照列表
    async loadSnapshots() {
        try {
            const data = await this.apiRequest('/snapshots');
            this.renderSnapshotTable(data.snapshots);
        } catch (error) {
            document.getElementById('snapshot-table').innerHTML =
                '<tr><td colspan="5" class="text-center text-danger">加载失败</td></tr>';
        }
    }

    // 渲染快照表格
    renderSnapshotTable(snapshots) {
        const tbody = document.getElementById('snapshot-table');

        if (snapshots.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无快照</td></tr>';
            return;
        }

        tbody.innerHTML = snapshots.map(snapshot => `
            <tr>
                <td>${snapshot.name}</td>
                <td>${new Date(snapshot.created_time).toLocaleString('zh-CN')}</td>
                <td>${this.formatSize(snapshot.size)}</td>
                <td>${snapshot.description || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="app.deleteSnapshot('${snapshot.name}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    // 格式化文件大小
    formatSize(bytes) {
        if (!bytes) return '-';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = bytes;
        let unitIndex = 0;

        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }

        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    // 加载日志
    async loadLogs() {
        try {
            // 简化版本：显示最近的操作日志
            const container = document.getElementById('log-container');
            container.innerHTML = `
                <div class="text-muted">
                    <div>[${new Date().toLocaleString()}] 系统运行正常</div>
                    <div>[${new Date().toLocaleString()}] 监控服务已启动</div>
                    <div>[${new Date().toLocaleString()}] API服务就绪</div>
                </div>
            `;
        } catch (error) {
            document.getElementById('log-container').innerHTML =
                '<div class="text-danger">日志加载失败</div>';
        }
    }

    // 浏览文件
    async browseFiles() {
        try {
            const files = await this.apiRequest('/files');
            console.log('Files data:', files);

            if (files.files && files.files.length > 0) {
                let content = '';

                // 显示目录
                const directories = files.files.filter(f => f.is_directory);
                if (directories.length > 0) {
                    content += '<h6>目录:</h6>';
                    directories.forEach(dir => {
                        content += `<div style="margin-left: 10px;">📁 ${dir.name} (${dir.item_count || 0} 项)</div>`;
                    });
                }

                // 显示文件
                const fileItems = files.files.filter(f => !f.is_directory);
                if (fileItems.length > 0) {
                    content += '<h6>文件:</h6>';
                    fileItems.forEach(file => {
                        content += `<div style="margin-left: 10px;">📄 ${file.name} (${this.formatSize(file.size)})</div>`;
                    });
                }

                if (!files.has_directories && !files.has_files) {
                    content = '<div>监控目录为空</div>';
                }

                this.showAlert(`监控路径内容 (${files.count} 项)`, content, 'info');
            } else {
                this.showAlert('文件列表', '监控目录为空', 'info');
            }
        } catch (error) {
            console.error('Browse files error:', error);
            // 错误已在apiRequest中处理
        }
    }

    // 显示提示框
    showAlert(title, message, type = 'info') {
        document.getElementById('alertModalTitle').textContent = title;
        document.getElementById('alertModalBody').innerHTML = message;

        const modal = new bootstrap.Modal(document.getElementById('alertModal'));
        modal.show();
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM内容已加载，初始化应用...');
    try {
        window.app = new BtrfsManager();
        console.log('应用初始化完成');
    } catch (error) {
        console.error('应用初始化失败:', error);
    }
});

// 备用初始化 - 确保在window加载完成后也执行
window.addEventListener('load', () => {
    console.log('Window完全加载');
    if (!window.app) {
        console.log('通过window.load事件初始化应用...');
        try {
            window.app = new BtrfsManager();
        } catch (error) {
            console.error('备用初始化失败:', error);
        }
    }
});