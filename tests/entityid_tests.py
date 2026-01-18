import pytest
import json
from azos.entityid import EntityId, tryparse, parse
from azos.atom import Atom
from azos.exceptions import AzosError


# Tests for tryparse function
def test_tryparse_01():
    """Test tryparse with full format: type.schema@system::address"""
    result = tryparse("car.vin@dealer::1A8987339HBz0909W874")
    assert result is not None
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type == Atom("car")
    assert schema == Atom("vin")
    assert address == "1A8987339HBz0909W874"


def test_tryparse_02():
    """Test tryparse with type only (no schema): type@system::address"""
    result = tryparse("car@dealer::ABC123")
    assert result is not None
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type == Atom("car")
    assert schema.is_zero
    assert address == "ABC123"


def test_tryparse_03():
    """Test tryparse with system only (no type/schema): system::address"""
    result = tryparse("dealer::I9973OD")
    assert result is not None
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type.is_zero
    assert schema.is_zero
    assert address == "I9973OD"


def test_tryparse_04():
    """Test tryparse with composite JSON address"""
    result = tryparse('sys@system::{"id": 123, "name": "test"}')
    assert result is not None
    sys, type, schema, address = result
    assert sys == Atom("system")
    assert type == Atom("sys")
    assert schema.is_zero
    assert address == '{"id": 123, "name": "test"}'


def test_tryparse_05():
    """Test tryparse with boat.license example from docstring"""
    result = tryparse("boat.license@dealer::I9973OD")
    assert result is not None
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type == Atom("boat")
    assert schema == Atom("license")
    assert address == "I9973OD"


def test_tryparse_06():
    """Test tryparse with complex address containing special characters"""
    result = tryparse("type.schema@sys::addr-with_special.chars123")
    assert result is not None
    sys, type, schema, address = result
    assert address == "addr-with_special.chars123"


def test_tryparse_invalid_01():
    """Test tryparse returns None for string without :: separator"""
    result = tryparse("invalid_string")
    assert result is None


def test_tryparse_invalid_02():
    """Test tryparse returns None for None input"""
    result = tryparse(None)
    assert result is None


def test_tryparse_invalid_03():
    """Test tryparse returns None for very short string (less than 4 chars)"""
    result = tryparse("a:b")
    assert result is None


def test_tryparse_invalid_04():
    """Test tryparse returns None for empty address"""
    result = tryparse("system::")
    assert result is None


def test_tryparse_invalid_05():
    """Test tryparse returns None for empty system"""
    result = tryparse("::address")
    assert result is None


def test_tryparse_invalid_06():
    """Test tryparse returns None for empty type when @ present"""
    result = tryparse("@system::address")
    assert result is None


def test_tryparse_invalid_07():
    """Test tryparse returns None for empty system when @ present"""
    result = tryparse("type@::address")
    assert result is None


def test_tryparse_invalid_08():
    """Test tryparse returns None for empty type part in type.schema"""
    result = tryparse(".schema@system::address")
    assert result is None


def test_tryparse_invalid_09():
    """Test tryparse returns None for empty schema part in type.schema"""
    result = tryparse("type.@system::address")
    assert result is None


def test_tryparse_invalid_10():
    """Test tryparse returns None for string with only @"""
    result = tryparse("@")
    assert result is None


def test_tryparse_invalid_11():
    """Test tryparse returns None for string with only ::"""
    result = tryparse("::")
    assert result is None


def test_tryparse_invalid_12():
    """Test tryparse returns None for empty string"""
    result = tryparse("")
    assert result is None


def test_tryparse_invalid_13():
    """Test tryparse returns None for invalid atom characters in type"""
    result = tryparse("^^@system::address")
    assert result is None


def test_tryparse_invalid_14():
    """Test tryparse returns None for invalid atom characters in system"""
    result = tryparse("type@!!invalid::address")
    assert result is None


def test_tryparse_invalid_15():
    """Test tryparse returns None for invalid atom characters in schema"""
    result = tryparse("type.$$bad@system::address")
    assert result is None


def test_tryparse_invalid_16():
    """Test tryparse returns None for invalid atom with special characters"""
    result = tryparse("type@sys##tem::address")
    assert result is None


def test_tryparse_invalid_17():
    """Test tryparse returns None for atom with spaces"""
    result = tryparse("type name@system::address")
    assert result is None


def test_tryparse_invalid_18():
    """Test tryparse returns None for system atom with spaces"""
    result = tryparse("type@sys tem::address")
    assert result is None


