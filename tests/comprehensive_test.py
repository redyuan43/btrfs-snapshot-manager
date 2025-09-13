#!/usr/bin/env python3

import os
import sys
import time
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snapshot_manager import SnapshotManager
from config_loader import ConfigLoader
from fs_watcher import FileSystemWatcher


class ComprehensiveTest:
    def __init__(self, use_real_btrfs=False):
        self.use_real_btrfs = use_real_btrfs
        self.test_results = []
        self.start_time = datetime.now()

        if use_real_btrfs and Path("/mnt/btrfs-test").exists():
            self.watch_dir = Path("/mnt/btrfs-test/test_data")
            self.snapshot_dir = Path("/mnt/btrfs-test/snapshots")
            self.test_mode = False
            print("🔥 使用真实 Btrfs 文件系统测试")
        else:
            self.test_dir = Path(tempfile.mkdtemp(prefix="comprehensive_test_"))
            self.watch_dir = self.test_dir / "watch"
            self.snapshot_dir = self.test_dir / "snapshots"
            self.test_mode = True
            print("🧪 使用测试模式")

        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        self.manager = SnapshotManager(
            watch_dir=str(self.watch_dir),
            snapshot_dir=str(self.snapshot_dir),
            max_snapshots=5,
            cleanup_mode='count',
            cooldown_seconds=3,
            test_mode=self.test_mode
        )

    def log_test(self, test_name, success, details="", duration=0):
        """记录测试结果"""
        result = {
            'test': test_name,
            'success': success,
            'details': details,
            'duration': f"{duration:.2f}s",
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)

        status = "✅" if success else "❌"
        print(f"{status} {test_name} ({duration:.2f}s)")
        if details:
            print(f"   {details}")

    def test_manual_snapshot_creation(self):
        """测试手动快照创建"""
        start = time.time()

        # 创建测试文件
        test_file = self.watch_dir / "manual_test.txt"
        test_file.write_text("Manual snapshot test content")

        # 创建快照
        success = self.manager.create_snapshot("Manual test")

        # 验证快照
        snapshots = self.manager.list_snapshots()

        duration = time.time() - start
        self.log_test(
            "手动快照创建",
            success and len(snapshots) > 0,
            f"创建了 {len(snapshots)} 个快照",
            duration
        )

        return success

    def test_multiple_snapshots(self):
        """测试多个快照创建和管理"""
        start = time.time()

        initial_count = len(self.manager.list_snapshots())

        # 创建多个快照
        self.manager.cooldown_seconds = 0  # 临时禁用冷却时间

        for i in range(3):
            test_file = self.watch_dir / f"multi_test_{i}.txt"
            test_file.write_text(f"Content {i} at {datetime.now()}")
            time.sleep(0.1)  # 确保时间戳不同
            self.manager.create_snapshot(f"Multi test {i}")

        final_count = len(self.manager.list_snapshots())
        expected_count = initial_count + 3

        duration = time.time() - start
        self.log_test(
            "多快照创建",
            final_count == expected_count,
            f"期望 {expected_count} 个快照，实际 {final_count} 个",
            duration
        )

        self.manager.cooldown_seconds = 3  # 恢复冷却时间
        return final_count == expected_count

    def test_snapshot_cleanup(self):
        """测试快照清理功能"""
        start = time.time()

        # 确保有足够的快照
        self.manager.cooldown_seconds = 0
        for i in range(7):  # 创建超过max_snapshots(5)的快照
            self.manager.create_snapshot(f"Cleanup test {i}")
            time.sleep(0.1)

        # 执行清理
        deleted = self.manager.cleanup_old_snapshots()
        remaining = self.manager.list_snapshots()

        duration = time.time() - start
        self.log_test(
            "快照清理",
            len(remaining) <= self.manager.max_snapshots,
            f"删除了 {len(deleted)} 个快照，剩余 {len(remaining)} 个",
            duration
        )

        self.manager.cooldown_seconds = 3
        return len(remaining) <= self.manager.max_snapshots

    def test_cooldown_mechanism(self):
        """测试冷却时间机制"""
        start = time.time()

        self.manager.cooldown_seconds = 2

        # 第一个快照应该成功
        success1 = self.manager.create_snapshot("Cooldown test 1")

        # 立即创建第二个快照应该失败
        success2 = self.manager.create_snapshot("Cooldown test 2")

        # 等待冷却时间后应该成功
        time.sleep(2.5)
        success3 = self.manager.create_snapshot("Cooldown test 3")

        duration = time.time() - start
        self.log_test(
            "冷却时间机制",
            success1 and not success2 and success3,
            f"第一个: {success1}, 第二个(应该失败): {success2}, 第三个: {success3}",
            duration
        )

        return success1 and not success2 and success3

    def test_file_monitoring(self):
        """测试文件监控功能"""
        start = time.time()

        events_received = []

        def callback(event_type, file_path):
            events_received.append((event_type, file_path))

        watcher = FileSystemWatcher(
            watch_dir=str(self.watch_dir),
            callback=callback,
            debounce_seconds=1
        )

        watcher.start()
        time.sleep(0.5)  # 等待启动

        # 创建文件
        test_file = self.watch_dir / "monitor_test.txt"
        test_file.write_text("Monitor test content")

        # 修改文件
        time.sleep(0.2)
        test_file.write_text("Modified content")

        # 等待事件处理
        time.sleep(2)
        watcher.stop()

        duration = time.time() - start
        self.log_test(
            "文件监控",
            len(events_received) > 0,
            f"接收到 {len(events_received)} 个事件",
            duration
        )

        return len(events_received) > 0

    def test_configuration_loading(self):
        """测试配置加载"""
        start = time.time()

        # 创建临时配置文件
        config_content = {
            'watch_dir': str(self.watch_dir),
            'snapshot_dir': str(self.snapshot_dir),
            'max_snapshots': 10,
            'cleanup_mode': 'time',
            'retention_days': 7
        }

        config_file = self.test_dir / "test_config.yaml" if hasattr(self, 'test_dir') else Path("/tmp/test_config.yaml")

        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f)

        # 加载配置
        loader = ConfigLoader(str(config_file))
        config = loader.load()

        # 验证配置
        success = (
            config['max_snapshots'] == 10 and
            config['cleanup_mode'] == 'time' and
            config['retention_days'] == 7
        )

        duration = time.time() - start
        self.log_test(
            "配置加载",
            success,
            f"最大快照: {config['max_snapshots']}, 清理模式: {config['cleanup_mode']}",
            duration
        )

        # 清理
        config_file.unlink()
        return success

    def test_snapshot_info(self):
        """测试快照信息获取"""
        start = time.time()

        # 确保有一些快照
        self.manager.cooldown_seconds = 0
        self.manager.create_snapshot("Info test 1")
        self.manager.create_snapshot("Info test 2")

        info = self.manager.get_snapshot_info()

        success = (
            info['count'] >= 2 and
            info['newest'] is not None and
            info['oldest'] is not None
        )

        duration = time.time() - start
        self.log_test(
            "快照信息获取",
            success,
            f"数量: {info['count']}, 最新: {info['newest']}, 最旧: {info['oldest']}",
            duration
        )

        self.manager.cooldown_seconds = 3
        return success

    def test_error_handling(self):
        """测试错误处理"""
        start = time.time()

        # 测试不存在的目录
        bad_manager = SnapshotManager(
            watch_dir="/non/existent/directory",
            snapshot_dir="/tmp/test_snapshots",
            test_mode=True
        )

        success = not bad_manager.create_snapshot("Should fail")

        duration = time.time() - start
        self.log_test(
            "错误处理",
            success,
            "正确处理了不存在的目录",
            duration
        )

        return success

    def run_all_tests(self):
        """运行所有测试"""
        print(f"\n{'='*60}")
        print(f"🚀 开始综合功能测试")
        print(f"测试环境: {'真实 Btrfs' if not self.test_mode else '模拟模式'}")
        print(f"监控目录: {self.watch_dir}")
        print(f"快照目录: {self.snapshot_dir}")
        print(f"{'='*60}\n")

        # 运行所有测试
        tests = [
            self.test_configuration_loading,
            self.test_manual_snapshot_creation,
            self.test_multiple_snapshots,
            self.test_cooldown_mechanism,
            self.test_snapshot_cleanup,
            self.test_file_monitoring,
            self.test_snapshot_info,
            self.test_error_handling
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                self.log_test(
                    test.__name__.replace('test_', '').replace('_', ' '),
                    False,
                    f"异常: {str(e)}",
                    0
                )

        self.generate_report()

    def generate_report(self):
        """生成测试报告"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r['success'])
        failed_tests = total_tests - passed_tests
        total_duration = (datetime.now() - self.start_time).total_seconds()

        print(f"\n{'='*60}")
        print(f"📊 测试报告")
        print(f"{'='*60}")
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
        print(f"总耗时: {total_duration:.2f}s")
        print(f"{'='*60}")

        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")

        # 保存详细报告
        report_file = Path("test_report.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total': total_tests,
                    'passed': passed_tests,
                    'failed': failed_tests,
                    'success_rate': passed_tests/total_tests*100,
                    'duration': total_duration,
                    'environment': 'real_btrfs' if not self.test_mode else 'test_mode'
                },
                'results': self.test_results
            }, f, indent=2, ensure_ascii=False)

        print(f"\n📄 详细报告保存至: {report_file}")

    def cleanup(self):
        """清理测试环境"""
        if hasattr(self, 'test_dir') and self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)


def main():
    use_real_btrfs = "--real-btrfs" in sys.argv

    test = ComprehensiveTest(use_real_btrfs=use_real_btrfs)

    try:
        test.run_all_tests()
    finally:
        test.cleanup()


if __name__ == "__main__":
    main()