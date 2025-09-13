#!/usr/bin/env python3

import os
import sys
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    DEFAULT_CONFIG = {
        'watch_dir': '/data/mydir',
        'snapshot_dir': '/data/snapshots',
        'max_snapshots': 50,
        'cleanup_mode': 'count',
        'retention_days': 7,
        'cooldown_seconds': 60,
        'debounce_seconds': 5,
        'log_file': '/var/log/btrfs_snapshot.log',
        'log_level': 'INFO'
    }

    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.config_path = self._find_config_file(config_path)

    def _find_config_file(self, config_path: Optional[str]) -> Optional[Path]:
        if config_path:
            path = Path(config_path)
            if path.exists():
                return path
            else:
                self.logger.warning(f"Config file not found: {config_path}")

        default_locations = [
            Path('config.yaml'),
            Path('config.yml'),
            Path('config.json'),
            Path('/etc/btrfs-snapshot-manager/config.yaml'),
            Path('/etc/btrfs-snapshot-manager/config.yml'),
            Path('/etc/btrfs-snapshot-manager/config.json'),
            Path.home() / '.config' / 'btrfs-snapshot-manager' / 'config.yaml',
        ]

        for location in default_locations:
            if location.exists():
                self.logger.info(f"Found config file: {location}")
                return location

        self.logger.info("No config file found, using default configuration")
        return None

    def load(self) -> Dict[str, Any]:
        config = self.DEFAULT_CONFIG.copy()

        if self.config_path:
            try:
                with open(self.config_path, 'r') as f:
                    if self.config_path.suffix in ['.yaml', '.yml']:
                        file_config = yaml.safe_load(f)
                    elif self.config_path.suffix == '.json':
                        file_config = json.load(f)
                    else:
                        self.logger.error(f"Unsupported config file format: {self.config_path}")
                        sys.exit(1)

                    if file_config:
                        config.update(file_config)
                        self.logger.info(f"Loaded configuration from {self.config_path}")

            except Exception as e:
                self.logger.error(f"Failed to load config file: {e}")
                sys.exit(1)

        self._load_env_overrides(config)
        self._validate_config(config)

        return config

    def _load_env_overrides(self, config: Dict[str, Any]):
        env_mappings = {
            'BTRFS_WATCH_DIR': 'watch_dir',
            'BTRFS_SNAPSHOT_DIR': 'snapshot_dir',
            'BTRFS_MAX_SNAPSHOTS': 'max_snapshots',
            'BTRFS_CLEANUP_MODE': 'cleanup_mode',
            'BTRFS_RETENTION_DAYS': 'retention_days',
            'BTRFS_COOLDOWN_SECONDS': 'cooldown_seconds',
            'BTRFS_LOG_FILE': 'log_file',
            'BTRFS_LOG_LEVEL': 'log_level'
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                if config_key in ['max_snapshots', 'retention_days', 'cooldown_seconds']:
                    try:
                        config[config_key] = int(value)
                    except ValueError:
                        self.logger.warning(f"Invalid integer value for {env_var}: {value}")
                else:
                    config[config_key] = value
                self.logger.debug(f"Override from environment: {config_key} = {value}")

    def _validate_config(self, config: Dict[str, Any]):
        required_fields = ['watch_dir', 'snapshot_dir']
        for field in required_fields:
            if field not in config or not config[field]:
                self.logger.error(f"Required configuration field missing: {field}")
                sys.exit(1)

        if config['cleanup_mode'] not in ['count', 'time']:
            self.logger.error(f"Invalid cleanup_mode: {config['cleanup_mode']}. Must be 'count' or 'time'")
            sys.exit(1)

        if config['max_snapshots'] < 1:
            self.logger.error("max_snapshots must be at least 1")
            sys.exit(1)

        if config['retention_days'] < 1:
            self.logger.error("retention_days must be at least 1")
            sys.exit(1)

        if config['cooldown_seconds'] < 0:
            self.logger.error("cooldown_seconds cannot be negative")
            sys.exit(1)

    def save_example_config(self, path: str = 'config.yaml.example'):
        example_config = {
            'watch_dir': '/data/mydir',
            'snapshot_dir': '/data/snapshots',
            'max_snapshots': 50,
            'cleanup_mode': 'count',
            'retention_days': 7,
            'cooldown_seconds': 60,
            'debounce_seconds': 5,
            'log_file': '/var/log/btrfs_snapshot.log',
            'log_level': 'INFO',
            'exclude_patterns': [
                '*.tmp',
                '*.swp',
                '.git/*',
                '__pycache__/*'
            ]
        }

        with open(path, 'w') as f:
            yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)
            f.write('\n# Configuration for Btrfs Snapshot Manager\n')
            f.write('# \n')
            f.write('# cleanup_mode: "count" or "time"\n')
            f.write('#   - count: Keep max_snapshots number of snapshots\n')
            f.write('#   - time: Keep snapshots for retention_days days\n')
            f.write('# \n')
            f.write('# cooldown_seconds: Minimum time between snapshots\n')
            f.write('# debounce_seconds: Wait time after file change before creating snapshot\n')

        self.logger.info(f"Example configuration saved to {path}")