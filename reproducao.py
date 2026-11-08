"""Reprodução das gravações com pydirectinput (scan codes / SendInput)."""
import os
import random
import threading
import time

import pydirectinput

from gravacao import carregar_eventos
from registro import log, log_erro
from teclas import reproduzivel

pydirectinput.PAUSE = 0


class Reprodutor:
    """Roda em thread própria. Sempre que é interrompido, solta tudo que pressionou."""

    def __init__(self, emitir=None):
        self.emitir = emitir or (lambda *a: None)
        # Cada execução ganha um Event próprio: se uma thread antiga demorar a
        # morrer, ela continua "parada" mesmo depois que outra execução começar.
        self._parar = threading.Event()
        self._cancelar = None          # Event externo (o do bot), checado junto
        self._thread = None
        self._trava = threading.Lock()     # protege teclas/botões entre a thread e o parar()
        self._pausa = threading.Event()    # acionado = reprodução congelada (ex: espectando)
        self.teclas = set()
        self.botoes = set()

    @property
    def rodando(self):
        return self._thread is not None and self._thread.is_alive()

    @property
    def pausado(self):
        return self._pausa.is_set()

    def pausar(self):
        """Congela a gravação no ponto atual e solta as teclas (a thread faz isso)."""
        self._pausa.set()

    def retomar(self):
        """Continua do ponto onde pausou, voltando a segurar as teclas que estavam seguradas."""
        self._pausa.clear()

    # ---------- controle ----------
    def iniciar_loop(self, arquivos, cancelar=None):
        """Reproduz gravações aleatórias em sequência (1–3 s entre elas) até parar().

        cancelar: Event do bot; se ele for acionado, a reprodução não envia mais nada."""
        gravacoes = []
        for arq in arquivos:
            try:
                ev = carregar_eventos(arq)
                if ev:
                    gravacoes.append((os.path.basename(arq), ev))
            except Exception as e:
                log(f"Gravação ignorada ({os.path.basename(arq)}): {e}")
        if not gravacoes:
            raise RuntimeError("nenhuma gravação válida para reproduzir")
        self._iniciar(self._loop, (gravacoes,), cancelar)

    def reproduzir_uma(self, arquivo, contagem=3):
        """Modo "testar": contagem regressiva e reproduz a gravação uma única vez."""
        ev = carregar_eventos(arquivo)
        self._iniciar(self._uma, ((os.path.basename(arquivo), ev), contagem), None)

    def _iniciar(self, alvo, args, cancelar):
        self.parar()
        if cancelar is not None and cancelar.is_set():
            return                         # o bot foi parado enquanto os arquivos carregavam
        parar = threading.Event()
        self._pausa.clear()
        with self._trava:
            self._parar = parar
            self._cancelar = cancelar
        self._thread = threading.Thread(target=self._executar_seguro, args=(alvo, args, parar), daemon=True)
        self._thread.start()

    def sinalizar_parada(self):
        """Só avisa a thread para parar (sem esperar). Seguro para chamar do hook de teclado."""
        self._parar.set()

    def parar(self):
        self._parar.set()
        t = self._thread
        if t and t is not threading.current_thread():
            t.join(timeout=3)
        self._thread = None
        self._pausa.clear()
        self.soltar_tudo()

    def _parado(self, parar):
        return parar.is_set() or (self._cancelar is not None and self._cancelar.is_set())

    def soltar_tudo(self):
        with self._trava:
            for t in list(self.teclas):
                try:
                    pydirectinput.keyUp(t)
                except Exception:
                    pass
            for b in list(self.botoes):
                try:
                    pydirectinput.mouseUp(button=b)
                except Exception:
                    pass
            self.teclas.clear()
            self.botoes.clear()

    # ---------- execução ----------
    def _executar_seguro(self, alvo, args, parar):
        try:
            alvo(*args, parar)
        except Exception as e:
            log_erro("na reprodução", e)
        finally:
            if self._parar is parar:       # só limpa se ainda for a execução atual
                self.soltar_tudo()
            self.emitir("replay_fim")

    def _evento(self, tipo, valor, parar):
        with self._trava:
            if self._parado(parar):        # parar() chegou: não pressiona mais nada
                return
            if tipo == "mv":
                # movimento relativo: é o que o jogo lê para girar a câmera
                pydirectinput.moveRel(valor[0], valor[1], relative=True, _pause=False)
            elif tipo == "kd" and reproduzivel(valor):
                pydirectinput.keyDown(valor)
                self.teclas.add(valor)
            elif tipo == "ku" and valor in self.teclas:
                pydirectinput.keyUp(valor)
                self.teclas.discard(valor)
            elif tipo == "md":
                pydirectinput.mouseDown(button=valor)
                self.botoes.add(valor)
            elif tipo == "mu" and valor in self.botoes:
                pydirectinput.mouseUp(button=valor)
                self.botoes.discard(valor)

    def _em_pausa(self, parar):
        """Fica parado enquanto pausado. Devolve True se mandaram parar de vez."""
        with self._trava:
            teclas, botoes = set(self.teclas), set(self.botoes)
        self.soltar_tudo()
        log("Gravação pausada")
        while self._pausa.is_set():
            if parar.wait(0.1) or self._parado(parar):
                return True
        with self._trava:
            if self._parado(parar):
                return True
            # volta a segurar o que estava segurado na hora da pausa (ex: W andando)
            for t in teclas:
                pydirectinput.keyDown(t)
                self.teclas.add(t)
            for b in botoes:
                pydirectinput.mouseDown(button=b)
                self.botoes.add(b)
        log("Gravação retomada")
        return False

    def _aguardar(self, segundos, parar):
        """Espera `segundos` de reprodução; o tempo em pausa não conta.
        Devolve (interrompida, segundos_em_pausa)."""
        em_pausa = 0.0
        fim = time.perf_counter() + segundos
        while True:
            if self._pausa.is_set():
                t0 = time.perf_counter()
                if self._em_pausa(parar):
                    return True, em_pausa
                d = time.perf_counter() - t0
                em_pausa += d
                fim += d
                continue
            resta = fim - time.perf_counter()
            if resta <= 0:
                return self._parado(parar), em_pausa
            if resta > 0.03:
                if parar.wait(min(resta - 0.02, 0.05)):
                    return True, em_pausa
            else:
                # o wait() do Windows só acorda a cada ~15 ms, o que deixaria a câmera truncada
                time.sleep(min(resta, 0.002))
                if parar.is_set():
                    return True, em_pausa

    def _tocar(self, eventos, parar):
        """Reproduz respeitando o tempo de cada evento. Devolve False se foi interrompida."""
        inicio = time.perf_counter()
        for t, tipo, valor in eventos:
            espera = t - (time.perf_counter() - inicio)
            interrompida, em_pausa = self._aguardar(max(0.0, espera), parar)
            inicio += em_pausa             # a pausa "congela" o relógio da gravação
            if interrompida:
                return False
            self._evento(tipo, valor, parar)
        return True

    def _loop(self, gravacoes, parar):
        while not self._parado(parar):
            nome, eventos = random.choice(gravacoes)
            log(f"Reproduzindo {nome}")
            self._tocar(eventos, parar)
            self.soltar_tudo()
            self._aguardar(random.uniform(1, 3), parar)

    def _uma(self, gravacao, contagem, parar):
        nome, eventos = gravacao
        for i in range(contagem, 0, -1):
            self.emitir("estado", f"Teste em {i}s")
            if parar.wait(1):
                return
        self.emitir("estado", f"Testando {nome}")
        log(f"Teste: reproduzindo {nome}")
        if self._tocar(eventos, parar):
            log("Teste concluído")
        else:
            log("Teste interrompido")
