import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

PRECISA_ROOT = os.geteuid() == 0 if hasattr(os, "geteuid") else False


def _rodar(diretorio, *args, entrada=None):
    """Lanca `python -m kvstore <diretorio> <args>` como processo real (E2E de verdade)."""
    return subprocess.run(
        [sys.executable, "-m", "kvstore", diretorio, *args],
        input=entrada,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )


class TestJornadaPrincipal(unittest.TestCase):
    def test_e2e001_golden_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")

            r = _rodar(d, "set", "posicao", "1042")
            self.assertEqual(r.returncode, 0)

            r = _rodar(d, "set", "config", '{"modo":"producao"}')
            self.assertEqual(r.returncode, 0)

            r = _rodar(d, "list")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"config\nposicao\n")

            r = _rodar(d, "get", "posicao")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"1042")

            r = _rodar(d, "del", "posicao")
            self.assertEqual(r.returncode, 0)

            r = _rodar(d, "list")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"config\n")

    def test_e2e002_get_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "get", "inexistente")
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.stderr, b"kvstore: chave nao encontrada: inexistente\n")
            self.assertEqual(r.returncode, 1)

    def test_e2e003_fidelidade_sem_newline(self):
        with tempfile.TemporaryDirectory() as tmp:
            _rodar(tmp, "set", "com_newline", "linha\n")
            r = _rodar(tmp, "get", "com_newline")
            self.assertEqual(r.stdout, b"linha\n")

            _rodar(tmp, "set", "sem_newline", "1042")
            r = _rodar(tmp, "get", "sem_newline")
            self.assertEqual(r.stdout, b"1042")

    def test_e2e004_sobrescrita(self):
        with tempfile.TemporaryDirectory() as tmp:
            _rodar(tmp, "set", "k", "primeiro")
            _rodar(tmp, "set", "k", "segundo")
            r = _rodar(tmp, "get", "k")
            self.assertEqual(r.stdout, b"segundo")

    def test_e2e008_del(self):
        with tempfile.TemporaryDirectory() as tmp:
            _rodar(tmp, "set", "posicao", "1042")

            r = _rodar(tmp, "del", "posicao")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")

            r = _rodar(tmp, "get", "posicao")
            self.assertEqual(r.returncode, 1)

            r = _rodar(tmp, "del", "posicao")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.stderr, b"")

    def test_e2e009_list_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "list")
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.returncode, 0)

    def test_e2e010_list_ordenado(self):
        with tempfile.TemporaryDirectory() as tmp:
            _rodar(tmp, "set", "posicao", "1")
            _rodar(tmp, "set", "config", "2")
            _rodar(tmp, "set", "contador", "3")
            r = _rodar(tmp, "list")
            self.assertEqual(r.stdout, b"config\ncontador\nposicao\n")
            self.assertEqual(r.returncode, 0)


