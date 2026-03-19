import importlib
import unittest


class ImportTests(unittest.TestCase):
    def test_import(self):
        mod = importlib.import_module("tigrcorn")
        self.assertTrue(hasattr(mod, "run"))


if __name__ == "__main__":
    unittest.main()
