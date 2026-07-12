"""
Provides convenience methods for performing fuzzy matching and searching such as extracting principal components
from US addresses, monophone sequences, and other structured textual data. All without 3rd party libraries.

Address processing logic based on Galaxy/Aqua circa 1999-2003

Copyright (C) 2019 - 2026 Azist, MIT License
"""

import re


ADDRESS_STOP_PARTS = frozenset([
    "street", "st", "str",
    "road", "rd",
    "avenue", "ave", "av",
    "boulevard", "blvd", "blv",
    "lane", "ln", "l",
    "drive", "dr", "drv",
    "court", "ct", "crt",
    "circle", "cir",
    "place", "pl",
    "square", "sq", "sqr",
    "trail", "trl", "tr",
    "terrace", "ter",
    "highway", "hwy",
    "parkway", "pkwy",
    "way", "wy",
    "commons",
    "plaza", "plz",
    "mall",
    "room", "rm",
    "apartment", "apt",
    "unit", "un",
    "suite", "ste",
    "floor", "fl",
    "north", "n",
    "south", "s",
    "east", "e",
    "west", "w"
])


def extract_address_line_principal_components(address_line: str) -> tuple[int, str | None]:
    """
    Extracts the principal components of an address line.

    Args:
        address_line (str): The address line to process.

    Returns:
        tuple[int, str]: A tuple containing the house number and the remaining address line.
        -1 if house number is unknown, and None if the remaining address is empty
    """
    if not address_line or not isinstance(address_line, str):
        return -1, None

    # 1. Lowercase the string
    clean = address_line.lower()

    # 2. Replace punctuation with spaces
    clean = re.sub(r'[^\w\s]', ' ', clean)

    # 3. Split the string into parts
    parts = clean.split()

    # 4. Extract the house number if present
    house_number = -1
    if parts and parts[0].isdigit():
        house_number = int(parts[0])
        parts = parts[1:]

    # 5. Remove stop parts
    remaining_parts = [part for part in parts if part not in ADDRESS_STOP_PARTS]
    if len(remaining_parts) == 0:
        remaining_parts = parts

    remaining_address = " ".join(remaining_parts)

    return house_number, remaining_address



if __name__ == "__main__":
    test_addresses = [
        "123 Main St.",
        "456 Elm Street Apt 7",
        "789 Oak Blvd Suite 10",
        "No Number Avenue",
        " 7797 North Hiram Lane",
        "7797 N. Hiram Ln",
        "7797 North Hiram L",
        "7797 N Hiram",
        "810 S Sussex Ct",
        "     810   South     Sussex    Ct",
        "6745 Morganford Rd",
        "4051 Folsom Ave",
        "10602 S 7th Ave"
    ]

    for address in test_addresses:
        house_number, remaining_address = extract_address_line_principal_components(address)
        print(f"Address: {address}")
        print(f"House Number: {house_number}, Remaining Address: {remaining_address}")
        print()
