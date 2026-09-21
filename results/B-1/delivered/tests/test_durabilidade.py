# Limitação declarada (design.md, Decisão 7): o teste de crash real desta seção mata o
# processo com SIGKILL, o que prova a ordem das operações sob morte de processo — a causa
# real de perda aqui (deploy e OOM). Isso NÃO prova sobrevivência a queda de energia: essa
# garantia depende só de o `fsync` ter sido de fato chamado, o que é responsabilidade do
# teste de ordem das operações abaixo (2.1), não do teste de crash (2.2).

import io
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import kvstore

_RAIZ_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT_CRASH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_apoio_crash.py")


class _FonteContada:
    """Envelope de leitura que registra o tamanho pedido em cada `.read(n)`."""

    def __init__(self, dados):
        self._buffer = io.BytesIO(dados)
        self.chamadas = []

    def read(self, tamanho=-1):
        bloco = self._buffer.read(tamanho)
        self.chamadas.append(tamanho)
        return bloco


class _DestinoContado:
    """Envelope de escrita que registra o tamanho de cada `.write(bloco)`."""

    def __init__(self):
        self._buffer = io.BytesIO()
        self.chamadas = []

    def write(self, bloco):
        self.chamadas.append(len(bloco))
        return self._buffer.write(bloco)

    def getvalue(self):
        return self._buffer.getvalue()


class TestOrdemDasOperacoes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.diretorio = self._tmp.name

    def test_set_faz_fsync_do_arquivo_antes_do_replace_e_fsync_do_diretorio_depois(self):
        sequencia = []

        def rastreador(nome, original):
            def chamada(*args, **kwargs):
                sequencia.append(nome)
                return original(*args, **kwargs)

            return chamada

        with mock.patch("os.fsync", side_effect=rastreador("fsync", os.fsync)), \
                mock.patch("os.close", side_effect=rastreador("close", os.close)), \
                mock.patch("os.replace", side_effect=rastreador("replace", os.replace)):
            kvstore.set(self.diretorio, "chave", "valor")

        self.assertEqual(sequencia, ["fsync", "close", "replace", "fsync", "close"])
        self.assertEqual(kvstore.get(self.diretorio, "chave"), "valor")

    def test_delete_faz_unlink_depois_fsync_do_diretorio_antes_do_retorno(self):
        kvstore.set(self.diretorio, "chave", "valor")
        sequencia = []

        def rastreador(nome, original):
            def chamada(*args, **kwargs):
                sequencia.append(nome)
                return original(*args, **kwargs)

            return chamada

        with mock.patch("os.unlink", side_effect=rastreador("unlink", os.unlink)), \
                mock.patch("os.fsync", side_effect=rastreador("fsync", os.fsync)), \
                mock.patch("os.close", side_effect=rastreador("close", os.close)):
            kvstore.delete(self.diretorio, "chave")

        self.assertEqual(sequencia, ["unlink", "fsync", "close"])
        with self.assertRaises(KeyError):
            kvstore.get(self.diretorio, "chave")


class TestCrashReal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.diretorio = self._tmp.name

    def _roda_crash(self, chave, valor, ponto):
        ambiente = dict(os.environ)
        ambiente["PYTHONPATH"] = _RAIZ_REPO
        return subprocess.run(
            [sys.executable, _SCRIPT_CRASH, self.diretorio, chave, valor, ponto],
            cwd=_RAIZ_REPO,
            env=ambiente,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

    def test_crash_antes_do_replace_preserva_valor_antigo_e_store_legivel(self):
        kvstore.set(self.diretorio, "chave", "valor-antigo")

        resultado = self._roda_crash("chave", "valor-novo", "antes_replace")

        self.assertEqual(resultado.returncode, -signal.SIGKILL, resultado.stderr)
        self.assertEqual(kvstore.get(self.diretorio, "chave"), "valor-antigo")
        self.assertEqual(kvstore.keys(self.diretorio), ["chave"])
        nomes = os.listdir(self.diretorio)
        self.assertTrue(
            any(nome.startswith(".tmp-") for nome in nomes),
            "esperava um temporario orfao apos crash antes do replace",
        )

    def test_crash_depois_do_replace_publica_valor_novo_e_store_legivel(self):
        kvstore.set(self.diretorio, "chave", "valor-antigo")

        resultado = self._roda_crash("chave", "valor-novo", "depois_replace")

        self.assertEqual(resultado.returncode, -signal.SIGKILL, resultado.stderr)
        self.assertEqual(kvstore.get(self.diretorio, "chave"), "valor-novo")
        self.assertEqual(kvstore.keys(self.diretorio), ["chave"])
        nomes = os.listdir(self.diretorio)
        self.assertFalse(
            any(nome.startswith(".tmp-") for nome in nomes),
            "o replace ja tinha publicado o arquivo definitivo antes do crash",
        )


class TestIsolamentoEntreChaves(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.diretorio = self._tmp.name

    def test_regravar_uma_chave_nao_toca_no_arquivo_de_outra(self):
        kvstore.set(self.diretorio, "a", "valor-a")
        kvstore.set(self.diretorio, "b", "valor-b")
        caminho_b = kvstore._caminho(self.diretorio, "b")
        stat_antes = os.stat(caminho_b)

        kvstore.set(self.diretorio, "a", "valor-a-novo")

        stat_depois = os.stat(caminho_b)
        self.assertEqual(stat_antes.st_mtime_ns, stat_depois.st_mtime_ns)
        self.assertEqual(kvstore.get(self.diretorio, "b"), "valor-b")
        self.assertEqual(kvstore.get(self.diretorio, "a"), "valor-a-novo")


class TestValorGrande(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.diretorio = self._tmp.name

    def test_valor_de_dez_mebibytes_ida_e_volta_em_blocos(self):
        tamanho = 10 * 1024 * 1024
        dados = os.urandom(tamanho)

        fonte = _FonteContada(dados)
        kvstore.set_stream(self.diretorio, "grande", fonte)

        self.assertGreater(len(fonte.chamadas), 1)
        self.assertTrue(all(n == kvstore._TAMANHO_BLOCO for n in fonte.chamadas[:-1]))

        destino = _DestinoContado()
        kvstore.get_stream(self.diretorio, "grande", destino)

        self.assertEqual(destino.getvalue(), dados)
        self.assertGreater(len(destino.chamadas), 1)
        self.assertTrue(all(n <= kvstore._TAMANHO_BLOCO for n in destino.chamadas))
        self.assertLess(max(destino.chamadas), tamanho)


if __name__ == "__main__":
    unittest.main()
