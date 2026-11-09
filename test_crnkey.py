import unittest

import crnkey as c


class ParseCrns(unittest.TestCase):
    def test_separators_and_comments(self):
        text = "# header\n12345\n23456 34567, 45678  # trailing\n\n"
        self.assertEqual(c.parse_crns(text),
                         ["12345", "23456", "34567", "45678"])

    def test_empty(self):
        self.assertEqual(c.parse_crns("# nothing\n"), [])


class ValidateCrns(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(c.validate_crns(["12345", "23456"]), ([], []))

    def test_non_digits_is_error(self):
        errors, _ = c.validate_crns(["12a45"])
        self.assertEqual(len(errors), 1)

    def test_unicode_digits_rejected(self):
        errors, _ = c.validate_crns(["١٢٣٤٥"])
        self.assertTrue(errors)

    def test_odd_length_only_warns(self):
        errors, warnings = c.validate_crns(["1234", "123456"])
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)

    def test_empty_is_error(self):
        errors, _ = c.validate_crns([])
        self.assertTrue(errors)

    def test_duplicate_warns(self):
        errors, warnings = c.validate_crns(["12345", "12345"])
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)


class BuildSequence(unittest.TestCase):
    def test_tab_after_every_crn_then_enter(self):
        self.assertEqual(
            c.build_sequence(["12", "34"]),
            ["1", "2", "TAB", "3", "4", "TAB", "ENTER"])

    def test_single(self):
        self.assertEqual(c.build_sequence(["9"]), ["9", "TAB", "ENTER"])


class ParseKeybind(unittest.TestCase):
    def test_default(self):
        self.assertEqual(c.parse_keybind("Ctrl+Alt+R"),
                         0x04000000 | 0x08000000 | ord("R"))

    def test_case_insensitive(self):
        self.assertEqual(c.parse_keybind("ctrl+alt+r"),
                         c.parse_keybind("Ctrl+Alt+R"))

    def test_function_key(self):
        self.assertEqual(c.parse_keybind("Ctrl+F5"), 0x04000000 | 0x01000034)

    def test_bad_input(self):
        for bad in ("R", "Foo+R", "Ctrl+Enter", "Ctrl+"):
            with self.assertRaises(ValueError, msg=bad):
                c.parse_keybind(bad)


if __name__ == "__main__":
    unittest.main()
