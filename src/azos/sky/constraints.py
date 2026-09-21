"""
Imposes global constraints on SKY distributed system like max field sizes and values

Copyright (C) 2020 - 2026 Azist, MIT License
"""

ENTITY_ID_MAX_LEN: int = 128

APP_NAME_MAX_LEN: int = 32
APP_COMPONENT_MAX_LEN: int = 128

NS_NAME_MAX_LEN: int = 128

HOST_MAX_LEN: int = 128
DESCRIPTION_MAX_LEN: int = 256

MUTEX_KEY_MAX_LEN: int = 256
MUTEX_VALUE_MAX_ITEMS: int = 128
MUTEX_MAX_TIMEOUT_SEC: float = 12 * 60 * 60  # 12 hours

SLOT_KEY_MAX_LEN: int = 256
SLOT_VALUE_MAX_ITEMS: int = 1024
