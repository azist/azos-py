"""
Application Chassis Component testing

Tests the component registration and lifecycle management within the AppChassis.
Verifies that components appear in the chassis.components collection and are
properly removed after disposal.

Copyright (C) 2026 Azist, MIT License
"""

import pytest
from typing import override
from azos.chassis import AppChassis, AppComponent


class MockComponent(AppComponent):
    """Mock component for testing AppComponent lifecycle"""

    def __init__(self, chassis: AppChassis, name: str, director: AppComponent | None = None):
        self.name = name
        super().__init__(chassis, director)

    def __repr__(self) -> str:
        return f"MockComponent({self.name})"


class MockDirector(AppComponent):
    """Mock director component that manages other components"""

    def __init__(self, chassis: AppChassis, name: str):
        self.name = name
        self.owned_components: list[AppComponent] = []
        super().__init__(chassis)

    def create_owned_component(self, name: str) -> MockComponent:
        """Create a component owned by this director"""
        component = MockComponent(self.chassis, name, director=self)
        self.owned_components.append(component)
        return component

    def dispose_owned_components(self):
        """Dispose all owned components"""
        for component in self.owned_components:
            component.dispose()
        self.owned_components.clear()

    def __repr__(self) -> str:
        return f"MockDirector({self.name})"

    @override
    def _dispose(self) -> None:
        self.dispose_owned_components()
        super()._dispose()


class TestComponentRegistration:
    """Tests for component registration with AppChassis"""

    def test_component_registration_single(self):
        """Test that a single component registers with chassis"""
        chassis = AppChassis("test_app_01", __file__, "test")
        initial_count = len(chassis.components)

        component = MockComponent(chassis, "test_comp_01")

        assert len(chassis.components) == initial_count + 1
        assert component in chassis.components
        assert component.chassis is chassis
        assert component.director is None

        chassis.dispose()

    def test_component_registration_multiple(self):
        """Test that multiple components register with chassis"""
        chassis = AppChassis("test_app_02", __file__, "test")
        initial_count = len(chassis.components)

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")
        comp3 = MockComponent(chassis, "comp3")

        assert len(chassis.components) == initial_count + 3
        assert comp1 in chassis.components
        assert comp2 in chassis.components
        assert comp3 in chassis.components

        chassis.dispose()

    def test_component_sequential_ids(self):
        """Test that components receive sequential sys ids"""
        chassis = AppChassis("test_app_03", __file__, "test")

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")
        comp3 = MockComponent(chassis, "comp3")

        # SIDs should be sequential (though possibly not starting at 1 if other tests ran)
        assert comp2.sid == comp1.sid + 1
        assert comp3.sid == comp2.sid + 1

        chassis.dispose()

    def test_component_without_chassis_raises_error(self):
        """Test that creating component without chassis raises ValueError"""
        with pytest.raises(ValueError, match="requires a non-null AppChassis reference"):
            MockComponent(None, "invalid")

    def test_component_with_invalid_director_raises_error(self):
        """Test that creating component with non-AppComponent director raises TypeError"""
        chassis = AppChassis("test_app_04", __file__, "test")

        with pytest.raises(TypeError, match="director must be of type AppComponent or None"):
            MockComponent(chassis, "comp", director="not_a_component")

        chassis.dispose()

    def test_component_with_director_from_different_chassis_raises_error(self):
        """Test that component director must be from same chassis"""
        chassis1 = AppChassis("test_app_05a", __file__, "test")
        chassis2 = AppChassis("test_app_05b", __file__, "test")

        director = MockComponent(chassis1, "director")

        with pytest.raises(ValueError, match="director component chassis mismatch"):
            MockComponent(chassis2, "comp", director=director)

        chassis1.dispose()
        chassis2.dispose()


