"""
SENTINEL — API Rate Limiter
In-memory sliding window rate limiter for API endpoints.
Used to protect the LLM and background queues from spam.
"""
from __future__ import annotations

import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    In-memory rate limiter dependency.
    Limits clients to `requests` per `window` seconds.
    """
    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        # Dictionary mapping IP/Client to list of timestamps
        self.clients: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request):
        # Identify the client by IP or forwarded-for header
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        current_time = time.time()
        
        # Clean up old requests for this client
        self.clients[client_ip] = [
            req_time for req_time in self.clients[client_ip] 
            if req_time > current_time - self.window
        ]
        
        if len(self.clients[client_ip]) >= self.requests:
            logger.warning(f"Rate limit exceeded for {client_ip} ({self.requests} req / {self.window} sec)")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.requests} requests per {self.window} seconds."
            )
            
        self.clients[client_ip].append(current_time)
