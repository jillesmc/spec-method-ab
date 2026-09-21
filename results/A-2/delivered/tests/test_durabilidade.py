import os
import sqlite3
import tempfile
import unittest

from kvstore import IncompatibleStore, KeyNotFound, KVStoreError, Store
from tests import apoio

_PREAMBULO = (
    "import os, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from kvstore import Store\n"
    "directory = sys.argv[2]\n"
    "write_fd = int(sys.argv[3])\n"
)

_LOOP_FINAL = "\nimport time\nwhile True:\n    time.sleep(1)\n"


def _codigo(corpo: str) -> str:
    return _PREAMBULO + corpo + _LOOP_FINAL


class TestConfiguracaoDeDurabilidade(unittest.TestCase):
    def test_ut018_journal_mode_wal_em_criacao_e_reabertura(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s1 = Store(d)
            s1.set("k", "v")
            modo1 = s1._conn.execute("PRAGMA journal_mode").fetchone()[0]
            s1.close()

            s2 = Store(d)
            s2.get("k")
            modo2 = s2._conn.execute("PRAGMA journal_mode").fetchone()[0]
            s2.close()

            self.assertEqual(modo1.lower(), "wal")
            self.assertEqual(modo2.lower(), "wal")

    def test_ut019_synchronous_full_em_criacao_e_reabertura(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s1 = Store(d)
            s1.set("k", "v")
            sync1 = s1._conn.execute("PRAGMA synchronous").fetchone()[0]
            s1.close()

            s2 = Store(d)
            s2.get("k")
            sync2 = s2._conn.execute("PRAGMA synchronous").fetchone()[0]
            s2.close()

            self.assertEqual(sync1, 2)
            self.assertEqual(sync2, 2)

    def test_ut020_versao_incompativel_e_recusada(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("k", "v")

            db_path = os.path.join(d, "kvstore.db")
            raw = sqlite3.connect(db_path)
            self.assertEqual(raw.execute("PRAGMA user_version").fetchone()[0], 1)
            raw.execute("PRAGMA user_version=2")
            raw.close()

            antes = os.stat(db_path)

            s2 = Store(d)
            with self.assertRaises(IncompatibleStore) as ctx:
                s2.get("k")
            self.assertIn("2", str(ctx.exception))

            depois = os.stat(db_path)
            self.assertEqual(antes.st_size, depois.st_size)
            self.assertEqual(antes.st_mtime_ns, depois.st_mtime_ns)

    def test_ut021_banco_corrompido_e_reportado(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("k", "v")

            db_path = os.path.join(d, "kvstore.db")
            with open(db_path, "r+b") as f:
                f.write(b"\x00" * 100)

            s2 = Store(d)
            with self.assertRaises(KVStoreError) as ctx:
                s2.get("k")
            self.assertIn("corrompido", str(ctx.exception))


class TestSobrevivenciaAKill(unittest.TestCase):
    def test_it001_kill_logo_apos_o_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            corpo = (
                "s = Store(directory)\n"
                "s.set('posicao', '1042')\n"
                "os.write(write_fd, b'\\x01')\n"
            )
            apoio.matar_apos_ack(_codigo(corpo), [apoio.raiz_repositorio(), d])

            s = Store(d)
            self.assertEqual(s.get("posicao"), "1042")
            s.close()

    def test_it002_cinquenta_chaves_sobrevivem(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            corpo = (
                "s = Store(directory)\n"
                "for i in range(50):\n"
                "    s.set('chave-%02d' % i, 'valor-%d' % i)\n"
                "os.write(write_fd, b'\\x01')\n"
            )
            apoio.matar_apos_ack(_codigo(corpo), [apoio.raiz_repositorio(), d])

            s = Store(d)
            esperadas = ["chave-%02d" % i for i in range(50)]
            primeira = s.list()
            self.assertEqual(primeira, sorted(esperadas))
            for i in range(50):
                self.assertEqual(s.get("chave-%02d" % i), "valor-%d" % i)
            segunda = s.list()
            self.assertEqual(primeira, segunda)
            s.close()

    def test_it003_kill_durante_escrita_grande(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            corpo = (
                "s = Store(directory)\n"
                "s.set('ancora', 'ok')\n"
                "import threading\n"
                "threading.Thread(target=lambda: os.write(write_fd, b'\\x01')).start()\n"
                "s.set('grande', 'x' * (32 * 1024 * 1024))\n"
            )
            apoio.matar_apos_ack(_codigo(corpo), [apoio.raiz_repositorio(), d], timeout=15.0)

            s = Store(d)
            self.assertEqual(s.get("ancora"), "ok")
            try:
                valor = s.get("grande")
            except KeyNotFound:
                pass
            else:
                self.assertEqual(valor, "x" * (32 * 1024 * 1024))
            s.close()

    def test_it004_dez_ciclos_de_kill_e_reabertura(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            esperadas = []
            for i in range(10):
                corpo = (
                    "s = Store(directory)\n"
                    f"s.set('chave-{i}', '{i}')\n"
                    "os.write(write_fd, b'\\x01')\n"
                )
                apoio.matar_apos_ack(_codigo(corpo), [apoio.raiz_repositorio(), d])
                esperadas.append(f"chave-{i}")

                s = Store(d)
                self.assertEqual(s.list(), sorted(esperadas))
                s.close()

    def test_it005_nunca_fechado_e_morto(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            corpo = (
                "s = Store(directory)\n"
                "s.set('um', '1')\n"
                "s.set('dois', '2')\n"
                "os.write(write_fd, b'\\x01')\n"
            )
            apoio.matar_apos_ack(_codigo(corpo), [apoio.raiz_repositorio(), d])

            s = Store(d)
            self.assertEqual(s.get("um"), "1")
            self.assertEqual(s.get("dois"), "2")
            s.close()


if __name__ == "__main__":
    unittest.main()
