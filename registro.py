"""Log do aplicativo: grava em log.txt e repassa as linhas para o painel da interface."""
import os
import queue
import threading
import traceback
from datetime import datetime

from config import ARQ_LOG

fila = queue.Queue()        # a interface lê daqui (via after) e mostra no painel
_trava = threading.Lock()   # várias threads escrevem no mesmo arquivo


def iniciar():
    # Evita que o log.txt cresça sem limite em sessões de muitas horas
    try:
        if os.path.getsize(ARQ_LOG) > 5 * 1024 * 1024:
            os.replace(ARQ_LOG, ARQ_LOG.replace(".txt", "_antigo.txt"))
    except OSError:
        pass


def _escrever(texto):
    with _trava:
        try:
            with open(ARQ_LOG, "a", encoding="utf-8") as f:
                f.write(texto + "\n")
        except OSError:
            pass


def log(msg):
    linha = f"[{datetime.now():%H:%M:%S}] {msg}"
    _escrever(linha)
    fila.put(linha)


def log_erro(contexto, exc):
    """Mostra o erro resumido no painel e o traceback completo só no arquivo."""
    log(f"ERRO {contexto}: {exc}")
    _escrever("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())
