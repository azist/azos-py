"""
Tests for AppChassis lifecycle and static properties

Copyright (C) 2026 Azist, MIT License
"""

from typing import override

from azos.oop import free
from azos.chassis import AppChassis, AppComponent


def test_10():

    assert AppChassis.get_default_instance() is not None
    assert AppChassis.get_default_instance().is_default

    assert AppChassis.get_current_instance() is not None
    assert AppChassis.get_current_instance().is_default

    assert AppChassis.get_current_instance() is AppChassis.get_default_instance()

def test_20():

    assert AppChassis.get_default_instance() is not None
    assert AppChassis.get_default_instance().is_default

    app = AppChassis("test_app_01", __file__, "test")
    assert AppChassis.get_current_instance() is app
    assert not AppChassis.get_current_instance().is_default
    assert AppChassis.get_default_instance() is not app

    app.dispose()
    assert AppChassis.get_current_instance() is AppChassis.get_default_instance()
    assert AppChassis.get_current_instance().is_default


class MockComponentA(AppComponent):
    pass

class MockComponentB(AppComponent):
    pass

class MockDirectorA(AppComponent):
    def __init__(self, chassis: AppChassis):
        super().__init__(chassis)
        self.component_a = MockComponentA(chassis, director=self)
        self.component_b = MockComponentB(chassis, director=self)

    @override
    def _dispose(self) -> None:
        free(self.component_b)
        free(self.component_a)
        super()._dispose() # Always call your own base dispose!!!


def test_30():
    assert AppChassis.get_default_instance() is not None
    assert AppChassis.get_default_instance().is_default

    app = AppChassis("test_app_01", __file__, "test")
    assert AppChassis.get_current_instance() is app
    assert not AppChassis.get_current_instance().is_default
    assert AppChassis.get_default_instance() is not app

    dir = MockDirectorA(app)
    assert len(app.components) == 3
    free(dir) # Director kills its children, so we don't need to free them separately
    assert len(app.components) == 0

    app.dispose()
    assert AppChassis.get_current_instance() is AppChassis.get_default_instance()
    assert AppChassis.get_current_instance().is_default

def test_31():
    assert AppChassis.get_default_instance() is not None
    assert AppChassis.get_default_instance().is_default

    app = AppChassis("test_app_01", __file__, "test")
    assert AppChassis.get_current_instance() is app
    assert not AppChassis.get_current_instance().is_default
    assert AppChassis.get_default_instance() is not app

    dir = MockDirectorA(app)
    assert len(app.components) == 3

    assert not app.is_disposed
    app.dispose() # we forgot to kill director, but we are killing the app, and it will kill them anyway!!!
    assert app.is_disposed
    assert len(app.components) == 0 # Got killed via app kill

    assert AppChassis.get_current_instance() is not app
    assert AppChassis.get_default_instance().is_default
