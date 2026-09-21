import os
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import kvstore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ler_com_timeout(fd, tamanho, prazo):
    """os.read com teto de tempo: nunca deixa a suite travar esperando um sinal que nao vem."""
    prontos, _, _ = select.select([fd], [], [], prazo)
    if not prontos:
        raise AssertionError(f"tempo esgotado ({prazo}s) esperando sinal de prontidao")
    return os.read(fd, tamanho)

SCRIPT_SET_E_MORRER = r"""
import os, sys
import kvstore

s = kvstore.Store(sys.argv[1])
s.set(sys.argv[2], sys.argv[3])
os._exit(0)
"""

SCRIPT_GRAVAR_E_BLOQUEAR = r"""
import os, sys
import kvstore

s = kvstore.Store(sys.argv[1])
s.set(sys.argv[2], sys.argv[3])
os.write(int(sys.argv[4]), b"pronto\n")
os.read(int(sys.argv[5]), 1)
"""

SCRIPT_MORRER_DURANTE_ESCRITA = r"""
import os, sys
import kvstore

fd_pronto = int(sys.argv[2])
valor = sys.stdin.read()
sinalizado = False

def _ao_meio():
    global sinalizado
    if not sinalizado:
        sinalizado = True
        os.write(fd_pronto, b"meio\n")
    return 0

s = kvstore.Store(sys.argv[1])
s._con.set_progress_handler(_ao_meio, 1)
s.set("blob", valor)
"""

SCRIPT_501_CHAVES = r"""
import os, sys
import kvstore

fd_pronto = int(sys.argv[2])
sinalizado = False

def _ao_meio():
    global sinalizado
    if not sinalizado:
        sinalizado = True
        os.write(fd_pronto, b"meio\n")
    return 0

s = kvstore.Store(sys.argv[1])
s._con.set_progress_handler(_ao_meio, 1)
s.set("chave00500", "valor500")
"""

SCRIPT_DELETE_E_MORRER = r"""
import os, sys
import kvstore

s = kvstore.Store(sys.argv[1])
s.delete(sys.argv[2])
os._exit(0)
"""

SCRIPT_FALHA_RLIMIT = r"""
import resource, sys
import kvstore

resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
valor = sys.stdin.read()
s = kvstore.Store(sys.argv[1])
s.set("blob", valor)
"""

SCRIPT_ESCRITOR_EM_LACO = r"""
import os, sys
import kvstore

fd_pronto = int(sys.argv[2])
n = int(sys.argv[3])
s = kvstore.Store(sys.argv[1])
os.write(fd_pronto, b"pronto\n")
for i in range(n):
    s.set("contador", f"valor{i:06d}")
"""

SCRIPT_TRAVAR_ESCRITA = r"""
import os, sys
import kvstore

s = kvstore.Store(sys.argv[1])
s._con.execute("BEGIN IMMEDIATE")
os.write(int(sys.argv[2]), b"pronto\n")
os.read(int(sys.argv[3]), 1)
"""

SCRIPT_GRAVAR_E_FECHAR = r"""
import sys
import kvstore

valor = sys.stdin.read()
with kvstore.Store(sys.argv[1]) as s:
    s.set(sys.argv[2], valor)
"""

SCRIPT_DELETAR_E_FECHAR = r"""
import sys
import kvstore

with kvstore.Store(sys.argv[1]) as s:
    s.delete(sys.argv[2])
"""

SCRIPT_CRESCER_MESMA_CHAVE = r"""
import sys
import kvstore

valor = "x" * 4096
n = int(sys.argv[2])
with kvstore.Store(sys.argv[1]) as s:
    for _ in range(n):
        s.set("contador", valor)
"""

SCRIPT_MUITAS_CHAVES = r"""
import sys
import kvstore

valor = "y" * 4096
n = int(sys.argv[2])
with kvstore.Store(sys.argv[1]) as s:
    for i in range(n):
        s.set(f"chave{i:05d}", valor)
"""


