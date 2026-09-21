import os
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


def despejo(tmp: str):
    conn = core.open_index(tmp, create=False)
    try:
        files = sorted(conn.execute("SELECT path, sha256 FROM files"))
        postings = sorted(conn.execute("SELECT term, path FROM postings"))
    finally:
        conn.close()
    return files, postings


class TestTolerancia(unittest.TestCase):
    def test_ut030_bytes_indecifraveis(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.md"), "wb") as f:
                f.write(b"\xff\xfe ola mundo")
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 0))
            self.assertEqual(core.search(tmp, "ola"), ["a.md"])

    def test_ut031_arquivo_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "vazio.md"), "wb").close()
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 0))
            conn = core.open_index(tmp, create=False)
            try:
                files = [r[0] for r in conn.execute("SELECT path FROM files")]
                postings = [r[0] for r in conn.execute("SELECT path FROM postings")]
            finally:
                conn.close()
            self.assertEqual(files, ["vazio.md"])
            self.assertEqual(postings, [])

    @unittest.skipIf(os.geteuid() == 0, "root ignora bit de permissao")
    def test_ut032_arquivo_sem_permissao_pulado(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento", "sem-acesso.md": "segredo"})
            caminho = os.path.join(tmp, "sem-acesso.md")
            os.chmod(caminho, 0o000)
            avisos: list[tuple[str, str]] = []
            try:
                resultado = core.index_dir(tmp, on_pulado=lambda p, m: avisos.append((p, m)))
            finally:
                os.chmod(caminho, 0o644)
            self.assertEqual(resultado, (1, 1, 0))
            self.assertEqual(len(avisos), 1)
            self.assertEqual(avisos[0][0], "sem-acesso.md")
            self.assertEqual(core.search(tmp, "orcamento"), ["a.md"])

    @unittest.skipIf(os.geteuid() == 0, "root ignora bit de permissao")
    def test_arquivo_ja_indexado_fica_ilegivel_nao_e_removido(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"segredo.md": "conteudo secreto"})
            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (1, 1, 0))
            self.assertEqual(core.search(tmp, "secreto"), ["segredo.md"])

            caminho = os.path.join(tmp, "segredo.md")
            os.chmod(caminho, 0o000)
            try:
                avisos: list[tuple[str, str]] = []
                resultado = core.index_dir(tmp, on_pulado=lambda p, m: avisos.append((p, m)))
            finally:
                os.chmod(caminho, 0o644)

            self.assertEqual(resultado, (1, 0, 0))
            self.assertEqual([p for p, _ in avisos], ["segredo.md"])
            self.assertEqual(core.search(tmp, "secreto"), ["segredo.md"])

    def test_ut033_arquivo_some_durante_varredura(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento", "some.md": "efemero"})
            original_iter = core.iter_files

            def fake_iter(root):
                for rel in original_iter(root):
                    if rel == "some.md":
                        os.remove(os.path.join(root, "some.md"))
                    yield rel

            avisos: list[tuple[str, str]] = []
            with mock.patch.object(core, "iter_files", side_effect=fake_iter):
                resultado = core.index_dir(tmp, on_pulado=lambda p, m: avisos.append((p, m)))
            self.assertEqual(resultado, (1, 1, 0))
            self.assertEqual([p for p, _ in avisos], ["some.md"])
            self.assertEqual(core.search(tmp, "orcamento"), ["a.md"])


class TestConcorrenciaEAtomicidade(unittest.TestCase):
    def test_it006_interrupcao_com_indice_existente_faz_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "b.md": "beta", "c.md": "gama"})
            core.index_dir(tmp)
            antes = despejo(tmp)

            original_iter = core.iter_files
            chamadas = {"n": 0}

            def fake_iter(root):
                for rel in original_iter(root):
                    chamadas["n"] += 1
                    if chamadas["n"] > 1:
                        raise RuntimeError("boom")
                    yield rel

            with mock.patch.object(core, "iter_files", side_effect=fake_iter):
                with self.assertRaises(RuntimeError):
                    core.index_dir(tmp)

            self.assertEqual(despejo(tmp), antes)

    def test_it007_rodada_concorrente_leva_indexbusy(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa"})
            core.index_dir(tmp)
            antes = despejo(tmp)

            bloqueio = sqlite3.connect(os.path.join(tmp, core.INDEX_NAME), isolation_level=None)
            bloqueio.execute("BEGIN IMMEDIATE")
            try:
                with mock.patch.object(core, "BUSY_TIMEOUT_S", 0.2):
                    with self.assertRaises(core.IndexBusy):
                        core.index_dir(tmp)
            finally:
                bloqueio.execute("ROLLBACK")
                bloqueio.close()

            self.assertEqual(despejo(tmp), antes)

    def test_it008_busca_durante_rodada_nao_bloqueia(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "orcamento"})
            core.index_dir(tmp)

            bloqueio = sqlite3.connect(os.path.join(tmp, core.INDEX_NAME), isolation_level=None)
            bloqueio.execute("BEGIN IMMEDIATE")
            try:
                with mock.patch.object(core, "BUSY_TIMEOUT_S", 0.5):
                    resultado = core.search(tmp, "orcamento")
            finally:
                bloqueio.execute("ROLLBACK")
                bloqueio.close()

            self.assertEqual(resultado, ["a.md"])

    def test_it009_interrupcao_na_rodada_inicial(self):
        with tempfile.TemporaryDirectory() as tmp:
            arvore(tmp, {"a.md": "alfa", "b.md": "beta"})

            original_iter = core.iter_files
            chamadas = {"n": 0}

            def fake_iter(root):
                for rel in original_iter(root):
                    chamadas["n"] += 1
                    if chamadas["n"] > 1:
                        raise RuntimeError("boom")
                    yield rel

            with mock.patch.object(core, "iter_files", side_effect=fake_iter):
                with self.assertRaises(RuntimeError):
                    core.index_dir(tmp)

            try:
                resultado_busca = core.search(tmp, "alfa")
            except core.IndexMissing:
                resultado_busca = []
            self.assertEqual(resultado_busca, [])

            resultado = core.index_dir(tmp)
            self.assertEqual(resultado, (2, 2, 0))
            self.assertEqual(core.search(tmp, "alfa"), ["a.md"])
            self.assertEqual(core.search(tmp, "beta"), ["b.md"])


if __name__ == "__main__":
    unittest.main()
