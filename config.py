"""Caminhos do aplicativo e configurações salvas em config.json."""
import copy
import json
import math
import os
import sys


def _pasta_base():
    # No .exe do PyInstaller, __file__ aponta para a pasta temporária (_MEIxxxx),
    # que some ao fechar. Os dados do usuário ficam ao lado do executável.
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE = _pasta_base()
PASTA_IMG = os.path.join(BASE, "imagens")
PASTA_GRAV = os.path.join(BASE, "gravacoes")
ARQ_CONFIG = os.path.join(BASE, "config.json")
ARQ_LOG = os.path.join(BASE, "log.txt")

# Imagens de referência com nome fixo: (arquivo, descrição, quando é obrigatória)
IMAGENS_FIXAS = [
    ("play.png", "Botão amarelo PLAY (painel esquerdo, não a aba do topo)", "obrigatória"),
    ("br.png", "Texto \"BATTLE ROYALE\" no painel", "obrigatória c/ verificação de modo"),
    ("mode.png", "Caixa \"Zero Build, Squad, Fill\"", "obrigatória c/ verificação de modo"),
    ("lobby.png", "Botão \"RETURN TO LOBBY\"", "obrigatória"),
    ("onibus.png", "Algo que aparece ao entrar no ônibus - a gravação começa aqui", "opcional, recomendada"),
    ("espectando.png", "Texto \"SPECTATING\" (assistindo um aliado) - pausa a gravação", "opcional, recomendada"),
    ("confirmar.png", "Confirmação após RETURN TO LOBBY", "opcional"),
]

PADRAO = {
    "check_min": 80,            # intervalo de verificação na partida (s)
    "check_max": 100,
    "lobby_min": 5,             # espera no lobby antes do PLAY (s)
    "lobby_max": 20,
    "poll_lobby": 5,            # intervalo enquanto procura o PLAY (s)
    "espera_onibus_max": 600,   # tempo máximo esperando o ônibus depois do PLAY (s)
    "intervalo_espectador": 5,  # de quanto em quanto tempo procura "SPECTATING" na partida (s)
    "confianca": 0.8,           # confiança do reconhecimento de imagem
    "verificar_modo": True,     # confere BATTLE ROYALE + modo antes do PLAY
    "tecla_gravar": "f8",
    "tecla_parar": "f9",
    "teclas_ignoradas": ["esc", "f8", "f9"],
    "max_partidas": 0,          # 0 = infinito
    "max_minutos": 0,           # timer: para depois de X minutos (0 = sem limite)
    "tempo_terminar_partida": True,  # ao fim do timer: termina a partida e para no lobby
    "nao_roubar_foco": True,    # a barra não tira o foco do jogo ao ser clicada
    "gravacoes_desativadas": [],
    "posicao_janela": None,     # [x, y] da barra principal
}


def garantir_pastas():
    os.makedirs(PASTA_IMG, exist_ok=True)
    os.makedirs(PASTA_GRAV, exist_ok=True)


def carregar():
    """Lê o config.json (criando-o se não existir). Chaves faltando usam o padrão."""
    cfg = copy.deepcopy(PADRAO)
    try:
        with open(ARQ_CONFIG, encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict):
            for chave, padrao in PADRAO.items():
                if chave not in dados:
                    continue
                valor = dados[chave]
                # números editados à mão no arquivo: só aceita valores finitos
                if isinstance(padrao, (int, float)) and not isinstance(padrao, bool):
                    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
                        continue
                elif padrao is not None and not isinstance(valor, type(padrao)):
                    continue
                cfg[chave] = valor
    except FileNotFoundError:
        pass
    except Exception:
        # Arquivo corrompido: guarda uma cópia e segue com o padrão
        try:
            os.replace(ARQ_CONFIG, ARQ_CONFIG + ".corrompido")
        except OSError:
            pass
    salvar(cfg)
    return cfg


def salvar(cfg):
    """Grava em arquivo temporário e troca, para não corromper se o PC desligar no meio."""
    tmp = ARQ_CONFIG + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, ARQ_CONFIG)
    except OSError:
        pass
