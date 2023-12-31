"""Provides interop functions for working with Azos Atom data type

Copyright (C) 20023 Azist, MIT License


"""

from azexceptions import AzosError


MAX_ATOM_LENGTH = 8
VALID_CHAR_CODES = frozenset([ 
    *range(ord('0'), ord('9') + 1), 
    ord('_'), 
    ord('-'), 
    *range(ord('A'), ord('Z') + 1), 
    *range(ord('a'), ord('z') + 1) 
    ])


__atoms = { }

def __validate_char(c: int) -> bool:
    return (c in VALID_CHAR_CODES)

def encode(astr: str) -> int:
    """Encodes a string value as an atom ulong
    
    This function does not maintain any caches and is relatively slow, this is because
    you should NOT encode strings into atoms in a loop or regular basis.

    If the value is invalid, then AzosError is raised.
    Atom values must have 1 to 8 characters, only from the following set: ['_','-','0'..'9','A'..'Z','a'..'z'].
    Empty or blank strings are treated az Atom.Zero (0 int)
    """
    
    if astr == None or astr == "":
        return 0
    
    if len(astr) > MAX_ATOM_LENGTH:
        raise AzosError(f"Invalid atom string length is over {MAX_ATOM_LENGTH}", "atom", f"encode(`{astr}`)")

    ax = 0
    i = 0
    for one in astr:
        c = ord(one)
        if not __validate_char(c):
            raise AzosError(f"Invalid atom char #{c} / `{chr(c)}`", "atom", f"encode(`{astr}`)")
        ax = ax | (c << (i * 8))
        i = i + 1
    return ax

def decode(id: int) -> str:
    """Decodes an ulong int atom value back to string
    
    The function maintains internal static cache. If the value is
    not in cache it gets converted to string and cached.

    !!!Warning!!!: atoms are designed to handle a finite number of values,
    most applications dealing with a few hundred values.
    Using atoms for arbitrary values is not a good idea as it trashes your
    Atom intern pool (cache).
    """
    if id == 0:
        return ""
    
    if id.bit_length() > 64:
        raise AzosError(f"Invalid atom id too big", "atom", f"decode({id})")

    result = __atoms.get(id) #check cache
    if result == None:
        ax = id
        result = ""
        ### print(f"Atom {id} is not in cache")
        for i in range(0, 8):
            c = ax & 0xff
            if c==0: 
                break
            if not __validate_char(c):
                raise AzosError(f"Invalid atom char #{c} / `{chr(c)}`", "atom", f"decode({id})")
            result = result + chr(c)
            ax = ax >> 8

    __atoms[id] = result
    return result

def is_valid(id: int) -> bool:
    """Returns true if the supplied integer represents a valid Atom id
    
    """
    if id == 0:
        return True
    
    if id.bit_length() > 64:
        return False

    ax = id
    for i in range(0, 8):
        c = ax & 0xff
        if not __validate_char(c):
            return False
        ax = ax >> 8
    return True

class Atom:
    """Encapsulates an Atom value which is up to 8 ASCII only characters coded as an int

    """
    def __init__(self, val: int | str) -> None:
        if val == None or type(val) == str:
            self._id = encode(val)
        else:
            self._id = val

    def __str__(self):
        return decode(self._id)
    
    def __repr__(self):
        if self._id != 0:
            return f"Atom(#{self._id}, `{decode(self._id)}`)"
        else:
            return "Atom.ZERO"
    
    def __eq__(self, other: object) -> bool:
        return self._id == other._id
    
    def __hash__(self):
        return hash(self._id)
    
    id = property(fget = lambda self: self._id, doc = "Gets Atom id: ulong")

    is_zero = property(fget = lambda self: self._id == 0, doc = "True if id=0")

    valid = property(fget = lambda self: is_valid(self._id), doc = "Returns true if the id value is valid")


if __name__ == "__main__":
    #for one in VALID_CHAR_CODES:
    #   print(f"{one} - {chr(one)}")
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(1634560358)}") # fima
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(7956003944985229683 )}") # syslogin
    print(f"Decoding atom from int: {decode(1634560358)}") # fima
    print(f"Encoding atom from string: {encode('fima')}") # fima
    print()
    a = Atom(1634560356)
    print(a)
    a = Atom("syslogin")
    print(repr(a))
    print(a.id)
    b = Atom("syslogin")
    print(a==b, a is b, hash(a), hash(b))

