# FortniteAFK

## O que é

App estilo TinyTask: grava suas ações e usa um bot para repetir partidas de Battle Royale em lobby de bots. Automação/AFK pode violar as regras da Epic e gerar banimento. Use por sua conta.

## Requisitos

- Windows 10 ou 11.
- Python 3.10+ para gerar o `.exe` ou rodar pelo Python; o `.exe` pronto dispensa Python.
- Fortnite em **INGLÊS**, no monitor principal.
- Modo de tela **Windowed Fullscreen** (Tela cheia em janela).

## Gerar o .exe

Dê dois cliques em `build.bat` e aguarde. O executável sai em `dist\FortniteAFK.exe`. Mova esse arquivo para uma pasta própria.

Alternativa sem `.exe`: abra um terminal na pasta do app e execute:

```powershell
pip install -r requirements.txt
python main.py
```

## A barra

| Botão | Para que serve |
| --- | --- |
| ● Gravar | Começa ou termina uma gravação. |
| ▶ Iniciar bot | Inicia o ciclo automático de partidas. |
| ■ Parar | Para tudo e solta as teclas. |
| ☰ Gravações | Gerencia, ativa e testa gravações. |
| ⛶ Imagens | Captura e testa as imagens de reconhecimento. |
| ⚙ Config | Abre as configurações. |
| ▾ Log | Mostra o registro de atividade. |
| ✕ Fechar | Fecha o app. |

Arraste pela linha de status para mover a barra; ela fica sempre por cima. **F8** grava/para a gravação e **F9** para o bot; os atalhos são configuráveis.

A opção **Não roubar foco do jogo** vem ligada para a barra não tirar o foco do Fortnite. Se algum botão não responder, desligue essa opção nas configurações.

## Capturar as imagens pelo app

Abra **⛶ Imagens**, deixe o jogo na tela certa e clique em **Capturar**. As janelas do app somem e você tem **3 segundos** para deixar a tela pronta. Quando a tela escurecer, arraste um retângulo justo em volta do elemento. **Esc** ou botão direito cancela.

