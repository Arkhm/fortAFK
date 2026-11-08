"""Interface gráfica (tkinter): barra principal estilo TinyTask + gerenciadores.

Regra de ouro: a interface nunca trava. Bot, gravação e reprodução rodam em
threads e falam com a interface por filas, lidas aqui com after()."""
import ctypes
import math
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import ImageEnhance, ImageTk

import config
import registro
import tela
from bot import Bot
from entrada import EntradaGlobal
from gravacao import Gravador, listar_gravacoes
from registro import log, log_erro
from reproducao import Reprodutor
from teclas import normalizar

COR = {
    "fundo": "#1b1c20", "painel": "#25272d", "botao": "#2f3238", "hover": "#3d414a",
    "texto": "#e8e8e8", "fraco": "#9aa0a6", "verde": "#3ecf6e", "vermelho": "#e5484d",
    "vermelho_esc": "#7a2427", "amarelo": "#f5c542", "azul": "#4c9aff",
}
FONTE = "Segoe UI"
FONTE_ICONE = "Segoe UI Symbol"
ATRASO_CAPTURA = 3       # segundos para deixar a tela do jogo pronta antes do recorte

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


def _fmt_tempo(seg):
    seg = int(seg)
    return f"{seg // 3600:02d}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


# =====================================================================
#  Tooltip
# =====================================================================
class Dica:
    def __init__(self, widget, texto):
        self.widget, self.texto, self.janela, self._id = widget, texto, None, None
        widget.bind("<Enter>", self._agendar, add="+")
        widget.bind("<Leave>", self._esconder, add="+")
        widget.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _e=None):
        self._id = self.widget.after(450, self._mostrar)

    def _mostrar(self):
        if self.janela:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.janela = tw = tk.Toplevel(self.widget)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        tk.Label(tw, text=self.texto, bg="#111214", fg=COR["texto"], font=(FONTE, 9),
                 padx=6, pady=3, relief="solid", bd=1).pack()
        tw.geometry(f"+{x}+{y}")

    def _esconder(self, _e=None):
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None
        if self.janela:
            self.janela.destroy()
            self.janela = None


def _estilo_ttk(raiz):
    st = ttk.Style(raiz)
    st.theme_use("clam")
    st.configure(".", background=COR["fundo"], foreground=COR["texto"], fieldbackground=COR["painel"],
                 font=(FONTE, 9), bordercolor=COR["botao"])
    st.configure("Treeview", background=COR["painel"], foreground=COR["texto"],
                 fieldbackground=COR["painel"], rowheight=24, borderwidth=0)
    st.configure("Treeview.Heading", background=COR["botao"], foreground=COR["texto"], relief="flat")
    st.map("Treeview", background=[("selected", "#3b4a6b")])
    st.map("Treeview.Heading", background=[("active", COR["hover"])])
    st.configure("TButton", background=COR["botao"], foreground=COR["texto"], borderwidth=0,
                 focusthickness=0, padding=(10, 4))
    st.map("TButton", background=[("active", COR["hover"]), ("disabled", COR["painel"])],
           foreground=[("disabled", COR["fraco"])])
    st.configure("TCheckbutton", background=COR["fundo"], foreground=COR["texto"])
    st.map("TCheckbutton", background=[("active", COR["fundo"])])
    st.configure("TEntry", fieldbackground=COR["painel"], foreground=COR["texto"],
                 insertcolor=COR["texto"], bordercolor=COR["botao"])
    st.configure("Vertical.TScrollbar", background=COR["botao"], troughcolor=COR["fundo"],
                 arrowcolor=COR["texto"], borderwidth=0)


