"""Conversão das teclas do pynput para os nomes usados pelo pydirectinput."""
import pydirectinput
from pynput import keyboard

# Teclas especiais (Key.xxx) cujo nome no pynput é diferente do pydirectinput
ESPECIAIS = {
    "alt_l": "altleft", "alt_r": "altright", "alt_gr": "altright",
    "ctrl_l": "ctrlleft", "ctrl_r": "ctrlright",
    "shift_l": "shiftleft", "shift_r": "shiftright",
    "cmd": "winleft", "cmd_l": "winleft", "cmd_r": "winright",
    "caps_lock": "capslock", "num_lock": "numlock", "scroll_lock": "scrolllock",
    "page_up": "pageup", "page_down": "pagedown",
    "print_screen": "printscreen", "menu": "apps",
}

# Teclas de pontuação pelo código virtual (vk). Usar o vk evita caracteres
# estranhos quando Ctrl/Shift estão pressionados (ex: Ctrl+A vira '\x01').
VK_NOMES = {
    186: ";", 187: "=", 188: ",", 189: "-", 190: ".", 191: "/", 192: "`",
    219: "[", 220: "\\", 221: "]", 222: "'",
    106: "multiply", 107: "add", 109: "subtract", 110: "decimal", 111: "divide",
}


def nome_tecla(k):
    """Recebe a tecla do pynput e devolve o nome no padrão do pydirectinput (ou None)."""
    if k is None:
        return None
    if isinstance(k, keyboard.KeyCode):
        vk = getattr(k, "vk", None)
        if vk is not None:
            if 65 <= vk <= 90 or 48 <= vk <= 57:      # letras e números
                return chr(vk).lower()
            if vk in VK_NOMES:
                return VK_NOMES[vk]
        if k.char and k.char.isprintable():
            return k.char.lower()
        return None
    nome = getattr(k, "name", None)
    if not nome:
        return None
    return ESPECIAIS.get(nome, nome)


def reproduzivel(nome):
    """True se o pydirectinput sabe enviar essa tecla (tem scan code)."""
    return bool(nome) and pydirectinput.KEYBOARD_MAPPING.get(nome) is not None


def normalizar(texto):
    """Normaliza o nome digitado pelo usuário nas configurações (ex: ' F8 ' -> 'f8')."""
    texto = (texto or "").strip().lower()
    apelidos = {"escape": "esc", "ctrl_l": "ctrlleft", "shift_l": "shiftleft"}
    return apelidos.get(texto, ESPECIAIS.get(texto, texto))
