"""
Secure Temporary File Manager

Handles temporary file storage with automatic cleanup, user isolation,
and privacy protection. Never stores files permanently.
"""

import os
import tempfile
import shutil
import threading
import time
import atexit
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class TempFileManager:
    """
    Manages temporary files with automatic cleanup and user isolation.

    Features:
    - Per-user isolated temporary directories
    - Automatic TTL-based file expiration
    - Cleanup on application shutdown
    - Thread-safe operations
    - No permanent storage - all files in system temp directory
    """

    def __init__(
        self,
        base_temp_dir: Optional[str] = None,
        ttl_seconds: int = 300,
        cleanup_interval: int = 60,
        max_file_size_mb: int = 50
    ):
        """
        Initialize temporary file manager.

        Args:
            base_temp_dir: Base directory for temp files (default: system temp)
            ttl_seconds: Time-to-live for files in seconds (default 5 minutes)
            cleanup_interval: Cleanup check interval in seconds (default 1 minute)
            max_file_size_mb: Maximum allowed file size in MB (default 50)
        """
        if base_temp_dir is None:
            base_temp_dir = tempfile.gettempdir()

        self.base_dir = Path(base_temp_dir) / "botble_watermark_bot"
        self.ttl_seconds = ttl_seconds
        self.cleanup_interval = cleanup_interval
        self.max_file_size = max_file_size_mb * 1024 * 1024

        self._user_dirs: Dict[int, Path] = {}
        self._file_timestamps: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        self._initialized = False

        # Register shutdown cleanup
        atexit.register(self.shutdown)

    def _ensure_initialized(self):
        """Lazy initialization of base directory and cleanup thread."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.base_dir.mkdir(parents=True, exist_ok=True)
            # Set restrictive permissions (owner only)
            try:
                os.chmod(self.base_dir, 0o700)
            except Exception:
                pass  # Windows may not support chmod

            self._start_cleanup_thread()
            self._initialized = True

    def _start_cleanup_thread(self):
        """Start background cleanup thread."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="TempFileManager-Cleanup"
        )
        self._cleanup_thread.start()

    def _cleanup_loop(self):
        """Background cleanup loop."""
        while not self._stop_cleanup.wait(self.cleanup_interval):
            try:
                self.cleanup_expired()
            except Exception as e:
                logger.warning(f"Temp file cleanup error: {e}")

    def _get_user_dir(self, user_id: int) -> Path:
        """Get or create user's isolated temporary directory."""
        self._ensure_initialized()

        with self._lock:
            if user_id not in self._user_dirs:
                # Create user-specific subdirectory with random component for security
                user_dir = self.base_dir / f"user_{user_id}"
                user_dir.mkdir(parents=True, exist_ok=True)
                try:
                    os.chmod(user_dir, 0o700)
                except Exception:
                    pass
                self._user_dirs[user_id] = user_dir
            return self._user_dirs[user_id]

    def save_uploaded_file(
        self,
        user_id: int,
        file_bytes: bytes,
        suffix: str = ".png",
        prefix: str = "upload_"
    ) -> Optional[Path]:
        """
        Save uploaded file to user's temporary directory.

        Args:
            user_id: User identifier
            file_bytes: File content
            suffix: File extension (default .png)
            prefix: Filename prefix

        Returns:
            Path to saved file, or None if failed
        """
        if len(file_bytes) > self.max_file_size:
            logger.warning(f"File too large for user {user_id}: {len(file_bytes)} bytes")
            return None

        user_dir = self._get_user_dir(user_id)

        # Generate secure filename
        import secrets
        filename = f"{prefix}{secrets.token_hex(8)}{suffix}"
        file_path = user_dir / filename

        try:
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            # Restrict file permissions
            try:
                os.chmod(file_path, 0o600)
            except Exception:
                pass

            with self._lock:
                self._file_timestamps[str(file_path)] = time.time()

            logger.debug(f"Saved temp file for user {user_id}: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to save temp file for user {user_id}: {e}")
            return None

    def save_processed_image(
        self,
        user_id: int,
        image_bytes: bytes,
        suffix: str = ".jpg",
        prefix: str = "result_"
    ) -> Optional[Path]:
        """Save processed result image."""
        return self.save_uploaded_file(user_id, image_bytes, suffix, prefix)

    def get_file_path(self, user_id: int, filename: str) -> Optional[Path]:
        """Get full path to a file in user's directory (validates ownership)."""
        user_dir = self._get_user_dir(user_id)
        file_path = user_dir / filename

        # Security: ensure file is within user's directory (prevent path traversal)
        try:
            file_path.resolve().relative_to(user_dir.resolve())
        except ValueError:
            logger.warning(f"Path traversal attempt by user {user_id}: {filename}")
            return None

        if file_path.exists():
            return file_path
        return None

    def read_file(self, file_path: Path) -> Optional[bytes]:
        """Read file content."""
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None

    def delete_file(self, file_path: Path) -> bool:
        """Delete a specific file."""
        try:
            file_path.unlink(missing_ok=True)
            with self._lock:
                self._file_timestamps.pop(str(file_path), None)
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    def delete_user_files(self, user_id: int) -> int:
        """Delete all files for a specific user."""
        count = 0
        user_dir = self._user_dirs.get(user_id)
        if user_dir and user_dir.exists():
            for file_path in user_dir.iterdir():
                if file_path.is_file():
                    self.delete_file(file_path)
                    count += 1
        return count

    def cleanup_expired(self) -> int:
        """Remove all expired temporary files."""
        current_time = time.time()
        deleted_count = 0

        with self._lock:
            expired_files = [
                path for path, timestamp in self._file_timestamps.items()
                if current_time - timestamp > self.ttl_seconds
            ]

            for file_path_str in expired_files:
                file_path = Path(file_path_str)
                if file_path.exists():
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception:
                        pass
                self._file_timestamps.pop(file_path_str, None)

            # Also clean up empty user directories
            for user_id, user_dir in list(self._user_dirs.items()):
                if user_dir.exists():
                    try:
                        if not any(user_dir.iterdir()):
                            user_dir.rmdir()
                            del self._user_dirs[user_id]
                    except Exception:
                        pass

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired temp files")
        return deleted_count

    def cleanup_user_expired(self, user_id: int) -> int:
        """Clean up expired files for a specific user."""
        current_time = time.time()
        deleted_count = 0

        user_dir = self._user_dirs.get(user_id)
        if not user_dir or not user_dir.exists():
            return 0

        with self._lock:
            for file_path in user_dir.iterdir():
                if file_path.is_file():
                    timestamp = self._file_timestamps.get(str(file_path))
                    if timestamp and current_time - timestamp > self.ttl_seconds:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except Exception:
                            pass
                        self._file_timestamps.pop(str(file_path), None)

        return deleted_count

    @contextmanager
    def temporary_file(self, user_id: int, suffix: str = ".tmp", prefix: str = "tmp_"):
        """
        Context manager for temporary file that auto-deletes on exit.

        Usage:
            with temp_manager.temporary_file(user_id, ".png") as path:
                # write to path
                # file auto-deleted when exiting context
        """
        file_path = None
        try:
            user_dir = self._get_user_dir(user_id)
            import secrets
            filename = f"{prefix}{secrets.token_hex(8)}{suffix}"
            file_path = user_dir / filename
            yield file_path
        finally:
            if file_path and file_path.exists():
                self.delete_file(file_path)

    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics for a user's temporary files."""
        user_dir = self._user_dirs.get(user_id)
        if not user_dir or not user_dir.exists():
            return {"file_count": 0, "total_size_bytes": 0}

        file_count = 0
        total_size = 0
        current_time = time.time()

        for file_path in user_dir.iterdir():
            if file_path.is_file():
                file_count += 1
                try:
                    total_size += file_path.stat().st_size
                except Exception:
                    pass

        return {
            "file_count": file_count,
            "total_size_bytes": total_size,
            "directory": str(user_dir)
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global temporary file statistics."""
        total_files = 0
        total_size = 0
        user_count = len(self._user_dirs)

        for user_dir in self._user_dirs.values():
            if user_dir.exists():
                for file_path in user_dir.iterdir():
                    if file_path.is_file():
                        total_files += 1
                        try:
                            total_size += file_path.stat().st_size
                        except Exception:
                            pass

        with self._lock:
            tracked_files = len(self._file_timestamps)

        return {
            "user_count": user_count,
            "total_files": total_files,
            "tracked_files": tracked_files,
            "total_size_bytes": total_size,
            "base_directory": str(self.base_dir),
            "ttl_seconds": self.ttl_seconds
        }

    def shutdown(self):
        """Shutdown cleanup thread and clean up all temporary files."""
        logger.info("Shutting down TempFileManager...")
        self._stop_cleanup.set()

        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)

        # Clean up all temp files on shutdown
        try:
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir, ignore_errors=True)
                logger.info(f"Removed temporary directory: {self.base_dir}")
        except Exception as e:
            logger.error(f"Error during temp directory cleanup: {e}")

        self._initialized = False


# Global instance for easy access
_global_temp_manager: Optional[TempFileManager] = None
_manager_lock = threading.Lock()


def get_temp_file_manager(**kwargs) -> TempFileManager:
    """Get or create global temp file manager instance."""
    global _global_temp_manager
    with _manager_lock:
        if _global_temp_manager is None:
            _global_temp_manager = TempFileManager(**kwargs)
        return _global_temp_manager


def shutdown_temp_file_manager():
    """Shutdown global temp file manager."""
    global _global_temp_manager
    with _manager_lock:
        if _global_temp_manager:
            _global_temp_manager.shutdown()
            _global_temp_manager = None