class TestEntradasELimites(unittest.TestCase):
    def test_e2e005_chave_vazia(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "", "v")
            self.assertEqual(r.stderr, b"kvstore: chave nao pode ser vazia\n")
            self.assertEqual(r.returncode, 2)

            r = _rodar(tmp, "list")
            self.assertEqual(r.stdout, b"")

    def test_e2e006_valor_vazio_distinto_de_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "k", "")
            self.assertEqual(r.returncode, 0)

            r = _rodar(tmp, "get", "k")
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.returncode, 0)

    def test_e2e007_chaves_hostis(self):
        with tempfile.TemporaryDirectory() as tmp:
            for chave in ("a/b", "../fuga", "chave com espaco"):
                r = _rodar(tmp, "set", chave, "v")
                self.assertEqual(r.returncode, 0, chave)
                r = _rodar(tmp, "get", chave)
                self.assertEqual(r.stdout, b"v", chave)

            arquivos = os.listdir(tmp)
            for nome in arquivos:
                self.assertTrue(nome.startswith("kvstore.sqlite3"), nome)

    def test_e2e011_valor_grande_por_stdin(self):
        with tempfile.TemporaryDirectory() as tmp:
            # o valor precisa ser UTF-8 valido; usa um byte ASCII repetido em vez de aleatorio puro.
            dados = b"a" * (10 * 1024 * 1024)
            r = _rodar(tmp, "set", "dump", "-", entrada=dados)
            self.assertEqual(r.returncode, 0)

            r = _rodar(tmp, "get", "dump")
            self.assertEqual(r.stdout, dados)

    def test_e2e012_stdin_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "k", "-", entrada=b"")
            self.assertEqual(r.returncode, 0)

            r = _rodar(tmp, "get", "k")
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.returncode, 0)

    def test_e2e013_stdin_e_argumento_juntos(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "k", "-", "extra", entrada=b"")
            self.assertEqual(
                r.stderr,
                b"kvstore: com '-' o valor vem da entrada padrao; remova o argumento\n",
            )
            self.assertEqual(r.returncode, 2)

    def test_e2e014_stdin_nao_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "k", "-", entrada=b"\xff\xfe")
            self.assertIn(
                b"kvstore: entrada padrao nao e' UTF-8 valido no byte ",
                r.stderr,
            )
            self.assertEqual(r.returncode, 2)

            r = _rodar(tmp, "list")
            self.assertEqual(r.stdout, b"")

    def test_e2e024_valor_5mb_por_pipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            valor = b"x" * 5_000_000
            r = _rodar(tmp, "set", "grande", "-", entrada=valor)
            self.assertEqual(r.returncode, 0)

            r = _rodar(tmp, "get", "grande")
            self.assertEqual(len(r.stdout), 5_000_000)
            self.assertEqual(r.stdout, valor)

    def test_e2e027_valor_literal_traco(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrada = subprocess.run(
                ["printf", "--", "-"], stdout=subprocess.PIPE, check=True
            ).stdout
            r = _rodar(tmp, "set", "k", "-", entrada=entrada)
            self.assertEqual(r.returncode, 0)

            r = _rodar(tmp, "get", "k")
            self.assertEqual(r.stdout, b"-")


class TestUsoEErrosDeInvocacao(unittest.TestCase):
    def test_e2e015_sem_argumentos(self):
        r = subprocess.run(
            [sys.executable, "-m", "kvstore"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(
            r.stderr,
            b"kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]\n",
        )
        self.assertEqual(r.returncode, 2)

    def test_e2e016_verbo_desconhecido(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "pop", "x")
            self.assertEqual(
                r.stderr,
                b"kvstore: uso: python -m kvstore <diretorio> {set|get|del|list} [args]\n",
            )
            self.assertEqual(r.returncode, 2)

    def test_e2e017_aridade_errada(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "posicao")
            self.assertEqual(
                r.stderr,
                b"kvstore: uso: python -m kvstore <diretorio> set <chave> <valor>\n",
            )
            self.assertEqual(r.returncode, 2)


class TestDiretorioESistemaDeArquivos(unittest.TestCase):
    def test_e2e018_diretorio_inexistente_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "nao_existe_ainda")
            self.assertFalse(os.path.exists(d))

            r = _rodar(d, "set", "k", "v")
            self.assertEqual(r.returncode, 0)
            self.assertTrue(os.path.isdir(d))

            r = _rodar(d, "get", "k")
            self.assertEqual(r.stdout, b"v")

    def test_e2e019_diretorio_inexistente_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "nao_existe_ainda")
            r = _rodar(d, "list")
            self.assertEqual(r.stdout, b"")
            self.assertEqual(r.returncode, 0)

    def test_e2e020_caminho_e_arquivo_comum(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "arquivo_comum")
            with open(caminho, "w") as f:
                f.write("nao sou diretorio")

            r = _rodar(caminho, "set", "k", "v")
            self.assertTrue(r.stderr.startswith(b"kvstore: nao foi possivel abrir "), r.stderr)
            self.assertIn(caminho.encode(), r.stderr)
            self.assertEqual(r.returncode, 3)

    @unittest.skipIf(PRECISA_ROOT, "root ignora permissao de diretorio")
    def test_e2e021_pai_sem_permissao(self):
        with tempfile.TemporaryDirectory() as tmp:
            pai = os.path.join(tmp, "pai")
            os.makedirs(pai)
            os.chmod(pai, 0o500)
            alvo = os.path.join(pai, "filho")
            try:
                r = _rodar(alvo, "set", "k", "v")
                self.assertEqual(r.returncode, 3)
                self.assertFalse(os.path.exists(alvo))
            finally:
                os.chmod(pai, 0o700)

    def test_e2e022_get_em_diretorio_virgem(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "virgem")
            r = _rodar(d, "get", "k")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(
                r.stderr, b"kvstore: chave nao encontrada: k\n"
            )

    @unittest.skipIf(PRECISA_ROOT, "root ignora permissao de diretorio")
    def test_e2e025_diretorio_sem_permissao_de_escrita(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "so_leitura")
            os.makedirs(d)
            antes = set(os.listdir(d))
            os.chmod(d, 0o500)
            try:
                r = _rodar(d, "set", "k", "v")
                self.assertEqual(r.returncode, 3)
            finally:
                os.chmod(d, 0o700)
            depois = set(os.listdir(d))
            self.assertEqual(antes, depois)

    def test_e2e026_arquivos_em_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _rodar(tmp, "set", "k", "v")
            self.assertEqual(r.returncode, 0)

            arquivos = os.listdir(tmp)
            self.assertIn("kvstore.sqlite3", arquivos)
            for nome in arquivos:
                self.assertTrue(nome.startswith("kvstore.sqlite3"), nome)


class TestRobustezDeSaida(unittest.TestCase):
    def test_e2e023_list_com_pipe_fechado(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = sqlite3.connect(os.path.join(tmp, "kvstore.sqlite3"))
            con.execute("PRAGMA journal_mode = WAL")
            con.execute(
                "CREATE TABLE IF NOT EXISTS kv (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)"
            )
            con.executemany(
                "INSERT INTO kv VALUES (?, ?)",
                [(f"chave{i:07d}", "v" * 40) for i in range(100_000)],
            )
            con.commit()
            con.close()

            proc = subprocess.Popen(
                [sys.executable, "-m", "kvstore", tmp, "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            primeira_linha = proc.stdout.readline()
            self.assertTrue(primeira_linha.startswith(b"chave"))
            proc.stdout.close()
            _, stderr = proc.communicate(timeout=30)

            self.assertNotIn(b"BrokenPipeError", stderr)
            self.assertNotIn(b"Traceback", stderr)


if __name__ == "__main__":
    unittest.main()