@unittest.skipUnless(os.name == "posix", "morte abrupta requer sinais POSIX")
class TestDurabilidade(unittest.TestCase):
    def test_it010_morte_sem_encerramento_limpo(self):
        with tempfile.TemporaryDirectory() as tmp:
            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_SET_E_MORRER, tmp, "posicao", "1042"],
                cwd=ROOT,
            )
            self.assertEqual(resultado.returncode, 0)
            with kvstore.Store(tmp) as s:
                self.assertEqual(s.get("posicao"), "1042")

    def test_it011_sigkill_externo_apos_confirmacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            r_pronto, w_pronto = os.pipe()
            r_bloqueio, w_bloqueio = os.pipe()
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    SCRIPT_GRAVAR_E_BLOQUEAR,
                    tmp,
                    "posicao",
                    "1042",
                    str(w_pronto),
                    str(r_bloqueio),
                ],
                cwd=ROOT,
                pass_fds=(w_pronto, r_bloqueio),
            )
            os.close(w_pronto)
            os.close(r_bloqueio)
            try:
                mensagem = os.read(r_pronto, 7)
                self.assertEqual(mensagem, b"pronto\n")
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait()
                self.assertEqual(proc.returncode, -signal.SIGKILL)
            finally:
                os.close(r_pronto)
                os.close(w_bloqueio)
            with kvstore.Store(tmp) as s:
                self.assertEqual(s.get("posicao"), "1042")

    def test_it012_morte_durante_escrita(self):
        antigo = "A" * 1_000_000
        novo = "B" * 8_000_000
        for _ in range(3):
            with tempfile.TemporaryDirectory() as tmp:
                with kvstore.Store(tmp) as s:
                    s.set("blob", antigo)
                    s.set("sentinela", "intacta")
                r_pronto, w_pronto = os.pipe()
                proc = subprocess.Popen(
                    [sys.executable, "-c", SCRIPT_MORRER_DURANTE_ESCRITA, tmp, str(w_pronto)],
                    cwd=ROOT,
                    pass_fds=(w_pronto,),
                    stdin=subprocess.PIPE,
                )
                os.close(w_pronto)
                proc.stdin.write(novo.encode("utf-8"))
                proc.stdin.close()
                mensagem = os.read(r_pronto, 5)
                os.close(r_pronto)
                self.assertEqual(mensagem, b"meio\n")
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait()
                with kvstore.Store(tmp) as s:
                    lido = s.get("blob")
                    self.assertIn(lido, (antigo, novo))
                    self.assertEqual(s.get("sentinela"), "intacta")

    def test_it013_nunca_volta_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                for i in range(500):
                    s.set(f"chave{i:05d}", f"valor{i}")
            r_pronto, w_pronto = os.pipe()
            proc = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_501_CHAVES, tmp, str(w_pronto)],
                cwd=ROOT,
                pass_fds=(w_pronto,),
            )
            os.close(w_pronto)
            mensagem = os.read(r_pronto, 5)
            os.close(r_pronto)
            self.assertEqual(mensagem, b"meio\n")
            os.kill(proc.pid, signal.SIGKILL)
            proc.wait()
            with kvstore.Store(tmp) as s:
                chaves = s.keys()
                self.assertIn(len(chaves), (500, 501))
                for i in range(500):
                    self.assertEqual(s.get(f"chave{i:05d}"), f"valor{i}")

    def test_it014_remocao_e_duravel(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("posicao", "1042")
            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_DELETE_E_MORRER, tmp, "posicao"],
                cwd=ROOT,
            )
            self.assertEqual(resultado.returncode, 0)
            with kvstore.Store(tmp) as s:
                self.assertIsNone(s.get("posicao"))

    def test_it040_falha_de_escrita_preserva_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            with kvstore.Store(tmp) as s:
                s.set("blob", "antigo")
            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_FALHA_RLIMIT, tmp],
                cwd=ROOT,
                input=("B" * 5_000_000).encode("utf-8"),
            )
            self.assertNotEqual(resultado.returncode, 0)
            with kvstore.Store(tmp) as s:
                self.assertEqual(s.get("blob"), "antigo")
                s.set("nova", "chave")
                self.assertEqual(s.get("nova"), "chave")


@unittest.skipUnless(os.name == "posix", "concorrencia entre processos requer sinais POSIX")
class TestConcorrencia(unittest.TestCase):
    def test_it020_leitor_durante_escritor(self):
        with tempfile.TemporaryDirectory() as tmp:
            r_pronto, w_pronto = os.pipe()
            n = 500
            proc = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_ESCRITOR_EM_LACO, tmp, str(w_pronto), str(n)],
                cwd=ROOT,
                pass_fds=(w_pronto,),
            )
            os.close(w_pronto)
            try:
                mensagem = _ler_com_timeout(r_pronto, 7, 10)
                self.assertEqual(mensagem, b"pronto\n")
                leitor = kvstore.Store(tmp)
                try:
                    prazo = time.monotonic() + 30
                    while proc.poll() is None:
                        if time.monotonic() > prazo:
                            proc.kill()
                            self.fail("escritor nao terminou dentro do prazo de seguranca")
                        valor = leitor.get("contador")
                        if valor is not None:
                            self.assertRegex(valor, r"^valor\d{6}$")
                    valor_final = leitor.get("contador")
                    self.assertRegex(valor_final, r"^valor\d{6}$")
                finally:
                    leitor.close()
            finally:
                os.close(r_pronto)
            self.assertEqual(proc.wait(timeout=10), 0)

    def test_it021_dois_escritores_chaves_diferentes(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc_a = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_SET_E_MORRER, tmp, "a", "valor-a"], cwd=ROOT
            )
            proc_b = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_SET_E_MORRER, tmp, "b", "valor-b"], cwd=ROOT
            )
            self.assertEqual(proc_a.wait(timeout=15), 0)
            self.assertEqual(proc_b.wait(timeout=15), 0)
            with kvstore.Store(tmp) as s:
                self.assertEqual(s.get("a"), "valor-a")
                self.assertEqual(s.get("b"), "valor-b")

    def test_it022_dois_escritores_mesma_chave(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc_1 = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_SET_E_MORRER, tmp, "k", "primeiro"], cwd=ROOT
            )
            proc_2 = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_SET_E_MORRER, tmp, "k", "segundo"], cwd=ROOT
            )
            self.assertEqual(proc_1.wait(timeout=15), 0)
            self.assertEqual(proc_2.wait(timeout=15), 0)
            with kvstore.Store(tmp) as s:
                self.assertIn(s.get("k"), ("primeiro", "segundo"))

    def test_it023_contencao_alem_da_espera(self):
        with tempfile.TemporaryDirectory() as tmp:
            r_pronto, w_pronto = os.pipe()
            r_bloqueio, w_bloqueio = os.pipe()
            proc = subprocess.Popen(
                [sys.executable, "-c", SCRIPT_TRAVAR_ESCRITA, tmp, str(w_pronto), str(r_bloqueio)],
                cwd=ROOT,
                pass_fds=(w_pronto, r_bloqueio),
            )
            os.close(w_pronto)
            os.close(r_bloqueio)
            try:
                mensagem = _ler_com_timeout(r_pronto, 7, 10)
                self.assertEqual(mensagem, b"pronto\n")
                inicio = time.monotonic()
                resultado = subprocess.run(
                    [sys.executable, "-m", "kvstore", tmp, "set", "k", "v"],
                    cwd=ROOT,
                    capture_output=True,
                    timeout=10,
                )
                duracao = time.monotonic() - inicio
                self.assertEqual(resultado.returncode, 3)
                self.assertIn(
                    b"kvstore: armazenamento ocupado por outro processo (5s)",
                    resultado.stderr,
                )
                self.assertLess(duracao, 10)
            finally:
                os.close(w_bloqueio)
                os.close(r_pronto)
                proc.wait(timeout=10)


