"""Suite de aceite OCULTA do A/B nº 3, dominio STORE.

POR QUE ESTA SUITE EXISTE, e e' o aprendizado dos dois A/B anteriores:
la os dois bracos bateram no teto e o experimento empatou. O diagnostico foi
que a tarefa nao tinha ARMADILHA: qualquer decomposicao decente funcionava, e
planejar nao pagava nada.

Aqui existe uma armadilha, e ela e' o ponto do experimento:

  caminho natural   reescrever o arquivo inteiro a cada gravacao
                    passa 100% de BASE e quase tudo de ROBUSTEZ
                    morre em INVARIANTE

  caminho planejado gravacao que sobrevive a morte do processo no meio
                    (append, rename atomico, fsync, recuperacao de cauda)

O enunciado NAO nomeia tecnica nenhuma. Ele diz o requisito em linguagem de
negocio: "o servico reinicia sozinho varias vezes por dia" e "quando responde
gravei, tem que estar la depois do restart". Traduzir requisito em tecnica e'
exatamente o trabalho que planejar deveria fazer. Se nao faz, nao esta pagando.

TRES CAMADAS:

  BASE (B)         8 testes. O basico. Qualquer solucao razoavel passa.
                   Existe para nao premiar quem so trata durabilidade e nao
                   guarda nada.

  ROBUSTEZ (R)     12 testes. Bordas que o enunciado nao cita.

  INVARIANTE (I)   10 testes. Durabilidade sob morte do processo.
                   METRICA PRIMARIA.

CRITERIO DE INVARIANTE, igual para os dez e escolhido para nao favorecer
desenho nenhum:

  1. stderr nao pode conter "Traceback" na REABERTURA
  2. toda chave cuja gravacao foi CONFIRMADA (processo saiu com codigo 0)
     tem que continuar legivel
  3. a chave cuja gravacao foi interrompida pode estar ou nao estar: as duas
     decisoes passam
  4. o store nao pode ficar travado: depois do crash, gravar de novo funciona

Nenhuma decisao de formato, de layout ou de API interna e' cobrada. So nao
passa nao ter decidido nada.

Roda com cwd na raiz do repo entregue pelo braco.
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path.cwd()
LIMITE = 60


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="kv-aceite-")
        self.loja = str(Path(self.tmp) / "dados")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ base
    def kv(self, *args, loja=None, limite=LIMITE):
        """Uma invocacao da CLI. Processo novo toda vez, de proposito: e' a
        unica forma de provar que o estado esta no DISCO e nao na memoria."""
        alvo = self.loja if loja is None else loja
        return subprocess.run(
            [sys.executable, "-m", "kvstore", alvo, *args],
            cwd=RAIZ, capture_output=True, text=True, errors="replace", timeout=limite,
        )

    def gravar(self, chave, valor):
        p = self.kv("set", chave, valor)
        self.assertEqual(p.returncode, 0, f"set {chave} falhou: {p.stderr[-300:]}")
        return p

    def ler(self, chave):
        return self.kv("get", chave)

    def semTraceback(self, p, quando):
        self.assertNotIn("Traceback", p.stderr, f"excecao vazou {quando}:\n{p.stderr[-800:]}")

    def contem(self, p, valor):
        """Aceita o valor em qualquer formatacao de saida: cru, com rotulo,
        entre aspas. O que se cobra e' que o dado voltou, nao o layout."""
        return valor in p.stdout

    # --------------------------------------------------- apoio ao invariante
    def maior_arquivo(self):
        arquivos = [p for p in Path(self.loja).rglob("*") if p.is_file()]
        self.assertTrue(arquivos, f"o store nao criou arquivo nenhum em {self.loja}")
        return max(arquivos, key=lambda p: p.stat().st_size)

    def semear(self, n, prefixo="k", tamanho=200):
        """Popula o store e devolve o dicionario do que foi CONFIRMADO."""
        esperado = {}
        for i in range(n):
            chave, valor = f"{prefixo}{i:04d}", f"v{i:04d}-" + "x" * tamanho
            self.gravar(chave, valor)
            esperado[chave] = valor
        return esperado

    def _instantaneo(self):
        """Tamanho de cada arquivo do store agora. E' o sinal que diz que a
        gravacao comecou a tocar o disco."""
        try:
            return {p: p.stat().st_size for p in Path(self.loja).rglob("*") if p.is_file()}
        except OSError:
            return {}

    def matar_durante_gravacao(self, chave, valor, *, limite=15.0):
        """Dispara um set e mata no INSTANTE em que o disco comeca a mudar.

        A primeira versao disto sorteava o momento da morte a partir do tempo
        medio de um set, e o resultado oscilava entre execucoes: as vezes a
        morte caia na subida do interpretador, antes de qualquer byte, e o
        teste passava sem ter testado nada. Medi isso na calibracao e troquei.

        Observar o disco e' deterministico e nao favorece desenho nenhum:

          reescreve tudo  -> o arquivo e' truncado no open, o tamanho cai,
                             mata-se ali, e o que ja estava confirmado se perde
          anexa           -> o arquivo cresce, mata-se ali, e o que se perde e'
                             no maximo o registro em voo
          tmp + rename    -> aparece um arquivo novo, mata-se ali, e o arquivo
                             bom continua intacto

        Devolve True se o processo ainda assim confirmou (saiu com 0)."""
        antes = self._instantaneo()
        p = subprocess.Popen(
            [sys.executable, "-m", "kvstore", self.loja, "set", chave, valor],
            cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if p.poll() is not None:
                break
            if self._instantaneo() != antes:
                p.send_signal(signal.SIGKILL)
                break
            time.sleep(0.0005)
        p.wait(timeout=LIMITE)
        return p.returncode == 0

    def matar_durante_remocao(self, chave, *, limite=15.0):
        antes = self._instantaneo()
        p = subprocess.Popen(
            [sys.executable, "-m", "kvstore", self.loja, "del", chave],
            cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if p.poll() is not None:
                break
            if self._instantaneo() != antes:
                p.send_signal(signal.SIGKILL)
                break
            time.sleep(0.0005)
        p.wait(timeout=LIMITE)
        return p.returncode == 0

    def conferir_todos(self, esperado, quando, tolerar=()):
        """Exige que todo par confirmado continue legivel. As chaves em
        'tolerar' podem faltar: sao as que estavam em voo quando o processo
        morreu, e perder uma gravacao nao confirmada e' legitimo."""
        p = self.kv("list")
        self.semTraceback(p, f"no list {quando}")
        perdidas = []
        for chave, valor in esperado.items():
            if chave in tolerar:
                continue
            g = self.ler(chave)
            self.semTraceback(g, f"no get {quando}")
            if g.returncode != 0 or not self.contem(g, valor):
                perdidas.append(chave)
        self.assertFalse(
            perdidas,
            f"{len(perdidas)} de {len(esperado)} chaves CONFIRMADAS sumiram {quando}"
            f" (ex.: {perdidas[:5]})",
        )


class TestBase(Base):
    """O basico. Existe para a camada I nao ser satisfeita por um programa que
    nunca guarda nada."""

    def test_B01_set_e_get(self):
        self.gravar("nome", "maria")
        p = self.ler("nome")
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        self.assertTrue(self.contem(p, "maria"), f"get nao devolveu o valor:\n{p.stdout[:400]}")

    def test_B02_sobrescreve(self):
        self.gravar("nome", "maria")
        self.gravar("nome", "joana")
        p = self.ler("nome")
        self.assertTrue(self.contem(p, "joana"), f"nao sobrescreveu:\n{p.stdout[:400]}")
        self.assertFalse(self.contem(p, "maria"), f"devolveu o valor antigo:\n{p.stdout[:400]}")

    def test_B03_del_remove(self):
        self.gravar("nome", "maria")
        p = self.kv("del", "nome")
        self.semTraceback(p, "no del")
        g = self.ler("nome")
        self.assertFalse(self.contem(g, "maria"), "get devolveu chave apagada")

    def test_B04_list_mostra_as_chaves(self):
        for c in ("alfa", "beta", "gama"):
            self.gravar(c, "x")
        p = self.kv("list")
        self.assertEqual(p.returncode, 0, p.stderr[-300:])
        for c in ("alfa", "beta", "gama"):
            self.assertIn(c, p.stdout, f"list nao mostrou {c}:\n{p.stdout[:400]}")

    def test_B05_list_nao_mostra_apagada(self):
        self.gravar("alfa", "x")
        self.gravar("beta", "x")
        self.kv("del", "alfa")
        p = self.kv("list")
        self.assertIn("beta", p.stdout)
        self.assertNotIn("alfa", p.stdout, f"list mostrou chave apagada:\n{p.stdout[:400]}")

    def test_B06_valor_com_espaco_e_acento(self):
        valor = "Relatório de produção, março de 2026"
        self.gravar("titulo", valor)
        p = self.ler("titulo")
        self.assertTrue(self.contem(p, valor), f"perdeu espaco ou acento:\n{p.stdout[:400]}")

    def test_B07_diretorio_novo_e_criado(self):
        novo = str(Path(self.tmp) / "ainda" / "nao" / "existe")
        p = self.kv("set", "a", "1", loja=novo)
        self.semTraceback(p, "com diretorio inexistente")
        self.assertEqual(p.returncode, 0, "o store deveria criar o diretorio dele")
        g = self.kv("get", "a", loja=novo)
        self.assertTrue(self.contem(g, "1"))

    def test_B08_sobrevive_a_restart_normal(self):
        """Processo novo a cada chamada ja prova isso, mas explicito e' melhor:
        e' o requisito central do enunciado no caminho feliz."""
        esperado = self.semear(20)
        self.conferir_todos(esperado, "depois de restart normal")


class TestRobustez(Base):
    """Bordas que o enunciado nao cita."""

    def test_R01_valor_vazio(self):
        p = self.kv("set", "vazio", "")
        self.semTraceback(p, "com valor vazio")
        self.assertEqual(p.returncode, 0, "valor vazio e' legitimo")
        g = self.ler("vazio")
        self.semTraceback(g, "lendo valor vazio")
        self.assertEqual(g.returncode, 0)

    def test_R02_valor_grande(self):
        """100 KB. Nao sobe mais que isso porque o proprio Linux corta um
        argumento de linha de comando em 128 KB (MAX_ARG_STRLEN), e o teste
        estouraria no subprocess em vez de medir o store."""
        valor = "z" * 100_000
        self.gravar("grande", valor)
        p = self.ler("grande")
        self.semTraceback(p, "lendo valor de 100 KB")
        self.assertGreaterEqual(
            p.stdout.count("z"), 100_000, "valor de 100 KB nao voltou inteiro"
        )

    def test_R03_chave_com_caractere_estranho(self):
        for chave in ("com espaco", "com=igual", "com/barra", "acentuação-ção"):
            p = self.kv("set", chave, "v")
            self.semTraceback(p, f"com chave {chave!r}")
            self.assertEqual(p.returncode, 0, f"chave {chave!r} recusada")
            g = self.kv("get", chave)
            self.assertTrue(self.contem(g, "v"), f"chave {chave!r} nao voltou")

    def test_R04_valor_com_quebra_de_linha(self):
        valor = "linha um\nlinha dois\nlinha tres"
        self.gravar("multi", valor)
        p = self.ler("multi")
        self.semTraceback(p, "lendo valor multilinha")
        for pedaco in ("linha um", "linha dois", "linha tres"):
            self.assertIn(pedaco, p.stdout, f"perdeu {pedaco!r} no valor multilinha")

    def test_R05_get_de_chave_ausente(self):
        """Qualquer decisao passa: erro, vazio, mensagem. So nao pode explodir
        nem inventar valor."""
        self.gravar("existe", "sim")
        p = self.ler("naoexiste")
        self.semTraceback(p, "no get de chave ausente")
        self.assertNotIn("sim", p.stdout, "inventou valor para chave ausente")

    def test_R06_del_de_chave_ausente(self):
        p = self.kv("del", "nuncaexistiu")
        self.semTraceback(p, "no del de chave ausente")

    def test_R07_subcomando_invalido(self):
        p = self.kv("voar", "alto")
        self.semTraceback(p, "com subcomando invalido")
        self.assertNotEqual(p.returncode, 0, "subcomando invalido tem que sinalizar erro")

    def test_R08_sem_argumento_nenhum(self):
        p = subprocess.run(
            [sys.executable, "-m", "kvstore"],
            cwd=RAIZ, capture_output=True, text=True, errors="replace", timeout=LIMITE,
        )
        self.semTraceback(p, "sem argumento")
        self.assertNotEqual(p.returncode, 0, "sem argumento tem que sinalizar erro")

    def test_R09_caminho_e_um_arquivo(self):
        arquivo = str(Path(self.tmp) / "sou-um-arquivo")
        Path(arquivo).write_text("nao sou diretorio")
        p = self.kv("set", "a", "1", loja=arquivo)
        self.semTraceback(p, "com caminho que e' arquivo")
        self.assertNotEqual(p.returncode, 0, "arquivo no lugar de diretorio tem que sinalizar erro")

    def test_R10_muitas_chaves(self):
        """800 chaves. Nao cobra estrutura de dados: cobra terminar e estar
        tudo la."""
        esperado = self.semear(800, tamanho=20)
        p = self.kv("list", limite=120)
        self.semTraceback(p, "no list de 800 chaves")
        faltando = [c for c in esperado if c not in p.stdout]
        self.assertFalse(faltando, f"{len(faltando)} chaves fora do list (ex.: {faltando[:5]})")

    def test_R11_valor_parecido_com_o_formato_interno(self):
        """Log de verdade tem valor que imita o proprio formato de
        armazenamento. Se o store nao escapa, o dado corrompe o indice."""
        # Sem byte nulo: argv do sistema operacional nao aceita, e o teste
        # estouraria no subprocess em vez de medir o store.
        venedores_de_formato = [
            '{"chave": "outra", "valor": "invadido"}',
            "chave=outra\nvalor=invadido",
            "\r\noutra\t invadido\r\n",
            "===fim-do-registro===\noutra invadido",
        ]
        venenos = venedores_de_formato
        for i, veneno in enumerate(venenos):
            chave = f"veneno{i}"
            p = self.kv("set", chave, veneno)
            self.semTraceback(p, f"gravando veneno {i}")
            if p.returncode != 0:
                continue  # recusar e' uma decisao legitima; corromper nao e'
            g = self.kv("get", "outra")
            self.semTraceback(g, f"lendo depois do veneno {i}")
            self.assertNotIn("invadido", g.stdout, f"o veneno {i} vazou para outra chave")

    def test_R12_muitos_ciclos_de_set_e_del(self):
        for volta in range(50):
            self.gravar("giratoria", f"volta{volta}")
            self.kv("del", "giratoria")
        self.gravar("giratoria", "final")
        p = self.ler("giratoria")
        self.semTraceback(p, "depois de 50 ciclos set/del")
        self.assertTrue(self.contem(p, "final"), f"estado errado apos ciclos:\n{p.stdout[:400]}")


class TestInvariante(Base):
    """Durabilidade sob morte do processo. METRICA PRIMARIA.

    Todo teste aqui segue a mesma regra: o que foi CONFIRMADO (exit 0) nao
    pode sumir. O que estava em voo pode sumir. Reabrir nao pode explodir."""

    def test_I01_cauda_com_lixo(self):
        """Morte no meio de uma gravacao deixa registro pela metade. Reabrir
        tem que ignorar a cauda ruim, nao perder o arquivo inteiro."""
        esperado = self.semear(60)
        alvo = self.maior_arquivo()
        with open(alvo, "ab") as fh:
            fh.write(b"\x00\xff lixo de gravacao interrompida sem fim")
        self.conferir_todos(esperado, "apos lixo na cauda")

    def test_I02_cauda_truncada(self):
        """O outro lado do mesmo acidente: o registro final saiu cortado."""
        esperado = self.semear(60)
        alvo = self.maior_arquivo()
        tamanho = alvo.stat().st_size
        with open(alvo, "r+b") as fh:
            fh.truncate(max(0, tamanho - 40))
        p = self.kv("list")
        self.semTraceback(p, "apos truncar a cauda")
        self.assertEqual(p.returncode, 0, "o store tem que reabrir com a cauda cortada")
        # A ultima chave pode ter ido junto; as outras 59 nao.
        ultima = max(esperado)
        self.conferir_todos(esperado, "apos truncar a cauda", tolerar={ultima})

    def test_I03_morte_no_meio_da_gravacao(self):
        """O teste central. Mata o processo em varios instantes diferentes
        enquanto ele grava. Nenhuma chave JA confirmada pode sumir.

        Reescrever o arquivo inteiro a cada set falha aqui: uma das mortes cai
        no meio da reescrita e leva tudo junto."""
        esperado = self.semear(400, tamanho=2000)
        interrompidas = set()
        for tentativa in range(30):
            chave = f"voo{tentativa:03d}"
            valor = f"w{tentativa}-" + "y" * 2000
            if self.matar_durante_gravacao(chave, valor):
                esperado[chave] = valor
            else:
                interrompidas.add(chave)
        self.conferir_todos(esperado, "apos 30 mortes durante gravacao", tolerar=interrompidas)

    def test_I04_reabre_apos_morte(self):
        """Mais fraco que o I03 de proposito: aqui so se cobra REABRIR sem
        explodir. Um store que perde dados mas abre passa neste e falha no I03,
        e essa diferenca e' informacao."""
        self.semear(150, tamanho=8000)
        for tentativa in range(12):
            self.matar_durante_gravacao(f"m{tentativa}", "z" * 2000)
            q = self.kv("list")
            self.semTraceback(q, f"reabrindo apos a morte {tentativa}")
            self.assertEqual(q.returncode, 0, f"store nao reabre apos a morte {tentativa}")

    def test_I05_continua_gravavel_apos_morte(self):
        """O store nao pode ficar travado. Depois do acidente, a vida segue."""
        esperado = self.semear(100, tamanho=2000)
        self.matar_durante_gravacao("emvoo", "q" * 5000)
        depois = self.kv("set", "depois", "consegui")
        self.semTraceback(depois, "gravando depois da morte")
        self.assertEqual(depois.returncode, 0, "o store travou depois de uma morte")
        esperado["depois"] = "consegui"
        self.conferir_todos(esperado, "apos gravar depois da morte", tolerar={"emvoo"})

    def test_I06_arquivo_de_tamanho_zero(self):
        """Crash logo apos criar o arquivo e antes de escrever nele."""
        esperado = self.semear(30)
        (Path(self.loja) / "zerado.dat").write_bytes(b"")
        self.conferir_todos(esperado, "com arquivo de tamanho zero no diretorio")

    def test_I07_sobra_de_arquivo_temporario(self):
        """Morte durante rename deixa .tmp para tras. Reabrir tem que ignorar
        o entulho, nao engasgar nele."""
        esperado = self.semear(30)
        for nome in ("store.tmp", ".store.swp", "dados.part"):
            (Path(self.loja) / nome).write_bytes(b"\x01\x02 restos de uma gravacao morta")
        self.conferir_todos(esperado, "com sobra de arquivo temporario")

    def test_I08_morte_com_store_grande(self):
        """O mesmo acidente do I03, agora com o store grande.

        O enunciado avisa que a quantidade de gravacoes cresce e ninguem limpa.
        Num desenho que reescreve o arquivo inteiro, a janela em que o dado
        fica vulneravel CRESCE junto com o arquivo. Num desenho que so anexa,
        ela nao cresce. Este teste e' onde essa diferenca aparece."""
        esperado = self.semear(120, tamanho=20000)   # ~2,4 MB no disco
        interrompidas = set()
        for tentativa in range(15):
            chave = f"pesado{tentativa:03d}"
            valor = f"p{tentativa}-" + "h" * 20000
            if self.matar_durante_gravacao(chave, valor):
                esperado[chave] = valor
            else:
                interrompidas.add(chave)
        self.conferir_todos(esperado, "apos 15 mortes com store grande", tolerar=interrompidas)

    def test_I09_morte_durante_remocao(self):
        esperado = self.semear(120, tamanho=8000)
        for tentativa in range(8):
            alvo = f"k{tentativa:04d}"
            self.matar_durante_remocao(alvo)
            esperado.pop(alvo, None)
        q = self.kv("list")
        self.semTraceback(q, "reabrindo apos mortes durante del")
        self.assertEqual(q.returncode, 0, "store nao reabre apos morte durante del")
        self.conferir_todos(esperado, "apos mortes durante del")

    def test_I10_store_e_realocavel(self):
        """Copiar o diretorio para outro lugar e abrir la tem que funcionar:
        caminho absoluto gravado dentro do store e' defeito, e aparece na hora
        de restaurar backup."""
        esperado = self.semear(40)
        outro = str(Path(self.tmp) / "mudou-de-lugar")
        shutil.copytree(self.loja, outro)
        p = self.kv("list", loja=outro)
        self.semTraceback(p, "abrindo copia em outro caminho")
        self.assertEqual(p.returncode, 0, "o store nao abre depois de mudar de diretorio")
        faltando = [c for c in esperado if c not in p.stdout]
        self.assertFalse(faltando, f"{len(faltando)} chaves sumiram na copia (ex.: {faltando[:5]})")


if __name__ == "__main__":
    unittest.main()