# =====================================================================
#  Janela principal (barra)
# =====================================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("Fortnite AFK")
        self.cfg = config.carregar()
        self.fila = queue.Queue()
        self.escala = max(1.0, self.winfo_fpixels("1i") / 96.0)   # 125% -> 1.25, 150% -> 1.5

        self.gravador = Gravador()
        self.reprodutor = Reprodutor(self.emitir)
        self.bot = Bot(self.reprodutor, self.emitir)
        self.entrada = EntradaGlobal(lambda nome: self.emitir("tecla", nome), self.gravador,
                                     self._parada_rapida)

        self.estado = "Parado"
        self.partidas = 0
        self.inicio_bot = None
        self.limite_seg = 0           # timer da execução atual (0 = sem limite)
        self.tempo_ultimo = 0.0
        self.log_aberto = False
        self.piscar = False
        self.janelas = {}             # gerenciadores abertos: nome -> Toplevel
        self._esperando_tecla = None  # callback do botão "Detectar" das configurações
        self._ocultas = []

        _estilo_ttk(self)
        self.report_callback_exception = self._erro_tk
        self._montar()
        self._posicionar()
        self.deiconify()
        self.attributes("-topmost", True)
        self.update_idletasks()
        self.aplicar_foco()

        self.entrada.iniciar()
        self.after(100, self._processar_filas)
        self.after(1000, self._tick)
        self.after(2000, self._manter_no_topo)
        log("Aplicativo aberto. F8 = gravar, F9 = parar (configurável).")
        self._atualizar_status()

    def px(self, v):
        return int(round(v * self.escala))

    def emitir(self, *evento):
        """Chamado por qualquer thread: coloca um evento na fila da interface."""
        self.fila.put(evento)

    def _erro_tk(self, exc, val, tb):
        # Erro dentro de um callback da interface: registra e segue (o app não fecha)
        log_erro("na interface", val)

    # ---------- montagem ----------
    def _montar(self):
        self.overrideredirect(True)        # sem barra de título, igual ao TinyTask
        self.configure(bg=COR["vermelho_esc"])
        borda = tk.Frame(self, bg=COR["fundo"])
        borda.pack(fill="both", expand=True, padx=1, pady=1)
        self.corpo = borda

        barra = tk.Frame(borda, bg=COR["fundo"])
        barra.pack(fill="x", padx=self.px(3), pady=(self.px(3), 0))
        self.btn = {}
        botoes = [
            ("gravar", "●", "Gravar / parar gravação ({g})", lambda: self.alternar_gravacao(via_botao=True)),
            ("iniciar", "▶", "Iniciar bot", self.iniciar_bot),
            ("parar", "■", "Parar tudo e soltar as teclas ({p})", self.parar_tudo),
            ("gravacoes", "☰", "Gravações", lambda: self.abrir("gravacoes", GerenciadorGravacoes)),
            ("imagens", "⛶", "Imagens de referência", lambda: self.abrir("imagens", GerenciadorImagens)),
            ("config", "⚙", "Configurações", lambda: self.abrir("config", JanelaConfig)),
            ("log", "▾", "Mostrar / esconder o log", self.alternar_log),
            ("fechar", "✕", "Fechar o aplicativo", self.fechar),
        ]
        cores_icone = {"gravar": COR["vermelho"], "iniciar": COR["verde"], "parar": COR["texto"],
                       "fechar": COR["fraco"]}
        self.dicas = {}
        for chave, icone, dica, cmd in botoes:
            b = tk.Button(barra, text=icone, command=cmd, font=(FONTE_ICONE, 12), width=3,
                          bg=COR["botao"], fg=cores_icone.get(chave, COR["azul"]),
                          activebackground=COR["hover"], activeforeground=COR["texto"],
                          relief="flat", bd=0, cursor="hand2", takefocus=0)
            b.pack(side="left", padx=self.px(1), ipady=self.px(1))
            b.bind("<Enter>", lambda e, k=chave: self._hover(k), add="+")
            b.bind("<Leave>", lambda e, w=b, k=chave: self._cor_botao(k), add="+")
            self.btn[chave] = b
            self.dicas[chave] = (Dica(b, ""), dica)
        self._atualizar_dicas()

        self.lbl_status = tk.Label(borda, text="", bg=COR["fundo"], fg=COR["fraco"], font=(FONTE, 8),
                                   anchor="w", cursor="fleur")
        self.lbl_status.pack(fill="x", padx=self.px(5), pady=(self.px(2), self.px(3)))

        # Painel de log (recolhido no início)
        self.frame_log = tk.Frame(borda, bg=COR["fundo"])
        self.txt_log = tk.Text(self.frame_log, height=10, width=10, bg="#121316", fg="#c9ccd1",
                               font=("Consolas", 8), relief="flat", bd=0, wrap="word",
                               state="disabled", padx=4, pady=4)
        sb = ttk.Scrollbar(self.frame_log, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

        # Arrastar a janela pela linha de status ou pelas bordas
        for w in (borda, barra, self.lbl_status):
            w.bind("<ButtonPress-1>", self._arrastar_inicio)
            w.bind("<B1-Motion>", self._arrastar)
            w.bind("<ButtonRelease-1>", self._arrastar_fim)

    def _atualizar_dicas(self):
        for chave, (dica, texto) in self.dicas.items():
            dica.texto = texto.format(g=self.cfg["tecla_gravar"].upper(), p=self.cfg["tecla_parar"].upper())

    def _hover(self, chave):
        if not (chave == "gravar" and self.gravador.ativo):   # o piscar do gravar tem prioridade
            self.btn[chave].configure(bg=COR["hover"])

    def _cor_botao(self, chave):
        b = self.btn[chave]
        if chave == "gravar" and self.gravador.ativo:
            b.configure(bg=COR["vermelho"] if self.piscar else COR["vermelho_esc"])
        else:
            b.configure(bg=COR["botao"])

    def _posicionar(self):
        pos = self.cfg.get("posicao_janela")
        self.update_idletasks()
        if isinstance(pos, list) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
            # Se a posição salva caiu fora da tela (monitor desligado), volta para o topo
            if not (-50 < x < self.winfo_screenwidth() - 50 and -10 < y < self.winfo_screenheight() - 30):
                x, y = self.winfo_screenwidth() // 2 - self.px(160), 10
        else:
            x, y = self.winfo_screenwidth() // 2 - self.px(160), 10
        self.geometry(f"+{x}+{y}")

    def _arrastar_inicio(self, e):
        self._arr = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _arrastar(self, e):
        if getattr(self, "_arr", None):
            self.geometry(f"+{e.x_root - self._arr[0]}+{e.y_root - self._arr[1]}")

    def _arrastar_fim(self, _e):
        self._arr = None
        self.cfg["posicao_janela"] = [self.winfo_x(), self.winfo_y()]
        config.salvar(self.cfg)

    # ---------- foco / topo ----------
    def _hwnd(self, janela):
        try:
            return int(janela.wm_frame(), 16)
        except Exception:
            return ctypes.windll.user32.GetParent(janela.winfo_id())

    def aplicar_foco(self):
        """WS_EX_NOACTIVATE: clicar na barra não tira o foco do jogo (as teclas
        continuam indo para o Fortnite). Pode ser desligado nas configurações."""
        try:
            hwnd = self._hwnd(self)
            estilo = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self.cfg.get("nao_roubar_foco", True):
                estilo |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            else:
                estilo &= ~WS_EX_NOACTIVATE
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo)
        except Exception as e:
            log_erro("ao configurar o foco da janela", e)

    def _manter_no_topo(self):
        # Alguns jogos em Windowed Fullscreen "empurram" janelas: reafirma o topo
        try:
            if self.state() != "withdrawn":
                self.attributes("-topmost", True)
                self.lift()
            for jan in self.janelas.values():
                if jan.winfo_exists() and jan.state() != "withdrawn":
                    jan.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.after(2000, self._manter_no_topo)

    # ---------- filas e status ----------
    def _processar_filas(self):
        try:
            for _ in range(200):
                linha = registro.fila.get_nowait()
                self._add_log(linha)
        except queue.Empty:
            pass
        try:
            while True:
                self._tratar(self.fila.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._processar_filas)

    def _tratar(self, ev):
        tipo = ev[0]
        try:
            if tipo == "estado":
                self.estado = ev[1]
            elif tipo == "partidas":
                self.partidas = ev[1]
            elif tipo == "aviso":
                messagebox.showwarning(ev[1], ev[2], parent=self)
            elif tipo == "bot_parado":
                self._bot_terminou(ev[1])
            elif tipo == "replay_fim":
                if not self.bot.rodando and not self.gravador.ativo:
                    self.estado = "Parado"
            elif tipo == "tecla":
                self._tecla_global(ev[1])
            elif tipo == "resultado":
                ev[1](ev[2])
            self._atualizar_status()
        except Exception as e:
            log_erro(f"ao tratar evento {tipo}", e)

    def _add_log(self, linha):
        t = self.txt_log
        t.configure(state="normal")
        t.insert("end", linha + "\n")
        linhas = int(t.index("end-1c").split(".")[0])
        if linhas > 600:
            t.delete("1.0", f"{linhas - 500}.0")
        t.see("end")
        t.configure(state="disabled")

    def _tick(self):
        if self.gravador.ativo:
            self.piscar = not self.piscar
            self._cor_botao("gravar")
        self._atualizar_status()
        self.after(500, self._tick)

    def _tempo_rodando(self):
        if self.inicio_bot is not None:
            return time.monotonic() - self.inicio_bot
        return self.tempo_ultimo

    def _atualizar_status(self):
        cor = {"Parado": COR["fraco"], "Gravando": COR["vermelho"], "MODO ERRADO": COR["vermelho"]}
        estado = self.estado
        c = cor.get(estado.split(" ·")[0], COR["verde"] if self.bot.rodando else COR["amarelo"])
        if estado.startswith("MODO ERRADO"):
            c = COR["vermelho"]
        tempo = _fmt_tempo(self._tempo_rodando())
        if self.inicio_bot is not None and self.limite_seg:
            # timer ligado: mostra quanto falta para parar sozinho
            tempo = f"falta {_fmt_tempo(max(0, self.limite_seg - self._tempo_rodando()))}"
        self.lbl_status.configure(
            text=f"● {estado}   |   Partidas: {self.partidas}   |   {tempo}", fg=c)

    def alternar_log(self):
        self.log_aberto = not self.log_aberto
        if self.log_aberto:
            self.frame_log.pack(fill="both", expand=True, padx=self.px(3), pady=(0, self.px(3)))
            self.btn["log"].configure(text="▴")
        else:
            self.frame_log.pack_forget()
            self.btn["log"].configure(text="▾")

    # ---------- atalhos globais ----------
    def _parada_rapida(self, nome):
        """Roda na thread do hook de teclado: só sinaliza (sem tkinter, sem esperas)."""
        if nome == self.cfg["tecla_parar"]:
            self.bot.sinalizar_parada()

    def _tecla_global(self, nome):
        # Com algo rodando, o atalho de parar sempre vale (mesmo durante o "Detectar")
        if nome == self.cfg["tecla_parar"] and (self.bot.rodando or self.reprodutor.rodando):
            self._esperando_tecla = None
            self.parar_tudo()
            return
        if self._esperando_tecla:
            cb, self._esperando_tecla = self._esperando_tecla, None
            cb(nome)
            return
        if nome == self.cfg["tecla_gravar"]:
            self.alternar_gravacao()
        elif nome == self.cfg["tecla_parar"]:
            self.parar_tudo()

    def detectar_tecla(self, callback):
        self._esperando_tecla = callback

    # ---------- ações ----------
    def ignoradas(self):
        return {normalizar(t) for t in self.cfg["teclas_ignoradas"]} | {
            self.cfg["tecla_gravar"], self.cfg["tecla_parar"]}

    def alternar_gravacao(self, via_botao=False):
        if self.gravador.ativo:
            res = None
            try:
                res = self.gravador.parar(descartar_clique_final=via_botao)
            except Exception as e:
                log_erro("ao salvar a gravação", e)
            self.estado = "Parado"
            self._cor_botao("gravar")
            if res:
                self._recarregar("gravacoes")
            return
        if self.bot.rodando or self.reprodutor.rodando:
            log("Pare o bot / o teste antes de gravar.")
            return
        self.gravador.iniciar(self.ignoradas())
        self.estado = "Gravando"
        log(f"Gravando... ({self.cfg['tecla_gravar'].upper()} para parar)")

    def iniciar_bot(self):
        if self.bot.rodando:
            return
        if self.gravador.ativo:
            messagebox.showwarning("Gravando", "Pare a gravação antes de iniciar o bot.", parent=self)
            return
        faltando = [n for n in ("play.png", "lobby.png") if not tela.existe(n)]
        if self.cfg["verificar_modo"]:
            faltando += [n for n in ("br.png", "mode.png") if not tela.existe(n)]
        desativadas = set(self.cfg["gravacoes_desativadas"])
        ativas = [g["arquivo"] for g in listar_gravacoes() if g["ok"] and g["nome"] not in desativadas]
        problemas = []
        if faltando:
            problemas.append("Faltam imagens em imagens\\:\n   " + ", ".join(faltando) +
                             "\n   (capture pelo botão ⛶ Imagens)")
        if not ativas:
            problemas.append("Nenhuma gravação ativa em gravacoes\\.\n   (grave com ● / "
                             f"{self.cfg['tecla_gravar'].upper()} ou ative uma no ☰ Gravações)")
        if problemas:
            messagebox.showwarning("Não dá para iniciar", "\n\n".join(problemas), parent=self)
            return
        self.reprodutor.parar()
        self.partidas = 0
        self.inicio_bot = time.monotonic()
        self.limite_seg = self.cfg["max_minutos"] * 60
        if self.limite_seg:
            log(f"Timer ligado: o bot para sozinho depois de {self.cfg['max_minutos']} min")
        self.estado = "Iniciando"
        self.bot.iniciar(self.cfg, ativas)
        self._atualizar_status()

    def _bot_terminou(self, motivo):
        if self.inicio_bot is not None:
            self.tempo_ultimo = time.monotonic() - self.inicio_bot
        self.inicio_bot = None
        self.estado = {"modo_errado": "MODO ERRADO (parado)", "erro": "Parado (erro - veja o log)",
                       "limite": "Parado (limite de partidas)",
                       "tempo": "Parado (timer)"}.get(motivo, "Parado")

    def parar_tudo(self):
        if self.gravador.ativo:
            self.alternar_gravacao()
        self.bot.parar()
        self.reprodutor.parar()
        if not self.bot.rodando:
            self.estado = "Parado"
        log("Parado - teclas e botões soltos")

    def testar_gravacao(self, arquivo):
        if self.bot.rodando or self.gravador.ativo:
            messagebox.showwarning("Ocupado", "Pare o bot / a gravação antes de testar.",
                                   parent=self.janelas.get("gravacoes") or self)
            return
        try:
            self.reprodutor.reproduzir_uma(arquivo, contagem=3)
            log(f"Teste em 3s: {os.path.basename(arquivo)} - clique no jogo! ({self.cfg['tecla_parar'].upper()} para parar)")
        except Exception as e:
            log_erro("ao testar a gravação", e)

    # ---------- janelas auxiliares ----------
    def abrir(self, nome, classe):
        jan = self.janelas.get(nome)
        if jan is not None and jan.winfo_exists():
            jan.deiconify()
            jan.lift()
            jan.focus_force()
            return
        self.janelas[nome] = classe(self)

    def _recarregar(self, nome):
        jan = self.janelas.get(nome)
        if jan is not None and jan.winfo_exists() and hasattr(jan, "recarregar"):
            jan.recarregar()

    def ocultar_tudo(self):
        self._ocultas = [self] + [j for j in self.janelas.values() if j.winfo_exists() and j.state() != "withdrawn"]
        for j in self._ocultas:
            j.withdraw()

    def mostrar_tudo(self):
        for j in self._ocultas:
            try:
                j.deiconify()
                j.attributes("-topmost", True)
            except tk.TclError:
                pass
        self._ocultas = []
        self.update_idletasks()
        self.aplicar_foco()

    def em_thread(self, funcao, ao_terminar):
        """Roda funcao() fora da interface; ao_terminar((ok, valor)) volta na thread da interface."""
        def alvo():
            try:
                r = (True, funcao())
            except Exception as e:
                r = (False, e)
            self.emitir("resultado", ao_terminar, r)
        threading.Thread(target=alvo, daemon=True).start()

    def capturar(self, nome, ao_terminar):
        """Esconde o app, espera ATRASO_CAPTURA s, tira um print e abre o recorte."""
        if self.bot.rodando:
            messagebox.showwarning("Bot rodando", "Pare o bot antes de capturar.", parent=self.janelas.get("imagens"))
            return
        log(f"Capturando {nome} em {ATRASO_CAPTURA}s - deixe a tela do jogo pronta")
        self.ocultar_tudo()

        def tirar_print():
            try:
                img = tela.capturar_tela()
            except Exception as e:
                self.mostrar_tudo()
                log_erro("ao capturar a tela", e)
                return
            Recorte(self, img, nome, ao_terminar)
        self.after(ATRASO_CAPTURA * 1000, tirar_print)

    def fechar(self):
        try:
            self.bot.parar()
            self.reprodutor.parar()
            if self.gravador.ativo:
                self.gravador.parar()
            self.entrada.parar()
            config.salvar(self.cfg)
            log("Aplicativo fechado")
        finally:
            self.destroy()


