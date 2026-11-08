"""Gravação (estilo TinyTask) e leitura dos arquivos de gravação.

Formato do arquivo (compatível com o script antigo): lista de [tempo_s, tipo, valor]
  tipo: kd/ku = tecla pressionada/solta, md/mu = botão do mouse pressionado/solto,
        mv = movimento da câmera (valor = [dx, dy])
"""
import glob
import json
import os
import threading
import time
from datetime import datetime

from pynput import mouse

from camera import CapturaCamera
from config import PASTA_GRAV
from registro import log
from teclas import reproduzivel

LLMHF_INJECTED = 0x01
TIPOS = {"kd", "ku", "md", "mu", "mv"}
BOTOES = {"left", "right", "middle"}
_cache_info = {}        # arquivo -> (mtime, tamanho, info): gravações com câmera são grandes


class Gravador:
    def __init__(self):
        self._trava = threading.Lock()
        self.ativo = False
        self.eventos = []
        self.t0 = 0.0
        self.seguradas = set()
        self.botoes = set()
        self.ignoradas = set()
        self._avisadas = set()
        self._mouse = None
        self._camera = None

    def iniciar(self, ignoradas, camera=False):
        with self._trava:
            self.eventos = []
            self.seguradas = set()
            self.botoes = set()
            self.ignoradas = set(ignoradas)
            self._avisadas = set()
            self.t0 = time.perf_counter()
            self.ativo = True
        # O hook de mouse só fica ligado durante a gravação (não pesa no jogo no resto do tempo).
        self._mouse = mouse.Listener(on_click=self._clique, win32_event_filter=self._filtro_mouse)
        self._mouse.daemon = True
        self._mouse.start()
        if camera:
            self._camera = CapturaCamera(self._mover)
            self._camera.iniciar()

    def _mover(self, instante, dx, dy):
        """Chamado pela thread da câmera com cada pacote de movimento."""
        with self._trava:
            if self.ativo:
                self.eventos.append([round(max(0.0, instante - self.t0), 3), "mv", [dx, dy]])

    @staticmethod
    def _filtro_mouse(msg, data):
        return not (data.flags & LLMHF_INJECTED)

    def _add(self, tipo, valor):
        self.eventos.append([round(time.perf_counter() - self.t0, 3), tipo, valor])

    def tecla(self, nome, pressionada):
        """Chamado pelo listener global de teclado (outra thread)."""
        if not self.ativo or nome in self.ignoradas:
            return
        with self._trava:
            if not self.ativo:
                return
            if not reproduzivel(nome):
                if nome not in self._avisadas:
                    self._avisadas.add(nome)
                    log(f"Tecla '{nome}' não pode ser reproduzida pelo pydirectinput - ignorada")
                return
            if pressionada:
                if nome in self.seguradas:      # auto-repeat do Windows: ignora
                    return
                self.seguradas.add(nome)
                self._add("kd", nome)
            elif nome in self.seguradas:
                self.seguradas.discard(nome)
                self._add("ku", nome)

    def _clique(self, x, y, botao, pressionado):
        nome = getattr(botao, "name", "")
        if nome not in BOTOES:
            return
        with self._trava:
            if self.ativo:
                self._add("md" if pressionado else "mu", nome)
                (self.botoes.add if pressionado else self.botoes.discard)(nome)

    def parar(self, descartar_clique_final=False):
        """Para e salva. Devolve (arquivo, n_eventos, duracao) ou None se ficou vazia.

        descartar_clique_final: quando a gravação é parada pelo botão da barra,
        remove o clique nesse botão (último 'md left' do último segundo)."""
        if self._mouse:
            self._mouse.stop()
            self._mouse = None
        if self._camera:
            self._camera.parar()
            self._camera = None
        with self._trava:
            self.ativo = False
            fim = round(time.perf_counter() - self.t0, 3)
            ev = self.eventos
            seguradas, botoes = self.seguradas, self.botoes
            self.eventos, self.seguradas, self.botoes = [], set(), set()
        ev.sort(key=lambda e: e[0])         # a câmera chega de outra thread
        if descartar_clique_final:
            for i in range(len(ev) - 1, -1, -1):
                if ev[i][1] == "md" and ev[i][2] == "left":
                    if fim - ev[i][0] <= 1.5:
                        ev = ev[:i]
                        botoes.discard("left")
                    break
        # Teclas/botões ainda pressionados ao parar: grava a soltura neste instante,
        # senão no replay a tecla seria solta logo depois de pressionada.
        if ev:
            ev += [[fim, "ku", t] for t in sorted(seguradas)]
            ev += [[fim, "mu", b] for b in sorted(botoes)]
        if not ev:
            log("Gravação vazia, nada salvo.")
            return None
        os.makedirs(PASTA_GRAV, exist_ok=True)
        base = f"gravacao_{datetime.now():%Y%m%d_%H%M%S}"
        arq = os.path.join(PASTA_GRAV, base + ".json")
        n = 2
        while os.path.exists(arq):
            arq = os.path.join(PASTA_GRAV, f"{base}_{n}.json")
            n += 1
        with open(arq, "w", encoding="utf-8") as f:
            json.dump(ev, f)
        dur = ev[-1][0]
        log(f"Gravação salva: {os.path.basename(arq)} ({len(ev)} eventos, {dur/60:.1f} min)")
        return arq, len(ev), dur


def _valor_ok(tipo, valor):
    if tipo == "mv":
        return (isinstance(valor, (list, tuple)) and len(valor) == 2
                and all(isinstance(v, int) and not isinstance(v, bool) for v in valor))
    return isinstance(valor, str)


def carregar_eventos(arq):
    """Lê e valida uma gravação. Aceita lista pura ou {"eventos": [...]}. Lança ValueError se inválida."""
    with open(arq, encoding="utf-8") as f:
        dados = json.load(f)
    if isinstance(dados, dict):
        dados = dados.get("eventos")
    if not isinstance(dados, list):
        raise ValueError("formato inválido")
    eventos = []
    for item in dados:
        if (isinstance(item, (list, tuple)) and len(item) == 3
                and isinstance(item[0], (int, float)) and item[1] in TIPOS and _valor_ok(item[1], item[2])):
            eventos.append((float(item[0]), item[1], item[2]))
    eventos.sort(key=lambda e: e[0])
    return eventos


def listar_gravacoes():
    """Info de todas as gravações: dicts com arquivo, nome, duracao, eventos, ok."""
    lista = []
    for arq in sorted(glob.glob(os.path.join(PASTA_GRAV, "*.json"))):
        try:
            stat = os.stat(arq)
            assinatura = (stat.st_mtime, stat.st_size)
        except OSError:
            continue
        guardado = _cache_info.get(arq)
        if guardado and guardado[0] == assinatura:     # não relê arquivo que não mudou
            lista.append(dict(guardado[1]))
            continue
        info = {"arquivo": arq, "nome": os.path.basename(arq), "duracao": 0.0, "eventos": 0, "ok": True}
        try:
            ev = carregar_eventos(arq)
            info["eventos"] = len(ev)
            info["duracao"] = ev[-1][0] if ev else 0.0
            info["ok"] = bool(ev)
        except Exception:
            info["ok"] = False
        _cache_info[arq] = (assinatura, dict(info))
        lista.append(info)
    return lista