class TestComponentDisposal:
    """Tests for component disposal and removal from chassis"""

    def test_component_disposal_single(self):
        """Test that disposing a component removes it from chassis"""
        chassis = AppChassis("test_app_06", __file__, "test")
        initial_count = len(chassis.components)

        component = MockComponent(chassis, "test_comp")
        assert len(chassis.components) == initial_count + 1
        assert component in chassis.components

        component.dispose()

        assert len(chassis.components) == initial_count
        assert component not in chassis.components

        chassis.dispose()

    def test_component_disposal_multiple(self):
        """Test that disposing multiple components works correctly"""
        chassis = AppChassis("test_app_07", __file__, "test")
        initial_count = len(chassis.components)

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")
        comp3 = MockComponent(chassis, "comp3")

        assert len(chassis.components) == initial_count + 3

        comp1.dispose()
        assert len(chassis.components) == initial_count + 2
        assert comp1 not in chassis.components
        assert comp2 in chassis.components
        assert comp3 in chassis.components

        comp3.dispose()
        assert len(chassis.components) == initial_count + 1
        assert comp1 not in chassis.components
        assert comp2 in chassis.components
        assert comp3 not in chassis.components

        comp2.dispose()
        assert len(chassis.components) == initial_count
        assert comp1 not in chassis.components
        assert comp2 not in chassis.components
        assert comp3 not in chassis.components

        chassis.dispose()

    def test_component_disposal_idempotent(self):
        """Test that disposing a component multiple times is safe"""
        chassis = AppChassis("test_app_08", __file__, "test")

        component = MockComponent(chassis, "test_comp")
        assert component in chassis.components

        component.dispose()
        assert component not in chassis.components

        # Disposing again should not raise
        component.dispose()
        assert component not in chassis.components

        chassis.dispose()

    def test_chassis_disposal_removes_all_components(self):
        """Test that disposing chassis removes all its components"""
        chassis = AppChassis("test_app_09", __file__, "test")

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")
        comp3 = MockComponent(chassis, "comp3")

        assert len(chassis.components) == 3

        chassis.dispose()

        # After chassis disposal, components should be removed
        assert comp1 not in chassis.components
        assert comp2 not in chassis.components
        assert comp3 not in chassis.components
        assert len(chassis.components) == 0

    def test_chassis_disposal_with_mixed_disposable_state(self):
        """Test that chassis disposal handles mix of disposed and undisposed components"""
        chassis = AppChassis("test_app_10", __file__, "test")

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")
        comp3 = MockComponent(chassis, "comp3")

        # Manually dispose one component
        comp2.dispose()

        assert len(chassis.components) == 2
        assert comp1 in chassis.components
        assert comp2 not in chassis.components
        assert comp3 in chassis.components

        # Now dispose the chassis
        chassis.dispose()

        assert comp1 not in chassis.components
        assert comp3 not in chassis.components
        assert len(chassis.components) == 0


class TestComponentHierarchy:
    """Tests for component hierarchies with directors"""

    def test_director_relationship(self):
        """Test that component director relationship is maintained"""
        chassis = AppChassis("test_app_11", __file__, "test")

        director = MockComponent(chassis, "director")
        owned1 = MockComponent(chassis, "owned1", director=director)
        owned2 = MockComponent(chassis, "owned2", director=director)

        assert owned1.director is director
        assert owned2.director is director
        assert director.director is None

        chassis.dispose()

    def test_director_component_creation(self):
        """Test that director can create owned components"""
        chassis = AppChassis("test_app_12", __file__, "test")
        initial_count = len(chassis.components)

        director = MockDirector(chassis, "my_director")
        assert len(chassis.components) == initial_count + 1

        comp1 = director.create_owned_component("owned1")
        comp2 = director.create_owned_component("owned2")

        assert len(chassis.components) == initial_count + 3
        assert comp1 in chassis.components
        assert comp2 in chassis.components
        assert comp1 in director.owned_components
        assert comp2 in director.owned_components

        chassis.dispose()

    def test_director_disposal_removes_owned_components(self):
        """Test that disposing director removes its owned components"""
        chassis = AppChassis("test_app_13", __file__, "test")
        initial_count = len(chassis.components)

        director = MockDirector(chassis, "my_director")
        comp1 = director.create_owned_component("owned1")
        comp2 = director.create_owned_component("owned2")

        assert len(chassis.components) == initial_count + 3

        director.dispose()

        # After director disposal, all owned components should be removed
        assert director not in chassis.components
        assert comp1 not in chassis.components
        assert comp2 not in chassis.components
        assert len(chassis.components) == initial_count

        chassis.dispose()

    def test_nested_director_hierarchy(self):
        """Test nested hierarchy of directors owning directors"""
        chassis = AppChassis("test_app_14", __file__, "test")
        initial_count = len(chassis.components)

        director1 = MockDirector(chassis, "director1")
        # Create a sub-director owned by director1
        director2 = MockDirector(chassis, "director2")
        director2._director = director1  # Set director relationship
        # Create a component owned by director2
        comp1 = director2.create_owned_component("owned1")

        assert len(chassis.components) == initial_count + 3
        assert director2.director is director1
        assert comp1.director is director2

        director2.dispose()

        # After director2 disposal, comp1 should also be disposed (owned by director2)
        assert len(chassis.components) == initial_count + 1
        assert director1 in chassis.components
        assert comp1 not in chassis.components
        assert director2 not in chassis.components

        director1.dispose()
        chassis.dispose()


