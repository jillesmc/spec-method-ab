import contextlib
import io
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import fidx
import fidx.__main__ as cli


def _rodar(argv):
    saida, erro = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
        codigo = cli.main(argv)
    return codigo, saida.getvalue(), erro.getvalue()


class TestArgparseContrato(unittest.TestCase):
    def test_subcomando_desconhecido_sai_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stderr(io.StringIO()) as erro:
                cli.main([tmp, "apagar"])
            self.assertEqual(ctx.exception.code, 2)
            self.assertTrue(erro.getvalue())

    def test_termo_faltando_no_search_sai_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as ctx, contextlib.redirect_stderr(io.StringIO()) as erro:
                cli.main([tmp, "search"])
            self.assertEqual(ctx.exception.code, 2)
            self.assertTrue(erro.getvalue())


class TestIndexCli(unittest.TestCase):
    def test_index_imprime_resumo_e_sai_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "nota.txt"), "w") as f:
                f.write("conteudo")

            codigo, saida, erro = _rodar([tmp, "index"])

            self.assertEqual(codigo, 0)
            self.assertEqual(erro, "")
            self.assertIn("reprocessados=1", saida)
            self.assertIn("inalterados=0", saida)
            self.assertIn("removidos=0", saida)


class TestSearchCli(unittest.TestCase):
    def test_search_com_resultado_sai_0_um_path_por_linha(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.txt"), "w") as f:
                f.write("orcamento")
            with open(os.path.join(tmp, "b.txt"), "w") as f:
                f.write("orcamento tambem")
            fidx.index(tmp)

            codigo, saida, erro = _rodar([tmp, "search", "orcamento"])

            self.assertEqual(codigo, 0)
            self.assertEqual(erro, "")
            self.assertEqual(saida.splitlines(), ["a.txt", "b.txt"])

    def test_search_sem_resultado_sai_1_e_stdout_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.txt"), "w") as f:
                f.write("conteudo")
            fidx.index(tmp)

            codigo, saida, erro = _rodar([tmp, "search", "inexistente"])

            self.assertEqual(codigo, 1)
            self.assertEqual(saida, "")


class TestErrosOperacionais(unittest.TestCase):
    def test_diretorio_inexistente_sai_2_com_stderr(self):
        codigo, saida, erro = _rodar(["/nao/existe/de/verdade", "index"])

        self.assertEqual(codigo, 2)
        self.assertEqual(saida, "")
        self.assertTrue(erro)

    def test_search_em_diretorio_nunca_indexado_sai_2_sem_varrer(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.txt"), "w") as f:
                f.write("conteudo")

            codigo, saida, erro = _rodar([tmp, "search", "conteudo"])

            self.assertEqual(codigo, 2)
            self.assertEqual(saida, "")
            self.assertIn("index", erro)
            self.assertFalse(os.path.exists(os.path.join(tmp, ".fidx")))

    def test_termo_com_mais_de_uma_palavra_sai_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            fidx.index(tmp)

            codigo, saida, erro = _rodar([tmp, "search", "nota fiscal"])

            self.assertEqual(codigo, 2)
            self.assertEqual(saida, "")
            self.assertTrue(erro)

    def test_termo_vazio_sai_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            fidx.index(tmp)

            codigo, saida, erro = _rodar([tmp, "search", "--", "---"])

            self.assertEqual(codigo, 2)
            self.assertTrue(erro)


class TestPastaSomenteLeitura(unittest.TestCase):
    def test_pasta_somente_leitura_sai_2_sem_stacktrace(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp, 0o555)
            try:
                codigo, saida, erro = _rodar([tmp, "index"])
            finally:
                os.chmod(tmp, 0o755)

            self.assertEqual(codigo, 2)
            self.assertEqual(saida, "")
            self.assertNotIn("Traceback", erro)
            self.assertIn(os.path.join(tmp, ".fidx"), erro)


class TestBancoTravado(unittest.TestCase):
    def test_indice_travado_por_rodada_concorrente_sai_2_sem_stacktrace(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.txt"), "w") as f:
                f.write("conteudo")
            fidx.index(tmp)

            banco = os.path.join(tmp, ".fidx", "index.sqlite3")
            travador = sqlite3.connect(banco)
            travador.execute("BEGIN EXCLUSIVE")
            try:
                original_connect = sqlite3.connect

                def _connect_timeout_curto(caminho, timeout=30, **kwargs):
                    return original_connect(caminho, timeout=0.05, **kwargs)

                with mock.patch("fidx.sqlite3.connect", side_effect=_connect_timeout_curto):
                    codigo, saida, erro = _rodar([tmp, "index"])
            finally:
                travador.rollback()
                travador.close()

            self.assertEqual(codigo, 2)
            self.assertEqual(saida, "")
            self.assertNotIn("Traceback", erro)
            self.assertTrue(erro)


if __name__ == "__main__":
    unittest.main()
