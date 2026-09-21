import unittest

import fidx


class TestPacote(unittest.TestCase):
    def test_pacote_importa(self):
        self.assertIsNotNone(fidx)


if __name__ == "__main__":
    unittest.main()
