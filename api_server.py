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

        # 设置路由
        self.setup_routes()

        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

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

        @self.app.route('/api/config', methods=['GET'])
        def get_config():
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

                success = self.manager.create_snapshot(event_info)

                if success:
                    # 获取最新快照信息
                    snapshots = self.manager.list_snapshots()
                    latest = snapshots[-1] if snapshots else None

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
                    return jsonify({
                        'success': False,
                        'message': 'Failed to create snapshot'
                    }), 400

            except Exception as e:
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
                if self.monitoring_active:
                    return jsonify({
                        'success': False,
                        'message': 'Monitoring is already active'
                    }), 400

                def on_file_change(event_type, file_path):
                    self.logger.info(f"File change detected: {event_type} - {file_path}")
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

                return jsonify({
                    'success': True,
                    'message': 'File monitoring started'
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/monitoring/stop', methods=['POST'])
        def stop_monitoring():
            """停止文件监控"""
            try:
                if not self.monitoring_active:
                    return jsonify({
                        'success': False,
                        'message': 'Monitoring is not active'
                    }), 400

                if self.watcher:
                    self.watcher.stop()

                self.monitoring_active = False

                return jsonify({
                    'success': True,
                    'message': 'File monitoring stopped'
                })

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/files', methods=['GET'])
        def list_files():
            """列出监控目录中的文件"""
            try:
                watch_path = Path(self.config['watch_dir'])

                if not watch_path.exists():
                    return jsonify({'error': 'Watch directory does not exist'}), 404

                files = []
                for item in watch_path.rglob('*'):
                    if item.is_file():
                        stat = item.stat()
                        rel_path = item.relative_to(watch_path)
                        files.append({
                            'name': item.name,
                            'path': str(rel_path),
                            'full_path': str(item),
                            'size': stat.st_size,
                            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })

                return jsonify({
                    'files': files,
                    'count': len(files),
                    'watch_dir': str(watch_path)
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