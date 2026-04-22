#!/usr/bin/env python3
"""Watch a directory tree for EPUB files and upgrade EPUB 2 to EPUB 3 via Calibre."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import uuid
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from epub_version import is_epub2

LOG = logging.getLogger("epub-upgrade")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def iter_epubs(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(".epub") and ".epub3-tmp-" not in lower:
                out.append(Path(dirpath) / name)
    return sorted(out)


def wait_file_stable(path: Path, seconds: float, checks: int = 3) -> bool:
    """Return True if file size is unchanged across several polls."""
    if not path.is_file():
        return False
    last = path.stat().st_size
    interval = max(seconds / checks, 0.2)
    for _ in range(checks):
        time.sleep(interval)
        if not path.is_file():
            return False
        cur = path.stat().st_size
        if cur != last:
            last = cur
            return wait_file_stable(path, seconds, checks)
    return True


def convert_with_calibre(src: Path) -> None:
    # Calibre picks the output plugin from the *final* file extension; names like
    # "book.epub.upgrading" are parsed as format "upgrading", not EPUB.
    suffix = src.suffix if src.suffix.lower() == ".epub" else ".epub"
    tmp = src.with_name(f"{src.stem}.epub3-tmp-{uuid.uuid4().hex}{suffix}")
    try:
        subprocess.run(
            [
                "ebook-convert",
                str(src),
                str(tmp),
                "--epub-version=3",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        os.replace(tmp, src)
        LOG.info("Upgraded to EPUB 3: %s", src)
    except subprocess.CalledProcessError as e:
        LOG.error(
            "Calibre failed for %s: %s\nstderr: %s",
            src,
            e,
            (e.stderr or "").strip(),
        )
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    except OSError as e:
        LOG.error("Filesystem error upgrading %s: %s", src, e)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def maybe_upgrade(
    path: Path,
    stable_seconds: float,
    *,
    progress: str | None = None,
) -> str:
    """
    Returns: upgraded | skipped_not_file | skipped_unstable | skipped_already_epub3
    """
    path = path.resolve()
    prefix = f"[{progress}] " if progress else ""
    if not path.is_file() or path.suffix.lower() != ".epub":
        return "skipped_not_file"
    if not wait_file_stable(path, stable_seconds):
        LOG.debug("%sSkipped (file still changing or missing): %s", prefix, path)
        return "skipped_unstable"
    if not is_epub2(path):
        LOG.debug("%sSkipped (already EPUB 3 or unreadable OPF): %s", prefix, path)
        return "skipped_already_epub3"
    LOG.info("%sEPUB 2 detected, converting: %s", prefix, path)
    convert_with_calibre(path)
    return "upgraded"


class EpubHandler(FileSystemEventHandler):
    def __init__(self, debounce_seconds: float, stable_seconds: float) -> None:
        super().__init__()
        self.debounce_seconds = debounce_seconds
        self.stable_seconds = stable_seconds
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, path: Path) -> None:
        key = str(path)

        def run() -> None:
            with self._lock:
                self._timers.pop(key, None)
            try:
                maybe_upgrade(path, self.stable_seconds)
            except Exception:
                LOG.exception("Unhandled error processing %s", path)

        with self._lock:
            old = self._timers.pop(key, None)
            if old is not None:
                old.cancel()
            t = threading.Timer(self.debounce_seconds, run)
            self._timers[key] = t
            t.daemon = True
            t.start()

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".epub":
            self._schedule(path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".epub":
            self._schedule(path)


def scan_existing(root: Path, stable_seconds: float) -> None:
    LOG.info("CONVERT_EXISTING: scanning %s", root)
    paths = iter_epubs(root)
    total = len(paths)
    LOG.info("CONVERT_EXISTING: found %d .epub file(s) in tree", total)
    counts = {
        "upgraded": 0,
        "skipped_not_file": 0,
        "skipped_unstable": 0,
        "skipped_already_epub3": 0,
        "failed": 0,
    }
    for idx, path in enumerate(paths, start=1):
        progress = f"{idx}/{total}"
        try:
            status = maybe_upgrade(path, stable_seconds, progress=progress)
            counts[status] += 1
        except Exception:
            LOG.exception("Failed during bulk scan: %s", path)
            counts["failed"] += 1
    LOG.info(
        "CONVERT_EXISTING: finished — upgraded=%d, skipped_already_epub3=%d, "
        "skipped_unstable=%d, skipped_not_file=%d, failed=%d (total .epub=%d)",
        counts["upgraded"],
        counts["skipped_already_epub3"],
        counts["skipped_unstable"],
        counts["skipped_not_file"],
        counts["failed"],
        total,
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    watch = Path(os.environ.get("WATCH_PATH", "/data")).resolve()
    if not watch.is_dir():
        LOG.error("WATCH_PATH is not a directory: %s", watch)
        return 2

    stable = float(os.environ.get("FILE_STABLE_SECONDS", "5"))
    debounce = float(os.environ.get("EVENT_DEBOUNCE_SECONDS", "2"))
    poll_interval = env_int("POLL_INTERVAL_SECONDS", 10)
    use_polling = env_bool("USE_POLLING", True)
    convert_existing = env_bool("CONVERT_EXISTING", False)

    if not shutil.which("ebook-convert"):
        LOG.error("ebook-convert not found in PATH (Calibre not installed?)")
        return 2

    if convert_existing:
        scan_existing(watch, stable)

    handler = EpubHandler(debounce_seconds=debounce, stable_seconds=stable)
    observer: Observer
    if use_polling:
        LOG.info(
            "Starting polling observer on %s (interval=%ss)",
            watch,
            poll_interval,
        )
        observer = PollingObserver(timeout=poll_interval)
    else:
        LOG.info("Starting inotify observer on %s", watch)
        observer = Observer()
    observer.schedule(handler, str(watch), recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        LOG.info("Shutting down")
    finally:
        observer.stop()
        observer.join(timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
