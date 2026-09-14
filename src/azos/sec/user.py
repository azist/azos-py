"""
Azos security model session. Provides a context object under which user activities, such as service calls, take place.
The object is ephemeral - it gets re-created/set by dedicated auth call flows.
Every session represents an instance of interaction between a user principal identified by `User` and the system.
Sessions can capture more contextual data such as culture and other preferences such as time zones etal.
Authorization is performed in a scope of Session not just User - this gives more control.

A session has user principal object, in addition it can store session-specific customization choices like locales
and data formatting rules.

User principal objects captures who the users are along wit their `Rights` vectors used for authorization.

Both classes provided sentinel value factories: `Session.nop()` and `User.invalid()`.

Copyright (C) 2018 - 2026 Azist, MIT License
"""
import time
from typing import Any
import uuid
from enum import IntEnum

from azos.chassis import AppChassis
from azos.descriptor import Descriptor
from azos.sec.credentials import Credentials, NopCredentials
from azos.sec.rights import Rights


class UserDescriptor(Descriptor):
    """
    Provides structured access to standardized and azure-specific OIDC/OAuth claims.
    `UserDescriptors` are used to make instances of `User` primcipal objects
    such as: "exp", "iat", "nbf" etc.
    """

    def __init__(self, data: dict, chassis: AppChassis, token: str | None = None):
        self._token = token
        super().__init__(data, chassis)

    def get_token(self) -> str | None:
        """Passes-through raw token as it came into authentication middleware, used for OBO delegation flows"""
        return self._token

    @property
    def is_valid(self) -> bool:
        """Deems structure as valid if eithhr `sub`, `name`, or `preferred_username` is set"""
        return bool(self.as_str("sub") or self.as_str("name") or self.as_str("preferred_username"))

    # List of standard OIDC claims follows....
    @property
    def sub(self) -> str | None:
        """Subject identifier: stable, locally unique user ID at the issuer."""
        return self.as_str("sub")

    @property
    def name(self) -> str | None:
        """End-user full display name."""
        return self.as_str("name")

    @property
    def given_name(self) -> str | None:
        """Given name(s) or first name."""
        return self.as_str("given_name") or self.as_str("givenName")

    @property
    def family_name(self) -> str | None:
        """Family name(s) or last name."""
        return self.as_str("family_name") or self.as_str("familyName") or self.as_str("surname")

    @property
    def middle_name(self) -> str | None:
        """Middle name(s)."""
        return self.as_str("middle_name")

    @property
    def nickname(self) -> str | None:
        """Casual nickname."""
        return self.as_str("nickname")

    @property
    def preferred_username(self) -> str | None:
        """Preferred shorthand username for UI display or login hints."""
        return self.as_str("preferred_username") or self.as_str("upn")

    @property
    def profile(self) -> str | None:
        """URL of the end-user profile page."""
        return self.as_str("profile")

    @property
    def picture(self) -> str | None:
        """URL of the end-user profile picture."""
        return self.as_str("picture")

    @property
    def website(self) -> str | None:
        """URL of the end-user web site or blog."""
        return self.as_str("website")

    @property
    def email(self) -> str | None:
        """Preferred email address."""
        return self.as_str("email")

    @property
    def email_verified(self) -> bool | None:
        """True when email ownership was verified by the identity provider."""
        return self.as_bool("email_verified")

    @property
    def gender(self) -> str | None:
        """End-user gender claim as provided by the issuer."""
        return self.as_str("gender")

    @property
    def birthdate(self) -> str | None:
        """Birthday, usually in ISO form YYYY-MM-DD."""
        return self.as_str("birthdate")

    @property
    def zoneinfo(self) -> str | None:
        """IANA time zone string, for example America/Los_Angeles."""
        return self.as_str("zoneinfo")

    @property
    def locale(self) -> str | None:
        """Locale preference, for example en-US."""
        return self.as_str("locale")

    @property
    def phone_number(self) -> str | None:
        """Preferred phone number, commonly in E.164 format."""
        return self.as_str("phone_number")

    @property
    def phone_number_verified(self) -> bool | None:
        """True when phone number ownership was verified by the provider."""
        return self.as_bool("phone_number_verified")

    @property
    def address(self) -> str | None:
        """Address claim payload, often structured JSON serialized as text."""
        return self.as_str("address")

    @property
    def updated_at(self) -> int | None:
        """Epoch seconds when profile data was last updated."""
        return self.as_int("updated_at")

    @property
    def iss(self) -> str | None:
        """Issuer identifier (token authority URL or URI)."""
        return self.as_str("iss")

    @property
    def aud(self) -> str | None:
        """Audience: intended recipient identifier for this token."""
        return self.as_str("aud")

    @property
    def exp(self) -> int | None:
        """Expiration time as epoch seconds."""
        return self.as_int("exp")

    @property
    def iat(self) -> int | None:
        """Issued-at time as epoch seconds."""
        return self.as_int("iat")

    @property
    def nbf(self) -> int | None:
        """Not-before time as epoch seconds."""
        return self.as_int("nbf")

    @property
    def auth_time(self) -> int | None:
        """End-user authentication time at the provider, in epoch seconds."""
        return self.as_int("auth_time")

    @property
    def nonce(self) -> str | None:
        """Opaque nonce used by clients to bind auth response to request."""
        return self.as_str("nonce")

    @property
    def acr(self) -> str | None:
        """Authentication Context Class Reference value."""
        return self.as_str("acr")

    @property
    def amr(self) -> str | None:
        """Authentication Methods References, typically method names or codes."""
        return self.as_str("amr")

    @property
    def azp(self) -> str | None:
        """Authorized party: client ID of the party to which ID token was issued."""
        return self.as_str("azp")

    @property
    def sid(self) -> str | None:
        """Session identifier at the identity provider."""
        return self.as_str("sid")

    @property
    def jti(self) -> str | None:
        """JWT ID: unique token identifier."""
        return self.as_str("jti")

    # Microsoft Azure/Entra specific Claims
    @property
    def azure_tid(self) -> str | None:
        """Tenant ID (Microsoft Entra directory UUID)."""
        return self.as_str("tid")

    @property
    def azure_oid(self) -> str | None:
        """Object ID of the user or service principal in the tenant."""
        return self.as_str("oid")

    @property
    def azure_upn(self) -> str | None:
        """User principal name, typically user@domain."""
        return self.as_str("upn")

    @property
    def azure_unique_name(self) -> str | None:
        """Legacy unique user name claim emitted by some token versions."""
        return self.as_str("unique_name")

    @property
    def azure_appid(self) -> str | None:
        """Client application ID (resource tokens, v1 style)."""
        return self.as_str("appid")

    @property
    def azure_appidacr(self) -> str | None:
        """How client app authenticated: 0 public, 1 secret, 2 certificate."""
        return self.as_str("appidacr")

    @property
    def azure_idtyp(self) -> str | None:
        """Identity type hint, commonly 'app' for app-only tokens."""
        return self.as_str("idtyp")

    @property
    def azure_scp(self) -> str | None:
        """Delegated OAuth scopes as a space-delimited string."""
        return self.as_str("scp")

    @property
    def azure_ver(self) -> str | None:
        """Access token version, usually '1.0' or '2.0'."""
        return self.as_str("ver")

    @property
    def azure_uti(self) -> str | None:
        """Internal token identifier used by Microsoft STS telemetry."""
        return self.as_str("uti")

    @property
    def azure_aio(self) -> str | None:
        """Microsoft-internal claim used for token reuse and session heuristics."""
        return self.as_str("aio")

    @property
    def azure_rh(self) -> str | None:
        """Refresh token/session handle metadata used by Microsoft STS."""
        return self.as_str("rh")

    @property
    def azure_tenant_region_scope(self) -> str | None:
        """Region affinity hint for tenant processing."""
        return self.as_str("tenant_region_scope")

    @property
    def azure_xms_cc(self) -> str | None:
        """Client capabilities claim (for example, CP1) from Microsoft tokens."""
        return self.as_str("xms_cc")

    @property
    def azure_xms_mirid(self) -> str | None:
        """Managed identity resource identifier for Azure managed identity tokens."""
        return self.as_str("xms_mirid")

    @property
    def azure_xms_tcdt(self) -> int | None:
        """Token creation date-time as Unix epoch seconds in Microsoft tokens."""
        return self.as_int("xms_tcdt")

    @property
    def azure_wids(self) -> str | None:
        """Directory role template IDs (often emitted as JSON array)."""
        return self.as_str("wids")

    @property
    def azure_roles(self) -> str | None:
        """App role assignments (often emitted as JSON array)."""
        return self.as_str("roles")

    @property
    def azure_groups(self) -> str | None:
        """Group membership IDs (often emitted as JSON array or overage marker)."""
        return self.as_str("groups")


