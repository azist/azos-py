import pytest

from azos.factoryutils import make, make_from_descriptor, make_component_from_descriptor, register
from azos.descriptor import Descriptor
from azos.chassis import AppChassis, AppComponent

# ==============================================================================
# MOCK CONTRACTS AND DERIVATIVES
# ==============================================================================

class IService:
    """Mock service contract."""
    def execute(self) -> str:
        """Execute the service."""
        pass

class ILog:
    """Mock logger contract."""
    def write(self, msg: str) -> str:
        """Write a message."""
        pass


@register("EmailService")
class EmailService(IService):
    def __init__(self, host: str, port: int = 25):
        self.host = host
        self.port = port

    def execute(self) -> str:
        return f"Email on {self.host}:{self.port}"


@register("SmsService")
class SmsService(IService):
    def __init__(self, **kwargs):
        self.provider = kwargs.get("provider", "unknown")

    def execute(self) -> str:
        return f"SMS via {self.provider}"


@register("ConsoleLog")
class ConsoleLog(ILog):
    def __init__(self, descriptor: Descriptor):
        self.prefix = descriptor.as_str("prefix", "Log:")

    def write(self, msg: str) -> str:
        return f"{self.prefix} {msg}"


@register("FileLog")
class FileLog(ILog):
    # This matches the signature enforced by make_component_from_descriptor
    # which passes: chassis, director, descriptor
    def __init__(self, chassis, director, descriptor: Descriptor):
        self.chassis = chassis
        self.director = director
        self.path = descriptor.as_str("path", "/tmp/log.txt")

    def write(self, msg: str) -> str:
        return f"File {self.path}: {msg}"


@register()
class ImplicitNameService(IService):
    def execute(self) -> str:
        return "implicit"

# ==============================================================================
# TESTS FOR register()
# ==============================================================================

def test_register_duplicate():
    with pytest.raises(ValueError, match="is already registered"):
        @register("EmailService")
        class AnotherEmailService(IService):
            pass

# ==============================================================================
# TESTS FOR make()
# ==============================================================================

def test_make_positional_args():
    service = make(IService, "EmailService", "smtp.example.com", 587)
    assert isinstance(service, EmailService)
    assert service.host == "smtp.example.com"
    assert service.port == 587
    assert service.execute() == "Email on smtp.example.com:587"

def test_make_implicit_name():
    service = make(IService, "ImplicitNameService")
    assert isinstance(service, ImplicitNameService)
    assert service.execute() == "implicit"

def test_make_keyword_args():
    service = make(IService, "EmailService", host="smtp.example.com", port=465)
    assert isinstance(service, EmailService)
    assert service.host == "smtp.example.com"
    assert service.port == 465

def test_make_kwargs_dict():
    config = {"provider": "Twilio"}
    service = make(IService, "SmsService", **config)
    assert isinstance(service, SmsService)
    assert service.provider == "Twilio"
    assert service.execute() == "SMS via Twilio"

def test_make_unregistered_type():
    with pytest.raises(TypeError, match="not registered"):
        make(IService, "UnknownService")

def test_make_wrong_base_type():
    with pytest.raises(TypeError, match="is not a subtype of"):
        make(ILog, "EmailService", "localhost")

# ==============================================================================
# TESTS FOR make_from_descriptor()
# ==============================================================================

def test_make_from_descriptor_with_type():
    desc = Descriptor({"type": "ConsoleLog", "prefix": "TEST>"})
    log = make_from_descriptor(ILog, desc, default_type_name="Unknown")
    assert isinstance(log, ConsoleLog)
    assert log.prefix == "TEST>"
    assert log.write("hello") == "TEST> hello"

def test_make_from_descriptor_default_type():
    desc = Descriptor({"prefix": "DEFAULT>"})
    log = make_from_descriptor(ILog, desc, default_type_name="ConsoleLog")
    assert isinstance(log, ConsoleLog)
    assert log.prefix == "DEFAULT>"

def test_make_from_descriptor_missing_type():
    desc = Descriptor({"prefix": "NO_TYPE"})
    with pytest.raises(ValueError, match="must have a 'type' attribute"):
        make_from_descriptor(ILog, desc, default_type_name="")

def test_make_from_descriptor_wrong_type():
    desc = Descriptor({"type": "EmailService", "host": "localhost"})
    # Will fail in make() because EmailService is not a subtype of ILog
    with pytest.raises(TypeError, match="is not a subtype of"):
        make_from_descriptor(ILog, desc, default_type_name="")

# ==============================================================================
# TESTS FOR make_component_from_descriptor()
# ==============================================================================

class MockDirector(AppComponent):
    pass

def test_make_component_from_descriptor_full():
    desc = Descriptor({"type": "FileLog", "path": "/var/log/test.log"})
    chassis = AppChassis.get_default_instance()
    director = MockDirector(chassis)

    log = make_component_from_descriptor(ILog, desc, chassis, director)
    assert isinstance(log, FileLog)
    assert log.chassis is chassis
    assert log.director is director
    assert log.path == "/var/log/test.log"

def test_make_component_from_descriptor_default_type():
    desc = Descriptor({"path": "/var/log/default.log"})
    chassis = AppChassis.get_default_instance()

    log = make_component_from_descriptor(ILog, desc, chassis, default_type_name="FileLog")
    assert isinstance(log, FileLog)
    assert log.chassis is chassis
    assert log.director is None
    assert log.path == "/var/log/default.log"

def test_make_component_from_descriptor_missing_type():
    desc = Descriptor({"path": "/fail"})
    chassis = AppChassis.get_default_instance()

    with pytest.raises(ValueError, match="must have a 'type' attribute"):
        make_component_from_descriptor(ILog, desc, chassis)
