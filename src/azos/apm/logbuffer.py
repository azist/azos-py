"""Memory circular buffer that keeps X log records"""

import collections
import logging

from typing import List, Optional

class MemoryLogBuffer:
    """Stores log records up to a given capacity"""

    __s_global_instance: Optional["MemoryLogBuffer"] = None

    @staticmethod
    def get_global() -> Optional["MemoryLogBuffer"]:
        """Returns global instance or None of not set yet"""
        return MemoryLogBuffer.__s_global_instance

    @staticmethod
    def set_global(instance: Optional["MemoryLogBuffer"]) -> None:
        """Sets the global instance"""
        MemoryLogBuffer.__s_global_instance = instance

    def __init__(self, capacity: int):
        """Initializes the buffer with the given capacity"""
        if capacity < 1:
            raise ValueError(f"Buffer capacity must be >= 1 ut got  {capacity}")
        self._capacity = capacity
        self._buffer: collections.deque[dict] = collections.deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        """Returns the capacity of this buffer"""
        return self._capacity

    def append(self, record: dict) -> None:
        """Appends a log record to the buffer replace oldest if at capacity"""
        self._buffer.append(record)

    def get_records(self, count: int | None) -> List[dict]:
        """Returns the most recent 'count' records from the buffer"""

        if count is None or count >= len(self._buffer):
            return list(self._buffer)

        return list(self._buffer)[-count:] if count > 0 else []

    def __len__(self) -> int:
        """Returns the number of records currently in the buffer"""
        return len(self._buffer)

    def clear(self) -> None:
        """Clears all records"""
        self._buffer.clear()



class MemoryLogBufferHandler(logging.Handler):
    """Captures log record as diction aries into a buffer """

    def __init__(self, buffer: MemoryLogBuffer):
        """Initializes handler with a MemoryLogBuffer instance"""
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        """Emits a log record by appending it to the buffer"""
        try:
            from azos.apm.log import AzLogRecord, AzLogRecordFormatter
            if isinstance(record, AzLogRecord) and isinstance(self.formatter, AzLogRecordFormatter):
                log_dict = self.formatter.build_log_dict(record)
                self._buffer.append(log_dict)
        except Exception:
            self.handleError(record)