def test_tryparse_invalid_19():
    """Test tryparse returns None for atom longer than 8 characters"""
    result = tryparse("verylongtype@system::address")
    assert result is None


def test_tryparse_invalid_20():
    """Test tryparse returns None for system atom longer than 8 characters"""
    result = tryparse("type@verylongsystem::address")
    assert result is None


def test_tryparse_invalid_21():
    """Test tryparse returns None for schema atom longer than 8 characters"""
    result = tryparse("type.verylongschema@system::address")
    assert result is None


def test_tryparse_invalid_22():
    """Test tryparse returns None for multiple invalid atoms"""
    result = tryparse("!!invalid.$$bad@##wrong::address")
    assert result is None


def test_tryparse_invalid_23():
    """Test tryparse returns None for system with invalid characters"""
    result = tryparse("car.vin@deal$er::ABC123")
    assert result is None


def test_tryparse_invalid_24():
    """Test tryparse returns None for type with punctuation"""
    result = tryparse("car!@dealer::ABC123")
    assert result is None


def test_tryparse_invalid_25():
    """Test tryparse returns None for schema with parentheses"""
    result = tryparse("car.(vin)@dealer::ABC123")
    assert result is None


# Tests for parse function
def test_parse_01():
    """Test parse with full format: type.schema@system::address"""
    result = parse("car.vin@dealer::1A8987339HBz0909W874")
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type == Atom("car")
    assert schema == Atom("vin")
    assert address == "1A8987339HBz0909W874"


def test_parse_02():
    """Test parse with type only (no schema): type@system::address"""
    result = parse("car@dealer::ABC123")
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type == Atom("car")
    assert schema.is_zero
    assert address == "ABC123"


def test_parse_03():
    """Test parse with system only (no type/schema): system::address"""
    result = parse("dealer::I9973OD")
    sys, type, schema, address = result
    assert sys == Atom("dealer")
    assert type.is_zero
    assert schema.is_zero
    assert address == "I9973OD"


def test_parse_04():
    """Test parse with composite JSON address"""
    result = parse('vehicle@registry::{"vin":"ABC123","year":2020}')
    sys, type, schema, address = result
    assert sys == Atom("registry")
    assert type == Atom("vehicle")
    assert address == '{"vin":"ABC123","year":2020}'


def test_parse_invalid_01():
    """Test parse raises AzosError for invalid string without ::"""
    with pytest.raises(AzosError) as exc_info:
        parse("invalid_string")
    assert "not parsable" in str(exc_info.value)
    assert exc_info.value.topic == "entityid"


def test_parse_invalid_02():
    """Test parse raises AzosError for None input"""
    with pytest.raises(AzosError) as exc_info:
        parse(None)
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_03():
    """Test parse raises AzosError for empty address"""
    with pytest.raises(AzosError) as exc_info:
        parse("system::")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_04():
    """Test parse raises AzosError for empty system"""
    with pytest.raises(AzosError) as exc_info:
        parse("::address")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_05():
    """Test parse raises AzosError for malformed type.schema"""
    with pytest.raises(AzosError) as exc_info:
        parse(".schema@system::address")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_06():
    """Test parse raises AzosError for empty string"""
    with pytest.raises(AzosError) as exc_info:
        parse("")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_07():
    """Test parse raises AzosError for invalid atom characters in type"""
    with pytest.raises(AzosError) as exc_info:
        parse("^^@system::address")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_08():
    """Test parse raises AzosError for invalid atom characters in system"""
    with pytest.raises(AzosError) as exc_info:
        parse("type@!!invalid::address")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_09():
    """Test parse raises AzosError for atom longer than 8 characters"""
    with pytest.raises(AzosError) as exc_info:
        parse("verylongtype@system::address")
    assert "not parsable" in str(exc_info.value)


def test_parse_invalid_10():
    """Test parse raises AzosError for system atom with spaces"""
    with pytest.raises(AzosError) as exc_info:
        parse("type@sys tem::address")
    assert "not parsable" in str(exc_info.value)


# Tests for EntityId constructor and basic properties
def test_constructor_01():
    """Test basic EntityId construction with all components"""
    eid = EntityId(Atom("dealer"), Atom("car"), Atom("vin"), "1A8987339HBz0909W874")
    assert eid.system.id == Atom("dealer").id
    assert eid.type.id == Atom("car").id
    assert eid.schema.id == Atom("vin").id
    assert eid.address == "1A8987339HBz0909W874"


