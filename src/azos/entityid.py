"""Provides interop functions for working with Azos EntityId data type

Copyright (C) 2023 Azist, MIT License

"""

import json

from .exceptions import AzosError
from .atom import Atom

TP_PREFIX = "@"
SCHEMA_DIV = "."
SYS_PREFIX = "::"

def tryparse(val: str) -> tuple | None:
    """Tries to parse a string as EntityId returning a tuple on success or None if val is not parsable

    """
    try:
        if val == None:
            return None

        vlen = len(val)

        if vlen < 4:
            return None

        # Find the :: separator which divides system/type/schema from address
        sys_idx = val.find(SYS_PREFIX)
        if sys_idx == -1:
            return None

        # Split into prefix (system/type/schema part) and address
        prefix = val[:sys_idx]
        address = val[sys_idx + len(SYS_PREFIX):]

        # Address must not be empty
        if not address:
            return None

        # Find @ separator which divides type/schema from system
        tp_idx = prefix.find(TP_PREFIX)

        if tp_idx == -1:
            # No type/schema qualifier, only system (format: system::address)
            if not prefix:
                return None
            sys = Atom(prefix)
            type = Atom(0)
            schema = Atom(0)
        else:
            # Has type/schema part (format: type.schema@system::address or type@system::address)
            type_schema_part = prefix[:tp_idx]
            system_part = prefix[tp_idx + len(TP_PREFIX):]

            if not system_part or not type_schema_part:
                return None

            sys = Atom(system_part)

            # Split type and schema
            schema_idx = type_schema_part.find(SCHEMA_DIV)
            if schema_idx == -1:
                # No schema (format: type@system::address)
                type = Atom(type_schema_part)
                schema = Atom(0)
            else:
                # Full format (type.schema@system::address)
                type_part = type_schema_part[:schema_idx]
                schema_part = type_schema_part[schema_idx + len(SCHEMA_DIV):]
                if not type_part or not schema_part:
                    return None
                type = Atom(type_part)
                schema = Atom(schema_part)

        return (sys, type, schema, address)
    except AzosError:
        # Invalid Atom construction (invalid characters or too long)
        return None

def parse(val: str) -> tuple:
    """Tries to parse a string as EntityId returning a tuple on success or throwing AzosError

    """
    result = tryparse(val)
    if result == None:
        raise AzosError("Supplied value is not parsable as EntityId", "entityid", f"parse(`{val}`)")
    return result


class EntityId:
    """Implements Azos EntityId a vector of (SYSTEM: Atom, TYPE: Atom, SCHEMA: Atom, ADDRESS: string)

    The concept is somewhat similar to an "URI" in its intended purpose, as it identifies objects by an "Address"
    string which is interpreted in a scope of "Type/Schema", which in turn is in the scope of a "System".

    As a string, an EntityId is formatted like: `type.schema@system::address`, for example: `car.vin@dealer::1A8987339HBz0909W874`
    vs `boat.license@dealer::I9973OD`. The system qualifier is required, but type (and schema) qualifier is optional, which denotes "default type"
    for example: `dealer::I9973OD` is a valid EntityId pointing to a "dealer" system "car" type with "license" address schema by default.

    The optional schema sub-qualifier defines the "schema" of addressing used per type, this way you can identify the same entity types within a system with
    different addressing schemas
    """

    @classmethod
    def from_value(cls, strval):
        """Class method to create EntityId by parsing a string value

        Throws AzosError if the value is not parsable.

        If you need conditional parsing you can call `tryparse()` with conditional
        `from_components(tuple)` class method if the value is parsable
        """
        eid = parse(strval)
        return cls(eid[0], eid[1], eid[2], eid[3])

    @classmethod
    def from_components(cls, components):
        """Class method to create EntityId from components tuple
        """
        return cls(components[0], components[1], components[2], components[3])


    def __init__(self, eid_sys: Atom, eid_type: Atom, eid_schema: Atom, eid_address: str) -> None:
        self._system = eid_sys
        self._type = eid_type
        self._schema = eid_schema
        self._address = eid_address

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"EntityId(`{self.get_value()}`)"

    def __eq__(self, other: object) -> bool:
        return self._system  == other.system and \
               self._type    == other.type and \
               self._schema  == other.schema and \
               self._address == other.address

    def __hash__(self):
        return hash(self._system) ^ hash(self._type) ^ hash(self._schema) ^ hash(self._address)

    @property
    def system(self) -> Atom:
        """Gets EntityId.System: Atom"""
        return self._system

    @property
    def type(self) -> Atom:
        """Gets EntityId.Type: Atom"""
        return self._type

    @property
    def schema(self) -> Atom:
        """Gets EntityId.Schema: Atom"""
        return self._schema

    @property
    def address(self) -> str:
        """Gets EntityId.Address: str"""
        return self._address

    @property
    def is_composite_address(self) -> bool:
        """Returns True when address is assigned as composite JSON object starting with '{' and ending with '}' without any leading or trailing spaces"""
        return self._address.startswith("{") and self._address.endswith("}")

    @property
    def value(self) -> str:
        """Returns EntityId string value"""
        if self._type.is_zero:
            return f"{self._system}{SYS_PREFIX}{self._address}"
        if self._schema.is_zero:
            return f"{self._type}{TP_PREFIX}{self._system}{SYS_PREFIX}{self._address}"

        return f"{self._type}{SCHEMA_DIV}{self._schema}{TP_PREFIX}{self._system}{SYS_PREFIX}{self._address}"

    @property
    def components(self) -> tuple:
        """Returns components of entity id a s a tuple of (sys,type,schema,address)

        """
        return (self._system, self._type, self._schema, self._address)

    def get_value(self) -> str:
        """Returns EntityId string value (deprecated: use .value property instead)"""
        return self.value

    def get_components(self) -> tuple:
        """Returns components of entity id a s a tuple of (sys,type,schema,address) (deprecated: use .components property instead)

        """
        return self.components

    def get_composite_address(self) -> map | None:
        """
        For address which starts with '{' and ends with '}' returns a parsed JSON as map.

        Returns None if address is not a composite address
        """
        if not self.is_composite_address:
            return None
        try:
            return json.loads(self._address)
        except Exception as cause:
            raise AzosError("EntityId contains invalid composite address", "entityid", f"get_composite_address()") from cause

