"""
Provides abstract daemon based on asyncio for periodic background tasks. This module defines the `AsyncDaemon` class,
which can be subclassed to create specific daemons that run asynchronously. The `AsyncDaemon` class provides a structure
for running background tasks without blocking the main application thread, allowing for efficient and responsive
applications.

Copyright (C) 2018 - 2026 Azist, MIT License
"""

import asyncio
import threading
from abc import abstractmethod
from typing import override

from azos.chassis import AppChassis, AppComponent, Daemon, DaemonStatus


class AsyncDaemon(Daemon):
    """
    An asynchronous daemon that runs its main logic using asyncio for periodic background tasks.
    Subclasses must implement `_do_spin()` to define the work performed on each tick, and may
    override `spin_interval_sec` to control the delay between consecutive spins.

    The daemon runs its own asyncio event loop in a dedicated background thread so it does not
    interfere with any other event loop in the application.  Stop signaling via `IDaemonControl`
    is fully supported and interrupts the inter-spin wait immediately.
    """

    DEFAULT_SPIN_INTERVAL_SEC: float = 5.0

    def __init__(self, chassis: AppChassis, director: AppComponent) -> None:
        super().__init__(chassis, director)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None

    # #############################
    # Overridable interval hook
    # #############################

    @property
    def spin_interval_sec(self) -> float:
        """
        Returns the number of seconds to wait between consecutive spins.
        Override in subclasses to provide a dynamic or custom interval.
        This property is consulted after every completed `_do_spin()` call,
        so it can return a different value on each invocation.
        """
        return self.DEFAULT_SPIN_INTERVAL_SEC


    # ####################################################################
    # Abstract spin hook – subclasses override this to perform actual work
    # ####################################################################
    @abstractmethod
    async def _do_spin(self) -> None:
        """
        Abstract async coroutine called periodically by the daemon's spin loop.
        Implement to define the background work performed on each tick.
        Unhandled exceptions propagate and will be logged and set failure by the spin loop, but do not stop
        the loop from continuing to run.
        """
        pass

    # #####################################
    # IDaemonControl protected _do_** impl
    # #####################################

    @override
    def _do_start(self) -> None:
        """Starts the asyncio event loop in a dedicated background thread."""
        self._stop_event = asyncio.Event()  # reset stop event in case of restart
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._thread_body,
            daemon=True,
            name=f"AsyncDaemon-{self.__class__.__name__}",
        )
        self._thread.start()

    @override
    def _do_signal_stop(self) -> None:
        """Signals the spin loop to stop by setting the stop event (thread-safe)."""
        if self._loop is not None:
            assert self._stop_event is not None
            self._loop.call_soon_threadsafe(self._stop_event.set)

    @override
    def _do_wait_for_stop(self, timeout_sec: float) -> bool:
        """Blocks until the background thread exits or the timeout elapses."""
        if self._thread is None:
            return True

        stopped = False
        try:
          self._thread.join(timeout=timeout_sec if timeout_sec > 0 else None)
          stopped = not self._thread.is_alive()
          return stopped
        finally:
          if stopped:
            self._thread = None
            self._stop_event = None
            self._loop = None


    # ########################
    # Internal async machinery
    # ########################

    def _thread_body(self) -> None:
        """Entry point for the background thread: runs the asyncio event loop."""
        assert self._loop is not None
        assert self._stop_event is not None
        try:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._spin_loop())
        finally:
            self._loop.close()

    async def _spin_loop(self) -> None:
        """
        Async spin loop: calls `_do_spin()` then waits `spin_interval_sec` before the next spin.
        The inter-spin wait is interrupted immediately when `daemon_signal_stop()` is called.
        """
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await self._do_spin()
            except Exception as ex:
                self._log.critical(f"_do_spin leaked: {ex}", exc_info=True)
                self._failure = ex

            if self._stop_event.is_set():
                break

            interval = self.spin_interval_sec
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                break  # stop event fired during the wait
            except asyncio.TimeoutError:
                pass  # normal interval expiry – continue spinning

