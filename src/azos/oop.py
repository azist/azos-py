"""
Object-Oriented Programming bases and utilities for Azos framework.

Copyright (C) 2020, 2026 Azist, MIT License

"""
import logging
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)

class DisposableObject(ABC):
    """
    Abstract base type for objects that can be disposed, such as components, chassis, etc.
    """

    def __init__(self) -> None:
        self._is_disposed: bool = False

    def __del__(self):
        """The non-deterministic finalizer used for leak detection."""
        # CRITICAL: Check if dispose() was never called:
        #   Always use getattr inside __del__: If an exception occurs inside your __init__ constructor before
        #   self._is_disposed is even created, __del__ will still run. Using getattr(self, '_is_disposed', True)
        #   prevents __del__ from throwing an AttributeError.
        if not getattr(self, '_is_disposed', True):
            logger.critical(f"MEMORY LEAK: {self.__class__.__name__} not disposed in GC")

    @property
    def is_disposed(self) -> bool:
        """
        Indicates whether the object has been disposed. Once an object is disposed, it should not be used anymore.
        You may use this property to return None/empty values from methods of a disposed object, or you can call
        `ensure_not_disposed()` to raise an exception if the object is already disposed
        """
        return self._is_disposed

    def ensure_not_disposed(self) -> None:
        """
        Utility method to check if the object is disposed and raise an exception if it is. This can be used in methods
        that require the object to be alive.
        """
        if self._is_disposed:
            raise RuntimeError(f"Object {self.__class__.__name__} is already disposed")

    @abstractmethod
    def _dispose(self) -> None:
        """
        Internal methods that performs tear/closing work. It is called only once by the public `dispose()` method,
        which handles the idempotency and error handling. Subclasses should implement this method to provide their
        specific disposal logic, such as releasing resources, closing connections, etc.
        """
        pass

    def dispose(self) -> None:
        """
        Disposed the object, performing any necessary cleanup. Once disposed, the object gets into invalid state for
        any further use. This method is idempotent, meaning that calling it multiple times will not cause errors or
        additional side effects.
        """
        if self._is_disposed:
            return

        try:
            self._dispose()
        except Exception as ex:
            raise RuntimeError(f"Error leaked in `(DisposableObject){self.__class__.__name__}`._dispose(): {ex}") from ex
        finally:
            self._is_disposed = True



def free(obj: object) -> None:
    """
    Utility function to dispose an object if it is an instance of `DisposableObject`.
    Does nothing if the object was already disposed.
    Just ignores objects that are not disposable.

    `resource = free(resource)  # Dispose the resource if it is a `DisposableObject` and set it to None`
    """
    if isinstance(obj, DisposableObject):
        obj.dispose()

    return None
