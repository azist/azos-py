"""
Provides abstract daemon based on asyncio for periodic background tasks. This module defines the `AsyncDaemon` class,
which can be subclassed to create specific daemons that run asynchronously. The `AsyncDaemon` class provides a structure
for running background tasks without blocking the main application thread, allowing for efficient and responsive
applications.

Copyright (C) 2018 - 2026 Azist, MIT License
"""

import asyncio
import time
import threading

from abc import abstractmethod
from typing import override

from azos.chassis import AppChassis, AppComponent, Daemon, DaemonStatus

QUANTA_MIN_SEC = 0.02  # minimum spin interval to prevent excessive CPU usage


class AsyncDaemon(Daemon):
    """
    An asynchronous daemon that runs its main logic using asyncio for periodic background tasks.
    Subclasses must implement `_do_spin()` to define the work performed on each tick, and may
    override `spin_interval_sec` to control the delay between consecutive spins.

    The daemon runs its own asyncio event loop in a dedicated background thread so it does not
    interfere with any other event loop in the application.  Stop signaling via `IDaemonControl`
    is fully supported and interrupts the inter-spin wait immediately.

    By design daemon control methods should only be called by primary/main application thread and not from within
    daemon's own execution context to avoid potential deadlocks. If you need to signal a daemon to stop from within
    its own execution context, consider using an internal event or flag that the daemon checks periodically to determine
    when to stop, rather than calling `daemon_signal_stop` directly from within the daemon's execution

    Notes:
     Why do we not have a Thread-based daemon without async io - foe simplicity as 98% of use cases
     are calling external async services (e.g. httpx) and we want to avoid the complexity of managing a thread pool
     and synchronization primitives for a non-async daemon.

     If you need to run a non-async background task (such as legacy data access code), you can still use `AsyncDaemon`
     and simply run your synchronous  code in an executor using `loop.run_in_executor()`:
     ```python
     async def _do_spin(self) -> None:
         await self._loop.run_in_executor(None, self._legacy_sync_task)
     ```
     This allows you to leverage the existing `AsyncDaemon` infrastructure while still running blocking code without
        blocking the event loop.

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

        WARNING: Never call `daemon_*` methods from within `_do_spin()`, as it may cause deadlocks or undefined behavior.
        These methods are for external daemon control only and are not thread-safe when called from the spin loop context.
        If you need to signal the daemon to stop from within `_do_spin()`, use the protected `_abort_daemon_from_spin()`
          method instead, which is designed for this purpose and is safe to call from within the spin loop.

        Normally you should never abort a running Daemon from within its own spin loop, but this can be useful in certain
        scenarios where you want to stop the daemon immediately based on some condition detected during the spin,
        without waiting for an external control.
        """
        pass


    def _abort_daemon_from_spin(self) -> None:
        """
        Utility method that can be called from within `_do_spin()` to signal the daemon to stop immediately.
        This is a thread-safe operation that sets the stop event, causing the spin loop to exit after the current
        spin iteration completes.

        WARNING: DO NOT call this protected method from outside the `_do_spin()` context, as it is not thread-safe and may
        cause race conditions
        """
        if self.is_daemon_active:
            self._status = DaemonStatus.STOPPING
            if self._stop_event is not None:
                self._stop_event.set()

    # #####################################
    # IDaemonControl protected _do_** impl
    # #####################################

    @override
    def _do_start(self) -> None:
        """Starts the asyncio event loop in a dedicated background thread."""
        self._thread = threading.Thread(
            target=self._thread_body,
            daemon=True,
            name=f"AsyncDaemon-{self.__class__.__name__}",
        )
        self._thread.start() # do not use run() to avoid blocking the caller thread

    @override
    def _do_signal_stop(self) -> None:
        """Signals the spin loop to stop by setting the stop event (thread-safe)."""
        # Capture local for GIL-free access
        loop = self._loop
        stop_event = self._stop_event
        if loop is not None and stop_event is not None:
            loop.call_soon_threadsafe(stop_event.set)

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


    # ####################
    # .pvt async spin loop
    # ####################

    def _thread_body(self) -> None:
        """Entry point for the background thread: runs the asyncio event loop."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)  # Must bind IN THE running thread before creating the stop event
            self._stop_event = asyncio.Event()  # Must be created AFTER the event loop is bound toi executing thread

            # ############## DO THE SPINNING ###############
            self._loop.run_until_complete(self._spin_loop())
            # ##############################################

        finally:
            if self._loop is not None:
                try:
                    self._loop.close()
                except Exception:
                    pass

                self._loop = None
                self._stop_event = None


    # this executes on _thread_body's event loop thread
    # can safely access the stop event and loop without locking
    async def _spin_loop(self) -> None:
        """
        Async spin loop: calls `_do_spin()` then waits `spin_interval_sec` before the next spin.
        The inter-spin wait is interrupted immediately when `daemon_signal_stop()` is called.
        """
        assert self._stop_event is not None
        while self.is_daemon_active and not self._stop_event.is_set():
            try:
                await self._do_spin()
            except Exception as ex:
                self._log.critical(f"_do_spin leaked: {ex}", exc_info=True)
                self._failure = ex

            if  not self.is_daemon_active or self._stop_event.is_set():
                break

            interval = self.spin_interval_sec

            if interval <= QUANTA_MIN_SEC: # keep in meaningful bounds
                interval = QUANTA_MIN_SEC

            try:
                await asyncio.wait_for(self._stop_event.wait(),
                                       timeout=interval)
                break  # stop event fired during the wait, bail out of the loop
            except asyncio.TimeoutError:
                pass  # expected interval expiry – continue spinning

