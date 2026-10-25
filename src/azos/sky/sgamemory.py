"""
System Global Area (SGA) is distributed cluster-global structure that provides shared logical memory for
distributed processes/tasks/fibers running on a cluster of nodes, such as Kubernetes pods, VM instances
or even dedicated physical machines.

SGA is a distributed memory structure that allows for efficient sharing of OS-like control data across
multiple nodes in a cluster, such as:
    - mutexes/semaphores for inter-process coordination
    - completion ports/mail slots
    - tasks with slices for distributed processing
    - fibers for cooperative multitasking

You may think of SGA as an OS kernel memory space which is shared across participating nodes. By using this library
you can easily implement your own job engines and coordinate complex business processes execution without relying on
expensive Platform-as-a-Service (PaaS) solutions which create a vendor lock-in.

This work is based on extensive research and development of distributed systems since 1998 (TDT/Galaxy Hosted), NFX,
 and Azos Sky .Net.

Copyright (C) 2020 - 2026 Azist, MIT License
"""


from asyncio import Event
from dataclasses import dataclass
from random import uniform
from typing import override

from azos.exceptions import Validol
from azos.apm.log import LogStrand, LOG_CHANNEL_ANL
from azos.chassis import AppChassis, AppComponent
from azos.daemons import AsyncDaemon
from azos.descriptor import Descriptor
import azos.sky.constraints as sz


@dataclass(frozen=True, slots=True)
class TaskHandle:
    """Controls a distributed task as a whole in SGA, used by task-level calls such as kill/bad request"""
    g_task: int
    trace_uuid: str


@dataclass(frozen=True, slots=True)
class TaskSliceHandle:
    """Controls distributed task slice in SGA akin to a distributed memory task pointer"""
    g_task: int
    g_slice: int
    trace_uuid: str
    seq: int
    caption: str
    app: str
    component: str
    runas: str
    timeout: float  # Max run time in seconds: tbl_task.slice_timeout_sec, after which the slice is deemed abandoned
    args: Descriptor
    run_count: int  # Execution attempt number (1 = first) assigned at acquire; used to reject stale releases



@dataclass(frozen=True, slots=True)
class MutexSetArgs:
    """Represents a set mutex record in SGA akin to a distributed memory mutex pointer"""
    owner_app: str
    owner_cmp: str
    ns: str  #pk
    key:   str  #pk
    value: str
    timeout: float
    description: str

    def __post_init__(self):
        Validol(self) \
          .is_str('owner_app', True, 1, sz.APP_NAME_MAX_LEN) \
          .is_str('owner_cmp', True, 1, sz.APP_COMPONENT_MAX_LEN) \
          .is_str('ns', True, 1, sz.NS_NAME_MAX_LEN) \
          .is_str('key', True, 1, sz.MUTEX_KEY_MAX_LEN) \
          .is_str('value', True, 1, sz.MUTEX_VALUE_MAX_LEN) \
          .is_str('description', True, 1, sz.DESCRIPTION_MAX_LEN) \
          .is_float('timeout', True, 0.1, sz.MUTEX_MAX_TIMEOUT_SEC) \
          .throw()


@dataclass(frozen=True, slots=True)
class MutexHandle:
    """Represents a set mutex record in SGA akin to a distributed memory mutex pointer"""
    g_mutex: int


@dataclass(frozen=True, slots=True)
class RamSlotSetArgs:
    ns: str  #pk
    key:   str  #pk
    value: dict
    component: str
    description: str
    timeout: float | None = None  # Optional auto-expire duration in seconds; None = never expires

    def __post_init__(self):
        Validol(self) \
          .is_str('ns', True, 1, sz.NS_NAME_MAX_LEN) \
          .is_str('key', True, 1, sz.SLOT_KEY_MAX_LEN) \
          .test('Value', lambda v: isinstance(v.target.value, dict) and len(v.target.value) < sz.SLOT_VALUE_MAX_ITEMS) \
          .is_str('component', True, 1, sz.APP_COMPONENT_MAX_LEN) \
          .is_str('description', True, 1, sz.DESCRIPTION_MAX_LEN) \
          .is_float('timeout', False, 0.1) \
          .throw()


@dataclass(frozen=True, slots=True)
class RamSlotGetArgs:
    ns:  str  #pk
    key: str  #pk

    def __post_init__(self):
        Validol(self) \
          .is_str('ns', True, 1, sz.NS_NAME_MAX_LEN) \
          .is_str('key', True, 1, sz.SLOT_KEY_MAX_LEN) \
          .throw()


@dataclass(frozen=True, slots=True)
class RamSlotData:
    ns: str  #pk
    key:   str  #pk
    value: dict
    component: str
    description: str
    timeout: float | None = None  # Remaining seconds until auto-expire; None = never expires


