import pytest
import time
from azos.gdid8 import GDID8

def test_encode_decode():
    """Test that decode perfectly recovers encode values."""
    authority = 15
    timestamp = 1234567890
    counter = 100

    gdid = GDID8.encode(authority, timestamp, counter)

    # Check manual decoding using max limits based on bitwise shift
    dec_auth, dec_ts, dec_ctr = GDID8.decode(gdid)

    assert dec_auth == authority
    assert dec_ts == timestamp
    assert dec_ctr == counter

def test_encode_out_of_bounds():
    """Test exceptions on encode arguments."""
    with pytest.raises(ValueError, match="Authority must be between 0 and 255."):
         GDID8.encode(256, 12345, 100)

    with pytest.raises(ValueError, match="Authority must be between 0 and 255."):
         GDID8.encode(-1, 12345, 100)

    with pytest.raises(ValueError, match=rf"Timestamp must be a 43-bit value \(0 to {GDID8.MAX_TIMESTAMP}\)."):
         GDID8.encode(15, GDID8.MAX_TIMESTAMP + 1, 100)

    with pytest.raises(ValueError, match=rf"Timestamp must be a 43-bit value \(0 to {GDID8.MAX_TIMESTAMP}\)."):
         GDID8.encode(15, -1, 100)

    with pytest.raises(ValueError, match=rf"Counter must be a 12-bit value \(0 to {GDID8.MAX_COUNTER}\)."):
         GDID8.encode(15, 12345, GDID8.MAX_COUNTER + 1)

    with pytest.raises(ValueError, match=rf"Counter must be a 12-bit value \(0 to {GDID8.MAX_COUNTER}\)."):
         GDID8.encode(15, 12345, -1)

def test_now_increasing():
    """Test that now() generates monotonically non-decreasing timestamps in general usage."""
    t1 = GDID8.now()
    time.sleep(0.01) # Sleep to allow system clock to increment
    t2 = GDID8.now()
    assert t2 > t1

def test_get_shard_path():
    """Test shard path generation with boolean list of length 8."""
    authority = 0

    # 0b10101010 = 170
    # 0b01010101 = 85
    timestamp = 170
    counter = 85

    gdid = GDID8.encode(authority, timestamp, counter)

    path = GDID8.get_shard_path(gdid)

    assert isinstance(path, list)
    assert len(path) == 8

    # For every bit in first 8 bits, timestamp bit is 1-0 alternating, counter is 0-1 alternating
    # XOR them -> 1^0 = 1. Therefore all bits should be 1 (True)
    assert all(path)

    # If same
    gdid_same = GDID8.encode(authority, 170, 170)
    path_same = GDID8.get_shard_path(gdid_same)
    assert not any(path_same)  # XOR of same sequence is 0 -> all False

def test_init_and_authority_property():
    """Test instance construction and authority property mapping."""
    g = GDID8(15)
    assert g.authority == 15

    with pytest.raises(ValueError, match="Authority must be between 0 and 255."):
        GDID8(-1)

    with pytest.raises(ValueError, match="Authority must be between 0 and 255."):
        GDID8(256)

def test_generate_successive_counter():
    """Test generation within the same millisecond increments counter."""
    g = GDID8(123)

    # Monkeypatch now() for controlled timestamp
    fake_ts = 5000

    # Save original
    original_now = GDID8.now

    GDID8.now = staticmethod(lambda: fake_ts)
    try:
        g1 = g.generate()
        g2 = g.generate()
        g3 = g.generate()

        _, ts1, count1 = GDID8.decode(g1)
        _, ts2, count2 = GDID8.decode(g2)
        _, ts3, count3 = GDID8.decode(g3)

        assert ts1 == ts2 == ts3 == fake_ts
        assert count1 == 0
        assert count2 == 1
        assert count3 == 2

        # Next millisecond
        fake_ts = 5001
        g4 = g.generate()
        _, ts4, count4 = GDID8.decode(g4)
        assert ts4 == 5001
        assert count4 == 0

    finally:
        GDID8.now = original_now


if __name__ == "__main__":
    g = GDID8(123)
    for i in range(10):
        gdid = g.generate()
        print(f"Generated GDID8: {gdid}  = {gdid:b} = {gdid.to_bytes(8, byteorder='big').hex('_')}")
