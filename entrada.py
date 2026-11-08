"""Escuta global do teclado (atalhos F8/F9 + gravação) usando pynput."""
from pynput import keyboard

from teclas import nome_tecla

LLKHF_INJECTED = 0x10   # flag do Windows: evento gerado por programa (SendInput)


class EntradaGlobal:
    """Um único listener de teclado para o app inteiro.

    - ao_atalho(nome) é chamado em toda tecla pressionada (a interface decide se é atalho).
    - Se o gravador estiver ativo, repassa pressionar/soltar para ele.
    - Ignora teclas injetadas (a própria reprodução), para o replay nunca disparar
      atalhos nem ser regravado."""

    def __init__(self, ao_atalho, gravador, parada_rapida=None):
        self.ao_atalho = ao_atalho
        self.gravador = gravador
        # parada_rapida(nome) roda direto aqui no hook: o F9 para o bot na hora,
        # mesmo que a interface esteja ocupada.
        self.parada_rapida = parada_rapida
        self.listener = None
        self._pressionadas = set()   # para ignorar o auto-repeat dos atalhos

    def iniciar(self):
        self.listener = keyboard.Listener(
            on_press=self._press, on_release=self._release,
            win32_event_filter=self._filtro)
        self.listener.daemon = True
        self.listener.start()

    def parar(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

    @staticmethod
    def _filtro(msg, data):
        # Retornar False impede o evento de chegar aos callbacks (não bloqueia o jogo)
        return not (data.flags & LLKHF_INJECTED)

    def _press(self, k):
        nome = nome_tecla(k)
        if not nome:
            return
        if nome not in self._pressionadas:        # só a primeira pressão (sem auto-repeat)
            self._pressionadas.add(nome)
            try:
                if self.parada_rapida:
                    self.parada_rapida(nome)
                self.ao_atalho(nome)
            except Exception:
                pass
        self.gravador.tecla(nome, True)

    def _release(self, k):
        nome = nome_tecla(k)
        if nome:
            self._pressionadas.discard(nome)
            self.gravador.tecla(nome, False)
