import unittest

import kvstore


class TestPacote(unittest.TestCase):
    def test_pacote_importa(self):
        self.assertIsNotNone(kvstore)


if __name__ == "__main__":
    unittest.main()
