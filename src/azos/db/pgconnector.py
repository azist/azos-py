"""
PostgreSQL database connector providing connection management for the application chassis

Copyright (C) 2011 - 2026 Azist, MIT License
"""

from typing import override
import time
import json
from datetime import datetime

import asyncio
import asyncpg

from configparser import ConfigParser

from azos.chassis import AppChassis, AppComponent, ChassisDescriptorFactory
from azos.descriptor import Descriptor
from azos.exceptions import AzosError
from azos.factoryutils import register


CONFIG_SECTION = "pg-sql-chassis"


class PgSqlCtreeChassisDescriptorFactory(ChassisDescriptorFactory):
    """
    Fetches application chassis descriptors by fetching the app config from PgSQL ctree
    bypassing complex ctree mechanics which rely on loaded modules.

    You have to have a running PgSQL instance and application configured under
    `/boot/app/{app_id}` path in the tree.

    Cluster boots central `gov` service using this bootloader, then subsequent services obtain full
    configuration from the `gov` service via a network call
    """

    async def acquire_connection(self, environment: str, config: ConfigParser) -> asyncpg.Connection:
        try:
            url = config.get(CONFIG_SECTION, "url", fallback=None)

            # If no URL provided, build it from individual components
            if not url:
                database = config.get(CONFIG_SECTION, "database", fallback=None)
                user = config.get(CONFIG_SECTION, "user", fallback=None)
                password = config.get(CONFIG_SECTION, "password", fallback=None)
                host = config.get(CONFIG_SECTION, "host", fallback="127.0.0.1")
                port = config.get(CONFIG_SECTION, "port", fallback="5432")

                url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

            # Pass only DSN, avoiding parameter conflicts
            return await asyncpg.connect(dsn=url)
        except Exception as e:
            raise AzosError(
                message=f"Unable to establish PgSql connection to ctree db as specified in `[{CONFIG_SECTION}]`",
                topic="pgconnector",
                frm=f"acquire_connection(env=`{environment}`, db=`{config.get(CONFIG_SECTION, 'database', fallback='?')}`)",
                src=0
            ) from e


    async def doWork(self,
                     instance_id: str,
                     entry_point_path: str,
                     app_id: str,
                     environment: str,
                     host: str,
                     config: ConfigParser) -> "Descriptor":

        cnn = await self.acquire_connection(environment, config)
        try:
            # we will read the config using schema in ../sky/ctree.pg.sql

            # we need to fetch the following paths: in sequence
            # `/` root, then `/boot`, `/boot/app`, `/boot/app/{app_id}`
            # so we need to do 4 reads, all AS OF UTC NOW (at the time of call).
            # we then need to override `config` Descriptor from top to bottom and return the final Descriptor.
            # You can hint how it is done from ../sky/ctree.py


            # Get current time as UTC timestamp for "as of" queries
            # Note: using naive datetime to match PostgreSQL 'timestamp' type (not 'timestamptz')
            asof_utc = datetime.fromtimestamp(time.time())

            # Build the list of paths to fetch in order
            paths = [
                "/",
                "/boot",
                "/boot/app",
                f"/boot/app/{app_id}"
            ]

            # Start with empty descriptor
            result = Descriptor({})

            # Query each path and override the result
            for path in paths:
                query = """
                    SELECT "config"
                    FROM "tbl_ctree"
                    WHERE "path" = $1
                        AND "asof_utc" <= $2
                        AND "ver_state" != 'd'
                    ORDER BY "asof_utc" DESC
                    LIMIT 1
                """

                row = await cnn.fetchrow(query, path, asof_utc)

                if not row:
                    raise AzosError(
                        message=f"Configuration node not found in ctree",
                        topic="pgconnector",
                        frm=f"doWork(path=`{path}`)",
                        src=1
                    )

                config_data = row["config"]
                if not config_data:
                    raise AzosError(
                        message=f"Configuration data is empty for path",
                        topic="pgconnector",
                        frm=f"doWork(path=`{path}`)",
                        src=2
                    )

                if isinstance(config_data, str):
                    config_data = json.loads(config_data)

                # Create descriptor from fetched config and override
                override_descriptor = Descriptor(config_data)
                result.override_by(override_descriptor)

            return result
        finally:
            await cnn.close()


    @override
    def __call__(self,
                instance_id: str,
                entry_point_path: str,
                app_id: str,
                environment: str,
                host: str,
                config: ConfigParser) -> "Descriptor":

        try:
            result = asyncio.run(self.doWork(instance_id,
                                             entry_point_path,
                                             app_id,
                                             environment,
                                             host,
                                             config))
            return result
        except Exception as e:
            raise AzosError(
                message=f"!!!Catastrophic failure!!!: \n"
                        f"PgSqlCtreeChassisDescriptorFactory was not able to obtain descriptor to bootload chassis \n"
                        f"Inspect the inner error for details \n"
                        f"Inner error: \n     {str(e)}",
                topic="pgconnector",
                frm=f"__call__(app_id=`{app_id}`, env=`{environment}`, host=`{host}`)",
                src=0
            ) from e


@register("PgConnector")
class PgConnector(AppComponent):
    """
    PostgreSQL database connector providing connection management for the application chassis.
    """

    def __init__(self, chassis: AppChassis, director: AppComponent | None, config: Descriptor):
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
