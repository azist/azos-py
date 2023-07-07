"""Provides interop functions for working with Azos EntityId data type

Copyright (C) 20023 Azist, MIT License


"""

from azexceptions import AzosError
from azatom import Atom

TP_PREFIX = "@"
SCHEMA_DIV = "."
SYS_PREFIX = "::"

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
        return hash(self._id)
    
    def get_value(self) -> str:
        if self._type.is_zero:
            return f"{self._system}{SYS_PREFIX}{self._address}"
        if self._schema.is_zero:
            return f"{self._type}{TP_PREFIX}{self._system}{SYS_PREFIX}{self._address}"
        
        return f"{self._type}{SCHEMA_DIV}{self._schema}{TP_PREFIX}{self._system}{SYS_PREFIX}{self._address}"

    system  = property(fget = lambda self: self._system,  doc = "Gets EntityId.System: Atom")
    type    = property(fget = lambda self: self._type,    doc = "Gets EntityId.Type: Atom")
    schema  = property(fget = lambda self: self._schema,  doc = "Gets EntityId.Schema: Atom")
    address = property(fget = lambda self: self._address, doc = "Gets EntityId.Address: str")

    value = property(fget = get_value, doc = "Returns EntityId string value")


if __name__ == "__main__":
    a = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "my-address-123")
    print(a)
    
