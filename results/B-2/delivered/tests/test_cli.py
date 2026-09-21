import os
import stat
import subprocess
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_cli(*args, input_bytes=None):
    return subprocess.run(
        [sys.executable, "-m", "kvstore", *args],
        cwd=_REPO_ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class TestSuperficieDeComandos(unittest.TestCase):
    def test_set_e_get_ida_e_volta(self):
        with tempfile.TemporaryDirectory() as store_dir:
            resultado_set = _run_cli(store_dir, "set", "foo", "bar")
            self.assertEqual(resultado_set.returncode, 0)

            resultado_get = _run_cli(store_dir, "get", "foo")
            self.assertEqual(resultado_get.returncode, 0)
            self.assertEqual(resultado_get.stdout, b"bar")

    def test_comando_desconhecido_sai_2_sem_tocar_no_diretorio(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "novo")
            resultado = _run_cli(store_dir, "nao-existe")
            self.assertEqual(resultado.returncode, 2)
            self.assertEqual(resultado.stdout, b"")
            self.assertFalse(os.path.exists(store_dir))

    def test_numero_de_argumentos_errado_sai_2_sem_tocar_no_diretorio(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "novo")
            resultado_set_sem_valor = _run_cli(store_dir, "set", "foo")
            self.assertEqual(resultado_set_sem_valor.returncode, 2)
            self.assertFalse(os.path.exists(store_dir))

            resultado_list_com_extra = _run_cli(store_dir, "list", "extra")
            self.assertEqual(resultado_list_com_extra.returncode, 2)
            self.assertFalse(os.path.exists(store_dir))


class TestGetEscreveValorSemAlteralo(unittest.TestCase):
    def test_valor_volta_byte_a_byte(self):
        with tempfile.TemporaryDirectory() as store_dir:
            valor = "linha 1\nlinha 2 com acentuação: ção, ã, é\n  espaços nas pontas  "
            resultado_set = _run_cli(store_dir, "set", "k", valor)
            self.assertEqual(resultado_set.returncode, 0)

            resultado_get = _run_cli(store_dir, "get", "k")
            self.assertEqual(resultado_get.returncode, 0)
            self.assertEqual(resultado_get.stdout, valor.encode("utf-8"))

    def test_chave_ausente_stdout_vazio_e_exit_1(self):
        with tempfile.TemporaryDirectory() as store_dir:
            resultado = _run_cli(store_dir, "get", "nunca-gravada")
            self.assertEqual(resultado.returncode, 1)
            self.assertEqual(resultado.stdout, b"")
            self.assertNotEqual(resultado.stderr, b"")


class TestSetAceitaStdin(unittest.TestCase):
    def test_valor_grande_lido_de_stdin(self):
        with tempfile.TemporaryDirectory() as store_dir:
            valor = ("x" * (1024 * 1024) + "\n") * 3
            valor_bytes = valor.encode("utf-8")

            resultado_set = _run_cli(store_dir, "set", "grande", "-", input_bytes=valor_bytes)
            self.assertEqual(resultado_set.returncode, 0)

            resultado_get = _run_cli(store_dir, "get", "grande")
            self.assertEqual(resultado_get.returncode, 0)
            self.assertEqual(resultado_get.stdout, valor_bytes)

    def test_valor_literal_continua_funcionando(self):
        with tempfile.TemporaryDirectory() as store_dir:
            resultado_set = _run_cli(store_dir, "set", "k", "valor-literal")
            self.assertEqual(resultado_set.returncode, 0)
            resultado_get = _run_cli(store_dir, "get", "k")
            self.assertEqual(resultado_get.stdout, b"valor-literal")


class TestCodigosDeSaida(unittest.TestCase):
    def test_chave_invalida_sai_2_e_nao_grava(self):
        with tempfile.TemporaryDirectory() as store_dir:
            resultado = _run_cli(store_dir, "set", "", "v")
            self.assertEqual(resultado.returncode, 2)
            self.assertNotEqual(resultado.stderr, b"")
            self.assertEqual(_run_cli(store_dir, "list").stdout, b"")

    @unittest.skipIf(os.geteuid() == 0, "root ignora permissão de escrita")
    def test_falha_de_io_por_permissao_negada_sai_3(self):
        with tempfile.TemporaryDirectory() as store_dir:
            somente_leitura = stat.S_IRUSR | stat.S_IXUSR
            os.chmod(store_dir, somente_leitura)
            try:
                resultado = _run_cli(store_dir, "set", "k", "v")
                self.assertEqual(resultado.returncode, 3)
                self.assertNotEqual(resultado.stderr, b"")
            finally:
                os.chmod(store_dir, stat.S_IRWXU)

    def test_corrupcao_real_do_arquivo_sai_3_em_vez_de_esconder_o_erro(self):
        with tempfile.TemporaryDirectory() as store_dir:
            resultado_set = _run_cli(store_dir, "set", "k", "v")
            self.assertEqual(resultado_set.returncode, 0)

            db_path = os.path.join(store_dir, "kvstore.sqlite3")
            with open(db_path, "r+b") as arquivo:
                arquivo.seek(0)
                arquivo.write(b"\xff" * 4096)

            resultado_get = _run_cli(store_dir, "get", "k")
            self.assertEqual(resultado_get.returncode, 3)
            self.assertEqual(resultado_get.stdout, b"")
            self.assertNotEqual(resultado_get.stderr, b"")

            resultado_list = _run_cli(store_dir, "list")
            self.assertEqual(resultado_list.returncode, 3)
            self.assertEqual(resultado_list.stdout, b"")
            self.assertNotEqual(resultado_list.stderr, b"")


class TestDelIdempotenteEListVazio(unittest.TestCase):
    def test_del_de_chave_inexistente_sai_0(self):
        with tempfile.TemporaryDirectory() as store_dir:
            resultado = _run_cli(store_dir, "del", "nunca-existiu")
            self.assertEqual(resultado.returncode, 0)

    def test_list_em_store_vazio_sai_0_com_stdout_vazio(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "nunca-criado")
            resultado = _run_cli(store_dir, "list")
            self.assertEqual(resultado.returncode, 0)
            self.assertEqual(resultado.stdout, b"")


if __name__ == "__main__":
    unittest.main()
