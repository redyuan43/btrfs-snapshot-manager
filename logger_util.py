#!/usr/bin/env python3

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


def setup_logging(log_file: str = '/var/log/btrfs_snapshot.log',
                  level: int = logging.INFO,
                  console: bool = True,
                  max_bytes: int = 10485760,
                  backup_count: int = 5):

    logger = logging.getLogger()
    logger.setLevel(level)

    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    except PermissionError:
        if console:
            logger.warning(f"Cannot write to log file {log_file} (permission denied). Using console only.")
        else:
            fallback_log = Path.home() / '.btrfs_snapshot.log'
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    str(fallback_log),
                    maxBytes=max_bytes,
                    backupCount=backup_count
                )
                file_handler.setLevel(level)
                file_handler.setFormatter(log_format)
                logger.addHandler(file_handler)
                logger.warning(f"Using fallback log location: {fallback_log}")
            except Exception as e:
                if console:
                    logger.error(f"Failed to setup any file logging: {e}")

    except Exception as e:
        if console:
            logger.error(f"Failed to setup file logging: {e}")

    logging.getLogger('watchdog').setLevel(logging.WARNING)

    return logger


class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def log_snapshot_created(self, snapshot_path: str, trigger: str = "", size: int = 0):
        self.logger.info(
            f"SNAPSHOT_CREATED | path={snapshot_path} | trigger={trigger} | size={size}"
        )

    def log_snapshot_deleted(self, snapshot_path: str, reason: str = ""):
        self.logger.info(
            f"SNAPSHOT_DELETED | path={snapshot_path} | reason={reason}"
        )

    def log_cleanup_summary(self, deleted_count: int, remaining_count: int):
        self.logger.info(
            f"CLEANUP_COMPLETE | deleted={deleted_count} | remaining={remaining_count}"
        )

    def log_error(self, operation: str, error: str, details: str = ""):
        self.logger.error(
            f"ERROR | operation={operation} | error={error} | details={details}"
        )

    def log_service_event(self, event: str, details: str = ""):
        self.logger.info(
            f"SERVICE | event={event} | details={details}"
        )


def get_structured_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)