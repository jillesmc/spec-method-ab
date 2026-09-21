import os
import tempfile
import unittest

from kvstore import (
    FORMAT_VERSION,
    InvalidKey,
    KeyNotFound,
    KVStoreError,
    Store,
    StoreBusy,
)


class TestOperacoesBasicas(unittest.TestCase):
    def test_ut001_set_e_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("modo", "rapido")
                self.assertEqual(s.get("modo"), "rapido")

    def test_ut002_sobrescreve_valor(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("modo", "rapido")
                s.set("modo", "lento")
                self.assertEqual(s.get("modo"), "lento")
                self.assertEqual(s.list(), ["modo"])

    def test_ut003_set_repetido_e_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("k", "v")
                s.set("k", "v")
                self.assertEqual(s.get("k"), "v")
                self.assertEqual(s.list(), ["k"])

    def test_ut004_get_de_chave_ausente_levanta_keynotfound(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("existente", "1")
                with self.assertRaises(KeyNotFound):
                    s.get("ausente")

    def test_ut005_delete_remove_e_reporta(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("k", "v")
                self.assertTrue(s.delete("k"))
                with self.assertRaises(KeyNotFound):
                    s.get("k")
                self.assertNotIn("k", s.list())

    def test_ut006_delete_e_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                self.assertFalse(s.delete("nunca"))
                self.assertEqual(s.list(), [])
                s.set("k", "v")
                self.assertTrue(s.delete("k"))
                self.assertFalse(s.delete("k"))
                self.assertEqual(s.list(), [])

    def test_ut007_list_retorna_ordenado(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("b", "1")
                s.set("a", "2")
                s.set("c", "3")
                self.assertEqual(s.list(), ["a", "b", "c"])

    def test_ut008_list_em_diretorio_ausente_nao_cria_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "nao-existe")
            s = Store(d)
            self.assertEqual(s.list(), [])
            self.assertFalse(os.path.exists(d))

    def test_ut009_get_em_diretorio_ausente_nao_cria_nada(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "nao-existe")
            s = Store(d)
            with self.assertRaises(KeyNotFound):
                s.get("k")
            self.assertFalse(os.path.exists(d))

    def test_ut010_chave_vazia_e_rejeitada(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s = Store(d)
            with self.assertRaises(InvalidKey):
                s.set("", "v")
            self.assertFalse(os.path.exists(d))

    def test_ut011_chave_com_quebra_ou_nul_e_rejeitada(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s = Store(d)
            with self.assertRaises(InvalidKey):
                s.set("a\nb", "v")
            with self.assertRaises(InvalidKey):
                s.set("a\x00b", "v")
            self.assertEqual(s.list(), [])

    def test_ut012_valor_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("vazio", "")
                self.assertEqual(s.get("vazio"), "")
                self.assertIn("vazio", s.list())

    def test_ut013_valor_com_caracteres_especiais_e_byte_exato(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            valor = "com\nquebras\x00e acentuação 日本語"
            with Store(d) as s:
                s.set("t", valor)
                self.assertEqual(s.get("t"), valor)

    def test_ut014_sobrevive_a_close_e_reabertura(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s = Store(d)
            s.set("a", "1")
            s.set("b", "2")
            s.delete("a")
            s.set("c", "3")
            s.close()

            s2 = Store(d)
            self.assertEqual(s2.list(), ["b", "c"])
            self.assertEqual(s2.get("c"), "3")
            s2.close()

    def test_ut015_primeiro_set_cria_exatamente_tres_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s = Store(d)
            s.set("k", "v")
            self.assertEqual(
                sorted(os.listdir(d)),
                ["kvstore.db", "kvstore.db-shm", "kvstore.db-wal"],
            )
            s.close()

    def test_ut016_caminho_e_arquivo_regular(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "arquivo.txt")
            conteudo = b"conteudo original"
            with open(caminho, "wb") as f:
                f.write(conteudo)
            s = Store(caminho)
            with self.assertRaises(KVStoreError) as ctx:
                s.set("k", "v")
            self.assertIn(caminho, str(ctx.exception))
            with open(caminho, "rb") as f:
                self.assertEqual(f.read(), conteudo)

    @unittest.skipIf(os.geteuid() == 0, "root ignora permissoes de diretorio")
    def test_ut017_diretorio_sem_permissao_de_escrita(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "somente-leitura")
            os.mkdir(d)
            os.chmod(d, 0o500)
            try:
                s = Store(d)
                with self.assertRaises(KVStoreError) as ctx:
                    s.set("k", "v")
                self.assertIn(d, str(ctx.exception))
            finally:
                os.chmod(d, 0o700)


class TestSuperficieAPI(unittest.TestCase):
    def test_ut022_arquivo_alheio_permanece_intocado(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            os.mkdir(d)
            anotacao = os.path.join(d, "anotacao.txt")
            with open(anotacao, "wb") as f:
                f.write(b"nao mexa")
            antes = os.stat(anotacao)

            with Store(d) as s:
                s.set("k", "v")
                s.get("k")
                s.delete("k")
                s.list()

            depois = os.stat(anotacao)
            with open(anotacao, "rb") as f:
                self.assertEqual(f.read(), b"nao mexa")
            self.assertEqual(antes.st_mtime_ns, depois.st_mtime_ns)
            self.assertEqual(antes.st_size, depois.st_size)

    def test_ut023_context_manager_fecha_e_propaga_excecao(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            with Store(d) as s:
                s.set("k", "v")
            self.assertIsNone(s._conn)

            s2 = Store(d)
            self.assertEqual(s2.get("k"), "v")
            s2.close()

            with self.assertRaises(RuntimeError):
                with Store(d) as s3:
                    s3.set("outra", "1")
                    raise RuntimeError("boom")
            self.assertIsNone(s3._conn)

            s4 = Store(d)
            self.assertEqual(s4.get("outra"), "1")
            s4.close()

    def test_ut024_duas_stores_na_mesma_pasta(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s1 = Store(d)
            s2 = Store(d)
            try:
                s1.set("k", "v")
                self.assertEqual(s2.get("k"), "v")
            finally:
                s1.close()
                s2.close()

    def test_ut025_hierarquia_de_excecoes_e_exportacoes(self):
        self.assertTrue(issubclass(KeyNotFound, KVStoreError))
        self.assertTrue(issubclass(KeyNotFound, KeyError))
        self.assertTrue(issubclass(InvalidKey, KVStoreError))
        self.assertTrue(issubclass(InvalidKey, ValueError))
        self.assertTrue(issubclass(StoreBusy, KVStoreError))
        self.assertEqual(FORMAT_VERSION, 1)
        self.assertTrue(callable(Store))


if __name__ == "__main__":
    unittest.main()
