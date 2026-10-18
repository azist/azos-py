"""
Provides `PgSGAMemory` implementing `SGAMemory` base class using Postgres SQL

Copyright (C) 2020 - 2026 Azist, MIT License
"""

from datetime import timedelta
from time import perf_counter
from typing import override

import asyncpg

from azos.ambient import Ambient
from azos.chassis import AppChassis, AppComponent
from azos.daemons import IAsyncDaemonControl
from azos.db.pgconnector import PgConnector
from azos.exceptions import AzosError
from azos.gdid8 import GDIDGenerator
import azos.sky.constraints as sz
from azos.sky.sgamemory import MutexHandle, MutexSetArgs, SGAMemory


# Name of the PgConnector pool used for SGA memory operations
SGA_MEMORY_POOL_NAME = "sga-memory"

# Inserts a new mutex record. Fails with a unique violation if [ns, key] already exists.
SQL_MUTEX_SET = '''INSERT INTO tbl_mutex
("gdid", "owner_app", "owner_cmp", "set_host", "set_utc", "set_actor","set_origin", "end_utc", "description", "ns", "key", "value")
VALUES
($gdid, $owner_app, $owner_cmp, $set_host, $set_utc, $set_actor, $set_origin, $end_utc, $description, $ns, $key, $value)'''

# Deletes a mutex record by its GDID. Returns the deleted GDID or nothing if not found.
SQL_MUTEX_RELEASE = 'DELETE FROM tbl_mutex WHERE "gdid" = $gdid RETURNING "gdid"'

# Deletes all mutexes that reached past their EOL and returns the count of dropped rows.
SQL_MUTEX_DROP_EXPIRED = '''WITH deleted AS (DELETE FROM tbl_mutex WHERE "end_utc" < $now RETURNING "gdid")
SELECT count(*) FROM deleted'''


class PgSGAMemory(SGAMemory):
    """
    Provides SGA memory implementation based on PG SQL backing store which keeps memory structures
    such as: tasks, slices, mutexes and completion slots in RDBMS tables in PG SQL database
    """

    def __init__(self, chassis: AppChassis, director: AppComponent | None = None) -> None:
        super().__init__(chassis, director)
        self._pgc: PgConnector | None = None
        self._gdid: GDIDGenerator | None = None

    @override
    async def __aenter__(self) -> IAsyncDaemonControl:
        # Lazy link module dependencies using service location
        self._pgc = self.chassis.deps.get(PgConnector)
        self._gdid = self.chassis.deps.get(GDIDGenerator)
        return await super().__aenter__()

    @override
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)
        self._pgc = None
        self._gdid = None


    @override
    async def mutex_set(self, args: MutexSetArgs) -> MutexHandle | None:
        """
        Sets the mutex or throws if the mutex is already set by another process.
        The mutex is auto-released after the timeout expires, so you must call `mutex_release` to release it
        early if you are done with it.
        None is returned if the system can not set mutexes now, e.g. shutting down
        """
        if not self.is_daemon_active or self._pgc is None or self._gdid is None:
            return None

        set_utc = Ambient.utc_now()
        end_utc = set_utc + timedelta(seconds=args.timeout)

        gdid = self._gdid.generate("sga::tbl_mutex")

        try:
            # pg connection stores prepared statements automatically
            async with self._pgc.get_connection(SGA_MEMORY_POOL_NAME) as conn:
                await conn.execute(
                    SQL_MUTEX_SET,
                    gdid=gdid,
                    owner_app=args.owner_app,
                    owner_cmp=args.owner_cmp,
                    set_host=self.chassis.host,
                    set_utc=set_utc,
                    set_actor=Ambient.get_user().name[:sz.ENTITY_ID_MAX_LEN],
                    set_origin=self.chassis.origin,
                    end_utc=end_utc,
                    description=args.description,
                    ns=args.ns,
                    key=args.key,
                    value=args.value,
                )
        except asyncpg.exceptions.UniqueViolationError as cause:
            raise AzosError(
                message=f"Mutex violation: ns=`{args.ns}` key=`{args.key}`",
                topic="sgamemory",
                frm=f"mutex_set(ns=`{args.ns}`, key=`{args.key}`)",
                src=429,
            ) from cause

        return MutexHandle(g_mutex=gdid)

    @override
    async def mutex_release(self, handle: MutexHandle) -> bool | None:
        """
        Releases the mutex. True if it was released, False if not found/already released.
        """
        if not self.is_daemon_active or self._pgc is None:
            return None

        async with self._pgc.get_connection(SGA_MEMORY_POOL_NAME) as conn:
            was = await conn.fetchval(SQL_MUTEX_RELEASE, gdid=handle.g_mutex)

        return was is not None

    @override
    async def drop_expired_mutexes(self):
        """Drops all mutexes that reached past EOL and never released"""
        if not self.is_daemon_active or self._pgc is None:
            return

        started = perf_counter()
        async with self._pgc.get_connection(SGA_MEMORY_POOL_NAME) as conn:
            count = await conn.fetchval(SQL_MUTEX_DROP_EXPIRED, now=Ambient.utc_now())
        elapsed_ms = (perf_counter() - started) * 1000

        if count:
            self._log.info(f"Dropped {count} expired mutexes in {elapsed_ms:.2f} ms")
