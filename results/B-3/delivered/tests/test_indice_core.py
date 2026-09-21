import os
import sqlite3
import tempfile
import time
import unittest

import fidx


class TestVarredura(unittest.TestCase):
    def test_ignora_ocultos_e_desce_subpastas(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "a", "b"))
            with open(os.path.join(tmp, "a", "b", "nota.txt"), "w") as f:
                f.write("nota")
            os.makedirs(os.path.join(tmp, ".git", "objects"))
            with open(os.path.join(tmp, ".git", "objects", "x"), "w") as f:
                f.write("x")
            with open(os.path.join(tmp, ".rascunho.txt"), "w") as f:
                f.write("rascunho")

            self.assertEqual(fidx._varrer(tmp), ["a/b/nota.txt"])


class TestTokenizacao(unittest.TestCase):
    def test_tokeniza_texto_com_acento_e_numero(self):
        self.assertEqual(
            fidx._tokenizar("Orçamento: R$ 10"), ["orçamento", "r", "10"]
        )


class TestBanco(unittest.TestCase):
    def test_abrir_duas_vezes_nao_duplica_esquema(self):
        with tempfile.TemporaryDirectory() as tmp:
            fidx._conectar(tmp).close()
            conexao = fidx._conectar(tmp)
            try:
                nomes = [
                    linha[0]
                    for linha in conexao.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                ]
                self.assertEqual(nomes.count("files"), 1)
                self.assertEqual(nomes.count("postings"), 1)
            finally:
                conexao.close()

    def test_versao_divergente_reconstroi_do_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            conexao = fidx._conectar(tmp)
            conexao.execute("INSERT INTO files (path, hash) VALUES ('a', 'h')")
            conexao.execute("PRAGMA user_version = 999")
            conexao.commit()
            conexao.close()

            conexao = fidx._conectar(tmp)
            try:
                versao = conexao.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(versao, fidx._SCHEMA_VERSION)
                linhas = conexao.execute("SELECT * FROM files").fetchall()
                self.assertEqual(linhas, [])
            finally:
                conexao.close()


class TestIndex(unittest.TestCase):
    def test_primeira_rodada_reprocessa_todos(self):
        with tempfile.TemporaryDirectory() as tmp:
            for nome in ("um.txt", "dois.txt", "tres.txt"):
                with open(os.path.join(tmp, nome), "w") as f:
                    f.write(f"conteudo de {nome}")

            self.assertEqual(fidx.index(tmp), (3, 0, 0))


class TestSearch(unittest.TestCase):
    def test_termo_em_dois_arquivos_retorna_ambos_em_ordem(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "b.txt"), "w") as f:
                f.write("orçamento do mes")
            with open(os.path.join(tmp, "a.txt"), "w") as f:
                f.write("Orçamento anual")
            with open(os.path.join(tmp, "c.txt"), "w") as f:
                f.write("sem o termo")

            fidx.index(tmp)

            self.assertEqual(fidx.search(tmp, "orçamento"), ["a.txt", "b.txt"])


