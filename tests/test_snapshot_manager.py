#!/usr/bin/env python3

import unittest
import tempfile
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from snapshot_manager import SnapshotManager
from config_loader import ConfigLoader
from fs_watcher import FileSystemWatcher


class TestSnapshotManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="btrfs_test_")
        self.watch_dir = Path(self.test_dir) / "watch"
        self.snapshot_dir = Path(self.test_dir) / "snapshots"

        self.watch_dir.mkdir(parents=True)
        self.snapshot_dir.mkdir(parents=True)

        self.manager = SnapshotManager(
            watch_dir=str(self.watch_dir),
            snapshot_dir=str(self.snapshot_dir),
            max_snapshots=3,
            cleanup_mode='count',
            cooldown_seconds=1,
            test_mode=True
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_snapshot(self):
        success = self.manager.create_snapshot("test event")
        self.assertTrue(success)

        snapshots = self.manager.list_snapshots()
        self.assertEqual(len(snapshots), 1)

    def test_cooldown_period(self):
        success1 = self.manager.create_snapshot("event 1")
        self.assertTrue(success1)

        success2 = self.manager.create_snapshot("event 2")
        self.assertFalse(success2)

        time.sleep(1.5)

        success3 = self.manager.create_snapshot("event 3")
        self.assertTrue(success3)

        snapshots = self.manager.list_snapshots()
        self.assertEqual(len(snapshots), 2)

    def test_cleanup_by_count(self):
        self.manager.cooldown_seconds = 0

        for i in range(5):
            self.manager.create_snapshot(f"event {i}")
            time.sleep(0.1)

        self.manager.cleanup_old_snapshots()

        snapshots = self.manager.list_snapshots()
        self.assertEqual(len(snapshots), 3)

    def test_cleanup_by_time(self):
        self.manager.cleanup_mode = 'time'
        self.manager.retention_days = 1  # Keep snapshots for 1 day
        self.manager.cooldown_seconds = 0

        for i in range(3):
            self.manager.create_snapshot(f"event {i}")
            time.sleep(0.1)

        snapshots = self.manager.list_snapshots()
        # Make first 2 snapshots older than retention period
        for snapshot in snapshots[:2]:
            old_time = time.time() - (2 * 86400)  # 2 days old
            os.utime(snapshot, (old_time, old_time))

        deleted = self.manager.cleanup_old_snapshots()

        self.assertEqual(len(deleted), 2)

        remaining = self.manager.list_snapshots()
        self.assertEqual(len(remaining), 1)

    def test_snapshot_info(self):
        self.manager.cooldown_seconds = 0

        for i in range(2):
            self.manager.create_snapshot(f"event {i}")
            time.sleep(0.1)

        info = self.manager.get_snapshot_info()

        self.assertEqual(info['count'], 2)
        self.assertIsNotNone(info['oldest'])
        self.assertIsNotNone(info['newest'])
        self.assertIsNotNone(info['last_snapshot_time'])


class TestConfigLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="config_test_")
        self.config_file = Path(self.temp_dir) / "test_config.yaml"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_config(self):
        loader = ConfigLoader()
        config = loader.load()

        self.assertIn('watch_dir', config)
        self.assertIn('snapshot_dir', config)
        self.assertIn('max_snapshots', config)
        self.assertEqual(config['cleanup_mode'], 'count')

    def test_load_yaml_config(self):
        import yaml

        test_config = {
            'watch_dir': '/test/watch',
            'snapshot_dir': '/test/snapshots',
            'max_snapshots': 100,
            'cleanup_mode': 'time'
        }

        with open(self.config_file, 'w') as f:
            yaml.dump(test_config, f)

        loader = ConfigLoader(str(self.config_file))
        config = loader.load()

        self.assertEqual(config['watch_dir'], '/test/watch')
        self.assertEqual(config['max_snapshots'], 100)
        self.assertEqual(config['cleanup_mode'], 'time')

    def test_env_override(self):
        os.environ['BTRFS_MAX_SNAPSHOTS'] = '200'

        loader = ConfigLoader()
        config = loader.load()

        self.assertEqual(config['max_snapshots'], 200)

        del os.environ['BTRFS_MAX_SNAPSHOTS']


class TestFileSystemWatcher(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="watcher_test_")
        self.events_received = []

        def callback(event_type, file_path):
            self.events_received.append((event_type, file_path))

        self.watcher = FileSystemWatcher(
            watch_dir=self.test_dir,
            callback=callback,
            debounce_seconds=1
        )

    def tearDown(self):
        self.watcher.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_file_creation_detection(self):
        self.watcher.start()

        test_file = Path(self.test_dir) / "test.txt"
        test_file.write_text("test content")

        time.sleep(2)

        self.assertTrue(len(self.events_received) > 0)

    def test_debouncing(self):
        self.watcher.start()

        for i in range(5):
            test_file = Path(self.test_dir) / f"test{i}.txt"
            test_file.write_text(f"content {i}")
            time.sleep(0.1)

        time.sleep(2)

        self.assertEqual(len(self.events_received), 1)

    def test_ignore_patterns(self):
        self.watcher.start()

        tmp_file = Path(self.test_dir) / "test.tmp"
        tmp_file.write_text("temp content")

        real_file = Path(self.test_dir) / "real.txt"
        real_file.write_text("real content")

        time.sleep(2)

        self.assertEqual(len(self.events_received), 1)


if __name__ == '__main__':
    unittest.main()