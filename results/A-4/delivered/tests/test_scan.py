import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from fidx import scan


class TestTokenizar(unittest.TestCase):
    def test_preserva_acento_e_normaliza_caixa(self):
        """UT-001"""
        self.assertEqual(
            scan.tokenizar("Orçamento Q3 aprovado"),
            {"orçamento", "q3", "aprovado"},
        )

    def test_repeticao_em_caixas_diferentes_vira_um_termo(self):
        """UT-002"""
        self.assertEqual(scan.tokenizar("GREP grep Grep"), {"grep"})

    def test_pontuacao_e_quebra_de_linha_separam_mas_underscore_nao(self):
        """UT-003"""
        self.assertEqual(
            scan.tokenizar("a-b, c.d\ne_f"),
            {"a", "b", "c", "d", "e_f"},
        )

    def test_texto_vazio_ou_so_pontuacao(self):
        """UT-004"""
        self.assertEqual(scan.tokenizar(""), set())
        self.assertEqual(scan.tokenizar("--- ... ///"), set())

    def test_unidade_e_a_palavra_inteira(self):
        """UT-005"""
        self.assertNotIn("orca", scan.tokenizar("orcamento anual"))


class TestLer(unittest.TestCase):
    def test_le_texto_e_calcula_digest(self):
        """UT-006"""
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "nota.txt"
            caminho.write_bytes(b"nota de reuniao")
            resultado = scan.ler(caminho)
            self.assertIsNotNone(resultado)
            digest, texto = resultado
            self.assertEqual(texto, "nota de reuniao")
            self.assertEqual(digest, hashlib.sha256(b"nota de reuniao").hexdigest())

    def test_binario_nao_decodificavel_devolve_none(self):
        """UT-007"""
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "dump.bin"
            caminho.write_bytes(b"\xff\xfe\x00\x01PK")
            self.assertIsNone(scan.ler(caminho))

    @unittest.skipIf(os.geteuid() == 0, "chmod 000 nao impede leitura como root")
    def test_arquivo_sem_permissao_devolve_none(self):
        """UT-008"""
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "secreto.txt"
            caminho.write_bytes(b"segredo")
            os.chmod(caminho, 0o000)
            try:
                self.assertIsNone(scan.ler(caminho))
            finally:
                os.chmod(caminho, 0o644)

    def test_digest_imune_a_mtime(self):
        """UT-009"""
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "a.txt"
            caminho.write_bytes(b"conteudo estavel")
            digest_original, _ = scan.ler(caminho)

            os.utime(caminho, (0, 0))
            digest_passado, _ = scan.ler(caminho)

            futuro = 4102444800  # 2100-01-01
            os.utime(caminho, (futuro, futuro))
            digest_futuro, _ = scan.ler(caminho)

            self.assertEqual(digest_original, digest_passado)
            self.assertEqual(digest_original, digest_futuro)

    def test_digest_sensivel_a_um_byte_com_mesmo_tamanho(self):
        """UT-010"""
        with tempfile.TemporaryDirectory() as tmp:
            caminho_a = Path(tmp) / "a.txt"
            caminho_b = Path(tmp) / "b.txt"
            caminho_a.write_bytes(b"aaaa")
            caminho_b.write_bytes(b"aaab")
            digest_a, _ = scan.ler(caminho_a)
            digest_b, _ = scan.ler(caminho_b)
            self.assertNotEqual(digest_a, digest_b)


class TestPercorrer(unittest.TestCase):
    def test_recursao_devolve_caminhos_relativos_com_barra(self):
        """UT-011"""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "a.txt").write_bytes(b"a")
            (raiz / "sub").mkdir()
            (raiz / "sub" / "b.txt").write_bytes(b"b")

            encontrados = {p.as_posix() for p in scan.percorrer(raiz)}
            self.assertEqual(encontrados, {"a.txt", "sub/b.txt"})

    def test_entradas_ocultas_e_git_sao_puladas(self):
        """UT-012"""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "visivel.txt").write_bytes(b"v")
            (raiz / ".oculto.txt").write_bytes(b"o")
            (raiz / ".fidx.sqlite3").write_bytes(b"x")
            (raiz / ".git").mkdir()
            (raiz / ".git" / "config").write_bytes(b"c")

            encontrados = {p.as_posix() for p in scan.percorrer(raiz)}
            self.assertEqual(encontrados, {"visivel.txt"})

    def test_pasta_vazia(self):
        """UT-013"""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(set(scan.percorrer(Path(tmp))), set())

    def test_link_simbolico_ciclico_termina_sem_repetir(self):
        """UT-014"""
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "a.txt").write_bytes(b"a")
            (raiz / "ciclo").symlink_to(raiz, target_is_directory=True)

            encontrados = list(scan.percorrer(raiz))
            encontrados_posix = [p.as_posix() for p in encontrados]

            self.assertEqual(len(encontrados_posix), len(set(encontrados_posix)))
            self.assertEqual(set(encontrados_posix), {"a.txt"})


if __name__ == "__main__":
    unittest.main()
