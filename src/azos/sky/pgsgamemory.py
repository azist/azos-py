"""
Implements SGAMemory using PG SQL

Copyright (C) 2020 - 2026 Azist, MIT License
"""

from typing import override

from azos.chassis import AppChassis, AppComponent
from azos.daemons import IAsyncDaemonControl
from azos.sky.sgamemory import SGAMemory
from azos.db.pgconnector import PgConnector


class PgSGAMemory(SGAMemory):

    def __init__(self, chassis: AppChassis, director: AppComponent | None = None) -> None:
        super().__init__(chassis, director)
        self._pgc: PgConnector | None = None

    @override
    async def __aenter__(self) -> IAsyncDaemonControl:
        # Lazy link module dependency using service location
        self._pgc = self.chassis.deps.get(PgConnector)
        return await super().__aenter__()
