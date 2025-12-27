"""Provides interop functions for working with Azos application

Copyright (C) 20023 Azist, MIT License

"""

import uuid
import azatom
from datetime import datetime
from azexceptions import AzosError

__instance = None

class AzosApp:
    def __init__(self, config) -> None:
        if __instance != None:
            raise AzosError(f"App already initialized", "app", "_init_")

        __instance = self
        self.instance_uuid = uuid.uuid4()
        self.start_utc = datetime.utcnow()

        if config == None:
            config = { }

        self.config_root = config
        # ---------------------------------------------------
        self.id          = azatom.Atom(config.get("id"))
        self.origin      = azatom.Atom(config.get("origin"))
        self.description = config.get("description") or ""
        self.copyright   = config.get("copyright") or ""
        self.environment = config.get("environment-name") or "dev"
        # ---------------------------------------------------

    def __del__(self):
        __instance = None


