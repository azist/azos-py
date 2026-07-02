
import asyncio
from typing import override

import azos.apm.log
from azos.chassis import AppChassis
from azos.daemons import AsyncDaemon

class MyDaemon(AsyncDaemon):
    @property
    @override
    def interval_s(self) -> float:
        return 1.0 # once a second

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        print("MyDaemon is shutting down...")
        await super().__aexit__(exc_type, exc_value, traceback)

    async def do_work(self, stop_event: asyncio.Event) -> None:
        print("MyDaemon is working...")




app = AppChassis("aaa", __file__)
MyDaemon(app)
print("Daemon made")

async def main():

    await app.__aenter__()  # Start the chassis and its components (including the daemon)

    try:
        print("Press Ctrl+C to exit...")
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        await app.__aexit__(None, None, None)  # Cleanly shut down the app chassis and all daemons



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass








