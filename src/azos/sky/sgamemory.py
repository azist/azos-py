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


from dataclasses import dataclass

from azos.exceptions import Validol
from azos.apm.log import LogStrand, LOG_CHANNEL_ANL
from azos.chassis import AppChassis, AppComponent
from azos.daemons import AsyncDaemon
from azos.descriptor import Descriptor


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
    timeout: float
    args: Descriptor



@dataclass(frozen=True, slots=True)
class MutexSetArgs:
    """Represents a set mutex record in SGA akin to a distributed memory mutex pointer"""
    app: str
    host: str
    # --------
    table: str #pk
    key:   str   #pk
    value: dict
    timeout: float
    component: str
    description: str

    def __post_init__(self):
        Validol(self) \
          .is_str('app', True, 1, 32) \
          .is_str('host', True, 1, 32) \
          .is_str('table', True, 1, 32) \
          .is_str('key', True, 1, 32) \
          .test('Value', lambda v: isinstance(v.target.value, dict) and len(v.target.value) < 32) \
          .is_str('component', True, 1, 32) \
          .is_str('description', True, 1, 128) \
          .is_int('timeout', True, 1, 3600) \
          .throw()




@dataclass(frozen=True, slots=True)
class MutexHandle:
    """Represents a set mutex record in SGA akin to a distributed memory mutex pointer"""
    g_mutex: int



class SGAMemory(AsyncDaemon):
    """
    Implements a distributed memory structure that allows for efficient sharing of OS-like control data across
    multiple nodes in a cluster, such as:
        - mutexes/semaphores for inter-process coordination
        - completion ports/mail slots
        - tasks with slices for distributed processing
        - fibers for cooperative multitasking
    """

    def __init__(self, chassis: AppChassis, director: AppComponent | None = None) -> None:
        super().__init__(chassis, director)
        self._anl = LogStrand("SGAMemory", channel=LOG_CHANNEL_ANL)


    async def task_slice_acquire(self, app: str, component: str) -> TaskSliceHandle | None:
        """
        Retrieves a slice of pending work for tasks scheduled to run by specific app and component.
        If None is returned - there is nothing pending to work on, otherwise the slice is acquired for execution
        and you must pair the call with `task_slice_release_ok` or `task_slice_release_failed` to release the slice back
        to SGA ASAP.
        """
        ...


    async def task_slice_release_failed(self, handle: TaskSliceHandle, error: Exception) -> None:
        """
        Releases the slice back to SGA and marks it as failed, so that it can be retried later.
        """
        ...


    async def task_slice_release_ok(self, handle: TaskSliceHandle, result: dict | None) -> None:
        """
        Releases the slice back to SGA and marks it as completed successfully, so that it can stop being considered
        for future work. The result is set on a slice level if any
        """
        ...


    async def mutex_set(self, args: MutexSetArgs) -> MutexHandle:
        """
        Sets the mutex or throws if the mutex is already set by another process.
        The mutex is auto-released after the timeout expires, so you must call `mutex_release` to release it
        early if you are done with it.
        """
        ...


    async def mutex_release(self, handle: MutexHandle) -> bool:
        """
        Releases the mutex. True if it was released, False if not found/already released.
        Only the process (identified by app id) that set the mutex can release it, otherwise an exception is thrown
        """
        ...