| Imagem | O que recortar |
| --- | --- |
| `play.png` | Só o botão amarelo **PLAY** do painel esquerdo. **NÃO** a aba PLAY do topo. |
| `br.png` | O texto **BATTLE ROYALE**. |
| `mode.png` | A caixa **Zero Build, Squad, Fill**. |
| `lobby.png` | O botão **RETURN TO LOBBY** da tela final (“YOU PLACED #…”), que só aparece quando o squad inteiro morreu. Enquanto você está em **SPECTATING** (assistindo um aliado), ele não aparece. |
| `onibus.png` | Recomendada: algo que aparece na tela **quando você entra no ônibus** (ex.: o aviso de pular do ônibus). A reprodução da gravação só começa quando essa imagem aparece. Sem ela, começa logo após o PLAY. |
| `espectando.png` | Recomendada: o texto **SPECTATING** do topo da tela, quando você morreu e está assistindo um aliado. Recorte **só a palavra SPECTATING**, sem o nome do aliado (ele muda). |
| `confirmar.png` | Opcional: o botão de confirmação, se aparecer. |
| `fim_1.png`, `fim_2.png`… | Opcional. Como o RETURN TO LOBBY só aparece quando o squad inteiro morreu, ele já basta. Se quiser um marcador extra, recorte só o texto **YOU PLACED** (sem o número). Não use o nome de quem você está assistindo: ele muda. |

**Atenção ao PLAY AGAIN:** a tela final também tem um botão amarelo **PLAY AGAIN**. Recorte o `play.png` no lobby pegando o botão **PLAY inteiro** (com as bordas do amarelo), não só as letras. O bot também só considera que está no lobby quando o PLAY aparece **e** o RETURN TO LOBBY não aparece.

Faça recortes pequenos, sem partes que mudam, como fundo animado ou números. Depois use **Testar** para ver a confiança do reconhecimento.

## Gravar

Aperte **F8 no momento em que a imagem do `onibus.png` aparecer** (ao entrar no ônibus). Na reprodução, o bot espera essa mesma imagem para começar, então os tempos batem. Jogue e aperte **F8** de novo para parar. Sem `onibus.png`, a reprodução começa logo após o PLAY; nesse caso, grave a partir do clique em PLAY.

A gravação guarda teclado e cliques com o tempo exato; **não grava movimento do mouse/câmera**. Você pode criar várias gravações. O bot sorteia entre as ativas, marcadas no checkbox do gerenciador **☰ Gravações**. O botão **Testar** reproduz uma vez após **3 segundos**.

## Rodar

Deixe o jogo no lobby com **Battle Royale / Zero Build, Squad, Fill** selecionado e clique em **▶ Iniciar bot**. Aguarde os **5 segundos** de contagem; depois não precisa fazer mais nada.

1. No lobby, o bot encontra e clica em **PLAY**.
2. Espera o ônibus (`onibus.png`) e reproduz gravações aleatórias entre as ativas. Se o ônibus não for reconhecido em 10 min (configurável), começa assim mesmo.
3. A cada **80–100 segundos**, verifica se o squad foi eliminado.
4. Quando o squad inteiro morre, clica em **RETURN TO LOBBY** e confirma se necessário.
5. De volta ao lobby, espera **5–20 segundos** e repete.

**F9** ou **■ Parar** para tudo e solta as teclas.

### Quando você morre (com `espectando.png`)

A cada 5 s (configurável) o bot procura **SPECTATING** na tela:

- **Viu SPECTATING:** pausa a gravação no ponto em que estava e solta as teclas.
- **Apareceu a tela final (RETURN TO LOBBY):** volta ao lobby na hora.
- **SPECTATING sumiu e não veio a tela final** (um aliado te reviveu): depois de conferir 2 vezes seguidas, retoma a gravação de onde parou, voltando a segurar as teclas que estavam seguradas.

Se o bot for iniciado enquanto você está assistindo um aliado, ele já entende que está em partida.

## Configurações

| Opção | Padrão |
| --- | --- |
| Intervalo de verificação (mín./máx.) | 80 / 100 s |
| Espera no lobby (mín./máx.) | 5 / 20 s |
| Checagem do PLAY | 5 s |
| Confiança | 0.8 |
| Verificar modo | Ligado |
| Atalhos de gravar / parar bot | f8 / f9 |
| Teclas ignoradas na gravação | esc, f8, f9 |
| Parar depois de X partidas | 0 = infinito |
| Timer: parar depois de X minutos | 0 = sem limite |
| Ao fim do timer: terminar a partida e parar no lobby | Ligado |
| Não roubar foco do jogo | Ligado |

As mudanças valem no próximo **Iniciar bot**.

### Timer

Em **⚙ Config**, preencha **Timer: parar depois de X minutos** (ex.: 120 = 2 horas). Com o timer ligado, a barra mostra `falta HH:MM:SS`. Quando o tempo acaba:

- **No lobby:** o bot para na hora.
- **Na partida, com "terminar a partida" ligado (padrão):** a reprodução para (o personagem fica parado), o bot espera o squad ser eliminado, volta ao lobby e para. Se a partida não acabar em 30 minutos, ele para assim mesmo.
- **Na partida, com a opção desligada:** para na hora, ainda dentro da partida.

O timer limita quanto tempo o bot roda. Ele **não** impede banimento.

## Se o reconhecimento falhar

- Use **Testar** e veja a confiança. Se encontrar com **0.7**, mas não com **0.8**, baixe a confiança para **0.7–0.75**. Abaixo de **0.6**, há risco de falso positivo.
- Se mudar a resolução, a escala do Windows (125%/150%) ou o modo de tela, refaça **TODOS** os recortes.
- Use **Windowed Fullscreen** (Tela cheia em janela).
- Faça um recorte menor e mais “único”, sem elementos que mudam.
- Desligue filtros de cor/modo daltônico ou recapture as imagens com eles ligados.
- Deixe o Fortnite no **monitor principal**.
- Se o Fortnite estiver rodando como administrador, rode o app como administrador também; senão as teclas não chegam ao jogo.
- Se só a aba PLAY do topo for clicada, recapture `play.png` apenas do **botão amarelo** do painel esquerdo.

## Arquivos ao lado do exe

- `config.json`: configurações.
- `log.txt`: registro de atividade com horário `[HH:MM:SS]`.
- `imagens\`: recortes para reconhecimento.
- `gravacoes\`: gravações salvas.

As pastas e o `config.json` são criados sozinhos na primeira execução.

## Limitações conhecidas

Se iniciar o bot com você **VIVO no meio de uma partida**, ele não tem como saber: nem PLAY, nem SPECTATING, nem RETURN TO LOBBY aparecem. Ele fica procurando o PLAY até você morrer.

Teclas específicas do layout ABNT2, como **ç** e acentos, podem não ser reproduzidas. Use teclas comuns no jogo.
