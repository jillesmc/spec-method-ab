import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fidx import store


class TestAbrir(unittest.TestCase):
    def test_cria_indice_vazio_e_arquivo_no_disco(self) -> None:
        """UT-020"""
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            idx = store.Indice.abrir(raiz, criar=True)
            self.assertTrue((raiz / store.NOME_ARQUIVO_INDICE).exists())
            self.assertEqual(idx.digests(), {})

    def test_ausente_sem_criar_levanta_e_nao_cria_arquivo(self) -> None:
        """UT-021"""
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            with self.assertRaises(FileNotFoundError):
                store.Indice.abrir(raiz, criar=False)
            self.assertFalse((raiz / store.NOME_ARQUIVO_INDICE).exists())

    def test_schema_version_divergente_reconstroi_sem_excecao(self) -> None:
        """UT-028"""
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            caminho = raiz / store.NOME_ARQUIVO_INDICE
            conexao = sqlite3.connect(caminho)
            conexao.execute("CREATE TABLE meta (chave TEXT PRIMARY KEY, valor TEXT)")
            conexao.execute(
                "INSERT INTO meta (chave, valor) VALUES ('schema_version', '0')"
            )
            conexao.commit()
            conexao.close()

            idx = store.Indice.abrir(raiz, criar=True)

            self.assertEqual(idx.digests(), {})

    def test_schema_version_divergente_sem_criar_levanta_e_preserva_indice(self) -> None:
        """Regressão issue_001: `search` (criar=False) nunca pode apagar um índice existente."""
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            caminho = raiz / store.NOME_ARQUIVO_INDICE
            idx = store.Indice.abrir(raiz, criar=True)
            idx.gravar("a.txt", "d1", {"orcamento"})
            idx.close()

            conexao = sqlite3.connect(caminho)
            conexao.execute(
                "UPDATE meta SET valor = '0' WHERE chave = 'schema_version'"
            )
            conexao.commit()
            conexao.close()

            with self.assertRaises(FileNotFoundError):
                store.Indice.abrir(raiz, criar=False)

            self.assertTrue(caminho.exists())
            conferencia = sqlite3.connect(caminho)
            linhas = conferencia.execute("SELECT caminho, digest FROM arquivos").fetchall()
            conferencia.close()
            self.assertEqual(linhas, [("a.txt", "d1")])

    def test_falha_ao_ler_schema_version_fecha_a_conexao_antes_de_repropagar(self) -> None:
        """Regressão issue_002: erro fora de OperationalError não deve vazar a conexão."""
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            caminho = raiz / store.NOME_ARQUIVO_INDICE
            caminho.write_bytes(b"isto nao e um banco sqlite valido")

            conexoes: list[sqlite3.Connection] = []
            conectar_original = store.sqlite3.connect

            def conectar_espiao(*args, **kwargs):
                conexao = conectar_original(*args, **kwargs)
                conexoes.append(conexao)
                return conexao

            with mock.patch.object(store.sqlite3, "connect", side_effect=conectar_espiao):
                with self.assertRaises(sqlite3.DatabaseError):
                    store.Indice.abrir(raiz, criar=True)

            self.assertEqual(len(conexoes), 1)
            with self.assertRaises(sqlite3.ProgrammingError):
                conexoes[0].execute("SELECT 1")

    def test_falha_ao_criar_indice_fecha_a_conexao_antes_de_repropagar(self) -> None:
        """Regressão issue_001: falha em _criar() não deve vazar a conexão."""

        class ConexaoQueFalhaNaSegundaExecucao(sqlite3.Connection):
            _chamadas = 0

            def execute(self, *args, **kwargs):  # type: ignore[override]
                type(self)._chamadas += 1
                if type(self)._chamadas == 2:
                    raise sqlite3.OperationalError("simulated disk full")
                return super().execute(*args, **kwargs)

        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)

            conexoes: list[sqlite3.Connection] = []
            conectar_original = store.sqlite3.connect

            def conectar_espiao(*args, **kwargs):
                kwargs["factory"] = ConexaoQueFalhaNaSegundaExecucao
                conexao = conectar_original(*args, **kwargs)
                conexoes.append(conexao)
                return conexao

            with mock.patch.object(store.sqlite3, "connect", side_effect=conectar_espiao):
                with self.assertRaises(sqlite3.OperationalError):
                    store.Indice.abrir(raiz, criar=True)

            self.assertEqual(len(conexoes), 1)
            with self.assertRaises(sqlite3.ProgrammingError):
                conexoes[0].execute("SELECT 1")


class TestClose(unittest.TestCase):
    def test_close_fecha_a_conexao_subjacente(self) -> None:
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            idx = store.Indice.abrir(raiz, criar=True)

            idx.close()

            with self.assertRaises(sqlite3.ProgrammingError):
                idx.digests()