class UserStatus(IntEnum):
    """Maps canonical Azos Auth enum: `Invalid` | `User` | `Admin` | `System`"""

    INVALID = 0
    """User without credentials and no rights"""

    USER = 1
    """Standard user archetype"""

    ADMIN = 1000
    """Elevated user archetype used for broader access"""

    SYSTEM = 1000000
    """
    Root system access effectively bypasses all permission checks.
    Do not grant this level to anyone beyond initial system setup and dev
    """


class User:

    @staticmethod
    def invalid() -> "User":
        """Creates a no-operation empty user with no credentials and invalid rights"""
        return User(
            credentials=NopCredentials(),
            auth_token=None,
            status=UserStatus.INVALID,
            name="John Doe (invalid)",
            description="Invalid user",
            roles=["none"],
            rights=Rights({}),
            create_utc=0,
            props=UserDescriptor({}, chassis=AppChassis.get_current_instance())
        )

    def __init__(
            self,
            credentials: Credentials,
            auth_token: Any,
            status: UserStatus,
            name: str,
            description: str,
            roles: list[str],
            rights: Rights,
            create_utc: float,
            props: UserDescriptor
        ):
        self._credentials = credentials
        self._auth_token = auth_token
        self._status = status
        self._name = name
        self._description = description
        self._roles = roles
        self._rights = rights
        self._create_utc = create_utc
        self._props = props

    @property
    def credentials(self) -> Credentials:
        """Returns the credentials object used to authenticate this user"""
        return self._credentials

    @property
    def auth_token(self) -> Any:
        """Returns the raw auth token used to authenticate this user"""
        return self._auth_token

    @property
    def status(self) -> UserStatus:
        """Returns the user status archetype"""
        return self._status

    @property
    def name(self) -> str:
        """Returns the user display name"""
        return self._name

    @property
    def description(self) -> str:
        """Returns the user description"""
        return self._description

    @property
    def roles(self) -> list[str]:
        """Returns the list of user roles"""
        return self._roles

    @property
    def rights(self) -> Rights:
        """Returns the user rights descriptor"""
        return self._rights

    @property
    def create_utc(self) -> float:
        """Returns the UTC timestamp when the user was created"""
        return self._create_utc

    @property
    def props(self) -> UserDescriptor:
        """Returns the user descriptor with structured access to claims and properties"""
        return self._props


class Session:
    """
    Sessions are ephemeral context objects which are typically created and set by service middleware
    such as getting `User` principal from `Authorization` token and computing the the culture descriptor.

    Note: this has nothing to do with "heavy" ASP.NET or PHP sessions stored in files or databases, albeit one could
    easily implement session adapter for such purpose.

    Sessions are typically used with `Ambient` design pattern - they pass the info about the logical calling
    session on behalf of which the work gets performed. System permission authorization is performed
    in the scope of ambient session unless particular session instance is passed.

    Session context is bigger than just `User` principal as it also includes culture and possibly other
    parameters which described the specific instance of interaction of the specific User principal with the system,
    hence authorization decisions are based on `Session` objects (which have `user: User` and other context) not just users.
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