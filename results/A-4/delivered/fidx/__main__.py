import argparse
import os
import sqlite3
import sys
from pathlib import Path

from fidx import scan
from fidx.store import IndiceEmUso, Indice


def indexar(raiz: Path) -> dict[str, int]:
    """Reindexa `raiz` reprocessando só o que mudou; devolve as cinco contagens do resumo."""
    contagens = {"novos": 0, "alterados": 0, "removidos": 0, "inalterados": 0, "ignorados": 0}
    idx = Indice.abrir(raiz, criar=True)
    try:
        with idx:
            digests_antigos = idx.digests()
            vistos: set[str] = set()
            for caminho in scan.percorrer(raiz):
                caminho_str = caminho.as_posix()
                resultado = scan.ler(raiz / caminho)
                if resultado is None:
                    contagens["ignorados"] += 1
                    continue
                digest, texto = resultado
                vistos.add(caminho_str)
                digest_antigo = digests_antigos.get(caminho_str)
                if digest_antigo == digest:
                    contagens["inalterados"] += 1
                    continue
                idx.gravar(caminho_str, digest, scan.tokenizar(texto))
                if digest_antigo is None:
                    contagens["novos"] += 1
                else:
                    contagens["alterados"] += 1
            removidos = [caminho for caminho in digests_antigos if caminho not in vistos]
            idx.remover(removidos)
            contagens["removidos"] = len(removidos)
    finally:
        idx.close()
    return contagens


def buscar(raiz: Path, termo: str) -> list[str]:
    """Caminhos indexados que contêm todas as palavras de `termo`, ordenados."""
    idx = Indice.abrir(raiz, criar=False)
    try:
        return idx.buscar(scan.tokenizar(termo))
    finally:
        idx.close()


def _imprimir_resumo(contagens: dict[str, int]) -> None:
    total = contagens["novos"] + contagens["alterados"] + contagens["inalterados"]
    print(
        f"{total} arquivos: {contagens['novos']} novos, {contagens['alterados']} alterados, "
        f"{contagens['removidos']} removidos, {contagens['inalterados']} inalterados, "
        f"{contagens['ignorados']} ignorados"
    )


def _construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fidx")
    parser.add_argument("diretorio")
    subparsers = parser.add_subparsers(dest="comando", required=True)
    subparsers.add_parser("index")
    parser_search = subparsers.add_parser("search")
    parser_search.add_argument("termo")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _construir_parser().parse_args(argv)
    raiz = Path(args.diretorio)
    if not raiz.is_dir():
        print(f"fidx: nao e um diretorio: {args.diretorio}", file=sys.stderr)
        return 2
    if args.comando == "index":
        if not os.access(raiz, os.W_OK):
            print(
                f"fidx: nao foi possivel gravar o indice em {args.diretorio}: Permission denied",
                file=sys.stderr,
            )
            return 2
        try:
            contagens = indexar(raiz)
        except IndiceEmUso:
            print(
                f"fidx: indice em uso por outra execucao: {args.diretorio}", file=sys.stderr
            )
            return 2
        except OSError as exc:
            detalhe = "Permission denied" if isinstance(exc, PermissionError) else str(exc)
            print(
                f"fidx: nao foi possivel gravar o indice em {args.diretorio}: {detalhe}",
                file=sys.stderr,
            )
            return 2
        except sqlite3.Error as exc:
            print(
                f"fidx: nao foi possivel gravar o indice em {args.diretorio}: {exc}",
                file=sys.stderr,
            )
            return 2
        _imprimir_resumo(contagens)
        return 0
    try:
        resultados = buscar(raiz, args.termo)
    except FileNotFoundError:
        print(
            f"fidx: indice nao encontrado em {args.diretorio}; "
            f"rode: python -m fidx {args.diretorio} index",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        detalhe = "Permission denied" if isinstance(exc, PermissionError) else str(exc)
        print(
            f"fidx: nao foi possivel ler o indice em {args.diretorio}: {detalhe}",
            file=sys.stderr,
        )
        return 2
    except sqlite3.Error as exc:
        print(
            f"fidx: nao foi possivel ler o indice em {args.diretorio}: {exc}",
            file=sys.stderr,
        )
        return 2
    if not resultados:
        return 1
    for caminho in resultados:
        print(caminho)
    return 0


if __name__ == "__main__":
    sys.exit(main())
