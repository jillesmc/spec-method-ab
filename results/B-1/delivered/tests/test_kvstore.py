import io
import os
import tempfile
import unittest
from urllib.parse import quote

import kvstore


class TestKVStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.diretorio = self._tmp.name

    def test_ida_e_volta(self):
        kvstore.set(self.diretorio, "foo", "bar")
        self.assertEqual(kvstore.get(self.diretorio, "foo"), "bar")

    def test_valor_vazio(self):
        kvstore.set(self.diretorio, "vazio", "")
        self.assertEqual(kvstore.get(self.diretorio, "vazio"), "")

    def test_valor_nao_ascii(self):
        valor = "café ☕ ação 日本語"
        kvstore.set(self.diretorio, "chave", valor)
        self.assertEqual(kvstore.get(self.diretorio, "chave"), valor)

    def test_chave_com_barra_e_preservada_sem_subdiretorio(self):
        kvstore.set(self.diretorio, "pos/topico-1", "valor")
        self.assertEqual(kvstore.get(self.diretorio, "pos/topico-1"), "valor")
        nomes = os.listdir(self.diretorio)
        self.assertIn("k." + quote("pos/topico-1", safe=""), nomes)
        self.assertFalse(os.path.isdir(os.path.join(self.diretorio, "pos")))

    def test_chave_vazia_invalida(self):
        with self.assertRaises(ValueError):
            kvstore.set(self.diretorio, "", "valor")

    def test_chave_com_newline_invalida(self):
        with self.assertRaises(ValueError):
            kvstore.set(self.diretorio, "linha\num", "valor")

    def test_chave_com_cr_invalida(self):
        with self.assertRaises(ValueError):
            kvstore.set(self.diretorio, "linha\rum", "valor")

    def test_chave_com_nulo_invalida(self):
        with self.assertRaises(ValueError):
            kvstore.set(self.diretorio, "linha\0um", "valor")

    def test_chave_longa_demais_invalida(self):
        chave = "x" * 300
        with self.assertRaises(ValueError):
            kvstore.set(self.diretorio, chave, "valor")

    def test_get_chave_ausente_levanta_key_error(self):
        kvstore.set(self.diretorio, "existe", "valor")
        with self.assertRaises(KeyError):
            kvstore.get(self.diretorio, "nao-existe")

    def test_get_diretorio_ausente_levanta_key_error(self):
        inexistente = os.path.join(self.diretorio, "nao-criado")
        with self.assertRaises(KeyError):
            kvstore.get(inexistente, "qualquer")

    def test_delete_remove_e_get_depois_levanta_key_error(self):
        kvstore.set(self.diretorio, "chave", "valor")
        kvstore.delete(self.diretorio, "chave")
        with self.assertRaises(KeyError):
            kvstore.get(self.diretorio, "chave")

    def test_delete_chave_ausente_levanta_key_error(self):
        with self.assertRaises(KeyError):
            kvstore.delete(self.diretorio, "nao-existe")

    def test_delete_diretorio_ausente_levanta_key_error(self):
        inexistente = os.path.join(self.diretorio, "nao-criado")
        with self.assertRaises(KeyError):
            kvstore.delete(inexistente, "qualquer")

    def test_keys_ordenado(self):
        kvstore.set(self.diretorio, "b", "1")
        kvstore.set(self.diretorio, "a", "2")
        kvstore.set(self.diretorio, "c", "3")
        self.assertEqual(kvstore.keys(self.diretorio), ["a", "b", "c"])

    def test_keys_ignora_temporarios_orfaos(self):
        kvstore.set(self.diretorio, "a", "1")
        fd, _ = tempfile.mkstemp(dir=self.diretorio, prefix=".tmp-")
        os.close(fd)
        self.assertEqual(kvstore.keys(self.diretorio), ["a"])

    def test_keys_diretorio_ausente_devolve_lista_vazia(self):
        inexistente = os.path.join(self.diretorio, "nao-criado")
        self.assertEqual(kvstore.keys(inexistente), [])

    def test_set_stream_e_get_stream(self):
        kvstore.set_stream(self.diretorio, "stream", io.BytesIO(b"conteudo em blocos"))
        saida = io.BytesIO()
        kvstore.get_stream(self.diretorio, "stream", saida)
        self.assertEqual(saida.getvalue(), b"conteudo em blocos")

    def test_set_nao_deixa_temporario_para_tras(self):
        kvstore.set(self.diretorio, "chave", "valor")
        self.assertEqual(os.listdir(self.diretorio), ["k.chave"])

    def test_regravar_chave_nao_afeta_outra(self):
        kvstore.set(self.diretorio, "a", "1")
        kvstore.set(self.diretorio, "b", "2")
        caminho_b = kvstore._caminho(self.diretorio, "b")
        antes = os.stat(caminho_b)
        kvstore.set(self.diretorio, "a", "novo valor")
        depois = os.stat(caminho_b)
        self.assertEqual(antes.st_mtime_ns, depois.st_mtime_ns)
        self.assertEqual(kvstore.get(self.diretorio, "b"), "2")

    def test_primeira_gravacao_cria_diretorio(self):
        novo = os.path.join(self.diretorio, "novo-store")
        self.assertFalse(os.path.isdir(novo))
        kvstore.set(novo, "chave", "valor")
        self.assertTrue(os.path.isdir(novo))
        self.assertEqual(kvstore.get(novo, "chave"), "valor")


if __name__ == "__main__":
    unittest.main()
