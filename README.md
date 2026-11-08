# FortniteAFK

Gravador de macros estilo TinyTask para Fortnite no Windows, com reconhecimento de tela. Ele grava teclado e cliques e repete partidas de Battle Royale sozinho: clica em PLAY, reproduz suas gravações, percebe quando o squad morreu e volta ao lobby.

> [!WARNING]
> **Usar automação ou ficar AFK vai contra as regras da Epic Games e pode resultar em banimento da conta.** O timer e as esperas aleatórias não impedem isso. Use por sua conta e risco.
>
> Projeto de fãs, sem nenhuma ligação com a Epic Games.

## O que ele faz

- **Barra pequena, sempre por cima do jogo**, com atalhos globais: F8 grava e F9 para tudo.
- **Grava teclado e cliques** com o tempo exato de cada evento. O movimento da câmera não é gravado.
- **Começa a gravação no ônibus**, não importa quanto tempo a fila e o carregamento demorem.
- **Pausa quando você morre** e está assistindo um aliado. Se você for revivido, continua de onde parou.
- **Volta ao lobby sozinho** quando o squad inteiro é eliminado e começa outra partida.
- **Sorteia entre as gravações ativas**, com intervalos aleatórios entre as verificações.
- **Para sozinho** depois de X minutos ou X partidas.
- **Captura e testa as imagens de referência** dentro do próprio app.

## Requisitos

- Windows 10 ou 11
- Fortnite em qualquer idioma, no modo **Windowed Fullscreen** (Tela cheia em janela) e no monitor principal
- [Python 3.10 ou mais novo](https://www.python.org/downloads/), só se você for gerar o `.exe` ou rodar pelo código. O `.exe` pronto não precisa de Python. Na instalação, marque **Add python.exe to PATH** e mantenha **tcl/tk and IDLE**.

## Instalação

1. Baixe o `FortniteAFK.exe` em [Releases](https://github.com/Arkhm/fortAFK/releases/latest).
2. Coloque em uma pasta só dele e abra. As configurações, as imagens e as gravações ficam ao lado do `.exe`.

A primeira abertura pode levar alguns segundos.

Para gerar o `.exe` você mesmo, baixe o projeto em **Code → Download ZIP**, extraia e dê dois cliques em `build.bat`. Ele sai em `dist\FortniteAFK.exe`.

Para rodar sem gerar o `.exe`:

```bash
pip install -r requirements.txt
```

```bash
python main.py
```

O antivírus ou o SmartScreen podem desconfiar do `.exe`, porque ele não é assinado e escuta o teclado para os atalhos globais. O código está todo aqui, se quiser conferir.

## Como usar

### 1. Capture as imagens

Cada pessoa precisa capturar as próprias imagens, porque elas dependem da resolução, da escala do Windows e do idioma do jogo. Os textos da tabela abaixo estão em inglês: se o seu jogo estiver em outro idioma, capture o equivalente.

Abra **⛶ Imagens**, deixe o jogo na tela certa e clique em **Capturar**. Você tem 3 segundos, depois a tela escurece e é só arrastar um retângulo. Use **Testar** para conferir cada imagem.

| Imagem | Onde capturar | O que recortar | Precisa? |
| --- | --- | --- | --- |
| `play.png` | Lobby | O botão amarelo PLAY inteiro, do painel esquerdo | Sim |
| `br.png` | Lobby | O texto BATTLE ROYALE | Sim, com a verificação de modo ligada |
| `mode.png` | Lobby | A caixa do modo (ex.: Zero Build, Squad, Fill) | Sim, com a verificação de modo ligada |
| `lobby.png` | Tela final (YOU PLACED) | O botão RETURN TO LOBBY | Sim |
| `onibus.png` | No ônibus | Algo que só aparece ao entrar no ônibus | Recomendada |
| `espectando.png` | Assistindo um aliado | Só a palavra SPECTATING, sem o nome | Recomendada |
| `confirmar.png` | Depois de RETURN TO LOBBY | O botão de confirmação, se aparecer | Opcional |
| `fim_1.png`, `fim_2.png`… | Tela final | Algo que só aparece quando o squad inteiro morreu | Opcional |

### 2. Grave

Aperte **F8** no momento em que a imagem do `onibus.png` aparecer, jogue e aperte **F8** de novo para salvar. Grave quantas quiser. Em **☰ Gravações** você ativa, desativa, renomeia e testa cada uma.

Sem `onibus.png`, a gravação começa logo depois do PLAY. Nesse caso, grave a partir do clique em PLAY.

### 3. Rode

Deixe o jogo no lobby com o modo certo selecionado, clique em **▶** e depois clique uma vez no jogo. O bot começa em 5 segundos. Para parar, aperte **F9** ou clique em **■**.

## Configurações

Ficam em **⚙ Config** e valem a partir do próximo início do bot.

| Opção | Padrão |
| --- | --- |
| Intervalo de verificação na partida | 80 a 100 s |
| Espera no lobby antes do PLAY | 5 a 20 s |
| Intervalo procurando o PLAY | 5 s |
| Tempo máximo esperando o ônibus | 600 s |
| Checagem de SPECTATING | 5 s |
| Confiança do reconhecimento | 0.8 |
| Verificar o modo antes do PLAY | Ligado |
| Parar depois de X partidas | 0 (sem limite) |
| Timer: parar depois de X minutos | 0 (sem limite) |
| Ao fim do timer, terminar a partida e parar no lobby | Ligado |
| Atalhos de gravar e parar | F8 e F9 |
| Teclas ignoradas na gravação | Esc, F8 e F9 |
| A barra não rouba o foco do jogo | Ligado |

## Problemas comuns

| Problema | O que fazer |
| --- | --- |
| Não encontra uma imagem | Use **Testar**. Se a confiança ficar entre 0.7 e 0.8, baixe a Confiança para 0.7. Abaixo de 0.6 aparecem falsos positivos. |
| Mudou a resolução ou a escala do Windows | Capture todas as imagens de novo. |
| Aparece MODO ERRADO | Selecione o modo certo no jogo ou capture o `mode.png` de novo. |
| As teclas não chegam ao jogo | Clique no jogo depois de iniciar. Se o Fortnite roda como administrador, rode o app como administrador também. |
| Algum botão da barra não responde | Desligue **A barra não rouba o foco** em ⚙ Config. |
| Quero saber o que aconteceu | Clique em **▾** para ver o log, ou abra o `log.txt` ao lado do programa. |

## Limitações

- Se o bot for iniciado com você vivo no meio de uma partida, ele não tem como saber disso e fica procurando o PLAY até você morrer.
- A sensibilidade não importa, porque a câmera não é gravada: o personagem anda, pula e atira olhando sempre para a mesma direção.
- Teclas do teclado numérico e teclas próprias do ABNT2, como ç e acentos, não são reproduzidas.

Mais detalhes no [LEIA-ME.md](LEIA-ME.md).
