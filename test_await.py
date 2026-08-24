import asyncpg
import asyncio

async def test():
    class DummyContext:
        def __await__(self):
            async def _yield_conn():
                return "ConnectionObj"
            return _yield_conn().__await__()
            
        async def __aenter__(self):
            return "ConnectionObj"
            
        async def __aexit__(self, exc_t, exc_v, exc_tb):
            pass
            
    def get_connection():
        return DummyContext()
        
    conn = await get_connection()
    print("Awaited:", conn)
    
    async with get_connection() as c2:
        print("Context:", c2)

asyncio.run(test())
