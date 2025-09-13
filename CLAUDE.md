# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Btrfs automatic snapshot management system for TrueNAS (FeiNiuOS) running on Intel N100 with 16GB RAM. The system monitors specified directories for changes and automatically creates/manages Btrfs snapshots.

## Key Requirements

### Core Functionality
- **Directory Monitoring**: Use `inotify` or `watchdog` to monitor file system events
- **Automatic Snapshots**: Create Btrfs snapshots on file changes using: `btrfs subvolume snapshot /data/mydir /data/snapshots/mydir_YYYYMMDD_HHMMSS`
- **Snapshot Management**: Maintain maximum N snapshots (e.g., 50) or time-based retention
- **Logging**: All operations logged to `/var/log/btrfs_snapshot.log`
- **Error Resilience**: Continue operation even if individual snapshot fails

### Configuration Parameters
- `watch_dir`: Directory to monitor (must be Btrfs subvolume)
- `snapshot_dir`: Location for snapshots
- `max_snapshots`: Maximum number of snapshots to retain
- `mode`: Cleanup mode (count-based or time-based)

## Development Commands

```bash
# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the snapshot manager (remember to activate venv first)
source venv/bin/activate
sudo python btrfs_snapshot_manager.py

# User installation (no sudo required, no systemd)
bash install.sh --user

# System installation (requires sudo for systemd service)
sudo bash install.sh

# Run as systemd service (after system installation)
sudo systemctl start btrfs-snapshot-manager
sudo systemctl enable btrfs-snapshot-manager

# Check logs
tail -f /var/log/btrfs_snapshot.log

# Test snapshot creation manually
sudo btrfs subvolume snapshot /data/mydir /data/snapshots/test_snapshot
```

## Architecture Notes

### Main Components
1. **FileWatcher**: Monitors directory using watchdog/inotify
2. **SnapshotManager**: Handles Btrfs snapshot creation/deletion
3. **ConfigLoader**: Reads YAML/JSON configuration
4. **Logger**: Structured logging to file

### Critical Considerations
- **Cooldown Period**: Implement 1-minute minimum between snapshots to avoid excessive snapshot creation
- **Root Privileges**: Script must run as root for Btrfs operations
- **Subvolume Validation**: Verify monitored directory is a Btrfs subvolume before starting
- **Disk Space**: Check available space before creating snapshots
- **Atomic Operations**: Use proper locking to prevent concurrent snapshot operations

### Error Handling
- Non-Btrfs filesystem: Exit with clear error message
- Insufficient permissions: Log and notify, require root
- Disk full: Skip snapshot, log error, continue monitoring
- Rapid file changes: Enforce cooldown period between snapshots

## File Structure
```
/
├── btrfs_snapshot_manager.py  # Main application
├── config.yaml                # Configuration file
├── requirements.txt           # Python dependencies
├── systemd/
│   └── btrfs-snapshot-manager.service
└── tests/
    └── test_snapshot_manager.py
```

## Testing Approach

```bash
# Unit tests
python -m pytest tests/

# Integration test with test directory
sudo python btrfs_snapshot_manager.py --test-mode --watch-dir /data/test_dir

# Verify snapshot creation
sudo btrfs subvolume list /data/snapshots
```

## Important Implementation Details

- Use `subprocess.run()` with proper error handling for Btrfs commands
- Implement signal handlers for graceful shutdown
- Use `pathlib.Path` for path operations
- Configuration should support both YAML and command-line arguments
- Snapshot naming must use format: `mydir_YYYYMMDD_HHMMSS` for sortability
- Implement dry-run mode for testing without actual snapshot creation