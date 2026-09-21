"""Suite de aceite OCULTA do A/B nº 3, dominio INDEXADOR.

A armadilha aqui e' invalidacao de cache:

  caminho natural   cache por data de modificacao (mtime)
                    passa 100% de BASE e quase toda ROBUSTEZ
                    morre no ORACULO

  caminho planejado decidir o que mudou pelo CONTEUDO

O enunciado diz o requisito em linguagem de negocio, e diz com todas as
letras: "os arquivos chegam por rsync e por checkout, entao a data de
modificacao deles nao e' confiavel". Nao nomeia tecnica nenhuma. Quem le o
enunciado e planeja pega isso; quem pula direto para o codigo usa mtime porque
e' o reflexo.

O ORACULO dispensa o meu julgamento por completo:

    indice incremental  ==  indice reconstruido do zero

Depois de qualquer sequencia de mudancas, buscar no indice que foi atualizado
incrementalmente tem que dar o MESMO resultado que apagar tudo e indexar de
novo. Nenhum formato, nenhuma estrutura e nenhuma API sao cobrados: so a
igualdade dos dois caminhos.

TRES CAMADAS:

  BASE (B)      8 testes. O basico.
  ROBUSTEZ (R)  10 testes. Bordas que o enunciado nao cita.
  ORACULO (O)   12 testes. Incremental == reconstrucao. METRICA PRIMARIA.

Roda com cwd na raiz do repo entregue pelo braco.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path.cwd()
LIMITE = 120


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fidx-aceite-")
        self.pasta = Path(self.tmp) / "notas"
        self.pasta.mkdir(parents=True)
        # Caminhos relativos dos arquivos que ESTE teste criou. Tudo o mais que
        # aparecer na pasta e' artefato do indexador, e e' isso que separa
        # "dado" de "indice" sem cobrar onde o indice mora.
        self.meus = set()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ apoio
    def fidx(self, *args, pasta=None, limite=LIMITE):
        alvo = str(self.pasta if pasta is None else pasta)
        return subprocess.run(
            [sys.executable, "-m", "fidx", alvo, *args],
            cwd=RAIZ, capture_output=True, text=True, errors="replace", timeout=limite,
        )

    def indexar(self, pasta=None, limite=LIMITE):
        p = self.fidx("index", pasta=pasta, limite=limite)
        self.semTraceback(p, "no index")
        self.assertEqual(p.returncode, 0, f"index falhou: {p.stderr[-400:]}")
        return p

    def buscar(self, termo, pasta=None):
        p = self.fidx("search", termo, pasta=pasta)
        self.semTraceback(p, f"na busca por {termo!r}")
        return p

    def semTraceback(self, p, quando):
        self.assertNotIn("Traceback", p.stderr, f"excecao vazou {quando}:\n{p.stderr[-800:]}")

    def escrever(self, nome, texto, quando=None, bytes_crus=None):
        """Cria ou sobrescreve um arquivo. 'quando' forca a data de
        modificacao, que e' como o rsync e o checkout se comportam."""
        alvo = self.pasta / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if bytes_crus is not None:
            alvo.write_bytes(bytes_crus)
        else:
            alvo.write_text(texto, encoding="utf-8")
        if quando is not None:
            os.utime(alvo, (quando, quando))
        self.meus.add(nome)
        return alvo

    def apagar(self, nome):
        (self.pasta / nome).unlink(missing_ok=True)
        self.meus.discard(nome)

    def renomear(self, de, para):
        (self.pasta / de).rename(self.pasta / para)
        self.meus.discard(de)
        self.meus.add(para)

    def achados(self, termo, pasta=None):
        """Conjunto de arquivos DE DADOS citados na saida da busca.

        Nao cobra formato: varre a saida atras dos nomes dos arquivos que o
        teste criou, entao tanto 'a.txt' quanto '/caminho/a.txt: 3 vezes'
        contam igual. So conta arquivo meu: se a implementacao guardar o
        indice dentro da pasta e acabar indexando o proprio indice, isso nao
        pode virar diferenca de placar."""
        p = self.buscar(termo, pasta=pasta)
        raiz = self.pasta if pasta is None else Path(pasta)
        vistos = set()
        for rel in self.meus:
            if not (raiz / rel).is_file():
                continue
            if rel in p.stdout or str(raiz / rel) in p.stdout:
                vistos.add(rel)
        return vistos

    # ------------------------------------------------------------- o oraculo
    def limpar_indice(self):
        """Apaga tudo que o indexador criou, preservando os arquivos que ESTE
        teste escreveu. E' o 'do zero' do oraculo.

        Descobre o que e' indice por exclusao, entao funciona com o indice em
        qualquer lugar: dentro da pasta, num subdiretorio oculto, ou ao lado
        dela. Nenhum layout e' cobrado."""
        guardar = set(self.meus)
        for rel in self.meus:  # os diretorios que seguram arquivos meus
            partes = Path(rel).parts
            for i in range(1, len(partes)):
                guardar.add(str(Path(*partes[:i])))
        for caminho in sorted(self.pasta.rglob("*"), key=lambda p: -len(p.parts)):
            if str(caminho.relative_to(self.pasta)) in guardar:
                continue
            if caminho.is_dir():
                shutil.rmtree(caminho, ignore_errors=True)
            else:
                caminho.unlink(missing_ok=True)
        for fora in Path(self.tmp).glob("*"):
            if fora != self.pasta:
                if fora.is_dir():
                    shutil.rmtree(fora, ignore_errors=True)
                else:
                    fora.unlink(missing_ok=True)

    def oraculo(self, termos, quando):
        """O coracao da camada O.

        Tira uma foto do resultado do indice INCREMENTAL, joga o indice fora,
        reconstroi do zero e compara. Se der diferente, o incremental mentiu.
        """
        incremental = {t: self.achados(t) for t in termos}
        self.limpar_indice()
        self.indexar()
        completo = {t: self.achados(t) for t in termos}
        divergentes = {
            t: (sorted(incremental[t]), sorted(completo[t]))
            for t in termos
            if incremental[t] != completo[t]
        }
        self.assertFalse(
            divergentes,
            f"incremental divergiu da reconstrucao {quando}.\n"
            + "\n".join(
                f"  termo {t!r}: incremental={i} reconstruido={c}"
                for t, (i, c) in divergentes.items()
            ),
        )


