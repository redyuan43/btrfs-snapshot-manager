#!/usr/bin/env python3

import os
import time
import logging
import threading
from pathlib import Path
from typing import Callable, Set, Optional
from datetime import datetime, timedelta

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class FileSystemWatcher:
    def __init__(self, watch_dir: str, callback: Callable, debounce_seconds: int = 5):
        self.watch_dir = Path(watch_dir)
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.logger = logging.getLogger(__name__)

        self.observer = Observer()
        self.handler = DebouncedEventHandler(
            callback=callback,
            debounce_seconds=debounce_seconds,
            logger=self.logger
        )

        self._setup_observer()

    def _setup_observer(self):
        self.observer.schedule(
            self.handler,
            str(self.watch_dir),
            recursive=True
        )
        self.logger.info(f"File watcher configured for: {self.watch_dir}")

    def start(self):
        self.observer.start()
        self.logger.info("File system watcher started")

    def stop(self):
        self.observer.stop()
        self.observer.join(timeout=5)
        self.logger.info("File system watcher stopped")

    def is_alive(self) -> bool:
        return self.observer.is_alive()


class DebouncedEventHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable, debounce_seconds: int, logger: logging.Logger):
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.logger = logger

        self.pending_events: Set[str] = set()
        self.last_event_time: Optional[datetime] = None
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()

        self.ignore_patterns = [
            '*.tmp',
            '*.swp',
            '*.swx',
            '*.lock',
            '.~lock.*',
            '~$*',
            '.git',
            '__pycache__',
            '*.pyc',
            '.DS_Store',
            'Thumbs.db'
        ]

    def should_ignore(self, path: str) -> bool:
        path_obj = Path(path)
        name = path_obj.name

        for pattern in self.ignore_patterns:
            if pattern.startswith('*.'):
                if name.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                if name.startswith(pattern[:-1]):
                    return True
            elif pattern in str(path_obj):
                return True

        return False

    def on_any_event(self, event: FileSystemEvent):
        if event.is_directory:
            return

        if self.should_ignore(event.src_path):
            self.logger.debug(f"Ignoring event for: {event.src_path}")
            return

        event_type = event.event_type
        file_path = event.src_path

        with self.lock:
            self.pending_events.add(f"{event_type}:{file_path}")
            self.last_event_time = datetime.now()

            if self.timer:
                self.timer.cancel()

            self.timer = threading.Timer(self.debounce_seconds, self._process_events)
            self.timer.start()

            self.logger.debug(f"Event queued - Type: {event_type}, Path: {file_path}")

    def _process_events(self):
        with self.lock:
            if not self.pending_events:
                return

            events_to_process = list(self.pending_events)
            self.pending_events.clear()
            self.timer = None

        self.logger.info(f"Processing {len(events_to_process)} debounced events")

        event_summary = self._summarize_events(events_to_process)

        try:
            self.callback(event_summary['type'], event_summary['description'])
        except Exception as e:
            self.logger.error(f"Error in callback: {e}", exc_info=True)

    def _summarize_events(self, events: list) -> dict:
        event_types = set()
        affected_files = set()

        for event in events:
            event_type, file_path = event.split(':', 1)
            event_types.add(event_type)
            affected_files.add(Path(file_path).name)

        if len(affected_files) <= 3:
            file_list = ', '.join(affected_files)
        else:
            file_list = f"{len(affected_files)} files"

        primary_type = 'modified' if 'modified' in event_types else list(event_types)[0]

        return {
            'type': primary_type,
            'description': file_list,
            'event_count': len(events),
            'unique_files': len(affected_files)
        }


class InotifyWatcher:
    def __init__(self, watch_dir: str, callback: Callable, debounce_seconds: int = 5):
        self.watch_dir = Path(watch_dir)
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.logger = logging.getLogger(__name__)
        self.running = False

        try:
            import inotify.adapters
            self.inotify_available = True
            self.inotify = inotify.adapters.InotifyTree(str(self.watch_dir))
        except ImportError:
            self.logger.info("inotify not available, falling back to watchdog")
            self.inotify_available = False

    def start(self):
        if not self.inotify_available:
            raise RuntimeError("inotify is not available")

        self.running = True
        self.thread = threading.Thread(target=self._watch_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info("Inotify watcher started")

    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=5)
        self.logger.info("Inotify watcher stopped")

    def _watch_loop(self):
        last_event_time = None
        pending_events = []

        while self.running:
            try:
                events = self.inotify.event_gen(timeout_s=1)
                for event in events:
                    if event is not None:
                        (header, type_names, watch_path, filename) = event

                        if filename and not filename.startswith('.'):
                            current_time = time.time()

                            if last_event_time is None or (current_time - last_event_time) > self.debounce_seconds:
                                if pending_events:
                                    self._process_pending_events(pending_events)
                                    pending_events = []

                            pending_events.append((type_names, os.path.join(watch_path, filename)))
                            last_event_time = current_time

                if pending_events and last_event_time:
                    if (time.time() - last_event_time) > self.debounce_seconds:
                        self._process_pending_events(pending_events)
                        pending_events = []
                        last_event_time = None

            except Exception as e:
                self.logger.error(f"Error in inotify loop: {e}", exc_info=True)
                time.sleep(1)

    def _process_pending_events(self, events):
        if not events:
            return

        event_types = set()
        for type_names, _ in events:
            event_types.update(type_names)

        primary_type = 'modified' if 'IN_MODIFY' in event_types else 'created'
        file_count = len(set(path for _, path in events))

        self.callback(primary_type, f"{file_count} file(s)")

    def is_alive(self) -> bool:
        return self.running and hasattr(self, 'thread') and self.thread.is_alive()