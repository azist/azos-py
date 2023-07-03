"""Provides interop functions for working with Azos application

Copyright (C) 20023 Azist, MIT License


"""
import uuid
import json
import azatom
from datetime import datetime
from azexceptions import AzosError

__instance = None

def __loadcfg(cfg: str) -> object:
    # todo exception handling
    dict = json.loads(str)
    return dict

class AzosApp:
    def __init__(self, config) -> None:
        if __instance != None:
            raise AzosError(f"App already initialized", "app", "_init_")
        
        __instance = self
        self.instance_uuid = uuid.uuid4()
        self.start_utc = datetime.utcnow()
        self.config_root = __loadcfg(config)


    def __del__(self):
        __instance = None