class TestBase(Base):
    def test_B01_indexa_e_acha(self):
        self.escrever("a.txt", "o orcamento de marco ficou apertado")
        self.indexar()
        self.assertIn("a.txt", self.achados("orcamento"))

    def test_B02_nao_acha_o_que_nao_existe(self):
        self.escrever("a.txt", "texto qualquer")
        self.indexar()
        self.assertEqual(self.achados("jabuticaba"), set())

    def test_B03_varios_arquivos(self):
        self.escrever("a.txt", "relatorio de vendas")
        self.escrever("b.txt", "relatorio de compras")
        self.escrever("c.txt", "nada a ver")
        self.indexar()
        self.assertEqual(self.achados("relatorio"), {"a.txt", "b.txt"})

    def test_B04_subpasta(self):
        self.escrever("time/a.txt", "reuniao de planejamento")
        self.indexar()
        self.assertIn("time/a.txt", self.achados("planejamento"))

    def test_B05_busca_sem_indexar_antes(self):
        self.escrever("a.txt", "qualquer coisa")
        p = self.buscar("qualquer")
        self.semTraceback(p, "buscando antes de indexar")

    def test_B06_reindexar_nao_duplica(self):
        self.escrever("a.txt", "orcamento")
        self.indexar()
        self.indexar()
        self.indexar()
        self.assertEqual(self.achados("orcamento"), {"a.txt"})

    def test_B07_acento_e_caixa(self):
        self.escrever("a.txt", "Orçamento Aprovado")
        self.indexar()
        achou = self.achados("Orçamento") or self.achados("orçamento")
        self.assertIn("a.txt", achou, "nao achou palavra com acento")

    def test_B08_incremental_e_mais_rapido_que_do_zero(self):
        """Nao cobra numero: cobra que a segunda passada nao refaz tudo.
        Limite folgado, so pega quem reindexa a pasta inteira toda vez."""
        for i in range(300):
            self.escrever(f"n{i:03d}.txt", f"documento numero {i} " + "palavra " * 200)
        t0 = time.monotonic()
        self.indexar(limite=600)
        primeira = time.monotonic() - t0
        t0 = time.monotonic()
        self.indexar(limite=600)
        segunda = time.monotonic() - t0
        self.assertLess(
            segunda, max(primeira * 0.6, 0.5),
            f"a segunda indexacao ({segunda:.2f}s) nao foi mais barata que a "
            f"primeira ({primeira:.2f}s): parece reindexar tudo",
        )


