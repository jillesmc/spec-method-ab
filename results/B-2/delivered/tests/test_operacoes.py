import os
import tempfile
import unittest

import kvstore


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


class TestSet(unittest.TestCase):
    def test_ultima_gravacao_vence(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "k", "v1")
            kvstore.set(store_dir, "k", "v2")
            self.assertEqual(kvstore.get(store_dir, "k"), "v2")


class TestGetEDelete(unittest.TestCase):
    def test_get_de_chave_ausente_levanta_key_not_found(self):
        with tempfile.TemporaryDirectory() as store_dir:
            with self.assertRaises(kvstore.KeyNotFoundError):
                kvstore.get(store_dir, "nunca-gravada")

    def test_remover_e_reler_reporta_ausencia(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "k", "v")
            kvstore.delete(store_dir, "k")
            with self.assertRaises(kvstore.KeyNotFoundError):
                kvstore.get(store_dir, "k")

    def test_delete_e_idempotente(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.delete(store_dir, "nunca-existiu")
            kvstore.delete(store_dir, "nunca-existiu")

    def test_gravar_remover_regravar_devolve_valor_novo(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "k", "v1")
            kvstore.delete(store_dir, "k")
            kvstore.set(store_dir, "k", "v3")
            self.assertEqual(kvstore.get(store_dir, "k"), "v3")
            self.assertIn("k", kvstore.list_keys(store_dir))


class TestListKeys(unittest.TestCase):
    def test_devolve_so_chaves_vivas_em_ordem_lexicografica(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "b", "1")
            kvstore.set(store_dir, "a", "2")
            kvstore.set(store_dir, "c", "3")
            kvstore.delete(store_dir, "b")
            self.assertEqual(kvstore.list_keys(store_dir), ["a", "c"])


class TestValidacaoDeChave(unittest.TestCase):
    def test_chave_vazia_e_recusada_sem_alterar_disco(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "existente", "v")
            with self.assertRaises(kvstore.InvalidKeyError):
                kvstore.set(store_dir, "", "v")
            self.assertEqual(kvstore.list_keys(store_dir), ["existente"])

    def test_chave_com_quebra_de_linha_e_recusada_sem_criar_nada(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "novo")
            with self.assertRaises(kvstore.InvalidKeyError):
                kvstore.set(store_dir, "linha\num", "v")
            self.assertFalse(os.path.exists(store_dir))

    def test_chave_com_nul_e_recusada_sem_criar_nada(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "novo")
            with self.assertRaises(kvstore.InvalidKeyError):
                kvstore.set(store_dir, "com\x00nul", "v")
            self.assertFalse(os.path.exists(store_dir))

    def test_get_com_chave_invalida_tambem_e_recusado(self):
        with tempfile.TemporaryDirectory() as store_dir:
            with self.assertRaises(kvstore.InvalidKeyError):
                kvstore.get(store_dir, "")

    def test_delete_com_chave_invalida_tambem_e_recusado(self):
        with tempfile.TemporaryDirectory() as store_dir:
            with self.assertRaises(kvstore.InvalidKeyError):
                kvstore.delete(store_dir, "\n")


class TestDiretorioInexistente(unittest.TestCase):
    def test_list_keys_em_diretorio_inexistente_vem_vazio_sem_criar_nada(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "nunca-criado")
            self.assertEqual(kvstore.list_keys(store_dir), [])
            self.assertFalse(os.path.exists(store_dir))

    def test_get_em_diretorio_inexistente_reporta_ausencia_sem_criar_nada(self):
        with tempfile.TemporaryDirectory() as base:
            store_dir = os.path.join(base, "nunca-criado")
            with self.assertRaises(kvstore.KeyNotFoundError):
                kvstore.get(store_dir, "k")
            self.assertFalse(os.path.exists(store_dir))


class TestEspacoProporcionalAoEstadoVivo(unittest.TestCase):
    def test_incremental_vacuum_apos_remocao_encolhe_o_diretorio(self):
        with tempfile.TemporaryDirectory() as store_dir:
            valor_grande = "x" * (200 * 1024)
            chaves = [f"chave-{i}" for i in range(50)]
            for chave in chaves:
                kvstore.set(store_dir, chave, valor_grande)

            tamanho_cheio = _dir_size(store_dir)
            self.assertGreater(tamanho_cheio, len(chaves) * len(valor_grande) * 0.5)

            for chave in chaves:
                kvstore.delete(store_dir, chave)

            tamanho_apos_remocao = _dir_size(store_dir)

            self.assertEqual(kvstore.list_keys(store_dir), [])
            self.assertLess(tamanho_apos_remocao, tamanho_cheio * 0.1)
            self.assertLess(
                tamanho_apos_remocao, 512 * 1024, "diretório deveria estar perto de vazio"
            )


class TestFidelidadeDeValor(unittest.TestCase):
    def test_valor_grande_com_quebras_acentos_espacos_e_nul_sobrevive_intacto(self):
        with tempfile.TemporaryDirectory() as store_dir:
            trecho = "linha com acentuação: ção, ã, é, ü\n  espaços nas pontas  \n\x00meio-nul\x00"
            valor = trecho * (3 * 1024 * 1024 // len(trecho.encode("utf-8")) + 1)
            valor = " " + valor + " "

            kvstore.set(store_dir, "k", valor)
            devolvido = kvstore.get(store_dir, "k")

            self.assertEqual(devolvido, valor)
            self.assertEqual(len(devolvido), len(valor))


if __name__ == "__main__":
    unittest.main()
