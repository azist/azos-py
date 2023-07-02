import sys
import unittest

sys.path.append("../src/azos")
import atom

class AtomTests(unittest.TestCase):

    def test_decode_01(self):
        num = 478560413032 #hello
        self.assertEqual("hello", atom.decode(num));

    def test_decode_02(self):
        num = 7956003944985229683 #syslogin
        self.assertEqual("syslogin", atom.decode(num));

    def test_decode_03(self):
        num = 97 #a
        self.assertEqual("a", atom.decode(num));

    def test_decode_04(self):
        num = 98 #b
        self.assertEqual("b", atom.decode(num));

    def test_decode_05(self):
        num = 0 #zero
        self.assertEqual("", atom.decode(num));

    def test_decode_06(self):
        num = 4123376657429507385  
        self.assertEqual("9-9-9-99", atom.decode(num));

    def test_decode_07(self):
        num = 28821929395970657
        self.assertEqual("abc_def", atom.decode(num));

    def test_decode_08(self):
        num = 28821928557109857 
        self.assertEqual("abc-def", atom.decode(num));

    def test_decode_09(self):
        try: 
            atom.decode(937) #invalid atom value
        except atom.AzosError as error:
             self.assertEqual("decode(937)", error.frm); # error frm field should contain method(arg) name
        else:
            self.fail("Missing AzosError for invalid atom int")



unittest.main()