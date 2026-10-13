import unittest
from app.services.base62 import decode_base62, encode_base62


class TestBase62(unittest.TestCase):
    def test_roundtrip(self):
        test_ids = [0, 1, 42, 100, 9999, 123456, 1000000, 987654321]
        for num in test_ids:
            encoded = encode_base62(num)
            self.assertTrue(isinstance(encoded, str))
            self.assertGreaterEqual(len(encoded), 6)
            decoded = decode_base62(encoded)
            self.assertEqual(decoded, num)

    def test_min_length(self):
        encoded_6 = encode_base62(1, min_length=6)
        self.assertGreaterEqual(len(encoded_6), 6)

        encoded_8 = encode_base62(1, min_length=8)
        self.assertEqual(len(encoded_8), 8)
        self.assertEqual(decode_base62(encoded_8), 1)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            encode_base62(-1)

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            decode_base62("")

    def test_invalid_chars(self):
        invalid_codes = ["abc#12", "test!", "code@9", "hello space"]
        for code in invalid_codes:
            with self.assertRaises(ValueError):
                decode_base62(code)

    def test_uniqueness(self):
        codes = [encode_base62(i) for i in range(1000)]
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main()
