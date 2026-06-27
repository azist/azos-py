from enum import Enum
from typing import TypeVar, Any

TEnum = TypeVar("TEnum", bound=Enum)

def get_enum(e: type[TEnum], val: Any) -> TEnum | None:
    pass
