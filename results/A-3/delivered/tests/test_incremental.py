import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from fidx import core


def arvore(raiz: str, arquivos: dict[str, str]) -> None:
    for caminho, conteudo in arquivos.items():
        full = os.path.join(raiz, caminho)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(conteudo)


class TestIncrementalBasico(unittest.TestCase):
    def test_ut020_rodada_sem_mudanca_nao_tokeniza(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento", "b.md": "outra coisa"})
            core.index_dir(tmp)
            with mock.patch.object(core, "tokenize", wraps=core.tokenize) as espiao:
                resultado = core.index_dir(tmp)
            espiao.assert_not_called()
            self.assertEqual(resultado, (2, 0, 0))

    def test_ut021_data_antiga_conteudo_novo_detectado(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            core.index_dir(tmp)
            caminho = os.path.join(tmp, "a.md")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("beta")
            antigo = 1577836800  # 2020-01-01, mais antiga que a original
            os.utime(caminho, (antigo, antigo))
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 0))
            self.assertEqual(core.search(tmp, "beta"), ["a.md"])

    def test_ut022_mesmo_tamanho_mtime_restaurado(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            caminho = os.path.join(tmp, "a.md")
            original = os.stat(caminho)
            core.index_dir(tmp)
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("beta")  # mesmo tamanho que "alfa"
            os.utime(caminho, (original.st_atime, original.st_mtime))
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 0))

    def test_ut023_data_nova_conteudo_igual_nao_reindexa(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            core.index_dir(tmp)
            os.utime(os.path.join(tmp, "a.md"), None)  # agora
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 0, 0))

    def test_ut024_substituicao_sem_posting_orfao(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            core.index_dir(tmp)
            with open(os.path.join(tmp, "a.md"), "w", encoding="utf-8") as f:
                f.write("beta")
            core.index_dir(tmp)
            self.assertEqual(core.search(tmp, "alfa"), [])
            self.assertEqual(core.search(tmp, "beta"), ["a.md"])

    def test_ut025_subpasta_apagada(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "sub/b.md": "beta", "sub/c.md": "gama"})
            core.index_dir(tmp)
            shutil.rmtree(os.path.join(tmp, "sub"))
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 0, 2))
            conn = core.open_index(tmp, create=False)
            try:
                paths_files = [r[0] for r in conn.execute("SELECT path FROM files")]
                paths_postings = [r[0] for r in conn.execute("SELECT path FROM postings")]
            finally:
                conn.close()
            self.assertFalse(any(p.startswith("sub/") for p in paths_files))
            self.assertFalse(any(p.startswith("sub/") for p in paths_postings))

    def test_ut026_rodada_mista(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "b.md": "beta", "c.md": "gama"})
            core.index_dir(tmp)
            with open(os.path.join(tmp, "b.md"), "w", encoding="utf-8") as f:
                f.write("beta2")
            os.remove(os.path.join(tmp, "c.md"))
            arvore(tmp, {"d.md": "delta"})
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (3, 2, 1))

    def test_ut027_idempotencia_despejo_identico(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa beta", "sub/b.md": "gama"})
            core.index_dir(tmp)

            def despejo():
                conn = core.open_index(tmp, create=False)
                try:
                    files = sorted(conn.execute("SELECT path, sha256 FROM files"))
                    postings = sorted(conn.execute("SELECT term, path FROM postings"))
                finally:
                    conn.close()
                return files, postings

            antes = despejo()
            core.index_dir(tmp)
            depois = despejo()
            self.assertEqual(antes, depois)

    def test_ut028_arquivo_movido(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento"})
            core.index_dir(tmp)
            os.makedirs(os.path.join(tmp, "sub"), exist_ok=True)
            os.rename(os.path.join(tmp, "a.md"), os.path.join(tmp, "sub", "a.md"))
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 1))
            self.assertEqual(core.search(tmp, "orcamento"), ["sub/a.md"])

    def test_ut029_conteudo_restaurado(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            core.index_dir(tmp)
            caminho = os.path.join(tmp, "a.md")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("beta")
            core.index_dir(tmp)
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("alfa")
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 0))
            self.assertEqual(core.search(tmp, "alfa"), ["a.md"])
            self.assertEqual(core.search(tmp, "beta"), [])


class TestIntegracaoIncremental(unittest.TestCase):
    def test_it002_ciclo_altera_com_data_mentirosa(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            core.index_dir(tmp)
            caminho = os.path.join(tmp, "a.md")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write("beta")
            os.utime(caminho, (1577836800, 1577836800))
            _, reindexados, _ = core.index_dir(tmp)
            self.assertEqual(reindexados, 1)
            self.assertEqual(core.search(tmp, "alfa"), [])
            self.assertEqual(core.search(tmp, "beta"), ["a.md"])

    def test_it003_ciclo_remocao_com_janela_de_busca(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "b.md": "exclusivo"})
            core.index_dir(tmp)
            os.remove(os.path.join(tmp, "b.md"))
            self.assertEqual(core.search(tmp, "exclusivo"), ["b.md"])  # US-001.EC-4
            _, _, removidos = core.index_dir(tmp)
            self.assertEqual(removidos, 1)
            self.assertEqual(core.search(tmp, "exclusivo"), [])

    def test_it004_indice_apagado_entre_rodadas(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "b.md": "beta"})
            core.index_dir(tmp)
            for sufixo in ("", "-wal", "-shm"):
                caminho = os.path.join(tmp, core.INDEX_NAME + sufixo)
                if os.path.exists(caminho):
                    os.remove(caminho)
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (2, 2, 0))
            self.assertEqual(core.search(tmp, "alfa"), ["a.md"])

    def test_it005_esquema_antigo_recria(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "b.md": "beta"})
            core.index_dir(tmp)
            conn = sqlite3.connect(os.path.join(tmp, core.INDEX_NAME))
            conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
            conn.commit()
            conn.close()
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (2, 2, 0))
            self.assertEqual(core.search(tmp, "alfa"), ["a.md"])

    def test_search_esquema_divergente_levanta_indexmissing(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento"})
            core.index_dir(tmp)
            conn = sqlite3.connect(os.path.join(tmp, core.INDEX_NAME))
            conn.execute("UPDATE meta SET value = '0' WHERE key = 'schema_version'")
            conn.commit()
            conn.close()
            with self.assertRaises(core.IndexMissing):
                core.search(tmp, "orcamento")


if __name__ == "__main__":
    unittest.main()
