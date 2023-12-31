"""Provides interop functions for working with Azos EntityId data type

Copyright (C) 20023 Azist, MIT License


"""

import json

from azexceptions import AzosError
from azatom import Atom

TP_PREFIX = "@"
SCHEMA_DIV = "."
SYS_PREFIX = "::"

def tryparse(val: str) -> tuple | None:
    """Tries to parse a string as EntityId returning a tuple on success or None if val is not parsable

    """
    if val == None:
        return None
    
    vlen = len(val)

    if vlen < 4:
        return None
    
    # Todo: Finish
    return (sys, type, schema, address)

def parse(val: str) -> tuple:
    """Tries to parse a string as EntityId returning a tuple on success or throwing AzosError

    """
    result = tryparse(val)
    if result == None:
        raise AzosError("Supplied value is not parsable as EntityId", "entityid", f"parse(`{val}`)")


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
    
    def get_value(self) -> str:
        if self._type.is_zero:
            return f"{self._system}{SYS_PREFIX}{self._address}"
        if self._schema.is_zero:
            return f"{self._type}{TP_PREFIX}{self._system}{SYS_PREFIX}{self._address}"
        
        return f"{self._type}{SCHEMA_DIV}{self._schema}{TP_PREFIX}{self._system}{SYS_PREFIX}{self._address}"
    
    def get_components(self) -> str:
        """Returns components of entity id a s a tuple of (sys,type,schema,address)

        """
        return (self._system, self._type, self._schema, self._address)

    def get_composite_address(self) -> map:
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


    system  = property(fget = lambda self: self._system,  doc = "Gets EntityId.System: Atom")
    type    = property(fget = lambda self: self._type,    doc = "Gets EntityId.Type: Atom")
    schema  = property(fget = lambda self: self._schema,  doc = "Gets EntityId.Schema: Atom")
    address = property(fget = lambda self: self._address, doc = "Gets EntityId.Address: str")
    is_composite_address = property(
        fget = lambda self: self._address.startswith("{") and self._address.endswith("}"),
        doc = "Returns True when address is assigned as composite JSON object starting with '{' and ending with '}' without any leading or trailing spaces"
    )

    value = property(fget = get_value, doc = "Returns EntityId string value")
    components = property(fget = get_components, doc = "Returns EntityId components tuple of (sys, type, schema, address)")

if __name__ == "__main__":
    a = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "o{\"a\": 1}")
    print(hash(a))
    print(a.is_composite_address)
    print(a.get_composite_address())
    print(a.components)
    
