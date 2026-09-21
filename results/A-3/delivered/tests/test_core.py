import hashlib
import os
import tempfile
import unittest

from fidx import core


def arvore(raiz: str, arquivos: dict[str, str]) -> None:
    for caminho, conteudo in arquivos.items():
        full = os.path.join(raiz, caminho)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(conteudo)


class TestTokenize(unittest.TestCase):
    def test_ut001_palavras_simples(self):
        self.assertEqual(core.tokenize("Orcamento Anual 2026"), ["orcamento", "anual", "2026"])

    def test_ut002_acento_preservado(self):
        self.assertEqual(core.tokenize("Orçamento do mês"), ["orçamento", "do", "mês"])

    def test_ut003_pontuacao_quebra_underscore_nao(self):
        self.assertEqual(core.tokenize("a,b\nc-d;e_f"), ["a", "b", "c", "d", "e_f"])

    def test_ut004_vazio_e_so_pontuacao(self):
        self.assertEqual(core.tokenize(""), [])
        self.assertEqual(core.tokenize("--- !!! ---"), [])


class TestFileDigest(unittest.TestCase):
    def test_ut005_digest_bate_com_hashlib(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.txt")
            with open(path, "wb") as f:
                f.write(b"conteudo\n")
            self.assertEqual(core.file_digest(path), hashlib.sha256(b"conteudo\n").hexdigest())

    def test_ut006_arquivo_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vazio.txt")
            open(path, "wb").close()
            self.assertEqual(
                core.file_digest(path),
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            )

    def test_ut007_arquivo_maior_que_bloco(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "grande.bin")
            data = os.urandom(3 * 1024 * 1024)
            with open(path, "wb") as f:
                f.write(data)
            self.assertEqual(core.file_digest(path), hashlib.sha256(data).hexdigest())


class TestIterFiles(unittest.TestCase):
    def test_ut008_subpastas_ordem_estavel(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "x", "sub/b.txt": "x", "sub/dir/c.md": "x"})
            self.assertEqual(list(core.iter_files(tmp)), ["a.md", "sub/b.txt", "sub/dir/c.md"])
            self.assertEqual(list(core.iter_files(tmp)), list(core.iter_files(tmp)))

    def test_ut009_dot_entries_ignoradas(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(
                tmp,
                {
                    ".git/config": "x",
                    ".oculto.md": "x",
                    ".fidx.sqlite3": "x",
                    ".fidx.sqlite3-wal": "x",
                    "visivel.md": "x",
                },
            )
            self.assertEqual(list(core.iter_files(tmp)), ["visivel.md"])

    def test_ut010_symlink_de_diretorio_nao_recursa(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "x"})
            os.makedirs(os.path.join(tmp, "sub"))
            os.symlink(tmp, os.path.join(tmp, "sub", "loop"), target_is_directory=True)
            resultado = list(core.iter_files(tmp))
            self.assertNotIn("sub/loop", resultado)
            self.assertEqual(resultado, ["a.md"])

    def test_ut011_symlink_de_arquivo_ignorado(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "x"})
            os.symlink(os.path.join(tmp, "a.md"), os.path.join(tmp, "link.md"))
            self.assertEqual(list(core.iter_files(tmp)), ["a.md"])

    def test_ut012_diretorio_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list(core.iter_files(tmp)), [])


class TestIndexSearchCiclo(unittest.TestCase):
    def test_ut013_termo_em_dois_arquivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento aqui", "sub/b.md": "tem orcamento tambem"})
            core.index_dir(tmp)
            self.assertEqual(core.search(tmp, "orcamento"), ["a.md", "sub/b.md"])

    def test_ut014_conteudo_identico_dois_caminhos(self):
        with tempfile.TemporaryDirectory() as tmp:
            conteudo = "orcamento " * 10
            arvore(tmp, {"a.md": conteudo, "copia.md": conteudo})
            core.index_dir(tmp)
            self.assertEqual(core.search(tmp, "orcamento"), sorted(["a.md", "copia.md"]))

    def test_ut015_search_sem_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(core.IndexMissing):
                core.search(tmp, "orcamento")
            self.assertFalse(os.path.exists(os.path.join(tmp, core.INDEX_NAME)))

    def test_ut016_varios_tokens_e_logico(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento 2026", "b.md": "orcamento"})
            core.index_dir(tmp)
            self.assertEqual(core.search(tmp, "orcamento 2026"), ["a.md"])

    def test_ut017_termo_sem_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento"})
            core.index_dir(tmp)
            with self.assertRaises(core.EmptyTerm):
                core.search(tmp, "---")
            with self.assertRaises(core.EmptyTerm):
                core.search(tmp, "")

    def test_ut018_primeira_rodada_conta_e_cria_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            arquivos = {f"f{i}.md": f"conteudo {i}" for i in range(12)}
            arvore(tmp, arquivos)
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (12, 12, 0))
            self.assertTrue(os.path.exists(os.path.join(tmp, core.INDEX_NAME)))

    def test_ut019_busca_insensivel_a_maiuscula(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "Orçamento Anual"})
            core.index_dir(tmp)
            self.assertEqual(core.search(tmp, "ORÇAMENTO"), ["a.md"])


class TestIntegracaoCicloCompleto(unittest.TestCase):
    def test_it001_arvore_com_acento_e_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(
                tmp,
                {
                    "a.md": "orçamento do mes",
                    "sub/b.txt": "tambem tem orçamento aqui",
                    ".git/config": "orçamento nao deve contar",
                },
            )
            total, reindexados, removidos = core.index_dir(tmp)
            self.assertEqual((total, reindexados, removidos), (2, 2, 0))
            self.assertEqual(core.search(tmp, "orçamento"), ["a.md", "sub/b.txt"])
            self.assertEqual(core.search(tmp, "mes"), ["a.md"])
            self.assertEqual(core.search(tmp, "nao"), [])


if __name__ == "__main__":
    unittest.main()
