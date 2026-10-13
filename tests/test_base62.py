import pytest
from app.services.base62 import decode_base62, encode_base62, OFFSET


def test_base62_encode_decode_roundtrip():
    """Verify bijective property: decode(encode(x)) == x."""
    test_ids = [0, 1, 42, 100, 9999, 123456, 1000000, 987654321]
    for num in test_ids:
        encoded = encode_base62(num)
        assert isinstance(encoded, str)
        assert len(encoded) >= 6
        decoded = decode_base62(encoded)
        assert decoded == num


def test_base62_min_length_padding():
    """Verify that encoded string obeys minimum length padding."""
    encoded_6 = encode_base62(1, min_length=6)
    assert len(encoded_6) >= 6

    encoded_8 = encode_base62(1, min_length=8)
    assert len(encoded_8) == 8
    assert decode_base62(encoded_8) == 1


def test_base62_negative_number_raises():
    """Negative IDs should raise ValueError."""
    with pytest.raises(ValueError):
        encode_base62(-1)


def test_base62_empty_string_raises():
    """Empty code should raise ValueError."""
    with pytest.raises(ValueError):
        decode_base62("")


def test_base62_invalid_characters():
    """Codes containing characters outside the Base62 alphabet should raise ValueError."""
    invalid_codes = ["abc#12", "test!", "code@9", "hello space"]
    for code in invalid_codes:
        with pytest.raises(ValueError):
            decode_base62(code)


def test_base62_uniqueness():
    """Verify that distinct sequential numbers produce distinct short codes."""
    codes = [encode_base62(i) for i in range(1000)]
    assert len(codes) == len(set(codes)), "Collision detected in Base62 sequential encoding!"
