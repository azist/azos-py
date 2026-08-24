"""
PostgreSQL database connector providing connection management for the application chassis

Copyright (C) 2011 - 2026 Azist, MIT License
"""

import asyncpg

from azos.chassis import AppChassis, AppComponent
from azos.descriptor import Descriptor


class PgConnector(AppComponent):
    """
    PostgreSQL database connector providing connection management for the application chassis.
    """

    def __init__(self, chassis: AppChassis, director: AppComponent, config: Descriptor):
        super().__init__(chassis, director=director)

        self._cfg = config.clone()
        self._pools = {}


    async def __aenter__(self):
        pools = self._cfg.navigate_required_value("pools")

        if not isinstance(pools, list) or not pools:
            raise ValueError("No connection pools defined in the configuration.")

        try:
            for pool_config in pools:
                name = pool_config.as_str("name")
                if name in self._pools:
                    raise ValueError(f"Duplicate connection pool name: {name}")

                pool = await self._create_pool(name, pool_config)
                self._pools[name] = pool
        except Exception:
            await self._close_all_pools()
            raise

        return self

    async def _close_all_pools(self):
        """
        Internal helper to safely close all established connection pools.
        """
        for name, pool in list(self._pools.items()):
            try:
                await self._close_pool(name, pool)
            except Exception:
                # todo: log the exception for debugging purposes
                pass # suppress exceptions during teardown to continue closing others
        self._pools.clear()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_all_pools()



    async def _create_pool(self, name: str, pool_config: Descriptor) -> asyncpg.pool.Pool:
        """
        Create a new connection pool for the given name and configuration.
        Override this method to use a custom connection pool creation logic if needed.

        :param name: The name of the connection pool.
        :param pool_config: The configuration descriptor for the pool.
        :return: An asyncpg.pool.Pool instance.
        """
        dsn = pool_config.as_str("dsn")
        return await asyncpg.create_pool(dsn=dsn)

    async def _close_pool(self, name: str, pool: asyncpg.pool.Pool):
        """
        Close an existing connection pool.
        Override this method to use a custom connection pool teardown logic if needed (e.g. for GCP Connector).

        :param name: The name of the connection pool.
        :param pool: The asyncpg.pool.Pool instance.
        """
        await pool.close()


    def get_connection(self, name: str) -> asyncpg.pool.PoolAcquireContext:
        """
        Retrieve a connection from the connection pool by name.
        Use it and release it:

        ```python
        async with pg_connector.get_connection("my_pool") as conn:
            # Use the connection
            cnt = await conn.fetchval("SELECT COUNT(*) FROM tbl_doctor")
            print(f"Doctor count: {cnt}")
        ```

        :param name: The name of the connection pool.
        :return: An async context manager resolving to an active asyncpg.Connection instance.
        :raises ValueError: If no connection pool is found for the given name.
        """
        pool = self._pools.get(name, None)

        if pool is None:
            raise ValueError(f"No connection pool found for name: {name}")

        return pool.acquire()