@unittest.skipUnless(os.name == "posix", "crescimento medido via processos requer sinais POSIX")
class TestCrescimento(unittest.TestCase):
    def test_it030_tamanho_acompanha_o_vivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            n = 2000
            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_CRESCER_MESMA_CHAVE, tmp, str(n)],
                cwd=ROOT,
                timeout=60,
            )
            self.assertEqual(resultado.returncode, 0)
            caminho_banco = os.path.join(tmp, "kvstore.sqlite3")
            self.assertLess(os.path.getsize(caminho_banco), 2 * 1024 * 1024)
            with kvstore.Store(tmp) as s:
                self.assertEqual(s.get("contador"), "x" * 4096)

    def test_it031_lista_e_leitura_em_escala(self):
        with tempfile.TemporaryDirectory() as tmp:
            n = 2000
            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_MUITAS_CHAVES, tmp, str(n)],
                cwd=ROOT,
                timeout=60,
            )
            self.assertEqual(resultado.returncode, 0)

            resultado_list = subprocess.run(
                [sys.executable, "-m", "kvstore", tmp, "list"],
                cwd=ROOT,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(resultado_list.returncode, 0)
            linhas = resultado_list.stdout.decode("utf-8").splitlines()
            self.assertEqual(linhas, [f"chave{i:05d}" for i in range(n)])

            meio = n // 2
            resultado_get = subprocess.run(
                [sys.executable, "-m", "kvstore", tmp, "get", f"chave{meio:05d}"],
                cwd=ROOT,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(resultado_get.returncode, 0)
            self.assertEqual(resultado_get.stdout.decode("utf-8"), "y" * 4096)

    def test_it032_reaproveitamento_de_espaco(self):
        with tempfile.TemporaryDirectory() as tmp:
            valor_grande = "z" * (4 * 1024 * 1024)
            caminho_banco = os.path.join(tmp, "kvstore.sqlite3")

            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_GRAVAR_E_FECHAR, tmp, "grande"],
                cwd=ROOT,
                input=valor_grande.encode("utf-8"),
                timeout=30,
            )
            self.assertEqual(resultado.returncode, 0)
            tamanho_com_dado = os.path.getsize(caminho_banco)

            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_DELETAR_E_FECHAR, tmp, "grande"],
                cwd=ROOT,
                timeout=30,
            )
            self.assertEqual(resultado.returncode, 0)
            tamanho_apos_remocao = os.path.getsize(caminho_banco)
            self.assertGreaterEqual(tamanho_apos_remocao, tamanho_com_dado)

            resultado = subprocess.run(
                [sys.executable, "-c", SCRIPT_GRAVAR_E_FECHAR, tmp, "novo"],
                cwd=ROOT,
                input=valor_grande.encode("utf-8"),
                timeout=30,
            )
            self.assertEqual(resultado.returncode, 0)
            tamanho_final = os.path.getsize(caminho_banco)
            self.assertLess(tamanho_final, tamanho_com_dado * 1.5)

            with kvstore.Store(tmp) as s:
                self.assertEqual(s.get("novo"), valor_grande)
                self.assertIsNone(s.get("grande"))


if __name__ == "__main__":
    unittest.main()