class TestIncrementalidade(unittest.TestCase):
    def test_conteudo_mudou_com_data_antiga_reprocessa(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "nota.txt")
            with open(caminho, "w") as f:
                f.write("termo_antigo")
            fidx.index(tmp)

            with open(caminho, "w") as f:
                f.write("termo_novo")
            data_antiga = time.time() - 86400 * 30
            os.utime(caminho, (data_antiga, data_antiga))

            resumo = fidx.index(tmp)

            self.assertEqual(resumo, (1, 0, 0))
            self.assertEqual(fidx.search(tmp, "termo_novo"), ["nota.txt"])
            self.assertEqual(fidx.search(tmp, "termo_antigo"), [])

    def test_data_nova_sem_mudanca_de_conteudo_nao_reprocessa(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "nota.txt")
            with open(caminho, "w") as f:
                f.write("conteudo estavel")
            fidx.index(tmp)

            data_futura = time.time() + 86400 * 30
            os.utime(caminho, (data_futura, data_futura))

            resumo = fidx.index(tmp)

            self.assertEqual(resumo, (0, 1, 0))

    def test_pasta_inalterada_devolve_zero_reprocessados_e_busca_identica(self):
        with tempfile.TemporaryDirectory() as tmp:
            for nome in ("um.txt", "dois.txt"):
                with open(os.path.join(tmp, nome), "w") as f:
                    f.write(f"conteudo de {nome}")
            fidx.index(tmp)
            busca_antes = fidx.search(tmp, "conteudo")

            resumo = fidx.index(tmp)
            busca_depois = fidx.search(tmp, "conteudo")

            self.assertEqual(resumo, (0, 2, 0))
            self.assertEqual(busca_antes, busca_depois)

    def test_uma_mudanca_entre_tres_arquivos_reprocessa_so_um(self):
        with tempfile.TemporaryDirectory() as tmp:
            for nome in ("um.txt", "dois.txt", "tres.txt"):
                with open(os.path.join(tmp, nome), "w") as f:
                    f.write(f"conteudo de {nome}")
            fidx.index(tmp)

            with open(os.path.join(tmp, "dois.txt"), "w") as f:
                f.write("conteudo novo")

            resumo = fidx.index(tmp)

            self.assertEqual(resumo, (1, 2, 0))

    def test_arquivo_removido_sai_do_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            alvo = os.path.join(tmp, "removivel.txt")
            with open(alvo, "w") as f:
                f.write("termo_exclusivo")
            with open(os.path.join(tmp, "outro.txt"), "w") as f:
                f.write("outro conteudo")
            fidx.index(tmp)

            os.remove(alvo)
            resumo = fidx.index(tmp)

            self.assertEqual(resumo, (0, 1, 1))
            self.assertEqual(fidx.search(tmp, "termo_exclusivo"), [])

    def test_indice_nao_indexa_a_si_mesmo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "nota.txt"), "w") as f:
                f.write("conteudo")
            fidx.index(tmp)
            resumo = fidx.index(tmp)

            self.assertEqual(resumo.reprocessados, 0)
            conexao = sqlite3.connect(os.path.join(tmp, ".fidx", "index.sqlite3"))
            try:
                paths = [linha[0] for linha in conexao.execute("SELECT path FROM files")]
            finally:
                conexao.close()
            self.assertEqual(paths, ["nota.txt"])

    def test_arquivo_binario_nao_interrompe_a_rodada(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "binario.dat"), "wb") as f:
                f.write(b"\xff\xfe\x00\x01texto_com_bytes_invalidos\xfa")
            with open(os.path.join(tmp, "texto.txt"), "w") as f:
                f.write("conteudo legivel")

            resumo = fidx.index(tmp)

            self.assertEqual(resumo, (1, 0, 0))
            self.assertEqual(fidx.search(tmp, "conteudo"), ["texto.txt"])

    def test_arquivo_texto_vira_binario_sai_do_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "a.txt")
            with open(caminho, "w") as f:
                f.write("termo_valioso")
            fidx.index(tmp)
            self.assertEqual(fidx.search(tmp, "termo_valioso"), ["a.txt"])

            with open(caminho, "wb") as f:
                f.write(b"\xff\xfe\x00\x01bytes_invalidos\xfa")

            resumo_transicao = fidx.index(tmp)
            self.assertEqual(resumo_transicao, (0, 0, 1))
            self.assertEqual(fidx.search(tmp, "termo_valioso"), [])

            conexao = sqlite3.connect(os.path.join(tmp, ".fidx", "index.sqlite3"))
            try:
                self.assertEqual(
                    conexao.execute("SELECT path FROM files WHERE path = ?", ("a.txt",)).fetchall(),
                    [],
                )
            finally:
                conexao.close()

            for _ in range(2):
                resumo = fidx.index(tmp)
                self.assertEqual(resumo, (0, 0, 0))
                self.assertEqual(fidx.search(tmp, "termo_valioso"), [])


if __name__ == "__main__":
    unittest.main()
