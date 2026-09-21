import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fidx import scan, store
from fidx.__main__ import buscar, indexar
from fidx.store import Indice, IndiceEmUso


class TestIndexar(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)

    def _escrever(self, nome: str, conteudo: str) -> Path:
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def test_primeira_indexacao_tres_arquivos_novos(self) -> None:
        """IT-001"""
        self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "jabuticaba madura")
        self._escrever("c.txt", "relatorio mensal")

        contagens = indexar(self.raiz)

        self.assertEqual(
            contagens,
            {"novos": 3, "alterados": 0, "removidos": 0, "inalterados": 0, "ignorados": 0},
        )
        self.assertEqual(buscar(self.raiz, "jabuticaba"), ["b.txt"])

    def test_segunda_rodada_sem_mudanca_nao_grava(self) -> None:
        """IT-002"""
        self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "jabuticaba madura")
        self._escrever("c.txt", "relatorio mensal")
        indexar(self.raiz)

        with mock.patch.object(Indice, "gravar") as gravar_mock:
            contagens = indexar(self.raiz)

        self.assertEqual(
            contagens,
            {"novos": 0, "alterados": 0, "removidos": 0, "inalterados": 3, "ignorados": 0},
        )
        gravar_mock.assert_not_called()

    def test_conteudo_novo_com_mtime_antigo_reprocessa(self) -> None:
        """IT-003"""
        caminho = self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "outro arquivo")
        self._escrever("c.txt", "mais um")
        indexar(self.raiz)

        caminho.write_text("previsao anual", encoding="utf-8")
        os.utime(caminho, (0, 0))
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["alterados"], 1)
        self.assertEqual(buscar(self.raiz, "previsao"), ["a.txt"])
        self.assertEqual(buscar(self.raiz, "orcamento"), [])

    def test_mtime_futuro_sem_mudanca_de_conteudo_e_inalterado(self) -> None:
        """IT-004"""
        caminho = self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "outro arquivo")
        self._escrever("c.txt", "mais um")
        indexar(self.raiz)

        futuro = time.time() + 10_000_000
        os.utime(caminho, (futuro, futuro))
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["alterados"], 0)
        self.assertEqual(contagens["inalterados"], 3)

    def test_arquivo_novo_entra_e_vira_buscavel(self) -> None:
        """IT-005"""
        self._escrever("a.txt", "orcamento anual")
        indexar(self.raiz)

        self._escrever("novo.txt", "jabuticaba madura")
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["novos"], 1)
        self.assertEqual(buscar(self.raiz, "jabuticaba"), ["novo.txt"])

    def test_so_arquivo_alterado_e_reprocessado(self) -> None:
        """IT-006"""
        self._escrever("a.txt", "orcamento anual")
        caminho_b = self._escrever("b.txt", "relatorio mensal")
        self._escrever("c.txt", "mais um texto")
        indexar(self.raiz)

        caminho_b.write_text("relatorio trimestral", encoding="utf-8")
        contagens = indexar(self.raiz)

        self.assertEqual(
            contagens,
            {"novos": 0, "alterados": 1, "removidos": 0, "inalterados": 2, "ignorados": 0},
        )

    def test_arquivo_apagado_sai_do_indice(self) -> None:
        """IT-007"""
        caminho = self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "outro texto")
        indexar(self.raiz)

        caminho.unlink()
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["removidos"], 1)
        self.assertEqual(buscar(self.raiz, "orcamento"), [])

    def test_renomeado_com_conteudo_identico(self) -> None:
        """IT-008"""
        caminho = self._escrever("a.txt", "orcamento anual")
        indexar(self.raiz)

        conteudo = caminho.read_text(encoding="utf-8")
        caminho.unlink()
        self._escrever("sub/renomeado.txt", conteudo)
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["novos"], 1)
        self.assertEqual(contagens["removidos"], 1)
        self.assertEqual(buscar(self.raiz, "orcamento"), ["sub/renomeado.txt"])

    def test_arquivo_que_virou_ignorado_sai_do_indice(self) -> None:
        """IT-009"""
        caminho = self._escrever("a.txt", "orcamento anual")
        indexar(self.raiz)

        caminho.write_bytes(b"\xff\xfe\x00\x01PK")
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["removidos"], 1)
        self.assertEqual(contagens["ignorados"], 1)
        self.assertEqual(buscar(self.raiz, "orcamento"), [])

    def test_binario_e_ocultos_nao_entram_no_indice(self) -> None:
        """IT-010"""
        self._escrever("nota.txt", "conteudo legivel")
        (self.raiz / "dump.bin").write_bytes(b"\xff\xfe\x00\x01PK")
        self._escrever(".oculto.txt", "nao deveria entrar")
        self._escrever(".git/config", "nao deveria entrar")

        contagens = indexar(self.raiz)

        self.assertEqual(contagens["novos"], 1)
        self.assertEqual(contagens["ignorados"], 1)
        idx = Indice.abrir(self.raiz, criar=False)
        self.assertEqual(set(idx.digests()), {"nota.txt"})

    def test_diretorio_vazio(self) -> None:
        """IT-011"""
        contagens = indexar(self.raiz)

        self.assertEqual(
            contagens,
            {"novos": 0, "alterados": 0, "removidos": 0, "inalterados": 0, "ignorados": 0},
        )
        self.assertTrue((self.raiz / ".fidx.sqlite3").exists())

    def test_todos_os_arquivos_removidos(self) -> None:
        """IT-012"""
        caminho_a = self._escrever("a.txt", "um")
        caminho_b = self._escrever("b.txt", "dois")
        caminho_c = self._escrever("c.txt", "tres")
        indexar(self.raiz)

        caminho_a.unlink()
        caminho_b.unlink()
        caminho_c.unlink()
        contagens = indexar(self.raiz)

        self.assertEqual(contagens["removidos"], 3)
        idx = Indice.abrir(self.raiz, criar=False)
        self.assertEqual(idx.digests(), {})

    def test_busca_reflete_ultimo_index_nao_o_disco(self) -> None:
        """IT-016"""
        caminho = self._escrever("a.txt", "orcamento anual")
        indexar(self.raiz)

        caminho.write_text("previsao anual", encoding="utf-8")

        self.assertEqual(buscar(self.raiz, "orcamento"), ["a.txt"])

    def test_indexacao_interrompida_nao_deixa_indice_pela_metade(self) -> None:
        """IT-013"""
        self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "relatorio mensal")
        indexar(self.raiz)

        digests_antes = Indice.abrir(self.raiz, criar=False).digests()
        busca_antes = buscar(self.raiz, "orcamento")

        (self.raiz / "a.txt").write_text("previsao revisada", encoding="utf-8")
        (self.raiz / "b.txt").write_text("relatorio trimestral", encoding="utf-8")

        ler_original = scan.ler
        chamadas = {"n": 0}

        def ler_falho(caminho: Path):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise RuntimeError("falha simulada")
            return ler_original(caminho)

        with mock.patch.object(scan, "ler", side_effect=ler_falho):
            with self.assertRaises(RuntimeError):
                indexar(self.raiz)

        self.assertEqual(Indice.abrir(self.raiz, criar=False).digests(), digests_antes)
        self.assertEqual(buscar(self.raiz, "orcamento"), busca_antes)

    def test_indexar_e_buscar_fecham_a_conexao_mesmo_quando_indexar_e_interrompido(
        self,
    ) -> None:
        """Regressão issue_002: indexar()/buscar() não devem vazar sqlite3.Connection."""
        self._escrever("a.txt", "orcamento anual")
        self._escrever("b.txt", "relatorio mensal")
        indexar(self.raiz)

        conexoes: list[sqlite3.Connection] = []
        conectar_original = store.sqlite3.connect

        def conectar_espiao(*args, **kwargs):
            conexao = conectar_original(*args, **kwargs)
            conexoes.append(conexao)
            return conexao

        def ler_falho(caminho: Path):
            raise RuntimeError("falha simulada")

        with mock.patch.object(store.sqlite3, "connect", side_effect=conectar_espiao):
            with mock.patch.object(scan, "ler", side_effect=ler_falho):
                with self.assertRaises(RuntimeError):
                    indexar(self.raiz)

            buscar(self.raiz, "orcamento")

        self.assertEqual(len(conexoes), 2)
        for conexao in conexoes:
            with self.assertRaises(sqlite3.ProgrammingError):
                conexao.execute("SELECT 1")

    def test_segunda_indexacao_simultanea_levanta_indiceemuso(self) -> None:
        """IT-014"""
        self._escrever("a.txt", "orcamento anual")
        indexar(self.raiz)

        caminho_indice = self.raiz / store.NOME_ARQUIVO_INDICE
        bloqueadora = sqlite3.connect(caminho_indice, isolation_level=None, timeout=1)
        bloqueadora.execute("BEGIN IMMEDIATE")
        try:
            with self.assertRaises(IndiceEmUso):
                indexar(self.raiz)
            self.assertEqual(buscar(self.raiz, "orcamento"), ["a.txt"])
        finally:
            bloqueadora.execute("ROLLBACK")
            bloqueadora.close()

    def test_busca_durante_index_em_andamento_nao_espera(self) -> None:
        """IT-015"""
        self._escrever("a.txt", "orcamento anual")
        indexar(self.raiz)

        caminho_indice = self.raiz / store.NOME_ARQUIVO_INDICE
        bloqueadora = sqlite3.connect(caminho_indice, isolation_level=None, timeout=1)
        bloqueadora.execute("BEGIN IMMEDIATE")
        try:
            inicio = time.monotonic()
            resultado = buscar(self.raiz, "orcamento")
            duracao = time.monotonic() - inicio
        finally:
            bloqueadora.execute("ROLLBACK")
            bloqueadora.close()

        self.assertEqual(resultado, ["a.txt"])
        self.assertLess(duracao, store.TIMEOUT_CONEXAO)

    @unittest.skipIf(os.geteuid() == 0, "chmod nao restringe escrita como root")
    def test_pasta_sem_permissao_de_escrita_levanta_erro_de_gravacao(self) -> None:
        """IT-017"""
        os.chmod(self.raiz, 0o555)
        try:
            with self.assertRaises((sqlite3.OperationalError, PermissionError)):
                indexar(self.raiz)
        finally:
            os.chmod(self.raiz, 0o755)


if __name__ == "__main__":
    unittest.main()