class TestRobustez(Base):
    def test_R01_pasta_vazia(self):
        p = self.fidx("index")
        self.semTraceback(p, "com pasta vazia")
        self.assertEqual(p.returncode, 0, "pasta vazia e' legitima")

    def test_R02_pasta_inexistente(self):
        p = self.fidx("index", pasta=str(Path(self.tmp) / "nao" / "existe"))
        self.semTraceback(p, "com pasta inexistente")
        self.assertNotEqual(p.returncode, 0, "pasta inexistente tem que sinalizar erro")

    def test_R03_arquivo_binario(self):
        self.escrever("foto.bin", None, bytes_crus=bytes(range(256)) * 40)
        self.escrever("a.txt", "texto de verdade")
        self.indexar()
        self.assertIn("a.txt", self.achados("texto"))

    def test_R04_encoding_quebrado(self):
        self.escrever(
            "sujo.txt", None,
            bytes_crus="acentuação normal ".encode("utf-8") + b"\xff\xfe quebrado\n",
        )
        self.escrever("a.txt", "controle")
        self.indexar()
        self.assertIn("a.txt", self.achados("controle"))

    def test_R05_arquivo_vazio(self):
        self.escrever("vazio.txt", "")
        self.escrever("a.txt", "controle")
        self.indexar()
        self.assertIn("a.txt", self.achados("controle"))

    def test_R06_arquivo_grande(self):
        self.escrever("grande.txt", ("linha de enchimento\n" * 60000) + "agulha\n")
        self.indexar(limite=300)
        self.assertIn("grande.txt", self.achados("agulha"))

    def test_R07_nome_com_espaco_e_acento(self):
        self.escrever("relatório final 2026.txt", "conclusao do estudo")
        self.indexar()
        self.assertIn("relatório final 2026.txt", self.achados("conclusao"))

    def test_R08_busca_vazia_ou_sem_argumento(self):
        self.escrever("a.txt", "x")
        self.indexar()
        p = self.fidx("search")
        self.semTraceback(p, "buscando sem termo")
        self.assertNotEqual(p.returncode, 0, "search sem termo tem que sinalizar erro")

    def test_R09_subcomando_invalido(self):
        p = self.fidx("dancar")
        self.semTraceback(p, "com subcomando invalido")
        self.assertNotEqual(p.returncode, 0)

    def test_R10_link_simbolico_quebrado(self):
        self.escrever("a.txt", "controle")
        os.symlink(str(self.pasta / "nao-existe.txt"), str(self.pasta / "quebrado.txt"))
        self.meus.add("quebrado.txt")
        p = self.fidx("index")
        self.semTraceback(p, "com link simbolico quebrado")
        self.assertEqual(p.returncode, 0, "link quebrado nao pode derrubar a indexacao")