def test_constructor_02():
    """Test EntityId with zero type"""
    eid = EntityId(Atom("dealer"), Atom(0), Atom(0), "I9973OD")
    assert eid.system.id == Atom("dealer").id
    assert eid.type.is_zero
    assert eid.schema.is_zero
    assert eid.address == "I9973OD"


# Tests for value property - formatted string representation
def test_value_01():
    """Test value property with full components: type.schema@system::address"""
    eid = EntityId(Atom("dealer"), Atom("car"), Atom("vin"), "1A8987339HBz0909W874")
    assert eid.value == "car.vin@dealer::1A8987339HBz0909W874"


def test_value_02():
    """Test value property with another full example: boat.license@dealer::I9973OD"""
    eid = EntityId(Atom("dealer"), Atom("boat"), Atom("license"), "I9973OD")
    assert eid.value == "boat.license@dealer::I9973OD"


def test_value_03():
    """Test value property with zero type - system::address format"""
    eid = EntityId(Atom("dealer"), Atom(0), Atom(0), "I9973OD")
    assert eid.value == "dealer::I9973OD"


def test_value_04():
    """Test value property with zero schema - type@system::address format"""
    eid = EntityId(Atom("dealer"), Atom("car"), Atom(0), "ABC123")
    assert eid.value == "car@dealer::ABC123"


# Tests for __str__ and __repr__
def test_str_01():
    """Test __str__ returns the value property"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    assert str(eid) == "tp.sch@sys::addr123"


def test_repr_01():
    """Test __repr__ returns formatted representation"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    assert repr(eid) == "EntityId(`tp.sch@sys::addr123`)"


# Tests for equality and hashing
def test_eq_01():
    """Test equality of two EntityIds with same components"""
    eid1 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    eid2 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    assert eid1 == eid2


def test_eq_02():
    """Test inequality of EntityIds with different addresses"""
    eid1 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    eid2 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr456")
    assert eid1 != eid2


def test_eq_03():
    """Test inequality of EntityIds with different systems"""
    eid1 = EntityId(Atom("sys1"), Atom("tp"), Atom("sch"), "addr123")
    eid2 = EntityId(Atom("sys2"), Atom("tp"), Atom("sch"), "addr123")
    assert eid1 != eid2


def test_eq_04():
    """Test inequality of EntityIds with different types"""
    eid1 = EntityId(Atom("sys"), Atom("tp1"), Atom("sch"), "addr123")
    eid2 = EntityId(Atom("sys"), Atom("tp2"), Atom("sch"), "addr123")
    assert eid1 != eid2


def test_eq_05():
    """Test inequality of EntityIds with different schemas"""
    eid1 = EntityId(Atom("sys"), Atom("tp"), Atom("sch1"), "addr123")
    eid2 = EntityId(Atom("sys"), Atom("tp"), Atom("sch2"), "addr123")
    assert eid1 != eid2


def test_hash_01():
    """Test hash equality for equal EntityIds"""
    eid1 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    eid2 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    assert hash(eid1) == hash(eid2)


def test_hash_02():
    """Test hash inequality for different EntityIds"""
    eid1 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    eid2 = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr456")
    assert hash(eid1) != hash(eid2)


