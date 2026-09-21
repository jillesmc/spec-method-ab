import os
import subprocess
import sys
import tempfile
import unittest

from tests import apoio

_USAGE = (
    b"uso: python -m kvstore <diretorio> <comando> [argumentos]\n"
    b"\n"
    b"comandos:\n"
    b"  set <chave> <valor>   grava o valor; use - no lugar do valor para ler do stdin\n"
    b"  get <chave>           escreve o valor no stdout, sem newline extra\n"
    b"  del <chave>           remove a chave\n"
    b"  list                  lista as chaves, uma por linha\n"
    b"\n"
    b"codigos de saida: 0 ok, 1 chave nao encontrada, 2 uso incorreto, 3 erro do store\n"
)


def _run(args, input_bytes=None):
    return subprocess.run(
        [sys.executable, "-m", "kvstore", *args],
        cwd=apoio.raiz_repositorio(),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class TestCaminhoFeliz(unittest.TestCase):
    def test_e2e001_caminho_de_ouro(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")

            r = _run([d, "set", "posicao", "1042"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")

            r = _run([d, "set", "modo", "rapido"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")

            r = _run([d, "list"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"modo\nposicao\n")

            self.assertEqual(
                sorted(os.listdir(d)),
                ["kvstore.db", "kvstore.db-shm", "kvstore.db-wal"],
            )

            r = _run([d, "get", "posicao"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"1042")

            r = _run([d, "del", "modo"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")

            r = _run([d, "list"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"posicao\n")


class TestSuperficieDeFalha(unittest.TestCase):
    def test_e2e002_get_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            r = _run([d, "get", "ausente"])
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.stderr, b"kvstore: chave nao encontrada: ausente\n")

    def test_e2e003_del_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            r = _run([d, "del", "ausente"])
            self.assertEqual(r.returncode, 1)
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.stderr, b"kvstore: chave nao encontrada: ausente\n")

    def test_e2e004_uso_e_comando_desconhecido(self):
        r = _run([])
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, _USAGE)
        self.assertEqual(r.stderr, b"")

        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            r = _run([d, "dump"])
            self.assertEqual(r.returncode, 2)
            self.assertEqual(r.stderr, b"kvstore: comando desconhecido: dump\n")

    def test_e2e005_chave_invalida(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")

            r = _run([d, "set", "", "valor"])
            self.assertEqual(r.returncode, 2)
            self.assertEqual(r.stderr, b"kvstore: chave vazia\n")

            r = _run([d, "set", "a\nb", "valor"])
            self.assertEqual(r.returncode, 2)
            self.assertEqual(
                r.stderr, b"kvstore: chave nao pode conter quebra de linha ou NUL\n"
            )

            r = _run([d, "list"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")


class TestFidelidadeDeValor(unittest.TestCase):
    def test_e2e006_valor_grande_via_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            entrada = os.urandom(2 * 1024 * 1024 - 7).hex().encode("ascii")[
                : 2 * 1024 * 1024
            ]

            r = _run([d, "set", "relatorio", "-"], input_bytes=entrada)
            self.assertEqual(r.returncode, 0)

            r = _run([d, "get", "relatorio"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, entrada)

    def test_e2e007_valor_com_quebras_de_linha(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            entrada = b"com\nquebras\n"

            r = _run([d, "set", "texto", "-"], input_bytes=entrada)
            self.assertEqual(r.returncode, 0)

            r = _run([d, "get", "texto"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, entrada)


class TestArmazenamentosVaziosOuIncomuns(unittest.TestCase):
    def test_e2e008_diretorio_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "nao-existe")

            r = _run([d, "list"])
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")

            r = _run([d, "get", "k"])
            self.assertEqual(r.returncode, 1)

            self.assertFalse(os.path.exists(d))

    def test_e2e009_chaves_incomuns_listadas_em_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            chaves = ["com espaco", "acentuação", "日本語"]
            for chave in chaves:
                r = _run([d, "set", chave, "v"])
                self.assertEqual(r.returncode, 0)

            r = _run([d, "list"])
            self.assertEqual(r.returncode, 0)
            esperado = "\n".join(sorted(chaves)) + "\n"
            self.assertEqual(r.stdout, esperado.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
