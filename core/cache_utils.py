"""
Smart caching utilities for OneCard.
"""
from django.core.cache import cache
from functools import wraps
import hashlib
import json


def get_or_set(key, func, timeout=60):
    """Get from cache or compute and set."""
    result = cache.get(key)
    if result is None:
        result = func()
        cache.set(key, result, timeout)
    return result


def invalidate_cache(*keys):
    """Delete specific cache keys."""
    for key in keys:
        cache.delete(key)


def invalidate_pattern(pattern):
    """Delete all keys matching a pattern (requires Redis, not LocMem)."""
    pass  # LocMem doesn't support pattern deletion


def cache_page(timeout=60):
    """Decorator to cache entire view response."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Build cache key from URL + user
            key = f"page_{request.path}_{request.user.id}"
            result = cache.get(key)
            if result is None:
                result = view_func(request, *args, **kwargs)
                cache.set(key, result, timeout)
            return result
        return wrapper
    return decorator


def make_key(*args):
    """Create a consistent cache key."""
    raw = '_'.join(str(a) for a in args)
    return hashlib.md5(raw.encode()).hexdigest()