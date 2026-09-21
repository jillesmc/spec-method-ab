import os
import sqlite3
import sys
import tempfile
import unittest

import kvstore


class TestStoreOperacoes(unittest.TestCase):
    def test_ut001_set_get_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("posicao", "1042")
                self.assertEqual(s.get("posicao"), "1042")

    def test_ut002_sobrescrita(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("k", "a")
                s.set("k", "b")
                self.assertEqual(s.get("k"), "b")

    def test_ut003_ausencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                self.assertIsNone(s.get("nunca_gravada"))

    def test_ut004_delete_de_existente(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("k", "v")
                self.assertTrue(s.delete("k"))
                self.assertIsNone(s.get("k"))

    def test_ut005_delete_de_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                self.assertFalse(s.delete("nunca_gravada"))

    def test_ut006_keys_ordenado(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("posicao", "1")
                s.set("config", "2")
                s.set("contador", "3")
                self.assertEqual(s.keys(), ["config", "contador", "posicao"])

    def test_ut007_keys_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                self.assertEqual(s.keys(), [])

    def test_ut008_valor_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("k", "")
                self.assertIsNotNone(s.get("k"))
                self.assertEqual(s.get("k"), "")

    def test_ut009_chave_vazia(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                with self.assertRaises(ValueError):
                    s.set("", "v")
                self.assertEqual(s.keys(), [])

    def test_ut010_chave_nao_str(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                with self.assertRaises(TypeError):
                    s.set(1, "v")
                with self.assertRaises(TypeError):
                    s.get(1)
                with self.assertRaises(TypeError):
                    s.delete(1)

    def test_ut011_chaves_hostis(self):
        chaves = ["a/b", "../fuga", "chave com espaço", "ação", "com\nnewline"]
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                for i, chave in enumerate(chaves):
                    s.set(chave, f"valor{i}")
                for i, chave in enumerate(chaves):
                    self.assertEqual(s.get(chave), f"valor{i}")
                self.assertEqual(set(chaves), set(s.keys()) & set(chaves))

    def test_ut012_valor_grande(self):
        valor = "x" * 5_000_000
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("blob", valor)
                lido = s.get("blob")
                self.assertEqual(lido, valor)
                self.assertEqual(len(lido), 5_000_000)

    def test_ut013_uso_apos_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = kvstore.Store(tmp)
            s.set("k", "v")
            s.close()
            with self.assertRaises(sqlite3.ProgrammingError):
                s.get("k")

    def test_ut014_gerenciador_de_contexto(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("k", "v")
            with kvstore.Store(tmp) as s2:
                self.assertEqual(s2.get("k"), "v")

    def test_ut015_diretorio_criado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "nao", "existe")
            with kvstore.Store(caminho) as s:
                s.set("k", "v")
                self.assertEqual(s.get("k"), "v")
            self.assertTrue(os.path.isdir(caminho))

    def test_ut016_caminho_e_arquivo_comum(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "arquivo_comum")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("dado")
            antes = set(os.listdir(tmp))
            with self.assertRaises(OSError) as ctx:
                kvstore.Store(caminho)
            self.assertIn(caminho, str(ctx.exception))
            self.assertEqual(set(os.listdir(tmp)), antes)

    @unittest.skipUnless(sys.platform.startswith("linux"), "requer /proc/self/fd (Linux)")
    def test_ut017_sem_vazamento_de_descritor(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                antes = len(os.listdir("/proc/self/fd"))
                for i in range(5000):
                    s.set(f"chave{i}", "v")
                depois = len(os.listdir("/proc/self/fd"))
                self.assertEqual(antes, depois)

    def test_ut018_newline_final_preservado(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("k", "linha\n")
                self.assertEqual(s.get("k"), "linha\n")

    def test_ut019_delete_repetido(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("k", "v")
                self.assertTrue(s.delete("k"))
                self.assertFalse(s.delete("k"))


class TestStoreConfiguracaoEEscala(unittest.TestCase):
    def test_ut020_journal_mode_efetivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                modo = s._con.execute("PRAGMA journal_mode").fetchone()[0].lower()
                self.assertEqual(modo, "wal")

    def test_ut021_synchronous_efetivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                nivel = s._con.execute("PRAGMA synchronous").fetchone()[0]
                self.assertEqual(nivel, 2)

    def test_ut022_busy_timeout_efetivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                espera = s._con.execute("PRAGMA busy_timeout").fetchone()[0]
                self.assertEqual(espera, 5000)

    def test_ut023_escala_de_chaves(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                for i in range(2000):
                    s.set(f"chave{i:05d}", f"valor{i}")
                chaves = s.keys()
                self.assertEqual(len(chaves), 2000)
                self.assertEqual(chaves, sorted(chaves))
                self.assertEqual(s.get("chave01234"), "valor1234")

    def test_ut024_chave_com_newline_em_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("a\nb", "v")
                self.assertIn("a\nb", s.keys())


if __name__ == "__main__":
    unittest.main()
