import os
import subprocess
import sys
import tempfile
import unittest


def arvore(raiz: str, arquivos: dict[str, str]) -> None:
    for caminho, conteudo in arquivos.items():
        full = os.path.join(raiz, caminho)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(conteudo)


def roda(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "fidx", *args],
        capture_output=True,
        text=True,
    )


class TestE2E(unittest.TestCase):
    def test_e2e001_index_depois_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "nada aqui", "sub/a.md": "orcamento aqui", "b.md": "nada tambem"})

            resultado = roda(tmp, "index")
            self.assertEqual(resultado.returncode, 0)
            self.assertEqual(
                resultado.stdout.strip(),
                "fidx: 3 arquivos, 3 reindexados, 0 removidos",
            )

            resultado = roda(tmp, "search", "orcamento")
            self.assertEqual(resultado.returncode, 0)
            self.assertEqual(
                resultado.stdout.strip().splitlines(),
                [os.path.join(tmp, "sub/a.md")],
            )

    def test_e2e002_sem_ocorrencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento"})
            roda(tmp, "index")

            resultado = roda(tmp, "search", "jabuticaba")
            self.assertEqual(resultado.returncode, 1)
            self.assertEqual(resultado.stdout, "")

    def test_e2e003_search_sem_index_previo(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = roda(tmp, "search", "orcamento")
            self.assertEqual(resultado.returncode, 2)
            self.assertIn("fidx: indice nao encontrado:", resultado.stderr)
            self.assertIn(f"fidx: rode primeiro: python3 -m fidx {tmp} index", resultado.stderr)

    def test_e2e004_diretorio_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = os.path.join(tmp, "nao-existe")

            resultado = roda(alvo, "index")
            self.assertEqual(resultado.returncode, 2)
            self.assertIn(f"fidx: nao e um diretorio: {alvo}", resultado.stderr)

            resultado = roda(alvo, "search", "orcamento")
            self.assertEqual(resultado.returncode, 2)
            self.assertIn(f"fidx: nao e um diretorio: {alvo}", resultado.stderr)

    def test_e2e005_varios_tokens_e_argumento_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento 2026", "b.md": "orcamento sem ano"})
            roda(tmp, "index")

            resultado = roda(tmp, "search", "orcamento", "2026")
            self.assertEqual(resultado.returncode, 0)
            self.assertEqual(
                resultado.stdout.strip().splitlines(),
                [os.path.join(tmp, "a.md")],
            )

    def test_e2e006_duas_rodadas_sem_alteracao(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento", "b.md": "outra coisa"})

            primeira = roda(tmp, "index")
            self.assertEqual(primeira.returncode, 0)

            segunda = roda(tmp, "index")
            self.assertEqual(segunda.returncode, 0)
            self.assertEqual(
                segunda.stdout.strip(),
                "fidx: 2 arquivos, 0 reindexados, 0 removidos",
            )

    def test_e2e007_termo_sem_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento"})
            roda(tmp, "index")

            resultado = roda(tmp, "search", "---")
            self.assertEqual(resultado.returncode, 2)
            self.assertIn("fidx: termo sem token indexavel: '---'", resultado.stderr)

    def test_e2e008_uso_invalido(self):
        resultado = roda()
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("fidx: uso: python3 -m fidx <diretorio> index", resultado.stderr)
        self.assertIn("python3 -m fidx <diretorio> search <termo>", resultado.stderr)

        with tempfile.TemporaryDirectory() as tmp:
            resultado = roda(tmp, "invalido")
            self.assertEqual(resultado.returncode, 2)
            self.assertIn("fidx: uso:", resultado.stderr)

            resultado = roda(tmp, "search")
            self.assertEqual(resultado.returncode, 2)
            self.assertIn("fidx: uso:", resultado.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root ignora bit de permissao")
    def test_e2e009_pasta_somente_leitura(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o500)
            try:
                resultado = roda(tmp, "index")
            finally:
                os.chmod(tmp, 0o700)
            self.assertEqual(resultado.returncode, 2)
            self.assertIn("fidx: nao foi possivel criar o indice:", resultado.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, ".fidx.sqlite3")))


if __name__ == "__main__":
    unittest.main()