def test_hash_03():
    """Test EntityId can be used as dict key"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    d = {eid: "test_value"}
    assert d[eid] == "test_value"


# Tests for components property
def test_components_01():
    """Test components property returns tuple of all components"""
    sys_atom = Atom("sys")
    type_atom = Atom("tp")
    schema_atom = Atom("sch")
    address = "addr123"
    eid = EntityId(sys_atom, type_atom, schema_atom, address)

    components = eid.components
    assert isinstance(components, tuple)
    assert len(components) == 4
    assert components[0] == sys_atom
    assert components[1] == type_atom
    assert components[2] == schema_atom
    assert components[3] == address


# Tests for from_components class method
def test_from_components_01():
    """Test creating EntityId from components tuple"""
    components = (Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    eid = EntityId.from_components(components)
    assert eid.system.id == Atom("sys").id
    assert eid.type.id == Atom("tp").id
    assert eid.schema.id == Atom("sch").id
    assert eid.address == "addr123"


def test_from_components_02():
    """Test from_components creates equivalent EntityId to direct constructor"""
    components = (Atom("dealer"), Atom("car"), Atom("vin"), "ABC123")
    eid1 = EntityId.from_components(components)
    eid2 = EntityId(Atom("dealer"), Atom("car"), Atom("vin"), "ABC123")
    assert eid1 == eid2


# Tests for from_value class method
def test_from_value_01():
    """Test from_value with full format: type.schema@system::address"""
    eid = EntityId.from_value("car.vin@dealer::1A8987339HBz0909W874")
    assert eid.system == Atom("dealer")
    assert eid.type == Atom("car")
    assert eid.schema == Atom("vin")
    assert eid.address == "1A8987339HBz0909W874"
    assert eid.value == "car.vin@dealer::1A8987339HBz0909W874"


def test_from_value_02():
    """Test from_value with type only (no schema): type@system::address"""
    eid = EntityId.from_value("boat@marina::BOAT123")
    assert eid.system == Atom("marina")
    assert eid.type == Atom("boat")
    assert eid.schema.is_zero
    assert eid.address == "BOAT123"


def test_from_value_03():
    """Test from_value with system only: system::address"""
    eid = EntityId.from_value("dealer::DEFAULT001")
    assert eid.system == Atom("dealer")
    assert eid.type.is_zero
    assert eid.schema.is_zero
    assert eid.address == "DEFAULT001"


def test_from_value_04():
    """Test from_value with composite JSON address"""
    eid = EntityId.from_value('vehicle@dmv::{"vin":"ABC","plate":"XYZ"}')
    assert eid.system == Atom("dmv")
    assert eid.type == Atom("vehicle")
    assert eid.is_composite_address
    comp = eid.get_composite_address()
    assert comp["vin"] == "ABC"
    assert comp["plate"] == "XYZ"


def test_from_value_05():
    """Test from_value round-trip: create from value, get value, parse again"""
    original_str = "boat.license@dealer::I9973OD"
    eid1 = EntityId.from_value(original_str)
    value_str = eid1.value
    eid2 = EntityId.from_value(value_str)
    assert eid1 == eid2
    assert eid1.value == eid2.value


def test_from_value_invalid_01():
    """Test from_value raises AzosError for invalid string"""
    with pytest.raises(AzosError) as exc_info:
        EntityId.from_value("invalid_string")
    assert "not parsable" in str(exc_info.value)


def test_from_value_invalid_02():
    """Test from_value raises AzosError for None"""
    with pytest.raises(AzosError) as exc_info:
        EntityId.from_value(None)
    assert "not parsable" in str(exc_info.value)


def test_from_value_invalid_03():
    """Test from_value raises AzosError for malformed string"""
    with pytest.raises(AzosError) as exc_info:
        EntityId.from_value("type@::address")
    assert "not parsable" in str(exc_info.value)


# Tests for is_composite_address property
def test_is_composite_address_01():
    """Test is_composite_address returns True for JSON object address"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), '{"id": 123, "name": "test"}')
    assert eid.is_composite_address


def test_is_composite_address_02():
    """Test is_composite_address returns False for simple string address"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "simple_address")
    assert not eid.is_composite_address


def test_is_composite_address_03():
    """Test is_composite_address returns False for partial JSON-like strings"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "{incomplete")
    assert not eid.is_composite_address


def test_is_composite_address_04():
    """Test is_composite_address requires no leading/trailing spaces"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), ' {"id": 1} ')
    assert not eid.is_composite_address


def test_is_composite_address_05():
    """Test is_composite_address with empty JSON object"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), '{}')
    assert eid.is_composite_address


# Tests for get_composite_address method
def test_get_composite_address_01():
    """Test get_composite_address returns parsed JSON for composite address"""
    json_str = '{"id": 123, "name": "test"}'
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), json_str)
    result = eid.get_composite_address()
    assert result is not None
    assert result["id"] == 123
    assert result["name"] == "test"


def test_get_composite_address_02():
    """Test get_composite_address returns None for non-composite address"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "simple_address")
    result = eid.get_composite_address()
    assert result is None


def test_get_composite_address_03():
    """Test get_composite_address with nested JSON object"""
    json_str = '{"user": {"id": 1, "email": "test@example.com"}, "active": true}'
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), json_str)
    result = eid.get_composite_address()
    assert result["user"]["id"] == 1
    assert result["user"]["email"] == "test@example.com"
    assert result["active"] == True


def test_get_composite_address_04():
    """Test get_composite_address with array in JSON"""
    json_str = '{"items": [1, 2, 3], "count": 3}'
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), json_str)
    result = eid.get_composite_address()
    assert result["items"] == [1, 2, 3]
    assert result["count"] == 3


def test_get_composite_address_05():
    """Test get_composite_address raises AzosError for invalid JSON"""
    invalid_json = '{"invalid": json content}'
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), invalid_json)
    with pytest.raises(AzosError) as exc_info:
        eid.get_composite_address()
    assert exc_info.value.frm == "get_composite_address()"


def test_get_composite_address_06():
    """Test get_composite_address with empty JSON object"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), '{}')
    result = eid.get_composite_address()
    assert result == {}