# =====================================================================
#  Recorte de tela (como a Ferramenta de Captura)
# =====================================================================
class Recorte(tk.Toplevel):
    def __init__(self, app, imagem, nome, ao_terminar):
        super().__init__(app)
        self.app, self.img, self.nome, self.ao_terminar = app, imagem, nome, ao_terminar
        w, h = imagem.size
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{w}x{h}+0+0")
        self.configure(cursor="crosshair")
        self.foto_escura = ImageTk.PhotoImage(ImageEnhance.Brightness(imagem).enhance(0.4))
        self.cv = tk.Canvas(self, width=w, height=h, highlightthickness=0, bd=0)
        self.cv.pack()
        self.cv.create_image(0, 0, image=self.foto_escura, anchor="nw")
        self.cv.create_text(w // 2, 40, fill="white", font=(FONTE, 14, "bold"),
                            text=f"Arraste um retângulo em volta de: {nome}    (Esc ou botão direito = cancelar)")
        self.ini = None
        self.ret = None
        self.claro = None
        self.foto_clara = None
        self.cv.bind("<ButtonPress-1>", self._ini)
        self.cv.bind("<B1-Motion>", self._mov)
        self.cv.bind("<ButtonRelease-1>", self._fim)
        self.bind("<Escape>", lambda e: self._sair(None))
        self.cv.bind("<ButtonPress-3>", lambda e: self._sair(None))
        self.after(50, self.focus_force)

    def _caixa(self, e):
        x0, y0 = self.ini
        return min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)

    def _ini(self, e):
        self.ini = (e.x, e.y)

    def _mov(self, e):
        if not self.ini:
            return
        x0, y0, x1, y1 = self._caixa(e)
        if self.ret:
            self.cv.delete(self.ret)
        if self.claro:
            self.cv.delete(self.claro)
        if x1 - x0 > 1 and y1 - y0 > 1:
            # mostra a área selecionada com o brilho normal
            self.foto_clara = ImageTk.PhotoImage(self.img.crop((x0, y0, x1, y1)))
            self.claro = self.cv.create_image(x0, y0, image=self.foto_clara, anchor="nw")
        self.ret = self.cv.create_rectangle(x0, y0, x1, y1, outline=COR["amarelo"], width=2)

    def _fim(self, e):
        if not self.ini:
            return
        x0, y0, x1, y1 = self._caixa(e)
        if x1 - x0 < 5 or y1 - y0 < 5:
            self.ini = None
            return
        self._sair(self.img.crop((x0, y0, x1, y1)))

    def _sair(self, recorte):
        self.destroy()
        self.app.mostrar_tudo()
        if recorte is None:
            log("Captura cancelada")
            return
        try:
            config.garantir_pastas()
            recorte.save(tela.caminho(self.nome))
            log(f"Imagem salva: {self.nome} ({recorte.size[0]}x{recorte.size[1]})")
        except Exception as e:
            log_erro(f"ao salvar {self.nome}", e)
        if self.ao_terminar:
            self.ao_terminar()


