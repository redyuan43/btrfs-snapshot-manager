#!/usr/bin/env python3
"""
Btrfs Snapshot Manager REST API Server
为前端界面提供HTTP API接口
"""

import os
import sys
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snapshot_manager import SnapshotManager
from config_loader import ConfigLoader
from fs_watcher import FileSystemWatcher


class SnapshotAPI:
    def __init__(self, config_path: Optional[str] = None):
        self.app = Flask(__name__)
        CORS(self.app)  # 允许跨域请求

        # 加载配置
        self.config = ConfigLoader(config_path).load()

        # 初始化快照管理器
        self.manager = SnapshotManager(
            watch_dir=self.config['watch_dir'],
            snapshot_dir=self.config['snapshot_dir'],
            max_snapshots=self.config.get('max_snapshots', 50),
            cleanup_mode=self.config.get('cleanup_mode', 'count'),
            retention_days=self.config.get('retention_days', 7),
            cooldown_seconds=self.config.get('cooldown_seconds', 60),
            test_mode=self.config.get('test_mode', False)
        )

        # 文件监控器状态
        self.watcher: Optional[FileSystemWatcher] = None
        self.monitoring_active = False

        # 请求跟踪记录
        self.recent_requests = []

        # 设置请求跟踪装饰器
        self.setup_request_tracking()

        # 设置路由
        self.setup_routes()

        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def setup_request_tracking(self):
        """设置请求跟踪"""
        @self.app.before_request
        def track_request():
            """跟踪每个请求"""
            from flask import request
            import time

            # 只跟踪API请求
            if request.path.startswith('/api/'):
                request_info = {
                    'time': time.strftime('%H:%M:%S'),
                    'method': request.method,
                    'path': request.path,
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'timestamp': time.time()
                }

                # 将请求信息添加到列表中（保留最近的50个请求）
                self.recent_requests.append(request_info)
                if len(self.recent_requests) > 50:
                    self.recent_requests.pop(0)

        @self.app.after_request
        def track_response(response):
            """跟踪响应状态"""
            from flask import request
            import time

            # 更新最后一个请求的状态码
            if request.path.startswith('/api/') and self.recent_requests:
                for req in reversed(self.recent_requests):
                    if (req['method'] == request.method and
                        req['path'] == request.path and
                        req['ip'] == request.remote_addr and
                        'status' not in req):
                        req['status'] = response.status_code
                        break

            return response

    def setup_routes(self):
        """设置API路由"""

        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            """健康检查"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0'
            })

        @self.app.route('/api/config', methods=['GET', 'POST'])
        def handle_config():
            """获取或保存配置"""
            if request.method == 'GET':
                """获取当前配置"""
                return jsonify({
                    'watch_dir': self.config['watch_dir'],
                    'snapshot_dir': self.config['snapshot_dir'],
                    'max_snapshots': self.config.get('max_snapshots', 50),
                    'cleanup_mode': self.config.get('cleanup_mode', 'count'),
                    'retention_days': self.config.get('retention_days', 7),
                    'cooldown_seconds': self.config.get('cooldown_seconds', 60),
                    'test_mode': self.config.get('test_mode', False)
                })
            elif request.method == 'POST':
                """保存配置"""
                try:
                    data = request.get_json()
                    if not data:
                        return jsonify({'error': 'No configuration data provided'}), 400

                    # 更新配置对象
                    self.config.update({
                        'watch_dir': data.get('watch_dir', self.config['watch_dir']),
                        'snapshot_dir': data.get('snapshot_dir', self.config['snapshot_dir']),
                        'max_snapshots': int(data.get('max_snapshots', self.config.get('max_snapshots', 50))),
                        'cooldown_seconds': int(data.get('cooldown_seconds', self.config.get('cooldown_seconds', 60))),
                        'cleanup_mode': data.get('cleanup_mode', self.config.get('cleanup_mode', 'count')),
                        'retention_days': int(data.get('retention_days', self.config.get('retention_days', 7))),
                        'debounce_seconds': int(data.get('debounce_seconds', self.config.get('debounce_seconds', 10))),
                        'test_mode': bool(data.get('test_mode', self.config.get('test_mode', False)))
                    })

                    # 这里可以添加保存到文件的逻辑
                    # 由于是Docker环境，暂时只在内存中更新
                    self.logger.info(f"Configuration updated: {data}")

                    return jsonify({
                        'success': True,
                        'message': 'Configuration updated successfully',
                        'config': self.config
                    })

                except Exception as e:
                    self.logger.error(f"Failed to update configuration: {e}")
                    return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshots', methods=['GET'])
        def list_snapshots():
            """列出所有快照"""
            try:
                snapshots = self.manager.list_snapshots()
                snapshot_list = []

                for snapshot in snapshots:
                    stat = snapshot.stat()
                    snapshot_list.append({
                        'name': snapshot.name,
                        'path': str(snapshot),
                        'created_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'size': stat.st_size
                    })

                return jsonify({
                    'snapshots': snapshot_list,
                    'count': len(snapshot_list)
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshots', methods=['POST'])
        def create_snapshot():
            """创建快照"""
            try:
                data = request.get_json() or {}
                event_info = data.get('description', 'Manual snapshot via API')
                client_ip = request.remote_addr
                self.logger.info(f"用户 {client_ip} 请求创建快照，描述: {event_info}")

                success = self.manager.create_snapshot(event_info)

                if success:
                    # 获取最新快照信息
                    snapshots = self.manager.list_snapshots()
                    latest = snapshots[-1] if snapshots else None
                    self.logger.info(f"用户 {client_ip} 成功创建快照: {latest.name if latest else 'Unknown'}")

                    return jsonify({
                        'success': True,
                        'message': 'Snapshot created successfully',
                        'snapshot': {
                            'name': latest.name if latest else None,
                            'path': str(latest) if latest else None,
                            'created_time': datetime.now().isoformat()
                        }
                    })
                else:
                    self.logger.error(f"用户 {client_ip} 快照创建失败")
                    return jsonify({
                        'success': False,
                        'message': 'Failed to create snapshot'
                    }), 400

            except Exception as e:
                self.logger.error(f"创建快照时发生异常: {str(e)}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshots/<snapshot_name>', methods=['DELETE'])
        def delete_snapshot(snapshot_name):
            """删除指定快照"""
            try:
                snapshot_path = Path(self.config['snapshot_dir']) / snapshot_name

                if not snapshot_path.exists():
                    return jsonify({'error': 'Snapshot not found'}), 404

                success = self.manager._delete_snapshot(snapshot_path)

                if success:
                    return jsonify({
                        'success': True,
                        'message': f'Snapshot {snapshot_name} deleted successfully'
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Failed to delete snapshot'
                    }), 400

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshots/<snapshot_name>/restore', methods=['POST'])
        def restore_snapshot(snapshot_name):
            """恢复指定快照"""
            try:
                snapshot_path = Path(self.config['snapshot_dir']) / snapshot_name
                watch_path = Path(self.config['watch_dir'])

                if not snapshot_path.exists():
                    return jsonify({'error': 'Snapshot not found'}), 404

                if not watch_path.exists():
                    return jsonify({'error': 'Watch directory not found'}), 404

                # 备份当前目录
                import shutil
                from datetime import datetime
                backup_name = f"projects_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_path = watch_path.parent / backup_name

                # 执行恢复
                import subprocess
                import os

                # 1. 备份当前目录
                if watch_path.exists():
                    shutil.move(str(watch_path), str(backup_path))

                # 2. 从快照创建新的子卷
                result = subprocess.run([
                    'btrfs', 'subvolume', 'snapshot', str(snapshot_path), str(watch_path)
                ], capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    self.logger.info(f"Snapshot {snapshot_name} restored successfully")
                    self.logger.info(f"Original directory backed up to: {backup_path}")

                    return jsonify({
                        'success': True,
                        'message': f'Snapshot {snapshot_name} restored successfully',
                        'backup_path': str(backup_path),
                        'restored_at': datetime.now().isoformat()
                    })
                else:
                    # 恢复失败，尝试恢复备份
                    if backup_path.exists():
                        shutil.move(str(backup_path), str(watch_path))
                    return jsonify({'error': f'Restore failed: {result.stderr}'}), 500

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshots/cleanup', methods=['POST'])
        def cleanup_snapshots():
            """清理旧快照"""
            try:
                deleted = self.manager.cleanup_old_snapshots()

                return jsonify({
                    'success': True,
                    'message': f'Cleaned up {len(deleted)} old snapshots',
                    'deleted_snapshots': deleted,
                    'count': len(deleted)
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshots/info', methods=['GET'])
        def get_snapshot_info():
            """获取快照统计信息"""
            try:
                info = self.manager.get_snapshot_info()
                return jsonify(info)

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/monitoring', methods=['GET'])
        def get_monitoring_status():
            """获取监控状态"""
            return jsonify({
                'active': self.monitoring_active,
                'watch_dir': self.config['watch_dir'],
                'watcher_alive': self.watcher.is_alive() if self.watcher else False
            })

        @self.app.route('/api/monitoring/start', methods=['POST'])
        def start_monitoring():
            """启动文件监控"""
            try:
                client_ip = request.remote_addr
                self.logger.info(f"用户 {client_ip} 请求启动文件监控")

                if self.monitoring_active:
                    self.logger.warning(f"用户 {client_ip} 尝试启动已运行的监控")
                    return jsonify({
                        'success': False,
                        'message': 'Monitoring is already active'
                    }), 400

                def on_file_change(event_type, file_path):
                    self.logger.info(f"检测到文件变化: {event_type} - {file_path}")
                    success = self.manager.create_snapshot(f"{event_type}: {file_path}")
                    if success:
                        self.manager.cleanup_old_snapshots()

                self.watcher = FileSystemWatcher(
                    watch_dir=self.config['watch_dir'],
                    callback=on_file_change,
                    debounce_seconds=self.config.get('debounce_seconds', 5)
                )

                self.watcher.start()
                self.monitoring_active = True
                self.logger.info(f"用户 {client_ip} 成功启动文件监控")

                return jsonify({
                    'success': True,
                    'message': 'File monitoring started'
                })

            except Exception as e:
                self.logger.error(f"启动监控时发生异常: {str(e)}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/monitoring/stop', methods=['POST'])
        def stop_monitoring():
            """停止文件监控"""
            try:
                client_ip = request.remote_addr
                self.logger.info(f"用户 {client_ip} 请求停止文件监控")

                if not self.monitoring_active:
                    self.logger.warning(f"用户 {client_ip} 尝试停止未运行的监控")
                    return jsonify({
                        'success': False,
                        'message': 'Monitoring is not active'
                    }), 400

                if self.watcher:
                    self.watcher.stop()

                self.monitoring_active = False
                self.logger.info(f"用户 {client_ip} 成功停止文件监控")

                return jsonify({
                    'success': True,
                    'message': 'File monitoring stopped'
                })

            except Exception as e:
                self.logger.error(f"停止监控时发生异常: {str(e)}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/files', methods=['GET'])
        def list_files():
            """列出监控目录中的文件和目录"""
            try:
                watch_path = Path(self.config['watch_dir'])

                if not watch_path.exists():
                    return jsonify({'error': 'Watch directory does not exist'}), 404

                items = []
                # 只列出直接子项，不递归
                for item in watch_path.iterdir():
                    try:
                        stat = item.stat()
                        is_directory = item.is_dir()

                        item_info = {
                            'name': item.name,
                            'path': item.name,
                            'full_path': str(item),
                            'is_directory': is_directory,
                            'size': stat.st_size if not is_directory else 0,
                            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        }

                        if is_directory:
                            # 如果是目录，计算子项数量
                            try:
                                sub_items = list(item.iterdir())
                                item_info['item_count'] = len(sub_items)
                            except:
                                item_info['item_count'] = 0

                        items.append(item_info)
                    except (PermissionError, OSError):
                        # 跳过无权限访问的项
                        continue

                return jsonify({
                    'files': items,
                    'count': len(items),
                    'watch_dir': str(watch_path),
                    'has_files': any(not item.get('is_directory', False) for item in items),
                    'has_directories': any(item.get('is_directory', False) for item in items)
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/stats', methods=['GET'])
        def get_stats():
            """获取系统统计信息"""
            try:
                import shutil
                import psutil

                # 磁盘使用情况
                disk_usage = shutil.disk_usage(self.config['snapshot_dir'])

                # 系统信息
                stats = {
                    'disk': {
                        'total': disk_usage.total,
                        'used': disk_usage.used,
                        'free': disk_usage.free,
                        'percent': (disk_usage.used / disk_usage.total) * 100
                    },
                    'system': {
                        'cpu_percent': psutil.cpu_percent(),
                        'memory_percent': psutil.virtual_memory().percent,
                        'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None
                    },
                    'snapshots': self.manager.get_snapshot_info(),
                    'monitoring': {
                        'active': self.monitoring_active,
                        'uptime': time.time() - getattr(self, 'start_time', time.time())
                    }
                }

                return jsonify(stats)

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/logs', methods=['GET'])
        def get_logs():
            """获取系统日志 - 显示实时API服务日志"""
            import time
            import re
            from datetime import datetime, timedelta
            from pathlib import Path
            import glob

            try:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S')
                logs = []

                # 系统状态信息
                logs.append(f"[{current_time}] 📊 实时系统日志")

                try:
                    # 直接从容器内的日志文件或应用日志获取信息
                    processed_logs = []

                    # 获取最近的API访问记录（从应用自身的日志记录）
                    # 这里我们直接记录当前API实例的访问情况
                    recent_requests = getattr(self, 'recent_requests', [])

                    # 添加最近的请求记录
                    for req in recent_requests[-10:]:
                        req_time = req.get('time', current_time.split(' ')[1])
                        method = req.get('method', 'GET')
                        path = req.get('path', '/')
                        status = req.get('status', 200)
                        ip = req.get('ip', 'unknown')

                        # 根据路径和状态添加图标和描述
                        if '/api/snapshots' in path and method == 'POST':
                            icon = "📸"
                            desc = f"创建快照请求 ({status}) from {ip}"
                        elif '/api/snapshots/' in path and 'restore' in path and method == 'POST':
                            icon = "🔄"
                            desc = f"恢复快照请求 ({status}) from {ip}"
                        elif '/api/snapshots/' in path and method == 'DELETE':
                            icon = "🗑️"
                            desc = f"删除快照请求 ({status}) from {ip}"
                        elif '/api/monitoring/start' in path and method == 'POST':
                            icon = "▶️"
                            desc = f"启动监控请求 ({status}) from {ip}"
                        elif '/api/monitoring/stop' in path and method == 'POST':
                            icon = "⏸️"
                            desc = f"停止监控请求 ({status}) from {ip}"
                        elif '/api/config' in path and method == 'POST':
                            icon = "⚙️"
                            desc = f"配置修改请求 ({status}) from {ip}"
                        elif '/api/logs' in path:
                            icon = "📋"
                            desc = f"日志查看请求 ({status}) from {ip}"
                        else:
                            icon = "🌐"
                            desc = f"{method} {path} ({status})"

                        processed_logs.append(f"[{req_time}] {icon} {desc}")

                    # 获取快照相关操作记录
                    snapshot_log_file = Path('/app/logs/snapshot_operations.log')
                    if snapshot_log_file.exists():
                        try:
                            with open(snapshot_log_file, 'r', encoding='utf-8') as f:
                                snapshot_lines = f.readlines()[-10:]  # 最近10行
                                for line in snapshot_lines:
                                    line = line.strip()
                                    if line:
                                        if 'created' in line.lower():
                                            processed_logs.append(f"[{current_time.split(' ')[1]}] ✅ {line}")
                                        elif 'deleted' in line.lower():
                                            processed_logs.append(f"[{current_time.split(' ')[1]}] 🗑️ {line}")
                                        elif 'restored' in line.lower():
                                            processed_logs.append(f"[{current_time.split(' ')[1]}] 🔄 {line}")
                        except:
                            pass

                    # 添加处理后的日志（最近的15条）
                    logs.extend(processed_logs[-15:])

                    # 获取当前系统状态信息
                    try:
                        # 快照统计信息
                        snapshot_dir = Path('/vol1/1000/snapshots')
                        if snapshot_dir.exists():
                            snapshots = [item for item in snapshot_dir.iterdir() if item.is_dir() and item.name not in ['.', '..']]
                            logs.append(f"[{current_time.split(' ')[1]}] 📸 当前快照总数: {len(snapshots)}")

                            # 显示最新的快照
                            if snapshots:
                                latest_snapshot = max(snapshots, key=lambda x: x.stat().st_mtime)
                                logs.append(f"[{current_time.split(' ')[1]}] 🆕 最新快照: {latest_snapshot.name}")

                        # 监控状态
                        if hasattr(self, 'watcher') and self.watcher and self.watcher.is_alive():
                            logs.append(f"[{current_time.split(' ')[1]}] 👀 监控服务运行中")
                        else:
                            logs.append(f"[{current_time.split(' ')[1]}] ⏸️ 监控服务已停止")

                    except Exception as e:
                        logs.append(f"[{current_time.split(' ')[1]}] ⚠️ 获取系统状态时出错: {str(e)}")

                    # 如果日志不够，添加一些默认信息
                    if len(logs) < 5:
                        logs.append(f"[{current_time.split(' ')[1]}] 💡 系统运行正常，等待用户操作...")

                except Exception as e:
                    logs.append(f"[{current_time}] ⚠️ 获取实时日志时出错: {str(e)}")

                # 添加最后更新时间
                logs.append(f"[{current_time.split(' ')[1]}] 🕐 日志更新时间")

                return jsonify({
                    'logs': logs[-20:],  # 返回最近20条日志
                    'count': len(logs[-20:]),
                    'source': 'realtime',
                    'timestamp': current_time
                })

            except Exception as e:
                error_time = time.strftime('%Y-%m-%d %H:%M:%S')
                fallback_logs = [
                    f"[{error_time}] ❌ 无法获取实时日志",
                    f"[{error_time}] 🔧 请检查API服务状态",
                    f"[{error_time}] 📞 联系系统管理员"
                ]
                return jsonify({
                    'logs': fallback_logs,
                    'count': len(fallback_logs),
                    'source': 'error',
                    'timestamp': error_time
                })

        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({'error': 'API endpoint not found'}), 404

        @self.app.errorhandler(500)
        def internal_error(error):
            return jsonify({'error': 'Internal server error'}), 500

    def run(self, host='127.0.0.1', port=5000, debug=False):
        """启动API服务器"""
        self.start_time = time.time()
        self.logger.info(f"Starting Btrfs Snapshot Manager API on {host}:{port}")
        self.logger.info(f"Watch directory: {self.config['watch_dir']}")
        self.logger.info(f"Snapshot directory: {self.config['snapshot_dir']}")

        try:
            self.app.run(host=host, port=port, debug=debug)
        finally:
            # 清理资源
            if self.watcher and self.monitoring_active:
                self.watcher.stop()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Btrfs Snapshot Manager API Server')
    parser.add_argument('-c', '--config', help='Configuration file path', default='config.yaml')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()

    api = SnapshotAPI(config_path=args.config)
    api.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()