"""
Digital Twin Backend — Database Connection
"""
import os
import asyncpg
from typing import Optional

POOL: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global POOL
    if POOL is None:
        POOL = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "dt_platform"),
            user=os.getenv("POSTGRES_USER", "dt_user"),
            password=os.getenv("POSTGRES_PASSWORD", "dt_pass_2025"),
            min_size=2,
            max_size=10,
        )
    return POOL


async def close_pool():
    global POOL
    if POOL:
        await POOL.close()
        POOL = None
