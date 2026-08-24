import urllib.request
import asyncio
code = """
import asyncpg
import asyncio

async def run():
    print(hasattr(asyncpg.Connection, '__aenter__'))
    print(hasattr(asyncpg.pool.PoolAcquireContext, '__aenter__'))

asyncio.run(run())
"""
with open("test_c.py", "w") as f:
    f.write(code)
