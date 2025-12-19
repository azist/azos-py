import unittest
import azcontext

import azatom
from azexceptions import AzosError


class AtomTests(unittest.TestCase):

    def test_decode_01(self):
        num = 478560413032 #hello
        self.assertEqual("hello", azatom.decode(num))

    def test_decode_02(self):
        num = 7956003944985229683 #syslogin
        self.assertEqual("syslogin", azatom.decode(num))

    def test_decode_03(self):
        num = 97 #a
        self.assertEqual("a", azatom.decode(num))

    def test_decode_04(self):
        num = 98 #b
        self.assertEqual("b", azatom.decode(num))

    def test_decode_05(self):
        num = 0 #zero
        self.assertEqual("", azatom.decode(num))

    def test_decode_06(self):
        num = 4123376657429507385
        self.assertEqual("9-9-9-99", azatom.decode(num))

    def test_decode_07(self):
        num = 28821929395970657
        self.assertEqual("abc_def", azatom.decode(num))

    def test_decode_08(self):
        num = 28821928557109857
        self.assertEqual("abc-def", azatom.decode(num))

    def test_decode_09(self):
        try:
            azatom.decode(937) #invalid azatom value
        except AzosError as error:
             self.assertEqual("decode(937)", error.frm) # error frm field should contain method(arg) name
        else:
            self.fail("Missing AzosError for invalid azatom int")

    def test_decode_10(self):
        try:
            azatom.decode(18446744073709551619) #invalid azatom value 2^64 = 18446744073709551616
        except AzosError as error:
             self.assertEqual("decode(18446744073709551619)", error.frm)
        else:
            self.fail("Missing AzosError for invalid azatom int")

    def test_encode_01(self):
        self.assertEqual(28821928557109857, azatom.encode("abc-def"))

    def test_encode_02(self):
        self.assertEqual(0, azatom.encode(None))
        self.assertEqual(0, azatom.encode(""))

    def test_encode_03(self):
        try:
            azatom.encode("too long of a string")
        except AzosError as error:
            self.assertEqual("encode(`too long of a string`)", error.frm)
        else:
            self.fail("Missing AzosError for invalid azatom string length")

    def test_encode_04(self):
       try:
           azatom.encode("^ba d")
       except AzosError as error:
           self.assertEqual("encode(`^ba d`)", error.frm)
       else:
           self.fail("Missing AzosError for invalid azatom string chars")

    def test_class_01(self):
        a = azatom.Atom("a")
        self.assertEqual(97, a.id)
        self.assertEqual("a", str(a))
        self.assertEqual("Atom(#97, `a`)", repr(a))

    def test_class_02(self):
        a = azatom.Atom(97)
        self.assertEqual(97, a.id)
        self.assertEqual("a", str(a))
        self.assertEqual("Atom(#97, `a`)", repr(a))

    def test_class_03(self):
        a = azatom.Atom("a")
        b = azatom.Atom("a")
        self.assertFalse(a is b)
        self.assertTrue(a == b)
        self.assertEqual(hash(a), hash(b))

    def test_class_04(self):
        a = azatom.Atom("a")
        b = a
        self.assertTrue(a is b)
        self.assertTrue(a == b)
        self.assertEqual(hash(a), hash(b))

    def test_class_05(self):
        a = azatom.Atom("a")
        b = azatom.Atom("b")
        self.assertFalse(a is b)
        self.assertFalse(a == b)
        self.assertNotEqual(hash(a), hash(b))

    def test_class_06(self):
        a = azatom.Atom(8825501086245354106)
        self.assertTrue(a.valid)

    def test_class_07(self):
        a = azatom.Atom(8825501086245354109)
        self.assertFalse(a.valid)

    def test_class_08(self):
        a = azatom.Atom(0)
        self.assertEqual(0, a.id)
        self.assertTrue(a.valid)
        self.assertTrue(a.is_zero)
        self.assertEqual("", str(a))
        self.assertEqual("Atom.ZERO", repr(a))

    def test_is_valid_06(self):
        a = 8825501086245354106
        self.assertTrue(azatom.is_valid(a))

    def test_is_valid_07(self):
        a = 8825501086245354109
        self.assertFalse(azatom.is_valid(a))



if __name__ == '__main__':
    unittest.main()
