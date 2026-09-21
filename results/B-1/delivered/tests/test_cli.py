import os
import subprocess
import sys
import tempfile
import unittest

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _executar(diretorio, *args, entrada=None):
    ambiente = dict(os.environ, PYTHONPATH=_RAIZ)
    return subprocess.run(
        [sys.executable, "-m", "kvstore", diretorio, *args],
        input=entrada,
        capture_output=True,
        cwd=_RAIZ,
        env=ambiente,
    )


class TestCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.diretorio = self._tmp.name

    def test_set_grava_e_get_devolve_exatamente_os_mesmos_bytes(self):
        resultado_set = _executar(self.diretorio, "set", "chave", "valor")
        self.assertEqual(resultado_set.returncode, 0)
        resultado_get = _executar(self.diretorio, "get", "chave")
        self.assertEqual(resultado_get.returncode, 0)
        self.assertEqual(resultado_get.stdout, b"valor")

    def test_get_chave_ausente_sai_com_1_e_nada_em_stdout(self):
        resultado = _executar(self.diretorio, "get", "inexistente")
        self.assertEqual(resultado.returncode, 1)
        self.assertEqual(resultado.stdout, b"")
        self.assertNotEqual(resultado.stderr, b"")

    def test_del_remove_e_get_depois_sai_com_1(self):
        _executar(self.diretorio, "set", "x", "valor")
        resultado_del = _executar(self.diretorio, "del", "x")
        self.assertEqual(resultado_del.returncode, 0)
        resultado_get = _executar(self.diretorio, "get", "x")
        self.assertEqual(resultado_get.returncode, 1)

    def test_del_chave_ausente_sai_com_1(self):
        resultado = _executar(self.diretorio, "del", "inexistente")
        self.assertEqual(resultado.returncode, 1)

    def test_list_enumera_em_ordem(self):
        _executar(self.diretorio, "set", "b", "1")
        _executar(self.diretorio, "set", "a", "2")
        _executar(self.diretorio, "set", "c", "3")
        resultado = _executar(self.diretorio, "list")
        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(resultado.stdout, b"a\nb\nc\n")

    def test_comando_desconhecido_sai_com_2(self):
        resultado = _executar(self.diretorio, "comando-invalido")
        self.assertEqual(resultado.returncode, 2)
        self.assertEqual(resultado.stdout, b"")
        self.assertNotEqual(resultado.stderr, b"")

    def test_argumentos_faltando_sai_com_2(self):
        resultado = _executar(self.diretorio, "set")
        self.assertEqual(resultado.returncode, 2)
        self.assertEqual(resultado.stdout, b"")
        self.assertNotEqual(resultado.stderr, b"")

    def test_chave_invalida_sai_com_2_e_nao_cria_arquivo(self):
        resultado = _executar(self.diretorio, "set", "linha\num", "valor")
        self.assertEqual(resultado.returncode, 2)
        self.assertNotEqual(resultado.stderr, b"")
        self.assertFalse(os.path.isdir(self.diretorio) and os.listdir(self.diretorio))

    def test_valor_grande_por_stdin(self):
        valor = ("conteudo-" * 1_200_000).encode("utf-8")
        self.assertGreater(len(valor), 10 * 1024 * 1024)
        resultado_set = _executar(self.diretorio, "set", "grande", entrada=valor)
        self.assertEqual(resultado_set.returncode, 0)
        resultado_get = _executar(self.diretorio, "get", "grande")
        self.assertEqual(resultado_get.returncode, 0)
        self.assertEqual(resultado_get.stdout, valor)

    def test_valor_vazio_por_argumento(self):
        _executar(self.diretorio, "set", "vazio", "")
        resultado = _executar(self.diretorio, "get", "vazio")
        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(resultado.stdout, b"")

    def test_diretorio_inexistente_em_get_sai_com_1(self):
        inexistente = os.path.join(self.diretorio, "nao-criado")
        resultado = _executar(inexistente, "get", "qualquer")
        self.assertEqual(resultado.returncode, 1)
        self.assertFalse(os.path.isdir(inexistente))

    def test_diretorio_inexistente_em_list_sai_com_0_e_stdout_vazio(self):
        inexistente = os.path.join(self.diretorio, "nao-criado")
        resultado = _executar(inexistente, "list")
        self.assertEqual(resultado.returncode, 0)
        self.assertEqual(resultado.stdout, b"")
        self.assertFalse(os.path.isdir(inexistente))

    def test_primeira_gravacao_cria_diretorio_via_cli(self):
        novo = os.path.join(self.diretorio, "novo-store")
        self.assertFalse(os.path.isdir(novo))
        resultado = _executar(novo, "set", "chave", "valor")
        self.assertEqual(resultado.returncode, 0)
        self.assertTrue(os.path.isdir(novo))


if __name__ == "__main__":
    unittest.main()
