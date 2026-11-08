"""Captura o movimento real do mouse (câmera) usando a Raw Input API do Windows.

O Fortnite gira a câmera com o deslocamento bruto do mouse, que os hooks comuns
não enxergam direito. Aqui uma janela invisível recebe os mesmos dados (WM_INPUT),
mesmo sem foco, e soma os deslocamentos em pacotes de alguns milissegundos.
"""
import ctypes
import threading
import time
from ctypes import wintypes

from registro import log, log_erro

# Instância própria: não mexe nas assinaturas usadas por pynput/pyautogui
user32 = ctypes.WinDLL("user32", use_last_error=True)

HWND_MESSAGE = wintypes.HWND(-3)
RIDEV_REMOVE = 0x00000001
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
WM_INPUT = 0x00FF
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
MOUSE_MOVE_ABSOLUTE = 0x0001
ERRO_LEITURA = 0xFFFFFFFF
INTERVALO_PACOTE = 0.008       # junta os movimentos em pacotes de 8 ms


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [("usFlags", wintypes.USHORT), ("ulButtons", wintypes.ULONG),
                ("ulRawButtons", wintypes.ULONG), ("lLastX", wintypes.LONG),
                ("lLastY", wintypes.LONG), ("ulExtraInformation", wintypes.ULONG)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("mouse", RAWMOUSE)]


user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.GetRawInputData.restype = wintypes.UINT
user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID,
                                   ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD
user32.MsgWaitForMultipleObjects.argtypes = [wintypes.DWORD, wintypes.LPVOID, wintypes.BOOL,
                                             wintypes.DWORD, wintypes.DWORD]


class CapturaCamera:
    """Roda em thread própria. ao_mover(tempo_perf_counter, dx, dy) recebe cada pacote."""

    def __init__(self, ao_mover):
        self.ao_mover = ao_mover
        self._rodando = False
        self._thread = None
        self._buffer = ctypes.create_string_buffer(ctypes.sizeof(RAWINPUT) + 16)
        self._dx = self._dy = 0
        self._t_primeiro = self._t_ultimo = 0.0

    def iniciar(self):
        self._rodando = True
        self._thread = threading.Thread(target=self._executar, daemon=True)
        self._thread.start()

    def parar(self):
        self._rodando = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def _executar(self):
        try:
            self._loop()
        except Exception as e:
            log_erro("na captura da câmera", e)

    def _loop(self):
        # A janela, o registro e a leitura precisam acontecer todos nesta mesma thread.
        # "STATIC" é uma classe pronta do Windows; HWND_MESSAGE deixa a janela invisível.
        hwnd = user32.CreateWindowExW(0, "STATIC", "", 0, 0, 0, 0, 0, HWND_MESSAGE, None, None, None)
        if not hwnd:
            log(f"Câmera não será gravada: janela de captura falhou ({ctypes.get_last_error()})")
            return
        dispositivo = RAWINPUTDEVICE(0x01, 0x02, RIDEV_INPUTSINK, hwnd)   # 0x01/0x02 = mouse
        if not user32.RegisterRawInputDevices(ctypes.byref(dispositivo), 1, ctypes.sizeof(RAWINPUTDEVICE)):
            log(f"Câmera não será gravada: registro do mouse falhou ({ctypes.get_last_error()})")
            user32.DestroyWindow(hwnd)
            return
        msg = wintypes.MSG()
        try:
            while self._rodando:
                user32.MsgWaitForMultipleObjects(0, None, False, 4, QS_ALLINPUT)
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    if msg.message == WM_INPUT:
                        self._ler(msg.lParam)
                        self._descarregar()
                    user32.DispatchMessageW(ctypes.byref(msg))
                self._descarregar()
            self._descarregar(forcar=True)     # não perde o último pedacinho do movimento
        finally:
            remover = RAWINPUTDEVICE(0x01, 0x02, RIDEV_REMOVE, None)
            user32.RegisterRawInputDevices(ctypes.byref(remover), 1, ctypes.sizeof(RAWINPUTDEVICE))
            user32.DestroyWindow(hwnd)

    def _ler(self, identificador):
        tamanho = wintypes.UINT(ctypes.sizeof(self._buffer))
        lidos = user32.GetRawInputData(identificador, RID_INPUT, self._buffer, ctypes.byref(tamanho),
                                       ctypes.sizeof(RAWINPUTHEADER))
        if lidos in (0, ERRO_LEITURA):
            return
        dado = ctypes.cast(self._buffer, ctypes.POINTER(RAWINPUT)).contents
        # hDevice vazio = movimento gerado por programa (SendInput): não é o seu mouse
        if dado.header.dwType != RIM_TYPEMOUSE or not dado.header.hDevice:
            return
        if dado.mouse.usFlags & MOUSE_MOVE_ABSOLUTE:      # tablets e área de trabalho remota
            return
        self.somar(dado.mouse.lLastX, dado.mouse.lLastY)

    def somar(self, dx, dy):
        if not dx and not dy:
            return
        agora = time.perf_counter()
        if not self._dx and not self._dy:
            self._t_primeiro = agora
        self._dx += dx
        self._dy += dy
        self._t_ultimo = agora

    def _descarregar(self, forcar=False):
        if not self._dx and not self._dy:
            return
        if forcar or time.perf_counter() - self._t_primeiro >= INTERVALO_PACOTE:
            dx, dy, self._dx, self._dy = self._dx, self._dy, 0, 0
            self.ao_mover(self._t_ultimo, dx, dy)
