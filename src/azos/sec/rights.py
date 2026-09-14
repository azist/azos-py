"""
Rights represent access control entitlements for users or other principals.
Rights is a top "config tree" object which is a subtype of descriptor:
a hierarchical tree of rights is a tree of namespaces and permissions (leaves) which can be granted to users
 or other principals.

Copyright (C) 2018 - 2026 Azist, MIT License
"""
from azos.descriptor import Descriptor

class Rights(Descriptor):
    """
    Rights ACL tree subclasses descriptor and represents a hierarchical tree of namespaces and permissions (leaves)
    which can be granted to users or other principals
    """

    @staticmethod
    def parse_role_spec(spec: str | list[str] | None) -> list[str] | None:
        """
        Parses a role specification string or list of strings into a list of role names.
        The spec can be a comma-separated string or a list of strings.
        Returns None if the spec is None or empty.
        """
        if spec is None:
            return None
        if isinstance(spec, str):
            return [role.strip() for role in spec.split(',') if role.strip()]
        elif isinstance(spec, list):
            return [role.strip() for role in spec if isinstance(role, str) and role.strip()]
        else:
            raise ValueError(f"Bad role spec: `{spec}`")

    def __init__(self, data: dict):
        super().__init__(data)