class SGAMemory(AsyncDaemon):
    """
    Implements an abstraction for a distributed memory structure that provides OS kernel-like  control data across
    multiple nodes in a cluster, such as:

        - mutexes/semaphores for inter-process coordination
        - completion data slots
        - tasks with slices for distributed processing
        - fibers for cooperative multitasking

    Concrete implementations derive from this class and provide physical mechanisms of storage, such as
    storing data in RDBMS or NoSQL/memory data stores
    """

    def __init__(self, chassis: AppChassis, director: AppComponent | None = None) -> None:
        super().__init__(chassis, director)
        self._anl = LogStrand("SGAMemory", channel=LOG_CHANNEL_ANL)


    @property
    @override
    def interval_s(self) -> float:
        return uniform(20, 60) # will read this from descriptor


    @override
    async def do_work(self, stop_event: Event) -> None:
        # if self.drop_expired_mutexes_enabled:
        await self.drop_expired_mutexes()

        # if self.drop_expired_slots_enabled:
        await self.drop_expired_slots()

        # this is a TaskInvariantDaemon-like work, but we do it here for simplicity and to avoid another daemon
        # if self.ensure_task_invariants_enabled:
        await self.ensure_task_invariants()


    async def drop_expired_mutexes(self):
        """Drops all mutexes that reached past EOL and never released"""
        if not self.is_daemon_active: return
        ...


    async def drop_expired_slots(self):
        """Drops all slots that reached past EOL and never deleted"""
        if not self.is_daemon_active: return
        ...


    async def ensure_task_invariants(self):
        """Ensures that all tasks in SGA are in a valid state, e.g. slices that are abandoned are failed, etc"""
        if not self.is_daemon_active: return
        ...


    async def task_slice_acquire(self, app: str, component: str) -> TaskSliceHandle | None:
        """
        Retrieves a slice of pending work for tasks scheduled to run by specific app and component.
        If None is returned - there is nothing pending to work on, otherwise the slice is acquired for execution
        and you must pair the call with `task_slice_release_ok` or `task_slice_release_failed` to release the slice back
        to SGA ASAP, within the task `slice_timeout_sec` (see `TaskSliceHandle.timeout`), otherwise the slice is
        considered abandoned and is failed/retried by the system.

        Only slices of tasks in RUNNING state (100/120) whose end date has not passed are eligible:
        slices in status 0, or in status 120 after the retry back-off elapsed, ordered by task niceness.
        Acquire is non-blocking (`FOR UPDATE SKIP LOCKED`). It sets slice status 100 and increments `run_count`.
        See memory.tasks.prd.md section 7.1.
        """
        if not self.is_daemon_active: return None
        ...


    async def task_slice_release_failed(self, handle: TaskSliceHandle, error: Exception) -> None:
        """
        Releases the slice back to SGA and marks it as failed. The outcome is decided atomically: if retries remain
        (`run_count <= task.retry_limit`) the slice goes to RETRYING (120) and is re-acquirable after back-off,
        otherwise it goes to permanently FAILED (500). The task status is NOT set here - it is stamped
        asynchronously by the task invariant daemon.
        A release for an attempt that is no longer current (the slice was reaped as abandoned and re-acquired) is ignored.
        See memory.tasks.prd.md sections 5.1 and 7.3.
        """
        if not self.is_daemon_active: return
        ...


    async def task_slice_release_ok(self, handle: TaskSliceHandle, result: dict | None) -> None:
        """
        Releases the slice back to SGA and marks it as completed successfully, so that it can stop being considered
        for future work. The result is set on a slice level if any.
        A release for an attempt that is no longer current is ignored (memory.tasks.prd.md section 7.3).
        """
        if not self.is_daemon_active: return
        ...


    async def task_set_bad_request(self, handle: TaskHandle, message: str, data: dict | None = None) -> bool:
        """
        Terminates the whole task as invalid (status 400): its arguments are not valid in principle, e.g. unknown
        app/component to execute, so retrying can never help. This is the "terminal exception" of the task:
        `message` is a short summary stored (truncated to `TASK_STATUS_MSG_MAX_LEN`) as the status message;
        `data` holds the error details (e.g. the exception) and is stored in the task `status_data`.
        Only a task in a non-terminal status (0/100/120) is changed; slices are not touched.
        Returns True if the task was changed, False if it does not exist or is already terminal.
        """
        if not self.is_daemon_active: return False
        ...


    async def task_kill(self, handle: TaskHandle, message: str, data: dict | None = None) -> bool:
        """
        Terminates the whole task by KILL signal (status 550). Only a task in a non-terminal status (0/100/120) is changed;
        slices are not touched: slices not started stay as-is, in-flight ones finish without affecting the task.
        `message` is a short summary stored (truncated to `TASK_STATUS_MSG_MAX_LEN`) as the status message;
        optional `data` is stored in the task `status_data`.
        Returns True if the task was changed, False if it does not exist or is already terminal.
        """
        if not self.is_daemon_active: return False
        ...


    async def mutex_set(self, args: MutexSetArgs) -> MutexHandle | None:
        """
        Sets the mutex or throws if the mutex is already set by another process.
        The mutex is auto-released after the timeout expires, so you must call `mutex_release` to release it
        early if you are done with it.
        None is returned if the system can not set mutexes now, e.g. shutting down
        """
        if not self.is_daemon_active: return None
        ...


    async def mutex_release(self, handle: MutexHandle) -> bool | None:
        """
        Releases the mutex. True if it was released, False if not found/already released.
        """
        if not self.is_daemon_active: return None
        ...
        return True


    async def ram_slot_set(self, args: RamSlotSetArgs) -> RamSlotData | None:
        """Sets the RAM slot record or throws if bad data. None if system is shutting down"""
        if not self.is_daemon_active: return None
        ...


    async def ram_slot_get(self, args: RamSlotGetArgs) -> RamSlotData | None:
        if not self.is_daemon_active: return None
        ...


    async def ram_slot_delete(self, args: RamSlotGetArgs) -> bool:
        """Deletes the RAM slot record. Returns True if deleted, False if not found"""
        if not self.is_daemon_active: return False
        ...
        return True