# =====================================================================
#  Base das janelas auxiliares
# =====================================================================
class JanelaBase(tk.Toplevel):
    def __init__(self, app, titulo, tamanho):
        super().__init__(app)
        self.app = app
        self.title(titulo)
        self.configure(bg=COR["fundo"])
        self.attributes("-topmost", True)
        w, h = tamanho
        app.update_idletasks()          # altura atual da barra (com ou sem log)
        x = min(app.winfo_x(), self.winfo_screenwidth() - app.px(w) - 20)
        y = app.winfo_y() + app.winfo_height() + 8
        self.geometry(f"{app.px(w)}x{app.px(h)}+{max(0, x)}+{y}")
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def botao(self, pai, texto, cmd, **kw):
        b = ttk.Button(pai, text=texto, command=cmd, **kw)
        return b


# =====================================================================
#  Gerenciador de gravações
# =====================================================================
class GerenciadorGravacoes(JanelaBase):
    def __init__(self, app):
        super().__init__(app, "Gravações", (520, 340))
        topo = tk.Frame(self, bg=COR["fundo"])
        topo.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ("ativo", "nome", "duracao", "eventos")
        self.tv = ttk.Treeview(topo, columns=cols, show="headings", selectmode="browse")
        for c, t, w, a in (("ativo", "Ativa", 50, "center"), ("nome", "Nome", 250, "w"),
                           ("duracao", "Duração", 80, "center"), ("eventos", "Eventos", 70, "center")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=app.px(w), anchor=a, stretch=(c == "nome"))
        sb = ttk.Scrollbar(topo, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<Button-1>", self._clique)
        self.tv.bind("<space>", lambda e: self._alternar(self.tv.focus()))
        self.tv.bind("<Double-1>", lambda e: self.renomear())

        rodape = tk.Frame(self, bg=COR["fundo"])
        rodape.pack(fill="x", padx=8, pady=(0, 8))
        for texto, cmd in (("Renomear", self.renomear), ("Excluir", self.excluir), ("Testar (3s)", self.testar),
                           ("Abrir pasta", lambda: os.startfile(config.PASTA_GRAV)),
                           ("Atualizar", self.recarregar)):
            self.botao(rodape, texto, cmd).pack(side="left", padx=(0, 6))
        tk.Label(self, text="Clique na coluna \"Ativa\" para ligar/desligar. O bot só sorteia entre as ativas.",
                 bg=COR["fundo"], fg=COR["fraco"], font=(FONTE, 8)).pack(anchor="w", padx=8, pady=(0, 6))
        self.recarregar()

    def recarregar(self):
        sel = self.tv.focus()
        self.tv.delete(*self.tv.get_children())
        desativadas = set(self.app.cfg["gravacoes_desativadas"])
        for g in listar_gravacoes():
            ativo = "☐" if g["nome"] in desativadas else "☑"
            dur = f"{int(g['duracao']) // 60}:{int(g['duracao']) % 60:02d}" if g["ok"] else "inválida"
            self.tv.insert("", "end", iid=g["nome"], values=(ativo, g["nome"], dur, g["eventos"]))
        if sel and self.tv.exists(sel):
            self.tv.focus(sel)
            self.tv.selection_set(sel)

    def _clique(self, e):
        if self.tv.identify_region(e.x, e.y) == "cell" and self.tv.identify_column(e.x) == "#1":
            self._alternar(self.tv.identify_row(e.y))

    def _alternar(self, nome):
        if not nome:
            return
        des = self.app.cfg["gravacoes_desativadas"]
        if nome in des:
            des.remove(nome)
        else:
            des.append(nome)
        config.salvar(self.app.cfg)
        self.recarregar()

    def _selecionada(self):
        nome = self.tv.focus()
        if not nome:
            messagebox.showinfo("Gravações", "Selecione uma gravação na lista.", parent=self)
            return None
        return nome

    def renomear(self):
        nome = self._selecionada()
        if not nome:
            return
        novo = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=nome[:-5], parent=self)
        if not novo:
            return
        novo = novo.strip()
        if any(c in novo for c in '\\/:*?"<>|') or not novo:
            messagebox.showerror("Renomear", "Nome inválido.", parent=self)
            return
        if not novo.lower().endswith(".json"):
            novo += ".json"
        destino = os.path.join(config.PASTA_GRAV, novo)
        if os.path.exists(destino):
            messagebox.showerror("Renomear", "Já existe uma gravação com esse nome.", parent=self)
            return
        try:
            os.rename(os.path.join(config.PASTA_GRAV, nome), destino)
        except OSError as e:
            messagebox.showerror("Renomear", str(e), parent=self)
            return
        des = self.app.cfg["gravacoes_desativadas"]
        if nome in des:
            des[des.index(nome)] = novo
            config.salvar(self.app.cfg)
        log(f"Gravação renomeada: {nome} -> {novo}")
        self.recarregar()

    def excluir(self):
        nome = self._selecionada()
        if not nome or not messagebox.askyesno("Excluir", f"Excluir {nome}?", parent=self):
            return
        try:
            os.remove(os.path.join(config.PASTA_GRAV, nome))
        except OSError as e:
            messagebox.showerror("Excluir", str(e), parent=self)
            return
        des = self.app.cfg["gravacoes_desativadas"]
        if nome in des:
            des.remove(nome)
            config.salvar(self.app.cfg)
        log(f"Gravação excluída: {nome}")
        self.recarregar()

    def testar(self):
        nome = self._selecionada()
        if nome:
            self.app.testar_gravacao(os.path.join(config.PASTA_GRAV, nome))


