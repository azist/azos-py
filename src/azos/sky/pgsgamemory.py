"""
Implements SGAMemory using PG SQL

Copyright (C) 2020 - 2026 Azist, MIT License
"""

import json
from datetime import timedelta
from typing import override

import asyncpg

from azos.ambient import Ambient
from azos.chassis import AppChassis, AppComponent
from azos.daemons import IAsyncDaemonControl
from azos.db.pgconnector import PgConnector
from azos.exceptions import AzosError
from azos.gdid8 import GDID8, GDIDGenerator
from azos.sky.sgamemory import MutexHandle, MutexSetArgs, SGAMemory


# Name of the PgConnector pool used for SGA memory operations
SGA_POOL_NAME = "sga"

# Fallback GDID8 generator used when no GDIDGenerator is registered in the chassis DI
_FALLBACK_GDID = GDID8(0)


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
        # Lazy link module dependency using service location
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

        sql = """
            INSERT INTO tbl_mutex
                ("gdid", "owner_app", "owner_cmp", "set_host", "set_utc", "set_actor",
                 "set_origin", "end_utc", "description", "ns", "key", "value")
            VALUES
                ($gdid, $owner_app, $owner_cmp, $set_host, $set_utc, $set_actor,
                 $set_origin, $end_utc, $description, $ns, $key, $value)
        """

        gdid = self._gdid.generate("sga::tbl_mutex")

        try:
            # pg connection stores prepared statements automatically
            async with self._pgc.get_connection(SGA_POOL_NAME) as conn:
                await conn.execute(
                    sql,
                    gdid=gdid,
                    owner_app=args.owner_app,
                    owner_cmp=args.owner_cmp,
                    set_host=self.chassis.host,
                    set_utc=set_utc,
                    set_actor=Ambient.get_user().name,
                    set_origin=self.chassis.origin,
                    end_utc=end_utc,
                    description=args.description,
                    ns=args.ns,
                    key=args.key,
                    value=args.value,
                )
        except asyncpg.exceptions.UniqueViolationError as cause:
            raise AzosError(
                message=f"Mutex is already set: ns=`{args.ns}` key=`{args.key}`",
                topic="sgamemory",
                frm=f"mutex_set(ns=`{args.ns}`, key=`{args.key}`)",
                src=429,
            ) from cause

        return MutexHandle(g_mutex=gdid)

    @override
    async def mutex_release(self, handle: MutexHandle) -> bool:
        """
        Releases the mutex. True if it was released, False if not found/already released.
        Only the process (identified by app id) that set the mutex can release it, otherwise it is "not found" and False is returned.
        """
        if not self.is_daemon_active or self._pgc is None:
            return False

        sql = """
            DELETE FROM tbl_mutex
            WHERE "gdid" = $gdid AND "owner_app" = $owner_app
            RETURNING "gdid"
        """

        async with self._pgc.get_connection(SGA_POOL_NAME) as conn:
            row = await conn.fetchval(sql, gdid=handle.g_mutex, owner_app=self.chassis.app)

        return row is not None
