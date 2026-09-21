import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _rodar(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "fidx", *args],
        capture_output=True,
        text=True,
    )


class TestCLI(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)

    def _escrever(self, nome: str, conteudo: str) -> Path:
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def test_jornada_completa_index_e_search(self) -> None:
        """E2E-001"""
        self._escrever("orcamento-q3.txt", "orcamento do terceiro trimestre")
        self._escrever("relatorios/2026-01.txt", "orcamento fechado de janeiro")

        resultado_index = _rodar(str(self.raiz), "index")
        self.assertEqual(resultado_index.returncode, 0)
        self.assertTrue(resultado_index.stdout.startswith("2 arquivos:"))
        for parte in ("novos", "alterados", "removidos", "inalterados", "ignorados"):
            self.assertIn(parte, resultado_index.stdout)

        resultado_search = _rodar(str(self.raiz), "search", "orcamento")
        self.assertEqual(resultado_search.returncode, 0)
        self.assertEqual(
            resultado_search.stdout, "orcamento-q3.txt\nrelatorios/2026-01.txt\n"
        )

    def test_busca_com_duas_palavras_e_conjuncao(self) -> None:
        """E2E-006"""
        self._escrever("a.txt", "relatorio mensal completo")
        self._escrever("b.txt", "relatorio anual")
        _rodar(str(self.raiz), "index")

        resultado = _rodar(str(self.raiz), "search", "relatorio mensal")

        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(resultado.stdout, "a.txt\n")

    def test_busca_insensivel_a_caixa(self) -> None:
        """E2E-007"""
        self._escrever("nota.txt", "Orçamento aprovado")
        _rodar(str(self.raiz), "index")

        resultado = _rodar(str(self.raiz), "search", "orçamento")

        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(resultado.stdout, "nota.txt\n")

    def test_segunda_rodada_index_sem_mudanca(self) -> None:
        """E2E-008"""
        self._escrever("a.txt", "um")
        self._escrever("b.txt", "dois")
        _rodar(str(self.raiz), "index")

        resultado = _rodar(str(self.raiz), "index")

        self.assertEqual(resultado.returncode, 0)
        self.assertIn("0 novos, 0 alterados, 0 removidos", resultado.stdout)
        self.assertIn("2 inalterados", resultado.stdout)

    def test_busca_sem_resultado_stdout_vazio_saida_1(self) -> None:
        """E2E-002"""
        self._escrever("a.txt", "orcamento anual")
        _rodar(str(self.raiz), "index")

        resultado = _rodar(str(self.raiz), "search", "jabuticaba")

        self.assertEqual(resultado.stdout, "")
        self.assertEqual(resultado.returncode, 1)

    def test_busca_antes_de_qualquer_index(self) -> None:
        """E2E-003"""
        resultado = _rodar(str(self.raiz), "search", "orcamento")

        self.assertEqual(resultado.stdout, "")
        self.assertIn("indice nao encontrado", resultado.stderr)
        self.assertIn(f"python -m fidx {self.raiz} index", resultado.stderr)
        self.assertEqual(resultado.returncode, 2)

    def test_caminho_inexistente_em_index_e_search(self) -> None:
        """E2E-004"""
        inexistente = self.raiz / "naoexiste"

        resultado_index = _rodar(str(inexistente), "index")
        self.assertEqual(resultado_index.stdout, "")
        self.assertIn("nao e um diretorio", resultado_index.stderr)
        self.assertIn(str(inexistente), resultado_index.stderr)
        self.assertEqual(resultado_index.returncode, 2)

        resultado_search = _rodar(str(inexistente), "search", "orcamento")
        self.assertEqual(resultado_search.stdout, "")
        self.assertIn("nao e um diretorio", resultado_search.stderr)
        self.assertEqual(resultado_search.returncode, 2)

        self.assertFalse(inexistente.exists())

    def test_indice_corrompido_reporta_erro_real_em_vez_de_permission_denied(self) -> None:
        """Regression for reviews-001/issue_001."""
        self._escrever(".fidx.sqlite3", "isto nao e um banco sqlite valido")

        resultado = _rodar(str(self.raiz), "index")

        self.assertEqual(resultado.returncode, 2)
        self.assertIn("file is not a database", resultado.stderr)
        self.assertNotIn("Permission denied", resultado.stderr)

    @unittest.skipIf(os.geteuid() == 0, "chmod nao restringe escrita como root")
    def test_pasta_sem_permissao_de_escrita_reporta_permission_denied(self) -> None:
        """Regression for reviews-005/issue_001."""
        os.chmod(self.raiz, 0o555)
        try:
            resultado = _rodar(str(self.raiz), "index")
        finally:
            os.chmod(self.raiz, 0o755)

        self.assertEqual(resultado.stdout, "")
        self.assertEqual(
            resultado.stderr.strip(),
            f"fidx: nao foi possivel gravar o indice em {self.raiz}: Permission denied",
        )
        self.assertEqual(resultado.returncode, 2)

    def test_search_com_indice_corrompido_reporta_erro_real_e_saida_2(self) -> None:
        """Regression for reviews-002/issue_001."""
        self._escrever(".fidx.sqlite3", "isto nao e um banco sqlite valido")

        resultado = _rodar(str(self.raiz), "search", "orcamento")

        self.assertEqual(resultado.stdout, "")
        self.assertEqual(resultado.returncode, 2)
        self.assertIn("file is not a database", resultado.stderr)

    def test_subcomando_ausente_ou_desconhecido(self) -> None:
        """E2E-005"""
        resultado_ausente = _rodar(str(self.raiz))
        self.assertEqual(resultado_ausente.returncode, 2)
        self.assertIn("usage:", resultado_ausente.stderr)

        resultado_desconhecido = _rodar(str(self.raiz), "listar")
        self.assertEqual(resultado_desconhecido.returncode, 2)
        self.assertIn("usage:", resultado_desconhecido.stderr)


if __name__ == "__main__":
    unittest.main()
