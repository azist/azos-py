"""
Daemons are application components that can be started and stopped, typically running in the background to perform tasks
 or services. This module defines protocols for daemons, including their status and control mechanisms.

Daemons are controlled using a context manager pattern, allowing for clean startup and shutdown sequences. The protocols defined here
 provide a standard interface for implementing daemons, ensuring consistency across different types of services.

The ideology is from Azos.NET but implemented using Pythonic idioms and patterns.

Copyright (C) 2018 - 2026 Azist, MIT License
"""

from enum import Enum
from typing import Protocol, runtime_checkable
import asyncio
from abc import abstractmethod

from azos.chassis import AppComponent, IAppComponent, AppChassis


class DaemonStatus(Enum):
    """
    Enum representing the status of a daemon.
    """
    STOPPED = 0
    STARTING = 1
    RUNNING = 2
    STOPPING = 3


@runtime_checkable
class IDaemon(IAppComponent, Protocol):
    """
    Protocol defining the contract for startable/stoppable services.
    This protocol is a marker one which is used for "read-only" access to daemons such as showing their
    registries/names and statuses in the management tools
    """
    @property
    def daemon_status(self) -> DaemonStatus:
        ...

    @property
    def is_daemon_active(self) -> bool:
        """Convenience property to check if the daemon is currently active: Starting or Running"""
        ...

    @property
    def daemon_failure(self) -> object | None:
        """Captures the last failure if any"""
        ...


@runtime_checkable
class IDaemonControl(IDaemon, Protocol):
    """
    Protocol defining the contract for startable/stoppable services/daemons.
    Notice that this protocol is a synchronous context manager, which is suitable for daemons that are controlled in a
    blocking manner. For asynchronous control, see IAsyncDaemonControl.
    """

    def __enter__(self) -> "IDaemonControl":
        """Starts the daemon if it is stopped, otherwise does nothing"""
        ...

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Stops the daemon if it is running"""
        ...


@runtime_checkable
class IAsyncDaemonControl(IDaemon, Protocol):
    """
    Protocol defining the contract for startable/stoppable services/daemons.
    Notice that this protocol is an asynchronous context manager, which is suitable for daemons that are controlled in a
    non-blocking manner. For synchronous control, see IDaemonControl.
    """

    async def __aenter__(self) -> "IAsyncDaemonControl":
        """Starts the daemon if it is stopped, otherwise does nothing"""
        ...

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Stops the daemon if it is running"""
        ...


class AsyncDaemon(AppComponent, IAsyncDaemonControl):
    """
    Base class for daemons that run on an existing asynchronous loop.
    This class provides a convenient way to implement daemons that need to perform periodic tasks in the background.
    Subclasses should implement the `do_work` method to define the daemon's behavior.

    You would activate such daemon in FastAPI app by using fastapi builder which installs FastApi context manager which
    in turn uses app chassis context manager to start and stop all components (such as this daemon) in a deterministic way.

    Note: this class does not spawn any threads or processes and is intended to be used in an existing async event loop,
    such as the one provided by FastAPI or other async frameworks or your own code.
    """

    def __init__(self, chassis: AppChassis, director: AppComponent | None = None) -> None:
        super().__init__(chassis, director)
        self._daemon_status = DaemonStatus.STOPPED
        self._daemon_failure: object | None = None
        self._stop_event: asyncio.Event | None = None
        self._loop_task: asyncio.Task | None = None

        from azos.apm.log import LogStrand
        self._log = LogStrand(f"{self.__class__.__name__}({self.sid})")

    @property
    def daemon_status(self) -> DaemonStatus:
        return self._daemon_status

    @property
    def is_daemon_active(self) -> bool:
        return self._daemon_status in (DaemonStatus.STARTING, DaemonStatus.RUNNING)

    @property
    def daemon_failure(self) -> object | None:
        return self._daemon_failure

    @property
    def interval_s(self) -> float:
        """Controls how often the daemon fires its do_work(). Override to change the interval. Default is 5 seconds."""
        return 5.0


    @abstractmethod
    async def do_work(self, stop_event: asyncio.Event) -> None:
        """
        Abstract async coroutine called periodically by the daemon's spin loop.
        Implement to define the background work performed on each tick.

        Check self.is_daemon_active and self._stop_event.is_set() to determine if the daemon is still active and
        should continue working. You can bail out early if the daemon is stopping or has been stopped.
        """
        pass


    async def __aenter__(self) -> "IAsyncDaemonControl":
        if self._daemon_status != DaemonStatus.STOPPED:
            return self

        self._daemon_status = DaemonStatus.STARTING
        self._daemon_failure = None
        self._stop_event = asyncio.Event()

        self._loop_task = asyncio.create_task(self._run_loop())
        self._daemon_status = DaemonStatus.RUNNING
        return self


    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._daemon_status not in (DaemonStatus.STARTING, DaemonStatus.RUNNING):
            return

        self._daemon_status = DaemonStatus.STOPPING
        try:
            if self._stop_event is not None:
                self._stop_event.set()

            if self._loop_task is not None:
                try:
                    await self._loop_task
                except asyncio.CancelledError:
                    if not self._loop_task.done():
                        self._loop_task.cancel()
                    raise
                finally:
                    self._loop_task = None
        finally:
            self._daemon_status = DaemonStatus.STOPPED


    async def _run_loop(self) -> None:
        while (self.is_daemon_active and
               self._stop_event is not None and
               not self._stop_event.is_set()):

            try:
                await self.do_work(self._stop_event)
            except Exception as e:
                self._daemon_failure = e
                self._log.critical(f"  do_work() leaked: {e.__class__.__name__}", exc_info=True)


            if not self.is_daemon_active or (self._stop_event is not None and self._stop_event.is_set()):
                break

            try:
                if self._stop_event is not None:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_s)
                break
            except asyncio.TimeoutError:
                pass



