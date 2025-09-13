#!/usr/bin/env python3

import os
import sys
import signal
import argparse
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from config_loader import ConfigLoader
from fs_watcher import FileSystemWatcher
from snapshot_manager import SnapshotManager
from logger_util import setup_logging


class BtrfsSnapshotService:
    def __init__(self, config_path: Optional[str] = None, test_mode: bool = False):
        self.test_mode = test_mode
        self.running = False
        self.logger = logging.getLogger(__name__)

        self.config = ConfigLoader(config_path).load()

        self.validate_environment()

        self.snapshot_manager = SnapshotManager(
            watch_dir=self.config['watch_dir'],
            snapshot_dir=self.config['snapshot_dir'],
            max_snapshots=self.config.get('max_snapshots', 50),
            cleanup_mode=self.config.get('cleanup_mode', 'count'),
            retention_days=self.config.get('retention_days', 7),
            cooldown_seconds=self.config.get('cooldown_seconds', 60),
            test_mode=test_mode
        )

        self.watcher = FileSystemWatcher(
            watch_dir=self.config['watch_dir'],
            callback=self.handle_file_change,
            debounce_seconds=self.config.get('debounce_seconds', 5)
        )

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def validate_environment(self):
        if os.geteuid() != 0 and not self.test_mode:
            self.logger.error("This script must be run as root for Btrfs operations")
            sys.exit(1)

        watch_dir = Path(self.config['watch_dir'])
        if not watch_dir.exists():
            self.logger.error(f"Watch directory does not exist: {watch_dir}")
            sys.exit(1)

        if not self.test_mode and not self.is_btrfs_subvolume(watch_dir):
            self.logger.error(f"Watch directory is not a Btrfs subvolume: {watch_dir}")
            sys.exit(1)

        snapshot_dir = Path(self.config['snapshot_dir'])
        if not snapshot_dir.exists():
            self.logger.info(f"Creating snapshot directory: {snapshot_dir}")
            snapshot_dir.mkdir(parents=True, exist_ok=True)

    def is_btrfs_subvolume(self, path: Path) -> bool:
        import subprocess
        try:
            result = subprocess.run(
                ['btrfs', 'subvolume', 'show', str(path)],
                capture_output=True,
                text=True,
                check=False
            )
            return result.returncode == 0
        except FileNotFoundError:
            self.logger.error("btrfs command not found. Is btrfs-progs installed?")
            return False

    def handle_file_change(self, event_type: str, file_path: str):
        self.logger.info(f"File change detected - Type: {event_type}, Path: {file_path}")

        success = self.snapshot_manager.create_snapshot(event_info=f"{event_type}: {file_path}")

        if success:
            self.snapshot_manager.cleanup_old_snapshots()

    def signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}. Shutting down gracefully...")
        self.stop()

    def start(self):
        self.logger.info("Starting Btrfs Snapshot Manager Service")
        self.logger.info(f"Monitoring: {self.config['watch_dir']}")
        self.logger.info(f"Snapshots: {self.config['snapshot_dir']}")
        self.logger.info(f"Max snapshots: {self.config.get('max_snapshots', 50)}")
        self.logger.info(f"Cleanup mode: {self.config.get('cleanup_mode', 'count')}")

        self.running = True
        self.watcher.start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            self.stop()

    def stop(self):
        if self.running:
            self.running = False
            self.watcher.stop()
            self.logger.info("Service stopped")


def main():
    parser = argparse.ArgumentParser(description='Btrfs Automatic Snapshot Manager')
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration file',
        default='config.yaml'
    )
    parser.add_argument(
        '--test-mode',
        action='store_true',
        help='Run in test mode (no actual snapshots, no root required)'
    )
    parser.add_argument(
        '--watch-dir',
        help='Directory to monitor (overrides config)'
    )
    parser.add_argument(
        '--snapshot-dir',
        help='Directory for snapshots (overrides config)'
    )
    parser.add_argument(
        '--max-snapshots',
        type=int,
        help='Maximum number of snapshots to keep (overrides config)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List existing snapshots and exit'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Run cleanup once and exit'
    )
    parser.add_argument(
        '--snapshot-now',
        action='store_true',
        help='Create a snapshot immediately and exit'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level'
    )

    args = parser.parse_args()

    setup_logging(level=getattr(logging, args.log_level))
    logger = logging.getLogger(__name__)

    try:
        if args.list or args.cleanup or args.snapshot_now:
            config = ConfigLoader(args.config).load()

            if args.watch_dir:
                config['watch_dir'] = args.watch_dir
            if args.snapshot_dir:
                config['snapshot_dir'] = args.snapshot_dir
            if args.max_snapshots:
                config['max_snapshots'] = args.max_snapshots

            manager = SnapshotManager(
                watch_dir=config['watch_dir'],
                snapshot_dir=config['snapshot_dir'],
                max_snapshots=config.get('max_snapshots', 50),
                cleanup_mode=config.get('cleanup_mode', 'count'),
                retention_days=config.get('retention_days', 7),
                test_mode=args.test_mode
            )

            if args.list:
                snapshots = manager.list_snapshots()
                print(f"\nFound {len(snapshots)} snapshots:")
                for snap in snapshots:
                    print(f"  {snap}")

            if args.cleanup:
                deleted = manager.cleanup_old_snapshots()
                print(f"Cleaned up {len(deleted)} old snapshots")

            if args.snapshot_now:
                success = manager.create_snapshot(event_info="Manual snapshot")
                if success:
                    print("Snapshot created successfully")
                else:
                    print("Failed to create snapshot")
                    sys.exit(1)
        else:
            service = BtrfsSnapshotService(
                config_path=args.config,
                test_mode=args.test_mode
            )
            service.start()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()