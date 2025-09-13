#!/usr/bin/env python3
"""Test file monitoring in real-time"""

import time
import tempfile
import subprocess
import os
from pathlib import Path

# Create test directories
test_dir = tempfile.mkdtemp(prefix="monitor_test_")
watch_dir = Path(test_dir) / "watch"
snapshot_dir = Path(test_dir) / "snapshots"
watch_dir.mkdir(parents=True)
snapshot_dir.mkdir(parents=True)

print(f"Test directories created:")
print(f"  Watch dir: {watch_dir}")
print(f"  Snapshot dir: {snapshot_dir}")

# Create temp config file
config_file = Path(test_dir) / "test_config.yaml"
config_content = f"""
watch_dir: {watch_dir}
snapshot_dir: {snapshot_dir}
max_snapshots: 5
cleanup_mode: count
cooldown_seconds: 5
debounce_seconds: 3
log_file: {test_dir}/test.log
log_level: DEBUG
"""
config_file.write_text(config_content)

# Start the monitor in background
cmd = [
    "python3", "btrfs_snapshot_manager.py",
    "--test-mode",
    "-c", str(config_file),
    "--log-level", "INFO"
]

print("\nStarting monitor process...")
process = subprocess.Popen(cmd, env={**os.environ, 'PYTHONPATH': '.'})

try:
    # Give it time to start
    time.sleep(2)

    # Create some files
    print("\n1. Creating test1.txt...")
    (watch_dir / "test1.txt").write_text("Initial content")
    time.sleep(6)  # Wait for debounce

    print("2. Modifying test1.txt...")
    (watch_dir / "test1.txt").write_text("Modified content")
    time.sleep(6)

    print("3. Creating multiple files quickly...")
    for i in range(3):
        (watch_dir / f"batch_{i}.txt").write_text(f"Content {i}")
    time.sleep(6)

    print("4. Creating a temp file (should be ignored)...")
    (watch_dir / "test.tmp").write_text("Temp content")
    time.sleep(6)

    # Check snapshots
    print("\nChecking snapshots created:")
    snapshots = list(snapshot_dir.iterdir())
    print(f"Found {len(snapshots)} snapshots:")
    for snap in sorted(snapshots):
        print(f"  - {snap.name}")

finally:
    print("\nStopping monitor process...")
    process.terminate()
    process.wait(timeout=5)

    # Cleanup
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)
    print("Test completed and cleaned up")