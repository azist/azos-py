
"""
 Global Distributed ID (GDID)

 Copyright (C) 2011, 2026 Azist, MIT License

 GDID8 is a 64 bit signed integer global distributed identifier (GDID). The design ideology follows Azos.GDID12 and Snowflake ids,
 yet GDID8 is optimized for 64 bit signed integer representation to be easily storable in RDBMSs INT64 type (unlike Azos.GDID).

 In most scenarios, GDID8 significantly outperforms Azos.GDID12 because:
 a). It can be natively stored in 64-bit integer columns of relational databases
 b). 1:1 fit in CPU registers and avoids ALL heap allocations (even in RDBMS engines) such as byte[]
 c). Compact - only 8 bytes instead of 12 bytes (Azos.GDID12)
 d). Faster to generate and faster to compare/sort than Azos.GDID12
 e). No need for dedicated authority nodes and buffering generators, because GDID8 is time-based and can be generated
     on any node in the cluster

 Features:
 1. Time sortable - built-in timestamp component
 2. Globally cross-dc unique (embeds authority)
 3. Compact storage - 8 bytes INT64 - fits in native CPU registers, and DB native types avoiding extra allocations
 4. Sufficient throughput for most data insertion needs (4,096,000/second/worker maximum)

 Limits:
 1. Supports up top 278 years only, then wraps around.
    (This is 10x more than enough for 99% of applications. Azos.GDIDs are MUCH more resilient in that regard)

 2. Consumes ID space even when no inserts are made, because it is time-based.
    (Azos.GDIDs are more efficient in that regard)

 3. Has an insertion limit per second, does not support inserting more records than 4,096,000/second/worker
    (this is a very high limit for most applications, but Azos.GDIDs are more efficient in that regard)

 4. Can not be used as logical vector clocks, because it is time-based and not monotonic, i.e. if a worker is down for a
    while, the next GDID8 will be greater than the last GDID8 generated before the worker went down, even if the worker
    was not generating GDID8s in the meantime.

 5. Significantly less capable in term of total item count, throughput, and longevity than Azos.GDID12.
    Probably not suitable for IoT samples, global telemetry, global call ids. etc..

    Example, within 1 day, this ID can generate only 86,400 * 1000 * 4,096 = 353,894,400,000 unique IDs per worker.
    If you have 256 workers, that is 90,529,228,800,000 unique IDs per day.

    While the number looks very large, it might not be sufficiently large for global applications such as decentralized
    global peer-to-peer networks, telemetry, IoT, etc.

 Structure of GDID8:
 1. 1  bit  = 0 - sign bit the highest bit # 64
 2. 43 bits = timestamp in milliseconds intervals since 20260101 00 UTC (43 bits = 8,796,093,022,207 milliseconds = 278.7 years)
 3. 8  bits = authority/worker id - 256 authorities/workers globally
 4. 12 bits = counter - 4,096 ids per 1ms per authority/worker
 ============================================================================================
    64 bits = 8 bytes = 1 long integer (can used signed or unsigned, the top bit is not used)
"""

import datetime
import time
import threading
import fcntl
from typing import override

from azos.chassis import AppChassis, AppComponent, ConfigError, expand_var_expressions as evars