# Tests for deprecated get_value and get_components methods
def test_get_value_deprecated_01():
    """Test deprecated get_value method still works"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    assert eid.get_value() == "tp.sch@sys::addr123"
    assert eid.get_value() == eid.value


def test_get_components_deprecated_01():
    """Test deprecated get_components method still works"""
    eid = EntityId(Atom("sys"), Atom("tp"), Atom("sch"), "addr123")
    assert eid.get_components() == eid.components


# Tests for property access
def test_properties_01():
    """Test all property accessors"""
    sys_atom = Atom("dealer")
    type_atom = Atom("car")
    schema_atom = Atom("vin")
    address = "1A8987339HBz0909W874"

    eid = EntityId(sys_atom, type_atom, schema_atom, address)

    assert eid.system == sys_atom
    assert eid.type == type_atom
    assert eid.schema == schema_atom
    assert eid.address == address


# Integration tests with real-world scenarios
def test_integration_01():
    """Test dealer car VIN scenario from docstring"""
    eid = EntityId(Atom("dealer"), Atom("car"), Atom("vin"), "1A8987339HBz0909W874")
    assert eid.value == "car.vin@dealer::1A8987339HBz0909W874"
    assert str(eid) == "car.vin@dealer::1A8987339HBz0909W874"


def test_integration_02():
    """Test dealer boat license scenario from docstring"""
    eid = EntityId(Atom("dealer"), Atom("boat"), Atom("license"), "I9973OD")
    assert eid.value == "boat.license@dealer::I9973OD"


def test_integration_03():
    """Test default type scenario from docstring"""
    eid = EntityId(Atom("dealer"), Atom(0), Atom(0), "I9973OD")
    assert eid.value == "dealer::I9973OD"


def test_integration_04():
    """Test EntityId with composite address containing multiple fields"""
    composite = '{"vin": "1A8987339HBz0909W874", "plate": "ABC123", "state": "CA"}'
    eid = EntityId(Atom("dmv"), Atom("vehicle"), Atom("full"), composite)

    assert eid.is_composite_address
    addr = eid.get_composite_address()
    assert addr["vin"] == "1A8987339HBz0909W874"
    assert addr["plate"] == "ABC123"
    assert addr["state"] == "CA"


def test_integration_05():
    """Test creating EntityId from components and verifying round-trip"""
    original = EntityId(Atom("sys"), Atom("type"), Atom("schema"), "address")
    components = original.components
    recreated = EntityId.from_components(components)

    assert original == recreated
    assert original.value == recreated.value
    assert hash(original) == hash(recreated)


# Integration tests using parse/from_value instead of constructor
def test_integration_parse_01():
    """Test dealer car VIN scenario from docstring using parse"""
    eid = EntityId.from_value("car.vin@dealer::1A8987339HBz0909W874")
    assert eid.value == "car.vin@dealer::1A8987339HBz0909W874"
    assert str(eid) == "car.vin@dealer::1A8987339HBz0909W874"


def test_integration_parse_02():
    """Test dealer boat license scenario from docstring using parse"""
    eid = EntityId.from_value("boat.license@dealer::I9973OD")
    assert eid.value == "boat.license@dealer::I9973OD"


def test_integration_parse_03():
    """Test default type scenario from docstring using parse"""
    eid = EntityId.from_value("dealer::I9973OD")
    assert eid.value == "dealer::I9973OD"


def test_integration_parse_04():
    """Test EntityId with composite address containing multiple fields using parse"""
    composite = '{"vin": "1A8987339HBz0909W874", "plate": "ABC123", "state": "CA"}'
    eid = EntityId.from_value(f'vehicle.full@dmv::{composite}')

    assert eid.is_composite_address
    addr = eid.get_composite_address()
    assert addr["vin"] == "1A8987339HBz0909W874"
    assert addr["plate"] == "ABC123"
    assert addr["state"] == "CA"


def test_integration_parse_05():
    """Test creating EntityId from string and verifying round-trip using parse"""
    original_str = "type.schema@sys::address"
    eid = EntityId.from_value(original_str)

    # Verify round-trip
    assert eid.value == original_str

    # Create another from the value property
    recreated = EntityId.from_value(eid.value)

    assert eid == recreated
    assert eid.value == recreated.value
    assert hash(eid) == hash(recreated)
