import os
import tempfile
import unittest

from kvstore import Store


def _checkpoint(store: Store) -> None:
    """Force a full WAL checkpoint so `kvstore.db`'s on-disk size reflects the store's
    current state, instead of depending on when SQLite's own auto-checkpoint happens to
    fire. Test-only: production code never calls this (Requirements: no maintenance verb).
    """
    store._conn.execute("PRAGMA wal_checkpoint(FULL)")


def _tamanho_db(diretorio: str) -> int:
    return os.path.getsize(os.path.join(diretorio, "kvstore.db"))


class TestCrescimentoLimitado(unittest.TestCase):
    def test_ut030_auto_vacuum_incremental_em_criacao_e_reabertura(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s1 = Store(d)
            s1.set("k", "v")
            av_criacao = s1._conn.execute("PRAGMA auto_vacuum").fetchone()[0]
            s1.close()

            s2 = Store(d)
            s2.get("k")
            av_reabertura = s2._conn.execute("PRAGMA auto_vacuum").fetchone()[0]
            s2.close()

            self.assertEqual(av_criacao, 2)
            self.assertEqual(av_reabertura, 2)

    def test_ut031_espaco_e_recuperado_apos_delete_em_massa(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            valor = "v" * (64 * 1024)
            with Store(d) as s:
                for i in range(200):
                    s.set(f"chave-{i}", valor)
                _checkpoint(s)
                pico = _tamanho_db(d)

                for i in range(200):
                    self.assertTrue(s.delete(f"chave-{i}"))
                self.assertEqual(s.list(), [])

                _checkpoint(s)
                pos_delete = _tamanho_db(d)

            # Medido: pico ~12.6 MiB, pos-delete ~16 KiB (o minimo de uma pagina) — o
            # limiar de 25% deixa larga margem para variacao de page_size/overhead entre
            # maquinas sem deixar de provar que o espaco de fato volta.
            self.assertLess(pos_delete, pico * 0.25)

    def test_ut032_reescritas_repetidas_nao_fazem_o_journal_crescer_sem_limite(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            ultimo_valor = None
            with Store(d) as s:
                for i in range(2000):
                    ultimo_valor = f"{i:07d}" + ("v" * (64 * 1024 - 7))
                    s.set("chave", ultimo_valor)

                db_path = os.path.join(d, "kvstore.db")
                wal_path = os.path.join(d, "kvstore.db-wal")
                tamanho_total = os.path.getsize(db_path)
                if os.path.exists(wal_path):
                    tamanho_total += os.path.getsize(wal_path)

                # Medido: ~4.0 MiB (db + wal) apos 2 000 reescritas de uma chave de 64
                # KiB; o limiar de 8 MiB da o dobro de margem sem deixar de provar que o
                # tamanho acompanha o dado vivo (1 chave), nao as 2 000 escritas.
                self.assertLess(tamanho_total, 8 * 1024 * 1024)

                self.assertEqual(s.get("chave"), ultimo_valor)


class TestEscalaDeLeitura(unittest.TestCase):
    def test_it009_100000_chaves_lista_ordenada_e_get_usa_indice(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "dados")
            s = Store(d)
            conn = s._open_for_write()
            try:
                chaves = [f"chave-{i:06d}" for i in range(100_000)]
                # Fixture shortcut (per _spec.md): the durable write path is covered by
                # task_01; this case is about read behavior at scale, so the 100 000
                # rows are bulk-seeded in one transaction rather than 100 000 fsynced
                # `set()` calls.
                conn.execute("BEGIN")
                conn.executemany(
                    "INSERT INTO kv (k, v) VALUES (?, ?)",
                    ((k, b"v") for k in chaves),
                )
                conn.execute("COMMIT")

                listadas = s.list()
                self.assertEqual(len(listadas), 100_000)
                self.assertEqual(listadas, sorted(listadas))

                plano = conn.execute(
                    "EXPLAIN QUERY PLAN SELECT v FROM kv WHERE k = ?",
                    ("chave-042000",),
                ).fetchall()
                detalhe = " ".join(str(linha[-1]) for linha in plano)
                self.assertIn("SEARCH", detalhe)
                self.assertNotIn("SCAN", detalhe)
            finally:
                s.close()


if __name__ == "__main__":
    unittest.main()