class GDID8:
    """
    Global Distributed ID (GDID) 8 bytes long, time-based, compact, sortable
    """

    EPOCH = datetime.datetime(2026, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
    """
    The epoch for GDID8 is set to January 1, 2026,
    which is the starting point for the timestamp component of the GDID8.
    This epoch allows for a 43-bit timestamp to represent milliseconds since this date,
    providing a range of approximately 278 years into the future.

    WARNING: If you change the epoch, it will render all previously generated GDID8 values invalid, as the timestamp
    component will no longer be accurate. DO NOT TOUCH this SYSTEM CODE.
    """

    MAX_TIMESTAMP = (1 << 43) - 1
    """Maximum value for the 43-bit timestamp"""

    MAX_AUTHORITY = (1 << 8) - 1
    """Maximum value for the 8-bit authority/worker ID"""

    MAX_COUNTER = (1 << 12) - 1
    """Maximum value for the 12-bit counter"""

    _LAST_NOW = 0;
    _CLOCK_DRIFT_ABORT_MS = 7500

    @staticmethod
    def now() -> int:
        """
        Gets the current timestamp in milliseconds since the GDID8 epoch.
        This now() never goes back in time, even if the system clock is adjusted backwards,
        because it uses time.monotonic() for measuring elapsed time.
        """

        while True:
            result = int((time.time() - GDID8.EPOCH) * 1000)

            # If the system clock was adjusted backwards, we wait until it catches up to the last known timestamp.
            if result < GDID8._LAST_NOW:
                if GDID8._LAST_NOW - result > GDID8._CLOCK_DRIFT_ABORT_MS:
                    raise RuntimeError(f"GDID8.now() System clock is too far behind the last known timestamp: {GDID8._LAST_NOW} vs {result}")

                time.sleep(0.025)  # Sleep for 25 milliseconds (compatible with Windows as well)
            else:
                break

        GDID8._LAST_NOW = result
        return result

    @staticmethod
    def encode(authority: int, timestamp: int, counter: int) -> int:
        """
        Encodes the authority, timestamp, and counter into a single GDID8 value.

        Args:
            authority (int): The authority/worker ID (0-255).
            timestamp (int): The timestamp in milliseconds since the GDID8 epoch.
            counter (int): The counter value (0-4095).
        """
        if not (0 <= authority <= GDID8.MAX_AUTHORITY):
            raise ValueError(f"Authority must be between 0 and {GDID8.MAX_AUTHORITY}.")
        if not (0 <= timestamp <= GDID8.MAX_TIMESTAMP):
            raise ValueError(f"Timestamp must be a 43-bit value (0 to {GDID8.MAX_TIMESTAMP}).")
        if not (0 <= counter <= GDID8.MAX_COUNTER):
            raise ValueError(f"Counter must be a 12-bit value (0 to {GDID8.MAX_COUNTER}).")

        gdid8 = (timestamp << 20) | (authority << 12) | counter
        return gdid8


    def __init__(self, authority: int):
        """
        Initializes a new instance of the GDID8 class.

        Args:
            authority (int): The authority/worker ID (0-255).
        """
        if not (0 <= authority <= GDID8.MAX_AUTHORITY):
            raise ValueError(f"Authority must be between 0 and {GDID8.MAX_AUTHORITY}.")
        self._authority = authority
        self._last_timestamp = 0
        self._counter = 0
        self._lock = threading.Lock()


    @property
    def authority(self) -> int:
        """Gets the authority/worker ID assigned at init"""
        return self._authority


    def generate(self) -> int:
        """Generates a new GDID8 value. This method is THREAD SAFE"""
        with self._lock:
            ts = GDID8.now()

            # Are we within the same millisecond? then inc counter
            if ts == self._last_timestamp:
                self._counter += 1
                # exhausted counter? wait until the next one (unlikely...)
                if self._counter > GDID8.MAX_COUNTER:
                    while ts <= self._last_timestamp:
                        time.sleep(0.001)
                        ts = GDID8.now()
                    self._counter = 0
            else:
                self._counter = 0

            self._last_timestamp = ts
            return GDID8.encode(self._authority, self._last_timestamp, self._counter)



class GDIDGenerator(AppComponent):
    """
    GDID8 generator component that can be used app-wide via DI. This class is THREAD SAFE.
    It encapsulates a GDID8 instance and provides a convenient way to generate GDID8 values by name.
    A name represents a logical group of GDIDs such as a sequence name/table/collection name.
    Each name has its own GDID8 instance, which is created on demand and stored in a dictionary.
    This allows for multiple logical sequences of GDID8 values to be generated independently, each with its own counter.

    WARNING: NEVER RUN MULTIPLE INSTANCES OF THIS CLASS WITH THE SAME AUTHORITY ON THE SAME MACHINE.
    DANGER: FastAPI uses ASGI workers, which means that each worker will have its own instance of this class,
    and if they share the same authority, they will generate duplicate GDID8 values.
    Never run multiple process workers with the same authority on the same machine. Each worker must have a unique authority.

    """

    def __init__(self,  chassis: AppChassis, director: AppComponent | None = None):
        """
        Initializes a new instance of the GDIDGenerator class.
        """
        super().__init__(chassis, director)

        auth = evars(chassis.config.get("gdid","authority", fallback=None), chassis=chassis)
        try:
            self._authority = int(auth) if auth is not None else -10
            if not (0 <= self._authority <= GDID8.MAX_AUTHORITY):
                 raise ValueError(f"Bad authority")
        except Exception:
            raise ConfigError(f"GDIDGenerator section `[gdid:authority]` must be an integer between "
                              f"0 and {GDID8.MAX_AUTHORITY}, got: {auth}. Revise configuration")

        # place machine wide lock on the authority file to prevent multiple instances of this class with the same
        # authority on the same machine
        self._lock_file = open(f"/tmp/azos_gdid8_authority_{self._authority}.lock", "w")
        try:
            # Try to acquire an exclusive lock without blocking (LOCK_NB)
            # Do not drop
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise RuntimeError(f"Another instance of GDIDGenerator with authority {self._authority} is already running on this machine.")

        self._lock = threading.Lock()
        self._generators = {}

    @override
    def _dispose(self) -> None:
        """Releases the lock file and closes it"""
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
        finally:
            super()._dispose()


    def generate(self, name: str) -> int:
        """
        Generates a new GDID8 value for a named sequence. This method is THREAD SAFE.
        If the sequence name is not already present, a new GDID8 instance is created for that name,
        otherwise, the existing GDID8 instance is used to generate the value.
        """
        with self._lock:
            seq = self._generators.get(name)
            if seq is None:
                seq = GDID8(authority=self._authority)
                self._generators[name] = seq

        return seq.generate()