class TestComponentCollectionProperty:
    """Tests for the components collection property"""

    def test_components_returns_sequence(self):
        """Test that components property returns a sequence"""
        chassis = AppChassis("test_app_15", __file__, "test")

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")

        components = chassis.components

        # Should be a sequence (tuple)
        assert isinstance(components, tuple)
        assert len(components) >= 2
        assert comp1 in components
        assert comp2 in components

        chassis.dispose()

    def test_components_is_readonly_copy(self):
        """Test that modifying returned components doesn't affect internal state"""
        chassis = AppChassis("test_app_16", __file__, "test")

        comp1 = MockComponent(chassis, "comp1")
        comp2 = MockComponent(chassis, "comp2")

        components_snapshot = chassis.components
        assert len(components_snapshot) >= 2

        # Create a new component
        comp3 = MockComponent(chassis, "comp3")

        # The snapshot should be unchanged
        assert len(components_snapshot) >= 2
        # But the current property should reflect the new component
        components_new = chassis.components
        assert len(components_new) > len(components_snapshot)
        assert comp3 in components_new

        chassis.dispose()

    def test_components_iteration(self):
        """Test that we can iterate over components collection"""
        chassis = AppChassis("test_app_17", __file__, "test")

        comps = [
            MockComponent(chassis, f"comp{i}")
            for i in range(5)
        ]

        component_names = []
        for component in chassis.components:
            if isinstance(component, MockComponent):
                component_names.append(component.name)

        for comp in comps:
            assert comp.name in component_names

        chassis.dispose()


class TestComponentStateManagement:
    """Tests for component state and lifecycle"""

    def test_component_attributes_preserved(self):
        """Test that component attributes are preserved across operations"""
        chassis = AppChassis("test_app_18", __file__, "test")

        component = MockComponent(chassis, "test_component")
        assert component.name == "test_component"
        assert component.chassis is chassis
        assert component.sid > 0

        # Attributes should persist until disposal
        assert component.name == "test_component"

        component.dispose()

        # Attributes should still exist after disposal (component is just removed from collection)
        assert component.name == "test_component"

        chassis.dispose()

    def test_multiple_chassis_instances(self):
        """Test that multiple chassis instances maintain separate component registries"""
        chassis1 = AppChassis("test_app_19a", __file__, "test")
        chassis2 = AppChassis("test_app_19b", __file__, "test")

        comp1_1 = MockComponent(chassis1, "comp1_1")
        comp1_2 = MockComponent(chassis1, "comp1_2")
        comp2_1 = MockComponent(chassis2, "comp2_1")
        comp2_2 = MockComponent(chassis2, "comp2_2")

        assert comp1_1 in chassis1.components
        assert comp1_2 in chassis1.components
        assert comp1_1 not in chassis2.components
        assert comp1_2 not in chassis2.components

        assert comp2_1 in chassis2.components
        assert comp2_2 in chassis2.components
        assert comp2_1 not in chassis1.components
        assert comp2_2 not in chassis1.components

        chassis1.dispose()
        chassis2.dispose()

    def test_component_count_accuracy(self):
        """Test that component count remains accurate through various operations"""
        chassis = AppChassis("test_app_20", __file__, "test")
        initial_count = len(chassis.components)

        # Add components incrementally
        comps = []
        for i in range(10):
            comp = MockComponent(chassis, f"comp{i}")
            comps.append(comp)
            assert len(chassis.components) == initial_count + i + 1

        # Remove components incrementally
        for i, comp in enumerate(comps):
            comp.dispose()
            assert len(chassis.components) == initial_count + len(comps) - i - 1

        assert len(chassis.components) == initial_count

        chassis.dispose()
