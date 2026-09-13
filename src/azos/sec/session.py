"""
Azos security model session. Provides a context object under which user activities, such as service calls, take place.
The object is ephemeral - it gets re-created/set by dedicated auth call flows.
Every session represents an instance of interaction between a user principal identified by `User` and the syste.
Sessions can capture more contextual data such as culture and other preferences such as time zones etal.
Authorization is performed in a scope of Session not just User - this gives more control.

A session has user principal object, in addition it can store session-specific customization choices like locales
and data formatting rules.

Copyright (C) 2018 - 2026 Azist, MIT License
"""
import time
import uuid

from azos.descriptor import Descriptor


class UserDescriptor(Descriptor):
    pass


class User:
    pass


class Session:
    """
    Sessions are ephemeral context objects which are typically created and set by service middleware
    such as getting `User` principal from `Authorization` token and computing the the culture descriptor.

    Note: this has nothing to do with "heavy" ASP.NET or PHP sessions stored in files or databases, albeit one could
    easily implement session adapter for such purpose.

    Sessions are typicsally used with `Ambient` design pattern - they pass the info about the logical calling
    session on behalf of which the work gets performed. System permission authorization is performed
    in the scope of ambient session unless particular session isnace is passed.

    Session context is bigger than just `User` principal as it also includes culture and possibly other
    paraameters which descrbed the specific instance of interaction of the specifc User principal with the system,
    hence authorization decisions are based on `Session`objects (which have `user: User` and other context) not just users.
    """

    @staticmethod
    def nop() -> "Session":
        """Creates a no-operation empty session with an invalid user and undefined culture"""
        return Session(user=User.invalid(), origin="sys::nop")

    def __init__(self, *,
                  id: str | None = None,
                  user: User | None,
                  origin: str | None = None,
                  start_utc: float = -1,
                  culture: Descriptor | None = None):
        self._id = id if id else uuid.uuid4().hex
        self._start_utc = start_utc if start_utc > 0 else time.time()
        self._user = user if user is not None else User.invalid()
        self._origin = origin if origin else "sys"
        self._culture = culture

    @property
    def session_id(self) -> str:
        """Unique session UUID"""
        return self._id

    @property
    def start_utc(self) -> float:
        """UTC timestamp when session started"""
        return self._start_utc

    @property
    def origin(self) -> str:
        """Origin -who created the session, a short decriptive phrase mostly for admin"""
        return self._origin

    @property
    def culture(self) -> Descriptor | None:
        """Optional culture descriptor or None. If none then use system-default culture"""
        return self._culture

    @property
    def user(self) -> User:
        """Returns the user prinicipal. User is always set even if invalid  s this is never None"""
        return self._user