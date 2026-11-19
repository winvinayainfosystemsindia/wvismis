"""
In-Memory Asynchronous Cache Layer with TTL and Tag/Prefix Invalidation
======================================================================
Optimizes database querying by caching slow-changing / read-heavy data:
- Subscription plans & pricing
- AI credit balances & usage metrics
- User profile & organization metadata
- System dashboard health & statistics
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps
from loguru import logger


class CacheItem:
    __slots__ = ("value", "expires_at", "tags")

    def __init__(self, value: Any, ttl_seconds: float, tags: Optional[List[str]] = None) -> None:
        self.value = value
        self.expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else float("inf")
        self.tags = set(tags or [])

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class InMemoryCache:
    """Thread-safe, high-performance in-memory cache with TTL and prefix/tag invalidation."""

    def __init__(self) -> None:
        self._cache: Dict[str, CacheItem] = {}
        self._lock = asyncio.Lock()
        self._cleanup_counter = 0

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from cache. Returns None if missing or expired."""
        async with self._lock:
            item = self._cache.get(key)
            if not item:
                return None
            if item.is_expired:
                del self._cache[key]
                return None
            return item.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: float = 60.0,
        tags: Optional[List[str]] = None,
    ) -> None:
        """Store an item in cache with a TTL (seconds) and optional tags."""
        async with self._lock:
            self._cache[key] = CacheItem(value, ttl_seconds, tags)
            self._cleanup_counter += 1
            if self._cleanup_counter >= 100:
                self._cleanup_expired_locked()
                self._cleanup_counter = 0

    async def delete(self, key: str) -> bool:
        """Delete an exact key from cache."""
        async with self._lock:
            return self._cache.pop(key, None) is not None

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all keys matching prefix."""
        async with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._cache[k]
            if keys_to_remove:
                logger.debug(f"Cache invalidated prefix '{prefix}': {len(keys_to_remove)} keys removed")
            return len(keys_to_remove)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching regex pattern."""
        regex = re.compile(pattern)
        async with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if regex.search(k)]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    async def invalidate_tags(self, tags: List[str]) -> int:
        """Invalidate all keys that carry any of the specified tags."""
        target_tags = set(tags)
        async with self._lock:
            keys_to_remove = [
                k for k, item in self._cache.items() if item.tags.intersection(target_tags)
            ]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    async def clear(self) -> None:
        """Purge entire cache."""
        async with self._lock:
            self._cache.clear()

    def _cleanup_expired_locked(self) -> None:
        """Remove expired entries in batch without blocking."""
        now = time.time()
        expired_keys = [k for k, item in self._cache.items() if now > item.expires_at]
        for k in expired_keys:
            del self._cache[k]


# Global In-Memory Cache Instance
memory_cache = InMemoryCache()


def cached(prefix: str, ttl: float = 30.0, key_builder: Optional[Callable[..., str]] = None):
    """
    Decorator for caching async function results.
    `key_builder`: optional custom function `(*args, **kwargs) -> str`
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if key_builder:
                cache_key = f"{prefix}:{key_builder(*args, **kwargs)}"
            else:
                # Default: use positional & kwargs string representation
                arg_strs = [str(a) for a in args[1:] if not hasattr(a, "execute")]  # skip db session objects
                kwarg_strs = [f"{k}={v}" for k, v in sorted(kwargs.items()) if k not in ("db", "session")]
                cache_key = f"{prefix}:{':'.join(arg_strs + kwarg_strs)}"

            cached_val = await memory_cache.get(cache_key)
            if cached_val is not None:
                return cached_val

            result = await func(*args, **kwargs)
            if result is not None:
                await memory_cache.set(cache_key, result, ttl_seconds=ttl)
            return result

        return wrapper

    return decorator
