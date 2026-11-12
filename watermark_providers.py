"""
Watermark Provider Abstraction Layer

This module defines the interface for watermark storage providers.
Supports different storage strategies for Free vs Pro users in the future.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from PIL import Image
import io


class WatermarkProvider(ABC):
    """Abstract base class for watermark providers."""

    @abstractmethod
    async def get_watermark(self, user_id: int) -> Optional[Image.Image]:
        """Get user's watermark as PIL Image. Returns None if not set."""
        pass

    @abstractmethod
    async def set_watermark(self, user_id: int, watermark: Image.Image) -> bool:
        """Set user's watermark. Returns True on success."""
        pass

    @abstractmethod
    async def remove_watermark(self, user_id: int) -> bool:
        """Remove user's watermark. Returns True if existed."""
        pass

    @abstractmethod
    async def has_watermark(self, user_id: int) -> bool:
        """Check if user has a watermark set."""
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired watermarks. Returns count of removed items."""
        pass


class TemporaryWatermarkProvider(WatermarkProvider):
    """
    In-memory watermark storage with TTL for Free users.

    Features:
    - Stores watermarks in memory (never writes to disk permanently)
    - Automatic TTL-based expiration
    - Thread-safe for concurrent access
    - Automatic cleanup of expired entries
    """

    def __init__(self, ttl_seconds: int = 300, cleanup_interval: int = 60):
        """
        Initialize temporary watermark provider.

        Args:
            ttl_seconds: Time-to-live for watermarks in seconds (default 5 minutes)
            cleanup_interval: How often to run cleanup in seconds (default 1 minute)
        """
        self._watermarks: Dict[int, Dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = 0
        import threading
        self._lock = threading.RLock()

    def _get_current_time(self) -> float:
        import time
        return time.time()

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        return self._get_current_time() - entry["timestamp"] > self._ttl_seconds

    def _maybe_cleanup(self):
        """Run cleanup if interval has passed."""
        current_time = self._get_current_time()
        if current_time - self._last_cleanup >= self._cleanup_interval:
            self._cleanup_expired_internal()
            self._last_cleanup = current_time

    def _cleanup_expired_internal(self) -> int:
        """Internal cleanup without lock (caller must hold lock)."""
        expired_users = [
            user_id for user_id, entry in self._watermarks.items()
            if self._is_expired(entry)
        ]
        for user_id in expired_users:
            del self._watermarks[user_id]
        return len(expired_users)

    async def get_watermark(self, user_id: int) -> Optional[Image.Image]:
        self._maybe_cleanup()

        with self._lock:
            entry = self._watermarks.get(user_id)
            if entry is None:
                return None

            if self._is_expired(entry):
                del self._watermarks[user_id]
                return None

            # Update timestamp on access (sliding window TTL)
            entry["timestamp"] = self._get_current_time()
            return entry["watermark"]

    async def set_watermark(self, user_id: int, watermark: Image.Image) -> bool:
        with self._lock:
            self._watermarks[user_id] = {
                "watermark": watermark,
                "timestamp": self._get_current_time()
            }
        return True

    async def remove_watermark(self, user_id: int) -> bool:
        with self._lock:
            if user_id in self._watermarks:
                del self._watermarks[user_id]
                return True
        return False

    async def has_watermark(self, user_id: int) -> bool:
        watermark = await self.get_watermark(user_id)
        return watermark is not None

    async def cleanup_expired(self) -> int:
        with self._lock:
            return self._cleanup_expired_internal()

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        with self._lock:
            current_time = self._get_current_time()
            active = sum(1 for e in self._watermarks.values() if not self._is_expired(e))
            expired = len(self._watermarks) - active
            return {
                "total_entries": len(self._watermarks),
                "active": active,
                "expired": expired,
                "ttl_seconds": self._ttl_seconds
            }


class PersistentWatermarkProvider(WatermarkProvider):
    """
    Placeholder for future Pro subscriber persistent watermark storage.

    This will be implemented when Pro subscription system is added.
    For now, it raises NotImplementedError to make the architecture explicit.
    """

    def __init__(self, storage_path: str = "user_watermarks"):
        self.storage_path = storage_path
        # TODO: Implement persistent storage (database, file system, cloud)
        # This is a placeholder for future Pro subscription feature

    async def get_watermark(self, user_id: int) -> Optional[Image.Image]:
        raise NotImplementedError("PersistentWatermarkProvider not implemented yet - Pro feature")

    async def set_watermark(self, user_id: int, watermark: Image.Image) -> bool:
        raise NotImplementedError("PersistentWatermarkProvider not implemented yet - Pro feature")

    async def remove_watermark(self, user_id: int) -> bool:
        raise NotImplementedError("PersistentWatermarkProvider not implemented yet - Pro feature")

    async def has_watermark(self, user_id: int) -> bool:
        raise NotImplementedError("PersistentWatermarkProvider not implemented yet - Pro feature")

    async def cleanup_expired(self) -> int:
        return 0  # Persistent watermarks don't expire


class WatermarkProviderFactory:
    """Factory for creating watermark providers based on user tier."""

    def __init__(self):
        self._temporary_provider = TemporaryWatermarkProvider()
        self._persistent_provider = PersistentWatermarkProvider()
        # In future: user_id -> tier mapping (free/pro)
        self._pro_users: set = set()

    def get_provider(self, user_id: int) -> WatermarkProvider:
        """Get appropriate provider for user."""
        if user_id in self._pro_users:
            return self._persistent_provider
        return self._temporary_provider

    def set_pro_user(self, user_id: int, is_pro: bool):
        """Set user's subscription tier (for future use)."""
        if is_pro:
            self._pro_users.add(user_id)
        else:
            self._pro_users.discard(user_id)

    @property
    def temporary_provider(self) -> TemporaryWatermarkProvider:
        return self._temporary_provider

    async def cleanup_all_expired(self) -> int:
        """Clean up expired watermarks across all providers."""
        return await self._temporary_provider.cleanup_expired()

    def get_stats(self) -> Dict[str, Any]:
        return self._temporary_provider.get_stats()