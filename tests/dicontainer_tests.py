import pytest

from azos.chassis import DIContainer


class IService:
    pass


class ServiceA(IService):
    pass


class ServiceB(IService):
    pass


class NotService:
    pass


class FalseyService(IService):
    def __bool__(self):
        return False


def test_register_default_name_and_try_get_get_success():
    container = DIContainer()
    instance = ServiceA()

    added = container.register(IService, instance)

    assert added is True
    assert container.try_get(IService) is instance
    assert container.get(IService) is instance


def test_register_named_and_resolve_by_name():
    container = DIContainer()
    one = ServiceA()
    two = ServiceB()

    container.register(IService, one, "one")
    container.register(IService, two, "two")

    assert container.try_get(IService, "one") is one
    assert container.try_get(IService, "two") is two
    assert container.try_get(IService) is None


def test_register_replacement_returns_false_and_overwrites():
    container = DIContainer()
    first = ServiceA()
    second = ServiceB()

    assert container.register(IService, first, "main") is True
    assert container.register(IService, second, "main") is False
    assert container.get(IService, "main") is second


def test_register_missing_type_raises_type_error():
    container = DIContainer()

    with pytest.raises(TypeError) as exc_info:
        container.register(None, ServiceA())  # pyright: ignore[reportArgumentType]

    assert "Missing dependency type" in str(exc_info.value)


def test_register_missing_instance_raises_value_error():
    container = DIContainer()

    with pytest.raises(ValueError) as exc_info:
        container.register(IService, None)

    assert "Missing dependency instance" in str(exc_info.value)


def test_register_mismatch_type_raises_type_error():
    container = DIContainer()

    with pytest.raises(TypeError) as exc_info:
        container.register(IService, NotService())

    assert "Mismatch in dep registration" in str(exc_info.value)


def test_register_falsey_instance_current_behavior_raises_value_error():
    container = DIContainer()

    with pytest.raises(ValueError) as exc_info:
        container.register(IService, FalseyService())

    assert "Missing dependency instance" in str(exc_info.value)


def test_try_get_none_type_returns_none():
    container = DIContainer()

    assert container.try_get(None) is None  # pyright: ignore[reportArgumentType]


def test_try_get_missing_type_returns_none():
    container = DIContainer()

    assert container.try_get(IService) is None


def test_try_get_missing_name_returns_none():
    container = DIContainer()
    container.register(IService, ServiceA(), "a")

    assert container.try_get(IService, "b") is None


def test_get_missing_dependency_raises_value_error():
    container = DIContainer()

    with pytest.raises(ValueError) as exc_info:
        container.get(IService)

    assert "Could not resolve requirement" in str(exc_info.value)


def test_get_missing_named_dependency_raises_value_error():
    container = DIContainer()
    container.register(IService, ServiceA(), "a")

    with pytest.raises(ValueError) as exc_info:
        container.get(IService, "b")

    assert "Could not resolve requirement" in str(exc_info.value)


def test_purge_all_clears_everything():
    container = DIContainer()
    container.register(IService, ServiceA())
    container.register(IService, ServiceB(), "named")

    container.purge()

    assert container.try_get(IService) is None
    assert container.try_get(IService, "named") is None


def test_purge_type_only_clears_that_bucket():
    class IOther:
        pass

    class Other(IOther):
        pass

    container = DIContainer()
    service = ServiceA()
    other = Other()

    container.register(IService, service)
    container.register(IOther, other)

    container.purge(IService)

    assert container.try_get(IService) is None
    assert container.try_get(IOther) is other


def test_purge_unknown_type_is_noop():
    class IUnknown:
        pass

    container = DIContainer()
    svc = ServiceA()

    container.register(IService, svc)
    container.purge(IUnknown)

    assert container.get(IService) is svc
