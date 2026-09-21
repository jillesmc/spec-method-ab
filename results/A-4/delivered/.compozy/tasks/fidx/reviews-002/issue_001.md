---
round: 2
round_created_at: 2026-09-21T02:21:13.318130226Z
status: resolved
file: fidx/__main__.py
line: 93
severity: high
author: unknown
---

# Issue 001: `search` crashes with exit code 1 (not 2) on a corrupted or unopenable index

## Review Comment

`fidx/__main__.py`'s `main()` search branch (lines 93-101) only catches `FileNotFoundError` around `buscar(raiz, args.termo)`. Any other exception raised while opening the index — e.g. `sqlite3.DatabaseError` from a corrupted `.fidx.sqlite3` — propagates uncaught out of `main()`, producing a raw Python traceback on stderr and Python's default uncaught-exception exit code of 1.

Reproduced directly:
```
$ echo 'isto nao e um banco sqlite valido' > /tmp/fidx_probe/.fidx.sqlite3
$ python3 -m fidx /tmp/fidx_probe search orcamento; echo $?
Traceback (most recent call last):
  ...
  File ".../fidx/store.py", line 51, in _ler_schema_version
    linha = conexao.execute(...)
sqlite3.DatabaseError: file is not a database
1
```
This violates `_spec.md` business rule 9 (`0` success; `1` search-with-no-result; `2` could-not-execute) and `_dx.md`'s exit-code table, which reserves exit 1 exclusively for a search thatran successfully but found nothing. Because index corruption now also returns 1, it is indistinguishable from a legitimate empty result to any caller checking the exit code — the cron consumer this feature is built for.

This is the same class of bug fixed in round 1 (`reviews-001/issue_001.md`), where `main()`'s `index` branch was given `except OSError` / `except sqlite3.Error` handlers translating the real exception into a `_dx.md`-formatted stderr message and exit 2. That fix was never mirrored onto the `search` branch, and no test exercises `search` against a corrupted index (only `test_indice_corrompido_reporta_erro_real_em_vez_de_permission_denied` in `tests/test_cli.py`, which only covers `index`).

Fix: wrap the `search` branch's `buscar(...)` call in the same `except OSError / except sqlite3.Error` pattern used for `index`, printing a `_dx.md`-consistent stderr message and returning 2, and add a regression test analogous to the existing corrupted-index test but for `search`.

## Triage

- Decision: `VALID`
- Root cause: `main()`'s `search` branch (fidx/__main__.py:93-101, pre-fix) only wrapped `buscar(raiz, args.termo)` in `except FileNotFoundError`. `Indice.abrir(criar=False)` opens a corrupted `.fidx.sqlite3` lazily via `sqlite3.connect` (no error yet), then `_ler_schema_version` runs a real `SELECT`, which raises `sqlite3.DatabaseError: file is not a database` for a non-sqlite file. That error is a subclass of `sqlite3.Error`, not `sqlite3.OperationalError`, so `_ler_schema_version`'s own `except sqlite3.OperationalError` doesn't swallow it either — it propagates out of `buscar()`, out of `main()`'s uncaught `try`, and becomes a raw traceback with Python's default exit code `1`, colliding with the legitimate "search ran, found nothing" exit code per `_spec.md` rule 9 and the `_dx.md` exit-code table.
- Reproduced pre-fix: `echo 'isto nao e um banco sqlite valido' > $tmp/.fidx.sqlite3; python3 -m fidx $tmp search termo` printed a traceback to stderr and exited `1`.
- Fix: added `except OSError` (mirroring the `PermissionError` -> "Permission denied" translation) and `except sqlite3.Error` handlers around the `search` branch's `buscar(...)` call, printing a `_dx.md`-consistent `fidx: nao foi possivel ler o indice em <dir>: <detalhe>` message to stderr and returning `2` — mirrors the round-1 fix already applied to the `index` branch (fidx/__main__.py:78-90), using "ler" instead of "gravar" since `search` only reads the index.
- Regression coverage: added `tests/test_cli.py::test_search_com_indice_corrompido_reporta_erro_real_e_saida_2`, analogous to the existing `test_indice_corrompido_reporta_erro_real_em_vez_de_permission_denied` (index case), asserting empty stdout, exit code `2`, and the real sqlite error text in stderr.
- Verified: full suite (`make test`) passes, 57/57, including the new test. Manually reran the reproduction from the review comment post-fix: now prints `fidx: nao foi possivel ler o indice em <dir>: file is not a database` and exits `2`.
