import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from kvstore import Store, StoreBusy
from tests import apoio

_PREAMBULO = (
    "import os, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from kvstore import Store\n"
    "directory = sys.argv[2]\n"
    "write_fd = int(sys.argv[3])\n"
)


def _run_cli(args, input_bytes=None, timeout=None):
    return subprocess.run(
        [sys.executable, "-m", "kvstore", *args],
        cwd=apoio.raiz_repositorio(),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


class TestValoresGrandes(unittest.TestCase):
    def test_ut026_valor_de_8mib_ida_e_volta(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            tamanho = 8 * 1024 * 1024
            valor = ("conteudo-" * (tamanho // 9 + 1))[:tamanho]
            self.assertEqual(len(valor), tamanho)
            with Store(d) as s:
                s.set("grande", valor)
                lido = s.get("grande")
            self.assertEqual(lido, valor)
            self.assertEqual(len(lido), len(valor))


class TestContencaoDeEscrita(unittest.TestCase):
    def test_ut027_busy_apos_timeout_e_sucesso_apos_liberar(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("existente", "1")

            db_path = os.path.join(d, "kvstore.db")
            bloqueador = sqlite3.connect(db_path, isolation_level=None, timeout=0)
            bloqueador.execute("BEGIN IMMEDIATE")
            try:
                s2 = Store(d, timeout=0.1)
                with self.assertRaises(StoreBusy):
                    s2.set("k", "v")

                verificador = sqlite3.connect(db_path, isolation_level=None, timeout=0)
                try:
                    linha = verificador.execute(
                        "SELECT v FROM kv WHERE k = ?", ("k",)
                    ).fetchone()
                finally:
                    verificador.close()
                self.assertIsNone(linha, "a tentativa que levantou StoreBusy nao devia ter escrito nada")
            finally:
                bloqueador.execute("ROLLBACK")
                bloqueador.close()

            s2.set("k", "v")
            self.assertEqual(s2.get("k"), "v")
            s2.close()

    def test_ut028_busy_timeout_e_aplicado_em_milissegundos(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s = Store(d, timeout=2.5)
            s.set("k", "v")
            valor = s._conn.execute("PRAGMA busy_timeout").fetchone()[0]
            s.close()
            self.assertEqual(valor, 2500)


class TestLeiturasNaoModificam(unittest.TestCase):
    def test_ut029_leitura_nao_modifica_kvstore_db_em_store_fechado_normalmente(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("a", "1")
                s.set("b", "2")

            db_path = os.path.join(d, "kvstore.db")
            antes = os.stat(db_path)

            s2 = Store(d)
            self.assertEqual(s2.get("a"), "1")
            self.assertEqual(s2.list(), ["a", "b"])
            depois = os.stat(db_path)
            s2.close()

            self.assertEqual(antes.st_size, depois.st_size)
            self.assertEqual(antes.st_mtime_ns, depois.st_mtime_ns)

    def test_leitura_apos_writer_morto_ainda_retorna_o_valor_acked(self):
        # Nao e' o mesmo caso do UT-029: aqui o ultimo escritor foi morto sem
        # fechar a conexao, entao a proxima abertura recupera o WAL, e recuperacao
        # e' escrita (Invariante de Seguranca 6 nao cobre recuperacao). Por isso
        # este caso nao afirma igualdade de tamanho/mtime do kvstore.db - so que a
        # leitura continua correta.
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            corpo = (
                "s = Store(directory)\n"
                "s.set('k', 'v')\n"
                "os.write(write_fd, b'\\x01')\n"
                "import time\n"
                "while True:\n"
                "    time.sleep(1)\n"
            )
            apoio.matar_apos_ack(_PREAMBULO + corpo, [apoio.raiz_repositorio(), d])

            s = Store(d)
            self.assertEqual(s.get("k"), "v")
            s.close()


class TestProcessosConcorrentes(unittest.TestCase):
    def test_it006_oito_escritores_concorrentes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            n = 8
            procs = [
                subprocess.Popen(
                    [sys.executable, "-m", "kvstore", d, "set", f"chave-{i}", f"valor-{i}"],
                    cwd=apoio.raiz_repositorio(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                for i in range(n)
            ]
            saidas = [p.communicate(timeout=15) for p in procs]

            for i, (p, (_out, err)) in enumerate(zip(procs, saidas)):
                self.assertEqual(p.returncode, 0, f"processo {i} falhou: {err!r}")

            s = Store(d)
            esperadas = sorted(f"chave-{i}" for i in range(n))
            self.assertEqual(s.list(), esperadas)
            for i in range(n):
                self.assertEqual(s.get(f"chave-{i}"), f"valor-{i}")
            s.close()

    def test_it007_leitor_concorrente_so_ve_valores_completos(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            a = "A" * 1024
            b = "B" * 1024

            with Store(d) as s:
                s.set("alvo", a)

            escritor_src = (
                _PREAMBULO
                + "s = Store(directory)\n"
                + "import time\n"
                + "fim = time.monotonic() + 1.0\n"
                + "toggle = False\n"
                + "while time.monotonic() < fim:\n"
                + "    s.set('alvo', ('B' if toggle else 'A') * 1024)\n"
                + "    toggle = not toggle\n"
                + "os.write(write_fd, b'\\x01')\n"
            )
            leitor_src = (
                _PREAMBULO
                + "s = Store(directory)\n"
                + "import time\n"
                + "validos = {'A' * 1024, 'B' * 1024}\n"
                + "fim = time.monotonic() + 1.0\n"
                + "while time.monotonic() < fim:\n"
                + "    try:\n"
                + "        valor = s.get('alvo')\n"
                + "    except Exception:\n"
                + "        os._exit(1)\n"
                + "    if valor not in validos:\n"
                + "        os._exit(1)\n"
                + "os.write(write_fd, b'\\x01')\n"
            )

            proc_escritor, fd_escritor = apoio.iniciar_filho(
                escritor_src, [apoio.raiz_repositorio(), d]
            )
            proc_leitor, fd_leitor = apoio.iniciar_filho(
                leitor_src, [apoio.raiz_repositorio(), d]
            )
            try:
                ack_escritor = apoio.esperar_ack(fd_escritor, timeout=10.0)
                ack_leitor = apoio.esperar_ack(fd_leitor, timeout=10.0)
                proc_escritor.wait(timeout=10.0)
                proc_leitor.wait(timeout=10.0)
            finally:
                os.close(fd_escritor)
                os.close(fd_leitor)

            self.assertTrue(ack_escritor, "escritor nunca confirmou")
            self.assertEqual(proc_escritor.returncode, 0)
            self.assertTrue(
                ack_leitor,
                "leitor nunca confirmou (viu um valor invalido ou uma falha de leitura)",
            )
            self.assertEqual(
                proc_leitor.returncode,
                0,
                "leitor observou um valor incompleto ou uma leitura que falhou",
            )

            with Store(d) as s:
                valor_final = s.get("alvo")
            self.assertIn(valor_final, (a, b))

    @unittest.skipUnless(
        os.environ.get("KVSTORE_SLOW_TESTS") == "1",
        "KVSTORE_SLOW_TESTS=1 nao definido: pulando o round-trip de 64 MiB (lento)",
    )
    def test_it008_64mib_via_stdin_do_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            entrada = os.urandom(32 * 1024 * 1024).hex().encode("ascii")
            self.assertEqual(len(entrada), 64 * 1024 * 1024)

            r = _run_cli([d, "set", "grande", "-"], input_bytes=entrada, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)

            r = _run_cli([d, "get", "grande"], timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, entrada)


if __name__ == "__main__":
    unittest.main()