class TestGravarRemoverBuscar(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.idx = store.Indice.abrir(self.raiz, criar=True)

    def test_gravar_e_buscar_pelo_termo(self) -> None:
        """UT-022"""
        self.idx.gravar("a.txt", "d1", {"orcamento"})
        self.assertEqual(self.idx.buscar({"orcamento"}), ["a.txt"])

    def test_gravar_de_novo_substitui_termos_e_digest_anteriores(self) -> None:
        """UT-023"""
        self.idx.gravar("a.txt", "d1", {"velho"})
        self.idx.gravar("a.txt", "d2", {"novo"})

        self.assertEqual(self.idx.buscar({"velho"}), [])
        self.assertEqual(self.idx.buscar({"novo"}), ["a.txt"])
        self.assertEqual(self.idx.digests()["a.txt"], "d2")

    def test_remover_apaga_caminho_de_digests_e_buscar(self) -> None:
        """UT-024"""
        self.idx.gravar("a.txt", "d1", {"orcamento"})

        self.idx.remover(["a.txt"])

        self.assertNotIn("a.txt", self.idx.digests())
        self.assertEqual(self.idx.buscar({"orcamento"}), [])

    def test_buscar_termo_sem_correspondencia_devolve_lista_vazia(self) -> None:
        """UT-025"""
        self.idx.gravar("a.txt", "d1", {"orcamento"})

        self.assertEqual(self.idx.buscar({"jabuticaba"}), [])

    def test_buscar_varios_termos_e_conjuncao(self) -> None:
        """UT-026"""
        self.idx.gravar("a.txt", "d1", {"relatorio", "mensal"})
        self.idx.gravar("b.txt", "d2", {"relatorio"})

        self.assertEqual(self.idx.buscar({"relatorio", "mensal"}), ["a.txt"])

    def test_buscar_conjunto_vazio_de_termos_devolve_lista_vazia(self) -> None:
        """UT-027"""
        self.idx.gravar("a.txt", "d1", {"orcamento"})

        self.assertEqual(self.idx.buscar(set()), [])

    def test_buscar_devolve_caminhos_em_ordem_alfabetica(self) -> None:
        """UT-029"""
        self.idx.gravar("c.txt", "d3", {"comum"})
        self.idx.gravar("a.txt", "d1", {"comum"})
        self.idx.gravar("b.txt", "d2", {"comum"})

        self.assertEqual(self.idx.buscar({"comum"}), ["a.txt", "b.txt", "c.txt"])

    def test_digests_devolve_dicionario_exato_de_caminho_para_digest(self) -> None:
        """UT-030"""
        self.idx.gravar("a.txt", "d1", {"x"})
        self.idx.gravar("b.txt", "d2", {"y"})
        self.idx.gravar("c.txt", "d3", {"z"})

        self.assertEqual(
            self.idx.digests(), {"a.txt": "d1", "b.txt": "d2", "c.txt": "d3"}
        )

    def test_dois_caminhos_com_mesmo_digest_aparecem_juntos_na_busca(self) -> None:
        """UT-032"""
        self.idx.gravar("a.txt", "d", {"orcamento"})
        self.idx.gravar("copia.txt", "d", {"orcamento"})

        self.assertEqual(self.idx.buscar({"orcamento"}), ["a.txt", "copia.txt"])


class TestTransacao(unittest.TestCase):
    def test_context_manager_commita_ao_sair_sem_excecao(self) -> None:
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            with store.Indice.abrir(raiz, criar=True) as idx:
                idx.gravar("a.txt", "d1", {"orcamento"})

            idx2 = store.Indice.abrir(raiz, criar=False)
            self.assertEqual(idx2.buscar({"orcamento"}), ["a.txt"])

    def test_context_manager_desfaz_ao_sair_com_excecao(self) -> None:
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            idx = store.Indice.abrir(raiz, criar=True)
            with idx:
                idx.gravar("a.txt", "d1", {"orcamento"})
            # commitado; a rodada seguinte falha no meio e deve ser desfeita
            with self.assertRaises(RuntimeError):
                with idx:
                    idx.gravar("b.txt", "d2", {"novo"})
                    raise RuntimeError("falha simulada")

            idx2 = store.Indice.abrir(raiz, criar=False)
            self.assertEqual(idx2.digests(), {"a.txt": "d1"})
            self.assertEqual(idx2.buscar({"novo"}), [])

    def test_indice_em_uso_por_segunda_conexao_levanta_indiceemuso_dentro_do_timeout(
        self,
    ) -> None:
        """UT-031"""
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz)
            store.Indice.abrir(raiz, criar=True)
            caminho = raiz / store.NOME_ARQUIVO_INDICE

            bloqueadora = sqlite3.connect(caminho, isolation_level=None, timeout=1)
            bloqueadora.execute("BEGIN IMMEDIATE")
            try:
                idx = store.Indice.abrir(raiz, criar=True)
                with self.assertRaises(store.IndiceEmUso):
                    with idx:
                        pass
            finally:
                bloqueadora.execute("ROLLBACK")
                bloqueadora.close()


if __name__ == "__main__":
    unittest.main()
