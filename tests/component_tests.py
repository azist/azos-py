"""
Tests for AppComponent lifecycle - ownership by chassis and by director.

Copyright (C) 2026 Azist, MIT License
"""

import pytest
from typing import override

from azos.oop import free
from azos.chassis import AppChassis, AppComponent


# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

class MockComponentA(AppComponent):
    """Simple leaf component with no children."""
    pass


class MockComponentB(AppComponent):
    """Simple leaf component with no children."""
    pass


class MockDirectorA(AppComponent):
    """
    Director that allocates and owns a MockComponentA and a MockComponentB.
    Disposing the director disposes its owned children.
    """

    def __init__(self, chassis: AppChassis, director: "AppComponent | None" = None) -> None:
        super().__init__(chassis, director)
        self.component_a = MockComponentA(chassis, director=self)
        self.component_b = MockComponentB(chassis, director=self)

    @override
    def _dispose(self) -> None:
        free(self.component_b)
        free(self.component_a)
        super()._dispose()  # Always call base _dispose to deregister from chassis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> AppChassis:
    return AppChassis("testcomp", __file__, "test")


# ---------------------------------------------------------------------------
# Tests - direct chassis ownership
# ---------------------------------------------------------------------------

def test_component_registers_with_chassis_on_creation():
    """Each component created with chassis ref appears in chassis.components."""
    app = _make_app()
    try:
        a = MockComponentA(app)
        assert a in app.components
        assert len(app.components) == 1

        b = MockComponentB(app)
        assert b in app.components
        assert len(app.components) == 2
    finally:
        app.dispose()


def test_component_deregisters_from_chassis_on_dispose():
    """Disposing a component removes it from chassis.components."""
    app = _make_app()
    try:
        a = MockComponentA(app)
        b = MockComponentB(app)
        assert len(app.components) == 2

        free(a)
        assert a.is_disposed
        assert a not in app.components
        assert b in app.components
        assert len(app.components) == 1

        free(b)
        assert len(app.components) == 0
    finally:
        app.dispose()


def test_component_chassis_property_returns_owning_chassis():
    """component.chassis returns the exact chassis instance passed at construction."""
    app = _make_app()
    try:
        a = MockComponentA(app)
        assert a.chassis is app
    finally:
        app.dispose()


def test_component_director_is_none_when_owned_directly_by_chassis():
    """Component created without a director has director == None."""
    app = _make_app()
    try:
        a = MockComponentA(app)
        assert a.director is None
    finally:
        app.dispose()


def test_component_sid_is_unique_and_positive():
    """Each component gets a unique positive sequential sid."""
    app = _make_app()
    try:
        a = MockComponentA(app)
        b = MockComponentB(app)
        assert a.sid > 0
        assert b.sid > 0
        assert a.sid != b.sid
    finally:
        app.dispose()


# ---------------------------------------------------------------------------
# Tests - director ownership
# ---------------------------------------------------------------------------

def test_director_allocates_child_components_all_visible_in_chassis():
    """MockDirectorA creates two children; all three components appear in chassis.components."""
    app = _make_app()
    try:
        d = MockDirectorA(app)
        assert d in app.components
        assert d.component_a in app.components
        assert d.component_b in app.components
        assert len(app.components) == 3
    finally:
        app.dispose()


def test_child_components_reference_their_director():
    """Children created by a director have director property pointing to that director."""
    app = _make_app()
    try:
        d = MockDirectorA(app)
        assert d.component_a.director is d
        assert d.component_b.director is d
        assert d.director is None  # top-level director has no parent
    finally:
        app.dispose()


def test_disposing_director_disposes_children_and_clears_chassis():
    """Disposing a director disposes all its children; chassis.components becomes empty."""
    app = _make_app()
    try:
        d = MockDirectorA(app)
        assert len(app.components) == 3

        free(d)

        assert d.is_disposed
        assert d.component_a.is_disposed
        assert d.component_b.is_disposed
        assert len(app.components) == 0
    finally:
        app.dispose()


def test_two_independent_directors_have_isolated_lifecycles():
    """Disposing one director does not affect the other director or its children."""
    app = _make_app()
    try:
        d1 = MockDirectorA(app)
        d2 = MockDirectorA(app)
        assert len(app.components) == 6  # 3 per director

        free(d1)
        assert d1.is_disposed
        assert len(app.components) == 3  # d2 and its two children remain

        assert d2 in app.components
        assert d2.component_a in app.components
        assert d2.component_b in app.components
    finally:
        app.dispose()


def test_nested_director_hierarchy():
    """A director can itself be directed by another director (nested hierarchy)."""
    app = _make_app()
    try:
        outer = MockDirectorA(app)             # outer + 2 children = 3
        inner = MockDirectorA(app, director=outer)  # inner + 2 children = 3
        assert len(app.components) == 6
        assert inner.director is outer

        free(inner)  # removes only inner and its 2 children
        assert inner.is_disposed
        assert len(app.components) == 3
        assert outer in app.components
        assert outer.component_a in app.components
        assert outer.component_b in app.components
    finally:
        app.dispose()


# ---------------------------------------------------------------------------
# Tests - chassis dispose interaction
# ---------------------------------------------------------------------------

def test_chassis_dispose_removes_all_dangling_components():
    """Chassis dispose cleans up components that were never explicitly freed."""
    app = _make_app()
    d = MockDirectorA(app)
    assert len(app.components) == 3

    # Dispose chassis without freeing director first
    app.dispose()

    assert app.is_disposed
    assert len(app.components) == 0


def test_chassis_dispose_restores_singleton_to_default():
    """After disposing a non-default chassis get_current_instance falls back to the default."""
    default = AppChassis.get_default_instance()
    app = _make_app()
    assert AppChassis.get_current_instance() is app

    app.dispose()

    assert AppChassis.get_current_instance() is default


# ---------------------------------------------------------------------------
# Tests - error / guard cases
# ---------------------------------------------------------------------------

def test_component_requires_non_null_chassis():
    """Passing None as chassis raises an appropriate error."""
    with pytest.raises((ValueError, TypeError)):
        MockComponentA(None)  # type: ignore


def test_director_chassis_mismatch_raises_value_error():
    """Director that belongs to a different chassis raises ValueError."""
    default_app = AppChassis.get_default_instance()
    orphan = MockComponentA(default_app)  # lives on the default chassis
    try:
        app = _make_app()
        try:
            with pytest.raises(ValueError):
                MockComponentA(app, director=orphan)  # chassis mismatch
        finally:
            app.dispose()
    finally:
        free(orphan)  # clean up from default chassis


def test_dispose_is_idempotent():
    """Calling dispose twice must not raise and must leave chassis.components consistent."""
    app = _make_app()
    try:
        a = MockComponentA(app)
        assert len(app.components) == 1

        free(a)
        assert len(app.components) == 0

        free(a)  # second call - idempotent, no error
        assert len(app.components) == 0
    finally:
        app.dispose()
