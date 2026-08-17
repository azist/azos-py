"""
Factory Utilities for instantiating objects by name.

Copyright (C) 2011, 2026 Azist, MIT License

"""

from typing import Type, TypeVar, Dict, Any, Callable

from azos.chassis import AppChassis, AppComponent
from azos.descriptor import Descriptor

T = TypeVar("T")

# maps string name to class type
_registry: Dict[str, Type] = {}


def register(name: str | None = None) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class to the factory by name, thus allowing factory to instantiate
    class instances by string name. The decorator can be used with or without a name argument.
    If no name is provided, the class's name is used.

    Usage:
        @register("MyNamespace.MyLogProvider")
        class MyLogger: ...
    """
    def decorator(subclass: Type[T]) -> Type[T]:
        key = name or subclass.__name__
        if key in _registry:
            raise ValueError(f"Type name '{key}' is already registered.")
        _registry[key] = subclass
        return subclass
    return decorator


def make(expected_type: Type[T], type_name: str, *args: Any, **kwargs: Any) -> T:
    """
    Analog to C# FactoryUtils.Make<T>(type: str, ctorargs).
    Instantiates a registered type by its string name, passing all remaining
    positional and keyword arguments directly to its constructor.

    ```python
    # 1. From explicit kwargs (C# kwargs analog):
    make(MyBaseClass, "MyImpl", param1="value", param2=42)

    # 2. From positional args (C# params object[] analog):
    make(MyBaseClass, "MyImpl", "value", 42)

    # 3. Reading straight from a dictionary containing a 'type' key gracefully:
    my_config = {"type": "MyImpl", "param1": "value"}
    type_name = my_config.pop("type")
    make(MyBaseClass, type_name, **my_config)
    ```
    """
    target_cls = _registry.get(type_name)
    if not target_cls:
        raise TypeError(f"Type '{type_name}' could not be resolved as it is not registered.")

    # Ensure the target class is a subtype of expected_type
    if not issubclass(target_cls, expected_type):
        raise TypeError(
            f"Registered type '{target_cls.__name__}' is not a subtype of '{expected_type.__name__}'"
        )

    return target_cls(*args, **kwargs)


def make_from_descriptor(expected_type: Type[T],
                         descriptor: Descriptor,
                         default_type_name: str) -> T:
    """
    Instantiates a registered type by its string name from a Descriptor object.
    The descriptor is expected to have a 'type' attribute that specifies the type name.
    All other attributes of the descriptor are passed as keyword arguments to the constructor of the type.

    ```python
    # Example usage:
    descriptor = Descriptor(type="MyImpl", param1="value", param2=42)
    instance = make_from_descriptor(MyBaseClass, descriptor, default_type_name="MyImpl")
    ```
    """
    type_name = descriptor.as_str("type", default_type_name)
    if not type_name:
        raise ValueError("Descriptor must have a 'type' attribute specifying the type name.")

    return make(expected_type, type_name, descriptor)


def make_component_from_descriptor(expected_type: Type[T],
                                   descriptor: Descriptor,
                                   chassis: AppChassis,
                                   director: AppComponent | None = None,
                                   default_type_name: str = "") -> T:
    """
    Instantiates a registered component type by its string name from a Descriptor object.
    The descriptor is expected to have a 'type' attribute that specifies the type name.
    All other attributes of the descriptor are passed as keyword arguments to the constructor of the type.

    This function is specifically designed for components that require a chassis and an optional director.

    ```python
    # Example usage:
    descriptor = Descriptor(type="MyComponent", param1="value", param2=42)
    instance = make_component_from_descriptor(MyBaseComponentClass, descriptor, chassis=my_chassis, director=my_director)
    ```
    """
    type_name = descriptor.as_str("type", default_type_name)
    if not type_name:
        raise ValueError("Descriptor must have a 'type' attribute specifying the type name.")

    return make(expected_type, type_name, chassis, director, descriptor)