class TestOraculo(Base):
    """Incremental tem que ser igual a reconstruir do zero. METRICA PRIMARIA.

    ANTIGO = 2026-01-01. NOVO = agora. O enunciado avisa que a data nao e'
    confiavel, entao mexer nela e' cenario previsto, nao pegadinha."""

    ANTIGO = 1767225600.0   # 2026-01-01T00:00:00Z

    def preparar(self, arquivos):
        for nome, texto in arquivos.items():
            self.escrever(nome, texto)
        self.indexar()

    def test_O01_arquivo_novo(self):
        self.preparar({"a.txt": "alfa"})
        self.escrever("b.txt", "beta")
        self.indexar()
        self.oraculo(["alfa", "beta"], "apos criar arquivo")

    def test_O02_arquivo_apagado(self):
        self.preparar({"a.txt": "alfa", "b.txt": "beta"})
        self.apagar("b.txt")
        self.indexar()
        self.oraculo(["alfa", "beta"], "apos apagar arquivo")

    def test_O03_conteudo_mudou_com_data_nova(self):
        self.preparar({"a.txt": "alfa"})
        time.sleep(1.1)
        self.escrever("a.txt", "gama")
        self.indexar()
        self.oraculo(["alfa", "gama"], "apos mudar conteudo com data nova")

    def test_O04_conteudo_mudou_com_data_PRESERVADA(self):
        """O caso que o enunciado descreve: o conteudo mudou e a data voltou
        para o que era. rsync e checkout fazem exatamente isso."""
        self.preparar({"a.txt": "alfa"})
        antes = (self.pasta / "a.txt").stat().st_mtime
        self.escrever("a.txt", "gama", quando=antes)
        self.indexar()
        self.oraculo(["alfa", "gama"], "apos mudar conteudo mantendo a data")

    def test_O05_conteudo_mudou_no_mesmo_segundo(self):
        """Sem forcar data nenhuma: so rapido. Cache por mtime de resolucao
        grossa erra aqui sozinho."""
        self.preparar({"a.txt": "alfa"})
        self.escrever("a.txt", "gama")
        self.indexar()
        self.oraculo(["alfa", "gama"], "apos mudar conteudo no mesmo segundo")

    def test_O06_mesmo_tamanho_conteudo_diferente(self):
        self.preparar({"a.txt": "aaaa bbbb"})
        antes = (self.pasta / "a.txt").stat().st_mtime
        self.escrever("a.txt", "cccc dddd", quando=antes)
        self.indexar()
        self.oraculo(["aaaa", "cccc"], "apos trocar conteudo do mesmo tamanho")

    def test_O07_data_nova_sem_mudar_conteudo(self):
        """O outro lado do aviso do enunciado: arquivo com data nova que nao
        mudou. Nao pode aparecer resultado errado nem sumir resultado certo."""
        self.preparar({"a.txt": "alfa"})
        agora = time.time() + 5000
        os.utime(self.pasta / "a.txt", (agora, agora))
        self.indexar()
        self.oraculo(["alfa"], "apos so mexer na data")

    def test_O08_arquivo_renomeado(self):
        self.preparar({"a.txt": "alfa"})
        self.renomear("a.txt", "renomeado.txt")
        self.indexar()
        self.oraculo(["alfa"], "apos renomear")

    def test_O09_troca_de_conteudo_entre_dois_arquivos(self):
        self.preparar({"a.txt": "alfa", "b.txt": "beta"})
        ta = (self.pasta / "a.txt").stat().st_mtime
        tb = (self.pasta / "b.txt").stat().st_mtime
        self.escrever("a.txt", "beta", quando=ta)
        self.escrever("b.txt", "alfa", quando=tb)
        self.indexar()
        self.oraculo(["alfa", "beta"], "apos trocar o conteudo entre dois arquivos")

    def test_O10_data_ANTIGA_com_conteudo_novo(self):
        """Checkout de branch antiga: conteudo novo, data velha."""
        self.preparar({"a.txt": "alfa"})
        self.escrever("a.txt", "gama", quando=self.ANTIGO)
        self.indexar()
        self.oraculo(["alfa", "gama"], "apos conteudo novo com data antiga")

    def test_O11_subpasta_inteira_trocada(self):
        self.preparar({"x/a.txt": "alfa", "x/b.txt": "beta"})
        shutil.rmtree(self.pasta / "x")
        self.meus -= {"x/a.txt", "x/b.txt"}
        self.escrever("x/a.txt", "delta", quando=self.ANTIGO)
        self.escrever("x/c.txt", "epsilon", quando=self.ANTIGO)
        self.indexar()
        self.oraculo(["alfa", "beta", "delta", "epsilon"], "apos trocar a subpasta inteira")

    def test_O12_sequencia_longa_de_mudancas(self):
        """Dez rodadas de mudancas variadas, cada uma seguida de um index
        incremental. Erro pequeno de invalidacao se acumula e aparece aqui."""
        self.preparar({f"f{i}.txt": f"termo{i}" for i in range(6)})
        for volta in range(10):
            alvo = self.pasta / f"f{volta % 6}.txt"
            # O arquivo pode ter sido apagado numa volta anterior: nesse caso
            # ele renasce, e renascer com data antiga e' justamente o cenario
            # do enunciado. Sem esta guarda o stat estoura e o teste vira ERROR
            # em vez de medir.
            quando = alvo.stat().st_mtime if alvo.exists() else self.ANTIGO
            self.escrever(alvo.name, f"termo{volta % 6} extra{volta}", quando=quando)
            if volta % 3 == 0:
                self.escrever(f"novo{volta}.txt", f"nascido{volta}", quando=self.ANTIGO)
            if volta % 4 == 3:
                self.apagar(f"f{(volta + 1) % 6}.txt")
            self.indexar()
        termos = [f"termo{i}" for i in range(6)] + [f"extra{v}" for v in range(10)]
        termos += [f"nascido{v}" for v in range(0, 10, 3)]
        self.oraculo(termos, "apos dez rodadas de mudanca")


if __name__ == "__main__":
    unittest.main()
