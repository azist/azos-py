"""Provides interop functions for working with Azos Atom data type

Copyright (C) 20023 Azist, MIT License


"""

from exceptions import *

MAX_ATOM_LENGTH = 8
VALID_CHAR_CODES = set([ 
    *range(ord('0'), ord('9') + 1), 
    ord('_'), 
    ord('-'), 
    *range(ord('A'), ord('Z') + 1), 
    *range(ord('a'), ord('z') + 1) 
    ])


__atoms = { }

def __validate_char(c: int) -> bool:
    return (c in VALID_CHAR_CODES)

def encode(sval: str):
    """Encodes a string value as an atom ulong
    
    Documentation paragraph.
    """
    
    print("Encoding: " + str)
    return 0

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

    result = __atoms.get(id) #check cache
    ax = id
    if result == None:
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



if __name__ == "__main__":
    #for one in VALID_CHAR_CODES:
    #   print(f"{one} - {chr(one)}")
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(1634560358)}") # fima
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(1634560356)}") # dima
    print(f"Decoding atom from int: {decode(7956003944985229683 )}") # syslogin
    print(f"Decoding atom from int: {decode(1634560358)}") # fima
