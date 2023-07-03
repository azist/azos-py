import unittest
import azcontext

import azatom
from azexceptions import AzosError


class AtomTests(unittest.TestCase):

    def test_decode_01(self):
        num = 478560413032 #hello
        self.assertEqual("hello", azatom.decode(num));

    def test_decode_02(self):
        num = 7956003944985229683 #syslogin
        self.assertEqual("syslogin", azatom.decode(num));

    def test_decode_03(self):
        num = 97 #a
        self.assertEqual("a", azatom.decode(num));

    def test_decode_04(self):
        num = 98 #b
        self.assertEqual("b", azatom.decode(num));

    def test_decode_05(self):
        num = 0 #zero
        self.assertEqual("", azatom.decode(num));

    def test_decode_06(self):
        num = 4123376657429507385  
        self.assertEqual("9-9-9-99", azatom.decode(num));

    def test_decode_07(self):
        num = 28821929395970657
        self.assertEqual("abc_def", azatom.decode(num));

    def test_decode_08(self):
        num = 28821928557109857 
        self.assertEqual("abc-def", azatom.decode(num));

    def test_decode_09(self):
        try: 
            azatom.decode(937) #invalid azatom value
        except AzosError as error:
             self.assertEqual("decode(937)", error.frm); # error frm field should contain method(arg) name
        else:
            self.fail("Missing AzosError for invalid azatom int")

    def test_encode_01(self):
        self.assertEqual(28821928557109857, azatom.encode("abc-def"));

    def test_encode_02(self):
        self.assertEqual(0, azatom.encode(None));
        self.assertEqual(0, azatom.encode(""));

    def test_encode_03(self):
        try: 
            azatom.encode("too long of a string") 
        except AzosError as error:
            self.assertEqual("encode(`too long of a string`)", error.frm); 
        else:
            self.fail("Missing AzosError for invalid azatom string length")

    def test_encode_04(self):
       try: 
           azatom.encode("^ba d") 
       except AzosError as error:
           self.assertEqual("encode(`^ba d`)", error.frm); 
       else:
           self.fail("Missing AzosError for invalid azatom string chars")


if __name__ == '__main__':
    unittest.main()