# =====================================================================
#  Gerenciador de imagens
# =====================================================================
class GerenciadorImagens(JanelaBase):
    def __init__(self, app):
        super().__init__(app, "Imagens de referência", (640, 520))
        self.fotos = []
        externo = tk.Frame(self, bg=COR["fundo"])
        externo.pack(fill="both", expand=True, padx=8, pady=8)
        self.cv = tk.Canvas(externo, bg=COR["fundo"], highlightthickness=0)
        sb = ttk.Scrollbar(externo, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.lista = tk.Frame(self.cv, bg=COR["fundo"])
        self._win = self.cv.create_window(0, 0, window=self.lista, anchor="nw")
        self.lista.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width))
        self.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(int(-e.delta / 120), "units"))

        rodape = tk.Frame(self, bg=COR["fundo"])
        rodape.pack(fill="x", padx=8, pady=(0, 8))
        self.botao(rodape, "+ Marcador de fim", self.novo_fim).pack(side="left", padx=(0, 6))
        self.botao(rodape, "Abrir pasta", lambda: os.startfile(config.PASTA_IMG)).pack(side="left", padx=(0, 6))
        self.botao(rodape, "Atualizar", self.recarregar).pack(side="left")
        tk.Label(self, text=f"Capturar: o app some, você tem {ATRASO_CAPTURA}s para deixar a tela do jogo pronta, "
                            "depois arraste o retângulo.", bg=COR["fundo"], fg=COR["fraco"],
                 font=(FONTE, 8)).pack(anchor="w", padx=8, pady=(0, 6))
        self.recarregar()

    def _itens(self):
        itens = list(config.IMAGENS_FIXAS)
        for nome in tela.listar_fim():
            itens.append((nome, "Marcador de squad eliminado", "opcional"))
        if not tela.listar_fim():
            itens.append(("fim_1.png", "Marcador de squad eliminado (sem ele, usa o RETURN TO LOBBY)", "opcional"))
        return itens

    def recarregar(self):
        for w in self.lista.winfo_children():
            w.destroy()
        self.fotos = []
        for nome, desc, quando in self._itens():
            self._linha(nome, desc, quando)

    def _linha(self, nome, desc, quando):
        app = self.app
        existe = tela.existe(nome)
        linha = tk.Frame(self.lista, bg=COR["painel"])
        linha.pack(fill="x", pady=3)
        ponto = tk.Canvas(linha, width=14, height=14, bg=COR["painel"], highlightthickness=0)
        ponto.create_oval(2, 2, 12, 12, fill=COR["verde"] if existe else COR["vermelho"], outline="")
        ponto.pack(side="left", padx=(8, 6))

        mini = tk.Label(linha, bg="#121316", width=app.px(120), height=app.px(44))
        if existe:
            try:
                img = tela.carregar(nome).copy()
                img.thumbnail((app.px(120), app.px(44)))
                foto = ImageTk.PhotoImage(img)
                self.fotos.append(foto)
                mini.configure(image=foto, width=app.px(120), height=app.px(44))
            except Exception:
                pass
        else:
            mini.configure(image="", text="(falta)", fg=COR["fraco"], width=12, height=2)
        mini.pack(side="left", padx=4, pady=4)

        textos = tk.Frame(linha, bg=COR["painel"])
        textos.pack(side="left", fill="x", expand=True, padx=6)
        tk.Label(textos, text=nome, bg=COR["painel"], fg=COR["texto"], font=(FONTE, 10, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(textos, text=f"{desc} · {quando}", bg=COR["painel"], fg=COR["fraco"], font=(FONTE, 8),
                 anchor="w", wraplength=app.px(260), justify="left").pack(fill="x")
        resultado = tk.Label(textos, text="", bg=COR["painel"], fg=COR["fraco"], font=(FONTE, 8), anchor="w")
        resultado.pack(fill="x")

        botoes = tk.Frame(linha, bg=COR["painel"])
        botoes.pack(side="right", padx=6)
        self.botao(botoes, "Capturar", lambda: app.capturar(nome, self.recarregar)).pack(side="left", padx=2)
        teste = self.botao(botoes, "Testar", lambda: self.testar(nome, resultado))
        teste.pack(side="left", padx=2)
        if not existe:
            teste.state(["disabled"])
        if nome.startswith("fim") and existe:
            self.botao(botoes, "Excluir", lambda: self.excluir(nome)).pack(side="left", padx=2)

    def testar(self, nome, rotulo):
        """Esconde o app, procura a imagem na tela agora e mostra a confiança."""
        app = self.app
        conf_min = float(app.cfg["confianca"])
        rotulo.configure(text="Procurando...", fg=COR["amarelo"])
        app.ocultar_tudo()

        def terminou(r):
            app.mostrar_tudo()
            if not rotulo.winfo_exists():
                return
            ok, valor = r
            if not ok:
                rotulo.configure(text=f"Erro: {valor}", fg=COR["vermelho"])
                return
            conf, pos = valor
            if conf >= conf_min:
                rotulo.configure(text=f"Encontrada (confiança {conf:.2f}) em {pos}", fg=COR["verde"])
                log(f"Teste {nome}: encontrada (confiança {conf:.2f}) em {pos}")
            else:
                rotulo.configure(text=f"Não encontrada (melhor: {conf:.2f}, mínimo {conf_min:.2f})", fg=COR["vermelho"])
                log(f"Teste {nome}: não encontrada (melhor {conf:.2f})")
        # pequena espera para as janelas sumirem antes do print
        app.after(400, lambda: app.em_thread(lambda: tela.testar(nome), terminou))

    def novo_fim(self):
        self.app.capturar(tela.proximo_fim(), self.recarregar)

    def excluir(self, nome):
        if messagebox.askyesno("Excluir", f"Excluir {nome}?", parent=self):
            try:
                os.remove(tela.caminho(nome))
                log(f"Imagem excluída: {nome}")
            except OSError as e:
                messagebox.showerror("Excluir", str(e), parent=self)
            self.recarregar()


# =====================================================================
#  Configurações
# =====================================================================
class JanelaConfig(JanelaBase):
    CAMPOS = [
        # chave, rótulo, tipo
        ("check_min", "Verificação na partida - mínimo (s)", float),
        ("check_max", "Verificação na partida - máximo (s)", float),
        ("lobby_min", "Espera no lobby antes do PLAY - mínimo (s)", float),
        ("lobby_max", "Espera no lobby antes do PLAY - máximo (s)", float),
        ("poll_lobby", "Intervalo procurando o PLAY (s)", float),
        ("espera_onibus_max", "Tempo máximo esperando o ônibus (s)", float),
        ("intervalo_espectador", "Checagem de \"SPECTATING\" na partida (s)", float),
        ("confianca", "Confiança do reconhecimento (0.5 a 1.0)", float),
        ("max_partidas", "Parar depois de X partidas (0 = infinito)", int),
        ("max_minutos", "Timer: parar depois de X minutos (0 = sem limite)", int),
    ]

    def __init__(self, app):
        super().__init__(app, "Configurações", (500, 590))
        self.vars = {}
        f = tk.Frame(self, bg=COR["fundo"])
        f.pack(fill="both", expand=True, padx=12, pady=10)
        f.columnconfigure(0, weight=1)
        lin = 0
        for chave, rotulo, _tipo in self.CAMPOS:
            tk.Label(f, text=rotulo, bg=COR["fundo"], fg=COR["texto"], anchor="w").grid(row=lin, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=self._fmt(app.cfg[chave]))
            ttk.Entry(f, textvariable=v, width=10).grid(row=lin, column=1, columnspan=2, sticky="e", pady=3)
            self.vars[chave] = v
            lin += 1

        for chave, rotulo in (("tecla_gravar", "Atalho gravar / parar gravação"), ("tecla_parar", "Atalho parar o bot")):
            tk.Label(f, text=rotulo, bg=COR["fundo"], fg=COR["texto"], anchor="w").grid(row=lin, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=app.cfg[chave])
            ttk.Entry(f, textvariable=v, width=10).grid(row=lin, column=1, sticky="e", pady=3)
            ttk.Button(f, text="Detectar", command=lambda v=v: self._detectar(v)).grid(row=lin, column=2, padx=(4, 0))
            self.vars[chave] = v
            lin += 1

        tk.Label(f, text="Teclas ignoradas (separadas por vírgula)", bg=COR["fundo"], fg=COR["texto"],
                 anchor="w").grid(row=lin, column=0, columnspan=3, sticky="w", pady=(8, 2))
        lin += 1
        self.vars["teclas_ignoradas"] = tk.StringVar(value=", ".join(app.cfg["teclas_ignoradas"]))
        ttk.Entry(f, textvariable=self.vars["teclas_ignoradas"]).grid(row=lin, column=0, columnspan=3, sticky="ew")
        lin += 1

        self.var_modo = tk.BooleanVar(value=bool(app.cfg["verificar_modo"]))
        ttk.Checkbutton(f, text="Verificar modo (BATTLE ROYALE + Zero Build Squad Fill) antes do PLAY",
                        variable=self.var_modo).grid(row=lin, column=0, columnspan=3, sticky="w", pady=(10, 2))
        lin += 1
        self.var_terminar = tk.BooleanVar(value=bool(app.cfg["tempo_terminar_partida"]))
        ttk.Checkbutton(f, text="Ao fim do timer: terminar a partida e parar no lobby (senão, para na hora)",
                        variable=self.var_terminar).grid(row=lin, column=0, columnspan=3, sticky="w", pady=2)
        lin += 1
        self.var_foco = tk.BooleanVar(value=bool(app.cfg["nao_roubar_foco"]))
        ttk.Checkbutton(f, text="Barra não rouba o foco do jogo ao ser clicada",
                        variable=self.var_foco).grid(row=lin, column=0, columnspan=3, sticky="w", pady=2)
        lin += 1
        self.lbl_info = tk.Label(f, text="Mudanças valem no próximo \"Iniciar bot\".", bg=COR["fundo"],
                                 fg=COR["fraco"], font=(FONTE, 8), anchor="w")
        self.lbl_info.grid(row=lin, column=0, columnspan=3, sticky="w", pady=(8, 0))
        lin += 1

        rodape = tk.Frame(self, bg=COR["fundo"])
        rodape.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Button(rodape, text="Salvar", command=self.salvar).pack(side="right")
        self.bind("<Destroy>", self._ao_fechar, add="+")
        ttk.Button(rodape, text="Restaurar padrão", command=self.padrao).pack(side="left")

    @staticmethod
    def _fmt(v):
        return str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v)

    def _ao_fechar(self, e):
        if e.widget is self:
            self.app._esperando_tecla = None    # cancela um "Detectar" pendente

    def _detectar(self, var):
        var.set("aperte uma tecla...")
        self.app.detectar_tecla(lambda nome: var.set(nome) if self.winfo_exists() else None)

    def padrao(self):
        for chave, _r, _t in self.CAMPOS:
            self.vars[chave].set(self._fmt(config.PADRAO[chave]))
        self.vars["tecla_gravar"].set(config.PADRAO["tecla_gravar"])
        self.vars["tecla_parar"].set(config.PADRAO["tecla_parar"])
        self.vars["teclas_ignoradas"].set(", ".join(config.PADRAO["teclas_ignoradas"]))
        self.var_modo.set(config.PADRAO["verificar_modo"])
        self.var_terminar.set(config.PADRAO["tempo_terminar_partida"])
        self.var_foco.set(config.PADRAO["nao_roubar_foco"])

    def salvar(self):
        cfg = self.app.cfg
        novo = {}
        try:
            for chave, rotulo, tipo in self.CAMPOS:
                texto = self.vars[chave].get().strip().replace(",", ".")
                if not math.isfinite(float(texto)):
                    raise ValueError(f"\"{rotulo}\" precisa ser um número")
                valor = tipo(float(texto)) if tipo is int else tipo(texto)
                if valor < 0:
                    raise ValueError(f"\"{rotulo}\" não pode ser negativo")
                novo[chave] = valor
        except ValueError as e:
            messagebox.showerror("Configurações", f"Valor inválido: {e}", parent=self)
            return
        erros = []
        if novo["check_min"] <= 0 or novo["check_min"] > novo["check_max"]:
            erros.append("Verificação: o mínimo deve ser > 0 e ≤ máximo.")
        if novo["lobby_min"] > novo["lobby_max"]:
            erros.append("Espera no lobby: o mínimo deve ser ≤ máximo.")
        if novo["intervalo_espectador"] < 1:
            erros.append("Checagem de SPECTATING deve ser de pelo menos 1 s.")
        if novo["espera_onibus_max"] < 30:
            erros.append("Tempo máximo esperando o ônibus deve ser de pelo menos 30 s.")
        if novo["poll_lobby"] <= 0:
            erros.append("Intervalo procurando o PLAY deve ser > 0.")
        if not 0.5 <= novo["confianca"] <= 1.0:
            erros.append("Confiança deve ficar entre 0.5 e 1.0.")
        gravar = normalizar(self.vars["tecla_gravar"].get())
        parar = normalizar(self.vars["tecla_parar"].get())
        if not gravar or not parar or " " in gravar or " " in parar:
            erros.append("Defina as duas teclas de atalho (ex: f8, f9).")
        elif gravar == parar:
            erros.append("As teclas de gravar e parar precisam ser diferentes.")
        if erros:
            messagebox.showerror("Configurações", "\n".join(erros), parent=self)
            return

        ignoradas = [normalizar(t) for t in self.vars["teclas_ignoradas"].get().split(",") if t.strip()]
        # Atalho antigo sai da lista; os atalhos atuais sempre entram
        for antiga, nova in ((cfg["tecla_gravar"], gravar), (cfg["tecla_parar"], parar)):
            if antiga != nova and antiga in ignoradas:
                ignoradas.remove(antiga)
        for t in (gravar, parar):
            if t not in ignoradas:
                ignoradas.append(t)

        cfg.update(novo)
        cfg["tecla_gravar"], cfg["tecla_parar"] = gravar, parar
        cfg["teclas_ignoradas"] = ignoradas
        cfg["verificar_modo"] = bool(self.var_modo.get())
        cfg["tempo_terminar_partida"] = bool(self.var_terminar.get())
        cfg["nao_roubar_foco"] = bool(self.var_foco.get())
        config.salvar(cfg)
        self.vars["teclas_ignoradas"].set(", ".join(ignoradas))
        self.app.aplicar_foco()
        self.app._atualizar_dicas()
        log("Configurações salvas")
        self.lbl_info.configure(text="Salvo! Mudanças valem no próximo \"Iniciar bot\".", fg=COR["verde"])
