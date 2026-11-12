"""
User State Management

Manages per-user state, watermark status, and interaction flow.
Provides clear state transitions and user experience handling.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import threading
import time
import logging

logger = logging.getLogger(__name__)


class UserState(Enum):
    """User interaction states."""
    # Mode selection
    MODE_SELECTION = "mode_selection"         # User needs to select mode

    # Watermark Mode states
    NO_WATERMARK = "no_watermark"             # User hasn't uploaded watermark yet
    WATERMARK_PENDING = "watermark_pending"   # User uploaded file, validating
    WATERMARK_READY = "watermark_ready"       # Valid watermark set, ready to process images
    WATERMARK_INVALID = "watermark_invalid"   # Last upload was invalid format

    # Logo Mode states
    NO_LOGO = "no_logo"                       # User hasn't uploaded logo yet
    LOGO_PENDING = "logo_pending"             # User uploaded logo, validating
    LOGO_POSITION_PENDING = "logo_position_pending"  # Waiting for position selection
    LOGO_SIZE_PENDING = "logo_size_pending"   # Waiting for size selection
    LOGO_READY = "logo_ready"                 # Valid logo + config set, ready to process images
    LOGO_INVALID = "logo_invalid"             # Last upload was invalid format

    # Common
    PROCESSING = "processing"                 # Currently processing an image


class WatermarkFormat(Enum):
    """Supported watermark formats."""
    PNG = "png"
    # Future: WEBP = "webp"


class LogoPosition(Enum):
    """Logo position options."""
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"


class LogoSize(Enum):
    """Logo size presets (relative to image width)."""
    SMALL = "small"      # ~8% of image width
    MEDIUM = "medium"    # ~13% of image width
    LARGE = "large"      # ~18% of image width


class ProcessingMode(Enum):
    """Processing mode selection."""
    WATERMARK = "watermark"
    LOGO = "logo"


@dataclass
class UserData:
    """Per-user data storage."""
    user_id: int
    state: UserState = UserState.MODE_SELECTION
    processing_mode: Optional[ProcessingMode] = None

    # Watermark Mode fields
    watermark_path: Optional[str] = None
    watermark_format: Optional[WatermarkFormat] = None
    watermark_size: Optional[tuple] = None  # (width, height)

    # Logo Mode fields
    logo_path: Optional[str] = None
    logo_format: Optional[WatermarkFormat] = None  # Same format enum (PNG)
    logo_size: Optional[tuple] = None  # (width, height)
    logo_position: Optional[LogoPosition] = None
    logo_size_preset: Optional[LogoSize] = None

    # Common fields
    last_activity: float = field(default_factory=time.time)
    images_processed: int = 0
    errors_count: int = 0
    # Future: subscription_tier = "free" | "pro"


class UserManager:
    """
    Manages user state and interaction flow.

    Features:
    - Thread-safe per-user state management
    - Automatic state transitions
    - Activity tracking for TTL integration
    - Statistics and monitoring
    """

    def __init__(self, inactivity_timeout: int = 300):
        """
        Initialize user manager.

        Args:
            inactivity_timeout: Seconds of inactivity before considering session expired
        """
        self._users: Dict[int, UserData] = {}
        self._lock = threading.RLock()
        self._inactivity_timeout = inactivity_timeout

    def _get_user(self, user_id: int) -> UserData:
        """Get or create user data."""
        with self._lock:
            if user_id not in self._users:
                self._users[user_id] = UserData(user_id=user_id)
            return self._users[user_id]

    def get_state(self, user_id: int) -> UserState:
        """Get user's current state."""
        self._update_activity(user_id)
        return self._get_user(user_id).state

    def set_state(self, user_id: int, state: UserState):
        """Set user's state."""
        with self._lock:
            user = self._get_user(user_id)
            old_state = user.state
            user.state = state
            user.last_activity = time.time()
            logger.debug(f"User {user_id} state: {old_state.value} -> {state.value}")

    def _update_activity(self, user_id: int):
        """Update user's last activity timestamp."""
        with self._lock:
            if user_id in self._users:
                self._users[user_id].last_activity = time.time()

    def is_session_expired(self, user_id: int) -> bool:
        """Check if user session has expired due to inactivity."""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return True
            return time.time() - user.last_activity > self._inactivity_timeout

    def set_watermark_info(
        self,
        user_id: int,
        watermark_path: str,
        format: WatermarkFormat,
        size: tuple
    ):
        """Set user's watermark information after successful upload."""
        with self._lock:
            user = self._get_user(user_id)
            user.watermark_path = watermark_path
            user.watermark_format = format
            user.watermark_size = size
            user.state = UserState.WATERMARK_READY
            user.last_activity = time.time()
            user.errors_count = 0
            logger.info(f"User {user_id} watermark set: {format.value} {size}")

    def clear_watermark(self, user_id: int):
        """Clear user's watermark (on expiry, replacement, or explicit removal)."""
        with self._lock:
            if user_id in self._users:
                user = self._users[user_id]
                user.watermark_path = None
                user.watermark_format = None
                user.watermark_size = None
                user.state = UserState.NO_WATERMARK
                user.last_activity = time.time()
                logger.info(f"User {user_id} watermark cleared")

    # ─── Logo Mode Methods ────────────────────────────────────────
    def set_mode(self, user_id: int, mode: ProcessingMode):
        """Set user's processing mode and initialize appropriate state."""
        with self._lock:
            user = self._get_user(user_id)
            user.processing_mode = mode
            user.last_activity = time.time()
            if mode == ProcessingMode.WATERMARK:
                user.state = UserState.NO_WATERMARK
            elif mode == ProcessingMode.LOGO:
                user.state = UserState.NO_LOGO
            logger.info(f"User {user_id} mode set to: {mode.value}")

    def set_logo_info(
        self,
        user_id: int,
        logo_path: str,
        format: WatermarkFormat,
        size: tuple
    ):
        """Set user's logo information after successful upload."""
        with self._lock:
            user = self._get_user(user_id)
            user.logo_path = logo_path
            user.logo_format = format
            user.logo_size = size
            user.state = UserState.LOGO_POSITION_PENDING
            user.last_activity = time.time()
            user.errors_count = 0
            logger.info(f"User {user_id} logo set: {format.value} {size}")

    def set_logo_position(self, user_id: int, position: LogoPosition):
        """Set user's logo position."""
        with self._lock:
            user = self._get_user(user_id)
            user.logo_position = position
            user.state = UserState.LOGO_SIZE_PENDING
            user.last_activity = time.time()
            logger.info(f"User {user_id} logo position set: {position.value}")

    def set_logo_size(self, user_id: int, size: LogoSize):
        """Set user's logo size preset."""
        with self._lock:
            user = self._get_user(user_id)
            user.logo_size_preset = size
            user.state = UserState.LOGO_READY
            user.last_activity = time.time()
            logger.info(f"User {user_id} logo size set: {size.value}")

    def clear_logo(self, user_id: int):
        """Clear user's logo and configuration."""
        with self._lock:
            if user_id in self._users:
                user = self._users[user_id]
                user.logo_path = None
                user.logo_format = None
                user.logo_size = None
                user.logo_position = None
                user.logo_size_preset = None
                user.state = UserState.NO_LOGO
                user.last_activity = time.time()
                logger.info(f"User {user_id} logo cleared")

    def get_logo_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's logo information."""
        with self._lock:
            user = self._users.get(user_id)
            if not user or user.state not in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY):
                return None
            return {
                "path": user.logo_path,
                "format": user.logo_format.value if user.logo_format else None,
                "size": user.logo_size,
                "position": user.logo_position.value if user.logo_position else None,
                "size_preset": user.logo_size_preset.value if user.logo_size_preset else None
            }

    def get_processing_mode(self, user_id: int) -> Optional[ProcessingMode]:
        """Get user's current processing mode."""
        with self._lock:
            user = self._users.get(user_id)
            if user:
                return user.processing_mode
            return None

    def get_watermark_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's watermark information."""
        with self._lock:
            user = self._users.get(user_id)
            if not user or user.state != UserState.WATERMARK_READY:
                return None
            return {
                "path": user.watermark_path,
                "format": user.watermark_format.value if user.watermark_format else None,
                "size": user.watermark_size
            }

    def increment_processed(self, user_id: int):
        """Increment processed images counter."""
        with self._lock:
            user = self._get_user(user_id)
            user.images_processed += 1
            user.last_activity = time.time()

    def increment_errors(self, user_id: int):
        """Increment error counter."""
        with self._lock:
            user = self._get_user(user_id)
            user.errors_count += 1
            user.last_activity = time.time()

    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics."""
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                return {"exists": False}

            has_logo = user.state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY)

            return {
                "exists": True,
                "state": user.state.value,
                "processing_mode": user.processing_mode.value if user.processing_mode else None,
                "has_watermark": user.state == UserState.WATERMARK_READY,
                "watermark_format": user.watermark_format.value if user.watermark_format else None,
                "watermark_size": user.watermark_size,
                "has_logo": has_logo,
                "logo_format": user.logo_format.value if user.logo_format else None,
                "logo_size": user.logo_size,
                "logo_position": user.logo_position.value if user.logo_position else None,
                "logo_size_preset": user.logo_size_preset.value if user.logo_size_preset else None,
                "images_processed": user.images_processed,
                "errors_count": user.errors_count,
                "last_activity": user.last_activity,
                "session_expired": self.is_session_expired(user_id)
            }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all users."""
        with self._lock:
            stats = {}
            for user_id, user in self._users.items():
                has_watermark = user.state == UserState.WATERMARK_READY
                has_logo = user.state in (UserState.LOGO_POSITION_PENDING, UserState.LOGO_SIZE_PENDING, UserState.LOGO_READY)
                stats[user_id] = {
                    "state": user.state.value,
                    "processing_mode": user.processing_mode.value if user.processing_mode else None,
                    "has_watermark": has_watermark,
                    "has_logo": has_logo,
                    "images_processed": user.images_processed,
                    "errors_count": user.errors_count,
                    "last_activity": user.last_activity,
                    "session_expired": time.time() - user.last_activity > self._inactivity_timeout
                }
            return {
                "total_users": len(self._users),
                "active_users": sum(1 for u in self._users.values() if not self.is_session_expired(u.user_id)),
                "users": stats
            }

    def cleanup_expired_sessions(self) -> int:
        """Remove expired user sessions."""
        current_time = time.time()
        expired_users = []

        with self._lock:
            for user_id, user in self._users.items():
                if current_time - user.last_activity > self._inactivity_timeout:
                    expired_users.append(user_id)

            for user_id in expired_users:
                del self._users[user_id]

        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired user sessions")
        return len(expired_users)

    def remove_user(self, user_id: int) -> bool:
        """Explicitly remove a user (e.g., on /reset command)."""
        with self._lock:
            if user_id in self._users:
                del self._users[user_id]
                logger.info(f"User {user_id} removed explicitly")
                return True
        return False

    def get_users_needing_watermark(self) -> list:
        """Get list of user IDs that need to upload watermark."""
        with self._lock:
            return [
                user_id for user_id, user in self._users.items()
                if user.state in (UserState.NO_WATERMARK, UserState.WATERMARK_INVALID)
            ]


# Global instance
_global_user_manager: Optional[UserManager] = None
_manager_lock = threading.Lock()


def get_user_manager(**kwargs) -> UserManager:
    """Get or create global user manager instance."""
    global _global_user_manager
    with _manager_lock:
        if _global_user_manager is None:
            _global_user_manager = UserManager(**kwargs)
        return _global_user_manager