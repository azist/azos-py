"""Provides custom exception related to Azos interop

Copyright (C) 2023 Azist, MIT License

"""
__all__ = ["AzosError"]

class AzosError(Exception):
    """Exception thrown by Azos interop code

    Attributes:
        topic -- exception topic string
        frm -- string specifier of the "from" place in code/system/component
        src -- error/source code (int)
        message -- explanation of the error
    """

    def __init__(self, message="Azos unspecified error", topic = "azos", frm = "", src = 0):
        self.topic = topic
        self.frm = frm
        self.src = src
        self.message = message
        super().__init__(self.message)


