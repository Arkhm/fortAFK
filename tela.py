"""Reconhecimento de tela (pyautogui/OpenCV) e cliques nos menus (pydirectinput)."""
import glob
import os
import random
import re
import threading

import cv2
import numpy as np
import pyautogui
import pydirectinput
from PIL import Image, ImageGrab

from config import PASTA_IMG

pyautogui.FAILSAFE = False
pydirectinput.FAILSAFE = False
pydirectinput.PAUSE = 0          # sem pausas automáticas: os tempos são controlados aqui

_cache = {}                      # nome -> (mtime, imagem PIL)
_trava = threading.Lock()


def caminho(nome):
    return os.path.join(PASTA_IMG, nome)


def existe(nome):
    return os.path.isfile(caminho(nome))


def carregar(nome):
    """Carrega a imagem como PIL (RGB), com cache que se renova se o arquivo mudar.

    Passar a imagem já aberta para o pyautogui evita o cv2.imread, que falha
    em pastas com acento no Windows (ex: "Área de Trabalho")."""
    arq = caminho(nome)
    try:
        mtime = os.path.getmtime(arq)
    except OSError:
        return None
    with _trava:
        item = _cache.get(nome)
        if item and item[0] == mtime:
            return item[1]
        try:
            with Image.open(arq) as im:
                img = im.convert("RGB")
        except Exception:
            return None
        _cache[nome] = (mtime, img)
        return img


def listar_fim():
    """Marcadores de fim de partida: imagens/fim*.png, em ordem natural (fim_2 antes de fim_10)."""
    nomes = [os.path.basename(a) for a in glob.glob(os.path.join(PASTA_IMG, "fim*.png"))]
    return sorted(nomes, key=lambda n: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", n.lower())])


def proximo_fim():
    """Próximo nome livre para um marcador extra: fim_1.png, fim_2.png, ..."""
    i = 1
    while existe(f"fim_{i}.png"):
        i += 1
    return f"fim_{i}.png"


def achar(nome, confianca):
    """Procura a imagem na tela. Devolve (x, y) do centro ou None.

    Versões novas do pyautogui/pyscreeze lançam ImageNotFoundException em vez de
    devolver None; qualquer exceção aqui vira "não encontrada"."""
    img = carregar(nome)
    if img is None:
        return None
    try:
        # grayscale=False: o padrão do pyscreeze é tons de cinza; em cor o PLAY amarelo
        # é mais fácil de distinguir e a confiança bate com o botão "Testar".
        pos = pyautogui.locateCenterOnScreen(img, confidence=confianca, grayscale=False)
    except Exception:
        return None
    if pos is None:
        return None
    return int(pos[0]), int(pos[1])


def testar(nome):
    """Usa o OpenCV direto (matchTemplate) para mostrar a confiança do melhor ponto.

    Devolve (confianca, (x, y)) ou lança exceção com uma mensagem legível."""
    img = carregar(nome)
    if img is None:
        raise FileNotFoundError(f"{nome} não existe")
    tela = cv2.cvtColor(np.array(ImageGrab.grab().convert("RGB")), cv2.COLOR_RGB2BGR)
    modelo = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    if modelo.shape[0] > tela.shape[0] or modelo.shape[1] > tela.shape[1]:
        raise ValueError("a imagem é maior que a tela (resolução mudou?)")
    res = cv2.matchTemplate(tela, modelo, cv2.TM_CCOEFF_NORMED)
    _, maximo, _, ponto = cv2.minMaxLoc(res)
    h, w = modelo.shape[:2]
    return float(maximo), (ponto[0] + w // 2, ponto[1] + h // 2)


def clicar(pos, parar=None):
    """Clique "humano" nos menus: move, espera 0,15–0,4 s e clica com pydirectinput.

    parar: threading.Event opcional; se for acionado durante a espera, não clica."""
    parar = parar or threading.Event()
    x, y = pos
    pydirectinput.moveTo(int(x), int(y))
    if parar.wait(random.uniform(0.15, 0.4)):
        return False
    pydirectinput.mouseDown(button="left")
    try:
        parar.wait(random.uniform(0.05, 0.12))
    finally:
        pydirectinput.mouseUp(button="left")   # nunca deixa o botão preso
    parar.wait(0.3)
    return True


def capturar_tela():
    """Print do monitor principal (mesmo monitor usado pelo pyautogui)."""
    return ImageGrab.grab().convert("RGB")
