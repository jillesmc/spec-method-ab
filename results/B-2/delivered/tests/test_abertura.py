import os
import tempfile
import unittest

import kvstore


class TestAberturaDoStore(unittest.TestCase):
    def test_cria_diretorio_sob_demanda_e_tabela_com_auto_vacuum_incremental(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "novo", "dados")
            self.assertFalse(os.path.isdir(store_dir))

            conn = kvstore._connect(store_dir)
            try:
                self.assertTrue(os.path.isdir(store_dir))

                auto_vacuum = conn.execute("PRAGMA auto_vacuum").fetchone()[0]
                self.assertEqual(auto_vacuum, 2, "auto_vacuum deve ser INCREMENTAL (2)")

                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='kv'"
                ).fetchall()
                self.assertEqual(len(tables), 1)
            finally:
                conn.close()

    def test_pragmas_de_durabilidade_sao_efetivos_em_tempo_de_execucao(self):
        with tempfile.TemporaryDirectory() as store_dir:
            conn = kvstore._connect(store_dir)
            try:
                synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
                journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                self.assertEqual(synchronous, 2, "synchronous deve ser FULL (2)")
                self.assertEqual(journal_mode, "wal", "journal_mode deve ser wal")
            finally:
                conn.close()

    def test_abertura_e_idempotente_em_store_ja_existente(self):
        with tempfile.TemporaryDirectory() as store_dir:
            conn1 = kvstore._connect(store_dir)
            conn1.execute("INSERT INTO kv (key, value) VALUES (?, ?)", ("k", "v"))
            conn1.commit()
            conn1.close()

            conn2 = kvstore._connect(store_dir)
            try:
                rows = conn2.execute("SELECT key, value FROM kv").fetchall()
                self.assertEqual(rows, [("k", "v")])

                tables = conn2.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='kv'"
                ).fetchall()
                self.assertEqual(len(tables), 1)
            finally:
                conn2.close()


if __name__ == "__main__":
    unittest.main()
