"""Fortnite AFK - ponto de entrada.

Rodar sem .exe:  python main.py
"""
import ctypes
import os
import sys

# No .exe sem console (--noconsole) não existe stdout/stderr; qualquer print quebraria.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# DPI: precisa vir ANTES de importar pyautogui/tkinter (o pyautogui chama
# SetProcessDPIAware ao ser importado). Com isso as coordenadas batem em 125%/150%.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Rodando pelo código-fonte em um venv/Python que não acha o Tcl/Tk sozinho:
# aponta as pastas tcl\tcl8.x e tcl\tk8.x da instalação base do Python.
if not getattr(sys, "frozen", False) and "TCL_LIBRARY" not in os.environ:
    import glob
    for var, padrao in (("TCL_LIBRARY", "tcl8.*"), ("TK_LIBRARY", "tk8.*")):
        achadas = sorted(glob.glob(os.path.join(sys.base_prefix, "tcl", padrao)))
        if achadas:
            os.environ[var] = achadas[-1]

import config  # noqa: E402

config.garantir_pastas()

import registro  # noqa: E402


def ja_aberto():
    """Impede duas cópias abertas (seriam dois hooks de teclado e dois bots)."""
    ctypes.windll.kernel32.CreateMutexW(None, False, "FortniteAFK_instancia_unica")
    return ctypes.windll.kernel32.GetLastError() == 183    # ERROR_ALREADY_EXISTS


def main():
    if ja_aberto():
        ctypes.windll.user32.MessageBoxW(None, "O Fortnite AFK já está aberto.", "Fortnite AFK", 0x40)
        return
    registro.iniciar()
    from interface import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
