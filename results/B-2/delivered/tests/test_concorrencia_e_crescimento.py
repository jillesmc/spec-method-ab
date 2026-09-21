"""Testes de concorrência entre processos distintos e de crescimento
controlado de espaço em disco (tasks.md, seção 5)."""

import os
import subprocess
import sys
import tempfile
import unittest

import kvstore

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    return total


def _iniciar_processo_set(store_dir, key, value):
    return subprocess.Popen(
        [sys.executable, "-m", "kvstore", store_dir, "set", key, value],
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _iniciar_escritor_continuo(store_dir, key, n, prefixo):
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests._escritor_continuo",
            store_dir,
            key,
            str(n),
            prefixo,
        ],
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class TestGravacoesSimultaneasDeProcessosDistintos(unittest.TestCase):
    """5.1 — N processos gravando chaves diferentes ao mesmo tempo no mesmo
    diretório: todas as gravações confirmadas são legíveis e nenhuma falha por
    contenção (`busy_timeout`, D4 em design.md)."""

    def test_n_processos_gravam_chaves_diferentes_sem_falhar_por_contencao(self):
        with tempfile.TemporaryDirectory() as store_dir:
            n = 10
            pares = [(f"chave-{i:02d}", f"valor-{i:02d}") for i in range(n)]

            # Todos os processos são disparados antes de qualquer `communicate`,
            # para que a concorrência seja real e não uma sequência disfarçada.
            processos = [
                _iniciar_processo_set(store_dir, chave, valor)
                for chave, valor in pares
            ]

            for proc, (chave, _valor) in zip(processos, pares):
                _stdout, stderr = proc.communicate(timeout=10)
                self.assertEqual(
                    proc.returncode,
                    0,
                    msg=f"set de {chave!r} falhou por contenção: {stderr!r}",
                )

            self.assertEqual(
                kvstore.list_keys(store_dir), sorted(chave for chave, _ in pares)
            )
            for chave, valor in pares:
                self.assertEqual(kvstore.get(store_dir, chave), valor)


class TestLeituraConcorrenteComEscrita(unittest.TestCase):
    """5.2 — leitura concorrente com escrita: a leitura devolve um estado
    consistente e nunca erra por arquivo ausente ou meio-escrito."""

    def test_leitura_durante_escrita_continua_nunca_erra(self):
        with tempfile.TemporaryDirectory() as store_dir:
            chave = "k"
            n = 300
            prefixo = "valor"
            valores_possiveis = {f"{prefixo}-{i}" for i in range(n)}

            escritor = _iniciar_escritor_continuo(store_dir, chave, n, prefixo)
            stderr = b""
            try:
                valores_vistos = []
                while escritor.poll() is None:
                    try:
                        valores_vistos.append(kvstore.get(store_dir, chave))
                    except kvstore.KeyNotFoundError:
                        pass
                    # `list_keys` só pode ver o store vazio ou com a única
                    # chave gravada — nunca lançar por arquivo meio-escrito.
                    listagem = kvstore.list_keys(store_dir)
                    self.assertIn(listagem, ([], [chave]))
                _stdout, stderr = escritor.communicate(timeout=10)
            finally:
                if escritor.poll() is None:
                    escritor.kill()
                    escritor.wait(timeout=5)

            self.assertEqual(escritor.returncode, 0, stderr)
            self.assertTrue(
                valores_vistos,
                "nenhuma leitura aconteceu durante a janela de escrita",
            )
            self.assertLessEqual(set(valores_vistos), valores_possiveis)
            self.assertEqual(kvstore.get(store_dir, chave), f"{prefixo}-{n - 1}")


class TestCrescimentoProporcionalAoEstadoVivo(unittest.TestCase):
    """5.3 — regravar a mesma chave muitas vezes: o tamanho do diretório fica
    na ordem de grandeza do valor vivo, não do total gravado (requisito
    "Espaço proporcional ao estado vivo")."""

    def test_regravar_a_mesma_chave_nao_cresce_com_o_historico(self):
        with tempfile.TemporaryDirectory() as store_dir:
            # `synchronous=FULL` custa um fsync por `set` (~15 ms nesta
            # máquina, medido): 1000 regravações já são "milhares", expõem
            # crescimento sem limite se ele existisse, e ainda rodam em
            # poucos segundos, o teto que a própria tarefa pede.
            n = 1000
            valor = "x" * 512

            for _ in range(n):
                kvstore.set(store_dir, "k", valor)

            total_gravado = n * len(valor.encode("utf-8"))
            tamanho_final = _dir_size(store_dir)

            self.assertEqual(kvstore.get(store_dir, "k"), valor)
            self.assertLess(tamanho_final, total_gravado * 0.1)
            self.assertLess(
                tamanho_final,
                64 * 1024,
                "diretório deveria ficar na ordem de grandeza do valor vivo",
            )


if __name__ == "__main__":
    unittest.main()
