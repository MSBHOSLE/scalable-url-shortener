"""Base62 encoding and decoding module.

Utilizes bijective base conversion between positive integers and short URL codes:
Alphabet: 0-9, a-z, A-Z (62 characters)
Capacity with 6 characters: 62^6 = 56,800,235,584 unique URLs.
"""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)
CHAR_TO_INDEX = {char: idx for idx, char in enumerate(ALPHABET)}

# Numerical offset to ensure codes start with at least 6 characters
# 62^4 = 14,776,336; 62^5 = 916,132,832
OFFSET = 100_000_000


def encode_base62(num: int, min_length: int = 6) -> str:
    """Encode an integer ID into a Base62 string representation.

    Args:
        num: Unique positive integer identifier (e.g. database sequence ID).
        min_length: Minimum string length to pad short codes.

    Returns:
        Base62 encoded string.
    """
    if num < 0:
        raise ValueError("Number must be a non-negative integer")

    # Apply offset to avoid trivial small numbers while keeping 1-to-1 bijection
    val = num + OFFSET

    if val == 0:
        return ALPHABET[0].rjust(min_length, ALPHABET[0])

    chars = []
    while val > 0:
        val, remainder = divmod(val, BASE)
        chars.append(ALPHABET[remainder])

    encoded = "".join(reversed(chars))

    if len(encoded) < min_length:
        encoded = encoded.rjust(min_length, ALPHABET[0])

    return encoded


def decode_base62(code: str) -> int:
    """Decode a Base62 string back to its original integer identifier.

    Args:
        code: Base62 encoded string.

    Returns:
        Original integer identifier.
    """
    if not code:
        raise ValueError("Code cannot be empty")

    num = 0
    for char in code:
        if char not in CHAR_TO_INDEX:
            raise ValueError(f"Invalid character '{char}' in Base62 code")
        num = num * BASE + CHAR_TO_INDEX[char]

    result = num - OFFSET
    if result < 0:
        raise ValueError("Decoded value is out of valid range")

    return result
