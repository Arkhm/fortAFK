"""Loop automático do Battle Royale: lobby -> PLAY -> partida -> squad eliminado -> lobby."""
import math
import random
import threading
import time

import tela
from registro import log, log_erro

TOLERANCIA_FIM = 30 * 60   # tempo esgotado + partida que não acaba: para depois de 30 min


class Bot:
    def __init__(self, reprodutor, emitir):
        self.reprodutor = reprodutor
        self.emitir = emitir           # manda eventos para a interface (fila)
        self._parar = threading.Event()
        self._thread = None
        self.cfg = {}
        self.arquivos = []
        self.partidas = 0
        self.motivo = ""
        self.inicio = 0.0
        self.espectando = False        # você morreu e está assistindo um aliado

    @property
    def rodando(self):
        return self._thread is not None and self._thread.is_alive()

    def iniciar(self, cfg, arquivos):
        if self.rodando:
            return
        self.cfg = dict(cfg)           # cópia: mudanças nas configs valem no próximo início
        self.arquivos = list(arquivos)
        self.partidas = 0
        self.motivo = ""
        self.inicio = time.monotonic()
        self.espectando = False
        self._parar.clear()
        self._thread = threading.Thread(target=self._executar, daemon=True)
        self._thread.start()

    def parar(self):
        """Pode ser chamado de qualquer thread. Solta as teclas na hora."""
        self._parar.set()
        self.reprodutor.parar()

    def sinalizar_parada(self):
        """Versão instantânea (sem esperar threads), usada direto pelo hook do F9."""
        self._parar.set()
        self.reprodutor.sinalizar_parada()

    # ---------- utilidades ----------
    def _estado(self, texto):
        self.emitir("estado", texto)

    def _esperar(self, segundos, rotulo):
        """Espera mostrando a contagem no status. Devolve True se mandaram parar."""
        fim = time.monotonic() + max(0.0, segundos)
        while True:
            resta = fim - time.monotonic()
            if resta <= 0:
                return self._parar.is_set()
            if rotulo:
                self._estado(rotulo.format(math.ceil(resta)))
            if self._parar.wait(min(1.0, resta)):
                return True

    def _achar(self, nome):
        if self._parar.is_set() or not tela.existe(nome):
            return None
        return tela.achar(nome, self.cfg["confianca"])

    def _clicar(self, pos):
        if not self._parar.is_set():
            tela.clicar(pos, self._parar)

    def _iniciar_replay(self):
        if self._parar.is_set():
            return
        try:
            self.reprodutor.iniciar_loop(self.arquivos, cancelar=self._parar)
        except Exception as e:
            log_erro("ao iniciar a reprodução", e)

    def _esperar_onibus(self):
        """Depois do PLAY: espera o ônibus aparecer (imagens/onibus.png) para começar a
        reprodução, porque as gravações começam no ônibus e o tempo de fila/carregamento
        varia. Devolve "ok" (reprodução iniciada), "lobby" (fila cancelada) ou "parar"."""
        if not tela.existe("onibus.png"):
            log("Sem onibus.png: a reprodução começa logo após o PLAY")
            self._iniciar_replay()
            return "ok"
        inicio = time.monotonic()
        limite = self.cfg["espera_onibus_max"]
        ultima_checagem = inicio
        log("Esperando o ônibus para começar a gravação...")
        while True:
            if self._parar.is_set():
                return "parar"
            if self._tempo_esgotado():
                return "ok"        # o loop principal trata o timer (sem iniciar reprodução)
            if self._achar("onibus.png"):
                log("Ônibus detectado - começando a gravação")
                self._iniciar_replay()
                return "ok"
            agora = time.monotonic()
            passou = agora - inicio
            if passou >= limite:
                log(f"Ônibus não detectado em {limite:.0f}s - começando a gravação assim mesmo")
                self._iniciar_replay()
                return "ok"
            # De vez em quando confere se a fila foi cancelada e voltou ao lobby.
            # (Só depois de 30 s: logo após o clique o PLAY ainda pode estar visível.)
            if passou > 30 and agora - ultima_checagem >= 10:
                ultima_checagem = agora
                if self._no_lobby():
                    log("Voltou ao lobby antes do ônibus (fila cancelada?)")
                    return "lobby"
            self._estado(f"Esperando o ônibus ({int(passou)}s)")
            if self._parar.wait(0.5):
                return "parar"

    def _vigiar_partida(self, segundos, rotulo):
        """Espera até a próxima verificação, mas a cada `intervalo_espectador` s confere a tela:
          - apareceu a tela final ou o lobby: encerra a espera na hora. Com a câmera na
            gravação, o cursor andaria pelos botões dessa tela enquanto os cliques tocam;
          - viu SPECTATING (imagens/espectando.png): pausa a gravação (você morreu e assiste um aliado);
          - pausado e a tela de espectador sumiu (2 vezes seguidas, sem tela final):
            você foi revivido -> retoma a gravação de onde parou.
        Devolve True se mandaram parar o bot."""
        tem_imagem = tela.existe("espectando.png")
        fim = time.monotonic() + segundos
        proxima = time.monotonic() + self.cfg["intervalo_espectador"]
        sumiu = 0                          # checagens seguidas sem SPECTATING nem tela final
        while True:
            agora = time.monotonic()
            resta = fim - agora
            if resta <= 0:
                return self._parar.is_set()
            if self.espectando:
                self._estado(f"Espectando aliados · gravação pausada (verifica em {math.ceil(resta)}s)")
            else:
                self._estado(rotulo.format(math.ceil(resta)))
            if agora >= proxima:
                proxima = agora + self.cfg["intervalo_espectador"]
                if self._squad_eliminado() or self._no_lobby():
                    return self._parar.is_set()          # tela final/lobby: verifica agora
                if tem_imagem and self._achar("espectando.png"):
                    sumiu = 0
                    if not self.espectando:
                        self.espectando = True
                        self.reprodutor.pausar()
                        log("Espectando aliados - gravação pausada")
                elif tem_imagem and self.espectando:
                    sumiu += 1
                    if sumiu >= 2:
                        self.espectando = False
                        self.reprodutor.retomar()
                        log("Tela de espectador sumiu sem fim de partida - revivido! Retomando a gravação")
            if self._parar.wait(min(1.0, resta)):
                return True

    def _tempo_esgotado(self):
        limite = self.cfg.get("max_minutos", 0)
        return bool(limite) and time.monotonic() - self.inicio >= limite * 60

    # ---------- detecções ----------
    def _no_lobby(self):
        """PLAY visível e RETURN TO LOBBY não. Sem a segunda condição, o "PLAY AGAIN"
        amarelo da tela de fim de partida poderia ser confundido com o lobby."""
        return self._achar("play.png") is not None and self._achar("lobby.png") is None

    def _modo_ok(self):
        """BATTLE ROYALE + modo certo. Tenta 3 vezes (o painel pode ainda estar carregando)."""
        for tentativa in range(3):
            if self._achar("br.png") and self._achar("mode.png"):
                return True
            if tentativa < 2 and self._esperar(2, None):
                return True   # parando: o loop principal encerra logo em seguida
        return False

    def _squad_eliminado(self):
        """Fim de partida = qualquer imagens/fim*.png na tela.
        Sem marcadores, usa o botão RETURN TO LOBBY como critério."""
        marcadores = tela.listar_fim()
        if marcadores:
            for nome in marcadores:
                if self._achar(nome):
                    log(f"Marcador de fim encontrado: {nome}")
                    return True
            return False
        return self._achar("lobby.png") is not None

    def _aguardar_play(self, limite):
        """Depois do clique: espera o lobby carregar (PLAY visível) por até `limite` s.
        Volta antes se o RETURN TO LOBBY reaparecer (o clique não pegou)."""
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if self._achar("lobby.png"):
                return False
            if self._achar("play.png"):
                return True
            if self._esperar(2, "Voltando ao lobby · carregando"):
                return False
        return False

    def _voltar_lobby(self):
        """Clica RETURN TO LOBBY (+ confirmar, se aparecer). Até 3 tentativas.
        Só conta como sucesso quando o PLAY aparece (prova de que chegou no lobby)."""
        for tentativa in range(1, 4):
            if self._parar.is_set():
                return False
            pos = self._achar("lobby.png")
            if pos is None and self._achar("play.png"):
                return True                      # já está no lobby
            if pos:
                self._clicar(pos)
                log(f"Clicou RETURN TO LOBBY (tentativa {tentativa})")
                if self._esperar(2, None):
                    return False
                conf = self._achar("confirmar.png")
                if conf:
                    self._clicar(conf)
                    log("Clicou confirmar")
                if self._aguardar_play(45):
                    return True
            elif self._esperar(2, None):
                return False
        return False

    # ---------- loop principal ----------
    def _executar(self):
        try:
            self._loop()
        except Exception as e:
            log_erro("inesperado no bot - parando com segurança", e)
            self.motivo = "erro"
            self.emitir("aviso", "Erro no bot", f"O bot parou por um erro inesperado:\n{e}\n\nDetalhes em log.txt.")
        finally:
            self.reprodutor.parar()              # solta todas as teclas e botões
            log(f"Bot parado. Partidas concluídas: {self.partidas}")
            self.emitir("bot_parado", self.motivo)

    def _loop(self):
        c = self.cfg
        log(f"Bot iniciado | {len(self.arquivos)} gravações ativas | "
            f"marcadores de fim: {', '.join(tela.listar_fim()) or 'só RETURN TO LOBBY'}")
        log("Deixe o Fortnite em primeiro plano. F9 = parar.")
        if self._esperar(5, "Iniciando em {}s"):
            return

        em_partida = False
        verificar_ja = False
        encerrando = False          # tempo acabou: esperando a partida terminar para parar
        while not self._parar.is_set():
            # ===== TIMER =====
            if self._tempo_esgotado():
                if not em_partida:
                    log(f"Tempo limite de {c['max_minutos']} min atingido - parando no lobby")
                    self.motivo = "tempo"
                    return
                if not encerrando:
                    if not c["tempo_terminar_partida"]:
                        log(f"Tempo limite de {c['max_minutos']} min atingido - parando agora")
                        self.motivo = "tempo"
                        return
                    log(f"Tempo limite de {c['max_minutos']} min atingido - parando a reprodução e "
                        "esperando a partida acabar para voltar ao lobby")
                    encerrando = True
                    self.reprodutor.parar()
                elif time.monotonic() - self.inicio > c["max_minutos"] * 60 + TOLERANCIA_FIM:
                    log("A partida não terminou 30 min depois do tempo limite - parando assim mesmo")
                    self.motivo = "tempo"
                    return

            # ===== 1. LOBBY =====
            if not em_partida:
                self._estado("No lobby")
                if self._achar("lobby.png"):
                    # RETURN TO LOBBY visível: bot iniciado no meio/fim de uma partida.
                    # (Checado antes do PLAY: o "PLAY AGAIN" amarelo da tela final
                    # pode parecer com o play.png.)
                    log("RETURN TO LOBBY visível - já está em partida")
                    em_partida = True
                    verificar_ja = True
                    continue
                pos = self._achar("play.png")
                if pos is None:
                    if self._achar("espectando.png"):
                        # Bot iniciado enquanto você assiste um aliado: já está em partida
                        log("Espectando aliados - já está em partida (gravação pausada)")
                        em_partida = True
                        self.espectando = True
                        self._iniciar_replay()
                        self.reprodutor.pausar()
                        continue
                    if self._esperar(c["poll_lobby"], "No lobby · procurando PLAY ({}s)"):
                        return
                    continue
                if c["verificar_modo"] and not self._modo_ok():
                    if self._parar.is_set():
                        return
                    self._estado("MODO ERRADO")
                    log("MODO ERRADO - BATTLE ROYALE/modo não encontrados. Não cliquei em PLAY.")
                    self.motivo = "modo_errado"
                    self.emitir("aviso", "MODO ERRADO",
                                "O painel não mostra BATTLE ROYALE / o modo certo (br.png e mode.png).\n"
                                "Selecione o modo no jogo (ou recapture as imagens) e inicie o bot de novo.")
                    return
                self._clicar(pos)
                if self._parar.is_set():
                    return
                log("Clicou PLAY")
                resultado = self._esperar_onibus()
                if resultado == "parar":
                    return
                em_partida = resultado == "ok"
                continue

            # ===== 2/3. PARTIDA + VERIFICAÇÃO =====
            if not verificar_ja:
                if encerrando:
                    # sem reprodução, só esperando o fim: verifica com mais frequência
                    espera = random.uniform(15, 25)
                    rotulo = "Tempo esgotado · esperando o fim da partida ({}s)"
                else:
                    espera = random.uniform(c["check_min"], c["check_max"])
                    rotulo = "Em partida · verifica em {}s"
                if self._vigiar_partida(espera, rotulo):
                    return
            verificar_ja = False

            if self._squad_eliminado():
                self.espectando = False
                self.reprodutor.parar()
                self._estado("Voltando ao lobby")
                log("Squad eliminado - voltando ao lobby")
                if not self._voltar_lobby():
                    if self._parar.is_set():
                        return
                    log("Não consegui voltar ao lobby após 3 tentativas - tento de novo na próxima verificação")
                    continue
                # ===== 4. VOLTOU AO LOBBY =====
                em_partida = False
                self.partidas += 1
                self.emitir("partidas", self.partidas)
                log(f"Partida concluída ({self.partidas})")
                if c["max_partidas"] and self.partidas >= c["max_partidas"]:
                    log(f"Limite de {c['max_partidas']} partidas atingido")
                    self.motivo = "limite"
                    return
                if encerrando or self._tempo_esgotado():
                    log(f"Tempo limite de {c['max_minutos']} min atingido - parando no lobby")
                    self.motivo = "tempo"
                    return
                espera = random.uniform(c["lobby_min"], c["lobby_max"])
                log(f"No lobby. Aguardando {espera:.0f}s")
                if self._esperar(espera, "Aguardando {}s"):
                    return
            elif self._no_lobby():
                # Voltou ao lobby sozinho (kick, fila cancelada...)
                self.espectando = False
                self.reprodutor.parar()
                em_partida = False
                espera = random.uniform(c["lobby_min"], c["lobby_max"])
                log(f"Lobby detectado sem fim de partida (kick/fila cancelada). Aguardando {espera:.0f}s")
                if self._esperar(espera, "Aguardando {}s"):
                    return
            else:
                log("Em partida (espectando aliados) - continuando" if self.espectando
                    else "Em partida - continuando")
                if not encerrando and not self.reprodutor.rodando:
                    self._iniciar_replay()
                    if self.espectando:
                        self.reprodutor.pausar()
