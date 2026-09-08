"""
SENTINEL — API Rate Limiter
In-memory sliding window rate limiter for API endpoints.
Used to protect the LLM and background queues from spam.
"""
from __future__ import annotations

import time
import os
import logging
import ipaddress
import redis.asyncio as aioredis
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

def is_trusted_proxy(ip: str) -> bool:
    """Check if the IP belongs to a trusted proxy (e.g., Docker bridge)."""
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback
    except ValueError:
        return False


class RateLimiter:
    """
    In-memory rate limiter dependency.
    Limits clients to `requests` per `window` seconds.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request):
        # Identify the client by IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Only trust X-Forwarded-For if it comes from our internal reverse proxies
        if is_trusted_proxy(client_ip):
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

        current_time = time.time()
        key = f"rate_limit:{client_ip}"
        member = f"{current_time}:{id(request)}"
        
        # Execute sliding window rate limit transaction
        try:
            async with redis_client.pipeline(transaction=True) as pipe:
                # Remove requests older than the window
                pipe.zremrangebyscore(key, 0, current_time - self.window)
                # Add current request
                pipe.zadd(key, {member: current_time})
                # Count valid requests in the window
                pipe.zcard(key)
                # Set expiration so keys don't leak
                pipe.expire(key, self.window + 1)
                results = await pipe.execute()
                
            request_count = results[2]
        except Exception as e:
            # Fallback to allow if Redis is down, but log heavily
            logger.error(f"Redis rate limiter failed: {e}")
            return
        
        if request_count > self.requests:
            logger.warning(f"Rate limit exceeded for {client_ip} ({self.requests} req / {self.window} sec)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.requests} requests per {self.window} seconds."
            )
