"""
Credentials represent data needed for authentication such as: API keys, user id/password, JWT tokens etc.
Every subclass represents a particular credential type with corresponding structure, for example `IdPwdCredentials`
rely on `uid` and `pwd` fields.

Call `forget()` method to drop sensitive information and keep just the object shell to signify how users authenticated
"""

from abc import ABC

class Credentials(ABC):
    """Derive credential concrete implementations from this class"""

    def forget(self):
        """Override to drop sensitive data, such as replace real password with a mask"""
        pass


class IdPwdCredentials(Credentials):
    """Id/Password string pair used for authentication"""
    def __init__(self, uid: str, pwd:  str):
        self._id = uid
        self._pwd = pwd

    @property
    def uid(self) -> str:
        """User ID"""
        return self._id

    @property
    def pwd(self) -> str:
        """User password"""
        return self._pwd

    def forget(self):
        """Drop sensitive data to prevent accidental disclosure"""
        self._pwd = "****"


class BearerTokenCredentials(Credentials):
    """Bearer token used for authentication"""
    def __init__(self, token: str):
        self._token = token

    @property
    def token(self) -> str:
        """Bearer token"""
        return self._token

    def forget(self):
        """Drop sensitive data to preent accidental disclosure"""
        self._token = "****"