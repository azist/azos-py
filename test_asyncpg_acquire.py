import asyncio
import asyncpg

async def main():
    try:
        pool = await asyncpg.create_pool(user='postgres', command_timeout=60)
        # Using it as async with:
        async with pool.acquire() as conn:
            pass
        
        # Awaiting it in a wrapper:
        async def get_connection():
            return await pool.acquire()
            
        async with get_connection() as conn: # This would fail because get_connection returns a coroutine context? Let's see
            pass
    except Exception as e:
        print(f"Exception: {e}")

asyncio.run(main())
