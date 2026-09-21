import os
import subprocess
import sys
import tempfile
import time
import unittest

import kvstore
from tests._sigkill_worker import (
    CONFIRMACAO,
    CONFIRMACAO_COMPACTACAO,
    _SINALIZAR_INICIO_DA_COMPACTACAO,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LINHA_CONFIRMACAO = (CONFIRMACAO + "\n").encode("utf-8")

# Grande o bastante para o `set` levar tempo mensurável (várias páginas de WAL),
# dando janela real para o SIGKILL cair no meio da gravação em vez de sempre
# antes ou sempre depois dela.
_VALOR_GRANDE = "n" * (2 * 1024 * 1024)


def _run_cli(*args, input_bytes=None):
    return subprocess.run(
        [sys.executable, "-m", "kvstore", *args],
        cwd=_REPO_ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _iniciar_worker(store_dir, op, key, env=None):
    return subprocess.Popen(
        [sys.executable, "-m", "tests._sigkill_worker", store_dir, op, key],
        cwd=_REPO_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def _matar_e_fechar(proc):
    proc.kill()
    proc.wait(timeout=5)
    proc.stdout.close()
    proc.stderr.close()
    return proc


def _gravar_e_matar_apos_confirmacao(store_dir, key, value):
    """Grava `key`→`value` num subprocesso e mata com SIGKILL assim que ele confirma.

    Sincroniza pela linha que o worker escreve em stdout depois do `kvstore.set`
    retornar — nunca por `sleep` — para o kill nunca acontecer antes da
    confirmação (tarefa 4.1).
    """
    proc = _iniciar_worker(store_dir, "set", key)
    proc.stdin.write(value.encode("utf-8"))
    proc.stdin.close()
    linha = proc.stdout.readline()
    if linha != _LINHA_CONFIRMACAO:
        erro = proc.stderr.read()
        _matar_e_fechar(proc)
        raise AssertionError(
            f"worker não confirmou a gravação: stdout={linha!r} stderr={erro!r}"
        )
    return _matar_e_fechar(proc)


def _remover_e_matar_apos_confirmacao(store_dir, key):
    """Remove `key` num subprocesso e mata com SIGKILL assim que ele confirma.

    Mesma sincronização por stdout que `_gravar_e_matar_apos_confirmacao`,
    aplicada a `del` (tarefa 4.1).
    """
    proc = _iniciar_worker(store_dir, "del", key)
    proc.stdin.close()
    linha = proc.stdout.readline()
    if linha != _LINHA_CONFIRMACAO:
        erro = proc.stderr.read()
        _matar_e_fechar(proc)
        raise AssertionError(
            f"worker não confirmou a remoção: stdout={linha!r} stderr={erro!r}"
        )
    return _matar_e_fechar(proc)


def _matar_durante_gravacao(store_dir, key, value, atraso):
    """Mata o subprocesso `atraso` segundos depois de disparar o `set`, sem
    esperar confirmação — o kill pode cair antes, durante ou logo depois do
    commit. Usado para varrer vários instantes possíveis (tarefas 4.4/4.5/4.6).
    """
    proc = _iniciar_worker(store_dir, "set", key)
    proc.stdin.write(value.encode("utf-8"))
    proc.stdin.close()
    time.sleep(atraso)
    return _matar_e_fechar(proc)


def _matar_ate_deixar_wal_pendente(store_dir, key, value, tentativas=10):
    """Repete `_matar_durante_gravacao` com atrasos crescentes até deixar o
    diretório com um `-wal` pendente (kill nem cedo demais — antes de o
    processo sequer abrir a conexão —, nem tarde demais — depois do fechamento
    limpo, que dispara checkpoint automático). Usado só pela tarefa 4.6, que
    precisa desse estado específico para ter algo a verificar.
    """
    wal_path = os.path.join(store_dir, "kvstore.sqlite3-wal")
    atraso = 0.01
    ultimo_proc = None
    for _ in range(tentativas):
        ultimo_proc = _matar_durante_gravacao(store_dir, key, value, atraso)
        if os.path.exists(wal_path):
            return ultimo_proc
        atraso *= 1.7
    raise AssertionError(
        "não foi possível produzir um diretório com -wal pendente depois de "
        f"{tentativas} tentativas; cenário da tarefa 4.6 não coberto"
    )


def _matar_durante_compactacao_do_delete(store_dir, key, atraso):
    """Remove `key` num subprocesso e mata `atraso` segundos depois que o
    `wal_checkpoint`/`incremental_vacuum` do `delete()` começa a rodar — nunca
    antes disso, porque a sincronização é pela linha que o worker instrumentado
    emite no início real da compactação (ver `_sigkill_worker.py`). Cobre o
    cenário "Interrupção durante manutenção preserva o estado" de storage/spec.md.
    """
    env = dict(os.environ, **{_SINALIZAR_INICIO_DA_COMPACTACAO: "1"})
    proc = _iniciar_worker(store_dir, "del", key, env=env)
    proc.stdin.close()
    linha = proc.stdout.readline()
    if linha != (CONFIRMACAO_COMPACTACAO + "\n").encode("utf-8"):
        erro = proc.stderr.read()
        _matar_e_fechar(proc)
        raise AssertionError(
            f"worker não sinalizou o início da compactação: stdout={linha!r} "
            f"stderr={erro!r}"
        )
    time.sleep(atraso)
    return _matar_e_fechar(proc)


class TestAuxiliarDeSigkill(unittest.TestCase):
    """4.1 — o auxiliar de fato mata (exit -9) sem depender de `sleep` para
    sincronizar com a confirmação da gravação."""

    def test_auxiliar_mata_com_sigkill_apos_confirmacao_sem_sleep(self):
        with tempfile.TemporaryDirectory() as store_dir:
            proc = _gravar_e_matar_apos_confirmacao(store_dir, "k", "v")
            self.assertEqual(proc.returncode, -9)

    def test_auxiliar_mata_remocao_confirmada_sem_sleep(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "k", "v")
            proc = _remover_e_matar_apos_confirmacao(store_dir, "k")
            self.assertEqual(proc.returncode, -9)


class TestGravacaoConfirmadaSobreviveASigkill(unittest.TestCase):
    """4.2 — `set` confirmado seguido de SIGKILL imediato: um processo novo lê
    o valor gravado."""

    def test_valor_gravado_sobrevive_a_kill_imediato(self):
        with tempfile.TemporaryDirectory() as store_dir:
            proc = _gravar_e_matar_apos_confirmacao(store_dir, "k", "v")
            self.assertEqual(proc.returncode, -9)

            leitura = _run_cli(store_dir, "get", "k")
            self.assertEqual(leitura.returncode, 0, leitura.stderr)
            self.assertEqual(leitura.stdout, b"v")


class TestRemocaoConfirmadaSobreviveASigkill(unittest.TestCase):
    """4.3 — `del` confirmado seguido de SIGKILL imediato: a chave continua
    ausente no processo novo."""

    def test_chave_continua_ausente_apos_kill_imediato(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "k", "v")

            proc = _remover_e_matar_apos_confirmacao(store_dir, "k")
            self.assertEqual(proc.returncode, -9)

            leitura = _run_cli(store_dir, "get", "k")
            self.assertEqual(leitura.returncode, 1)
            self.assertEqual(leitura.stdout, b"")

            listagem = _run_cli(store_dir, "list")
            self.assertEqual(listagem.returncode, 0)
            self.assertEqual(listagem.stdout, b"")


class TestInterrupcaoDuranteGravacaoNuncaProduzLixo(unittest.TestCase):
    """4.4 — SIGKILL durante a gravação, em vários instantes diferentes, sobre
    uma chave que já tinha valor: a leitura seguinte devolve o valor antigo ou
    o novo, nunca lixo, truncado ou vazio."""

    def test_kill_durante_gravacao_preserva_valor_antigo_ou_novo(self):
        valor_antigo = "valor-antigo"
        atrasos = (0, 0.0002, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.02)

        for atraso in atrasos:
            with self.subTest(atraso=atraso):
                with tempfile.TemporaryDirectory() as store_dir:
                    kvstore.set(store_dir, "k", valor_antigo)

                    proc = _matar_durante_gravacao(
                        store_dir, "k", _VALOR_GRANDE, atraso
                    )
                    self.assertEqual(proc.returncode, -9)

                    leitura = _run_cli(store_dir, "get", "k")
                    self.assertEqual(leitura.returncode, 0, leitura.stderr)
                    self.assertIn(
                        leitura.stdout,
                        (
                            valor_antigo.encode("utf-8"),
                            _VALOR_GRANDE.encode("utf-8"),
                        ),
                    )


class TestInterrupcaoNaoDestroiEstadoAcumulado(unittest.TestCase):
    """4.5 — store com muitas chaves confirmadas, SIGKILL no meio de uma
    gravação nova: todas as chaves anteriores continuam legíveis com os
    valores corretos."""

    def test_kill_durante_gravacao_nova_preserva_chaves_anteriores(self):
        with tempfile.TemporaryDirectory() as store_dir:
            # "100 chaves confirmadas", como no cenário de design.md/spec.md.
            chaves_anteriores = {
                f"chave-{i:04d}": f"valor-{i:04d}" for i in range(100)
            }
            for chave, valor in chaves_anteriores.items():
                kvstore.set(store_dir, chave, valor)

            proc = _matar_durante_gravacao(
                store_dir, "chave-nova", _VALOR_GRANDE, 0.005
            )
            self.assertEqual(proc.returncode, -9)

            # Confirma via um processo realmente novo que o conjunto de chaves
            # não foi destruído, além de conferir cada valor no processo atual.
            listagem = _run_cli(store_dir, "list")
            self.assertEqual(listagem.returncode, 0)
            chaves_listadas = listagem.stdout.decode("utf-8").splitlines()
            for chave in chaves_anteriores:
                self.assertIn(chave, chaves_listadas)

            for chave, valor_esperado in chaves_anteriores.items():
                self.assertEqual(kvstore.get(store_dir, chave), valor_esperado)


class TestReaberturaAposFalhaAbrupta(unittest.TestCase):
    """4.6 — abrir um diretório deixado por SIGKILL, com `-wal` pendente: a
    primeira operação funciona sem reparo manual nem remoção de arquivo
    temporário."""

    def test_primeira_operacao_funciona_com_wal_pendente(self):
        with tempfile.TemporaryDirectory() as store_dir:
            kvstore.set(store_dir, "k", "valor-inicial")

            proc = _matar_ate_deixar_wal_pendente(store_dir, "k", _VALOR_GRANDE)
            self.assertEqual(proc.returncode, -9)

            wal_path = os.path.join(store_dir, "kvstore.sqlite3-wal")
            self.assertTrue(os.path.exists(wal_path))

            # Nenhum arquivo é tocado ou removido antes da primeira operação:
            # a recuperação SHALL ser automática (Requirement em storage/spec.md).
            resultado = _run_cli(store_dir, "list")
            self.assertEqual(resultado.returncode, 0, resultado.stderr)


class TestInterrupcaoDuranteCompactacaoPreservaEstado(unittest.TestCase):
    """Cenário "Interrupção durante manutenção preserva o estado" (storage/spec.md):
    SIGKILL durante o `wal_checkpoint`/`incremental_vacuum` que `delete()` dispara
    depois do `DELETE` já confirmado — um processo novo lê exatamente o conjunto de
    chaves e valores confirmados que existia antes da interrupção: a chave removida
    continua ausente, e todas as outras continuam com o valor correto."""

    def test_kill_durante_compactacao_do_delete_preserva_as_demais_chaves(self):
        atrasos = (0, 0.0002, 0.0005, 0.001, 0.005)

        for atraso in atrasos:
            with self.subTest(atraso=atraso):
                with tempfile.TemporaryDirectory() as store_dir:
                    # Muitas chaves com valores grandes: dá ao `incremental_vacuum`
                    # páginas suficientes para liberar, alongando a janela de
                    # compactação o bastante para o kill ter chance real de cair
                    # dentro dela.
                    chaves_anteriores = {
                        f"chave-{i:04d}": _VALOR_GRANDE for i in range(20)
                    }
                    for chave, valor in chaves_anteriores.items():
                        kvstore.set(store_dir, chave, valor)
                    chave_removida = "chave-0000"
                    del chaves_anteriores[chave_removida]

                    proc = _matar_durante_compactacao_do_delete(
                        store_dir, chave_removida, atraso
                    )
                    self.assertEqual(proc.returncode, -9)

                    with self.assertRaises(kvstore.KeyNotFoundError):
                        kvstore.get(store_dir, chave_removida)

                    listagem = _run_cli(store_dir, "list")
                    self.assertEqual(listagem.returncode, 0, listagem.stderr)
                    chaves_listadas = listagem.stdout.decode("utf-8").splitlines()
                    self.assertNotIn(chave_removida, chaves_listadas)
                    for chave, valor_esperado in chaves_anteriores.items():
                        self.assertIn(chave, chaves_listadas)
                        self.assertEqual(
                            kvstore.get(store_dir, chave), valor_esperado
                        )


if __name__ == "__main__":
    unittest.main()
