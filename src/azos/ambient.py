"""
Ambient context design pattern as used in Azos C#

Copyright (C) 2018 - 2026 Azist, MIT License
"""

import contextvars
from azos.sec.user import User
from azos.sec.session import Session


class Ambient:
    """
    Establishes a global scope for passing session/user identity information along asynchronous call flows.
    This pattern is useful for any asyncio-driven flows, such as custom event loops and FastAPI.
    This pattern should not be used for passing business info, only for system params like auth.

    See `Apps/ExecutionContext.cs` in Azos
    """

    _session = contextvars.ContextVar("ambient_session", default=Session.nop())

    @staticmethod
    def get_session() -> Session:
        """Gets current call flow session or NOP session if another was not set yet"""
        return Ambient._session.get()

    @staticmethod
    def set_session(session: Session | None):
        """Sets current call flow session, or NOP session if you pass none"""
        Ambient._session.set(session if session is not None else Session.nop())

    @staticmethod
    def get_user() -> User:
        """Returns current call flow user. Never returns None as NOP session would return an invalid user"""
        return Ambient.get_session().user