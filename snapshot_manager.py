#!/usr/bin/env python3

import os
import subprocess
import logging
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import psutil


class SnapshotManager:
    def __init__(self, watch_dir: str, snapshot_dir: str, max_snapshots: int = 50,
                 cleanup_mode: str = 'count', retention_days: int = 7,
                 cooldown_seconds: int = 60, test_mode: bool = False):
        self.watch_dir = Path(watch_dir)
        self.snapshot_dir = Path(snapshot_dir)
        self.max_snapshots = max_snapshots
        self.cleanup_mode = cleanup_mode
        self.retention_days = retention_days
        self.cooldown_seconds = cooldown_seconds
        self.test_mode = test_mode

        self.logger = logging.getLogger(__name__)
        self.last_snapshot_time: Optional[datetime] = None

        self.snapshot_prefix = self.watch_dir.name

        if not self.snapshot_dir.exists():
            self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, event_info: str = "") -> bool:
        if not self._check_cooldown():
            self.logger.info(f"Skipping snapshot - cooldown period active (last snapshot: {self.last_snapshot_time})")
            return False

        if not self._check_disk_space():
            self.logger.error("Insufficient disk space for snapshot")
            return False

        # Add microseconds to ensure unique timestamps in test mode
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Use milliseconds
        snapshot_name = f"{self.snapshot_prefix}_{timestamp}"
        snapshot_path = self.snapshot_dir / snapshot_name

        try:
            if self.test_mode:
                self.logger.info(f"[TEST MODE] Would create snapshot: {snapshot_path}")
                if not snapshot_path.exists():
                    snapshot_path.mkdir(parents=True, exist_ok=True)
                    (snapshot_path / "test_file.txt").write_text(f"Test snapshot created at {timestamp}")
            else:
                cmd = [
                    'btrfs', 'subvolume', 'snapshot',
                    str(self.watch_dir),
                    str(snapshot_path)
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

            self.last_snapshot_time = datetime.now()
            self.logger.info(f"Snapshot created: {snapshot_path}")

            if event_info:
                self.logger.info(f"Triggered by: {event_info}")

            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create snapshot: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating snapshot: {e}", exc_info=True)
            return False

    def _check_cooldown(self) -> bool:
        if self.last_snapshot_time is None:
            return True

        elapsed = (datetime.now() - self.last_snapshot_time).total_seconds()
        return elapsed >= self.cooldown_seconds

    def _check_disk_space(self, min_free_gb: float = 1.0) -> bool:
        try:
            stat = shutil.disk_usage(self.snapshot_dir)
            free_gb = stat.free / (1024 ** 3)

            if free_gb < min_free_gb:
                self.logger.warning(f"Low disk space: {free_gb:.2f} GB free")
                return False

            return True
        except Exception as e:
            self.logger.error(f"Failed to check disk space: {e}")
            return True

    def list_snapshots(self) -> List[Path]:
        try:
            snapshots = []
            prefix_pattern = f"{self.snapshot_prefix}_"

            for item in self.snapshot_dir.iterdir():
                if item.is_dir() and item.name.startswith(prefix_pattern):
                    snapshots.append(item)

            snapshots.sort(key=lambda x: x.stat().st_mtime)
            return snapshots

        except Exception as e:
            self.logger.error(f"Failed to list snapshots: {e}", exc_info=True)
            return []

    def cleanup_old_snapshots(self) -> List[str]:
        deleted = []

        try:
            snapshots = self.list_snapshots()

            if not snapshots:
                return deleted

            if self.cleanup_mode == 'count':
                deleted = self._cleanup_by_count(snapshots)
            elif self.cleanup_mode == 'time':
                deleted = self._cleanup_by_time(snapshots)
            else:
                self.logger.error(f"Unknown cleanup mode: {self.cleanup_mode}")

        except Exception as e:
            self.logger.error(f"Failed during cleanup: {e}", exc_info=True)

        return deleted

    def _cleanup_by_count(self, snapshots: List[Path]) -> List[str]:
        deleted = []

        if len(snapshots) <= self.max_snapshots:
            self.logger.debug(f"Snapshot count ({len(snapshots)}) within limit ({self.max_snapshots})")
            return deleted

        snapshots_to_delete = snapshots[:-self.max_snapshots]

        for snapshot in snapshots_to_delete:
            if self._delete_snapshot(snapshot):
                deleted.append(str(snapshot))

        if deleted:
            self.logger.info(f"Deleted {len(deleted)} old snapshots (keeping {self.max_snapshots})")

        return deleted

    def _cleanup_by_time(self, snapshots: List[Path]) -> List[str]:
        deleted = []
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)

        for snapshot in snapshots:
            try:
                snapshot_time = datetime.fromtimestamp(snapshot.stat().st_mtime)

                if snapshot_time < cutoff_time:
                    if self._delete_snapshot(snapshot):
                        deleted.append(str(snapshot))
                        self.logger.info(f"Deleted old snapshot: {snapshot.name} (age: {(datetime.now() - snapshot_time).days} days)")

            except Exception as e:
                self.logger.error(f"Error checking snapshot age for {snapshot}: {e}")

        return deleted

    def _delete_snapshot(self, snapshot_path: Path) -> bool:
        try:
            if self.test_mode:
                self.logger.info(f"[TEST MODE] Would delete snapshot: {snapshot_path}")
                if snapshot_path.exists():
                    shutil.rmtree(snapshot_path)
            else:
                cmd = ['btrfs', 'subvolume', 'delete', str(snapshot_path)]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True
                )

                if result.returncode != 0:
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)

            self.logger.info(f"Deleted snapshot: {snapshot_path}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to delete snapshot {snapshot_path}: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error deleting snapshot {snapshot_path}: {e}", exc_info=True)
            return False

    def get_snapshot_info(self) -> dict:
        snapshots = self.list_snapshots()
        total_size = 0

        for snapshot in snapshots:
            try:
                if self.test_mode:
                    size = sum(f.stat().st_size for f in snapshot.rglob('*') if f.is_file())
                else:
                    cmd = ['btrfs', 'filesystem', 'du', '-s', str(snapshot)]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        if lines:
                            size_str = lines[-1].split()[0]
                            try:
                                size = self._parse_size(size_str)
                                total_size += size
                            except:
                                pass
            except:
                pass

        return {
            'count': len(snapshots),
            'total_size': total_size,
            'oldest': snapshots[0].name if snapshots else None,
            'newest': snapshots[-1].name if snapshots else None,
            'last_snapshot_time': self.last_snapshot_time.isoformat() if self.last_snapshot_time else None
        }

    def _parse_size(self, size_str: str) -> int:
        size_str = size_str.upper()
        multipliers = {
            'B': 1,
            'K': 1024,
            'M': 1024**2,
            'G': 1024**3,
            'T': 1024**4
        }

        for suffix, multiplier in multipliers.items():
            if size_str.endswith(suffix):
                return int(float(size_str[:-1]) * multiplier)

        return int(float(size_str))