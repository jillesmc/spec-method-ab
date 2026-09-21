import os
import subprocess
import sys
import tempfile
import unittest

import fidx


class TestPacote(unittest.TestCase):
    def test_pacote_importa(self):
        self.assertIsNotNone(fidx)


class TestFumacaCliSubprocesso(unittest.TestCase):
    """Roda `python -m fidx` como processo real, sem chamar `main()` diretamente."""

    def test_index_e_search_via_python_dash_m(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "nota.txt"), "w") as f:
                f.write("orcamento anual")

            index = subprocess.run(
                [sys.executable, "-m", "fidx", tmp, "index"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(index.returncode, 0)
            self.assertIn("reprocessados=1", index.stdout)

            busca = subprocess.run(
                [sys.executable, "-m", "fidx", tmp, "search", "orcamento"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(busca.returncode, 0)
            self.assertEqual(busca.stdout.splitlines(), ["nota.txt"])


if __name__ == "__main__":
    unittest.main()
