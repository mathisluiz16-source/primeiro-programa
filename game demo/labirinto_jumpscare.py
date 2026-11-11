import base64
import io
import json
import math
import os
import random
from collections import deque

import pygame

COLS, LINHAS, T = 21, 15, 40          # precisam ser ímpares para o gerador
LARGURA, ALTURA = COLS * T, LINHAS * T
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIR_TECLAS = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
}
BUFFER_MS = 150        # quanto tempo uma virada apertada "cedo demais" continua valendo

PASTA = os.path.dirname(os.path.abspath(__file__))
IMAGEM_SUSTO = os.path.join(PASTA, "susto.png")   # imagem na mesma pasta do script
SOM_SUSTO = os.path.join(PASTA, "grito.wav")      # opcional
ARQ_SAVE = os.path.join(PASTA, "save.json")       # ponto de save (fase)


# ---------- labirinto ----------
def gerar_labirinto(fase=1):
    m = [[1] * COLS for _ in range(LINHAS)]
    m[1][1] = 0
    pilha = [(1, 1)]
    while pilha:
        x, y = pilha[-1]
        vizinhos = [
            (x + dx * 2, y + dy * 2, dx, dy)
            for dx, dy in DIRS
            if 0 < x + dx * 2 < COLS - 1
            and 0 < y + dy * 2 < LINHAS - 1
            and m[y + dy * 2][x + dx * 2] == 1
        ]
        if vizinhos:
            nx, ny, dx, dy = random.choice(vizinhos)
            m[y + dy][x + dx] = 0
            m[ny][nx] = 0
            pilha.append((nx, ny))
        else:
            pilha.pop()
    abrir_atalhos(m, max(0.10, 0.30 - 0.03 * fase))
    return m


def abrir_atalhos(m, fracao):
    """Derruba algumas paredes para criar voltas (sem isso só existe 1 caminho)."""
    candidatos = []
    for y in range(1, LINHAS - 1):
        for x in range(1, COLS - 1):
            if m[y][x] == 1:
                horizontal = m[y][x - 1] == 0 and m[y][x + 1] == 0 and m[y - 1][x] == 1 and m[y + 1][x] == 1
                vertical = m[y - 1][x] == 0 and m[y + 1][x] == 0 and m[y][x - 1] == 1 and m[y][x + 1] == 1
                if horizontal or vertical:
                    candidatos.append((x, y))
    random.shuffle(candidatos)
    for x, y in candidatos[: int(len(candidatos) * fracao)]:
        m[y][x] = 0


def distancias(m, origem):
    dist = {origem: 0}
    fila = deque([origem])
    while fila:
        x, y = fila.popleft()
        for dx, dy in DIRS:
            n = (x + dx, y + dy)
            if n not in dist and m[n[1]][n[0]] == 0:
                dist[n] = dist[(x, y)] + 1
                fila.append(n)
    return dist


def proximo_passo(m, origem, alvo):
    """BFS: devolve a próxima célula no caminho de origem até alvo."""
    fila = deque([origem])
    veio = {origem: None}
    while fila:
        atual = fila.popleft()
        if atual == alvo:
            break
        for dx, dy in DIRS:
            n = (atual[0] + dx, atual[1] + dy)
            if n not in veio and m[n[1]][n[0]] == 0:
                veio[n] = atual
                fila.append(n)
    if alvo not in veio:
        return origem
    p = alvo
    while veio[p] is not None and veio[p] != origem:
        p = veio[p]
    return p


# ---------- jumpscare ----------
def _imagem_original():
    """Usa susto.png se existir ao lado do script; senão, usa a imagem embutida."""
    if os.path.exists(IMAGEM_SUSTO):
        return pygame.image.load(IMAGEM_SUSTO).convert_alpha()
    if IMAGEM_EMBUTIDA:
        dados = base64.b64decode(IMAGEM_EMBUTIDA)
        return pygame.image.load(io.BytesIO(dados), "susto.png").convert_alpha()
    return None


def carregar_susto():
    orig = _imagem_original()
    if orig is not None:
        iw, ih = orig.get_size()

        # fundo: a própria imagem esticada e escurecida (evita barras pretas feias)
        img = pygame.transform.smoothscale(orig, (LARGURA, ALTURA))
        escuro = pygame.Surface((LARGURA, ALTURA))
        escuro.set_alpha(170)
        img.blit(escuro, (0, 0))

        # frente: imagem na proporção original, ocupando a altura toda
        w = int(iw * ALTURA / ih)
        frente = pygame.transform.scale(orig, (w, ALTURA))  # scale = pixels nítidos
        img.blit(frente, ((LARGURA - w) // 2, 0))
        return img
    # imagem reserva desenhada por código, caso o arquivo não exista
    img = pygame.Surface((LARGURA, ALTURA))
    img.fill((10, 0, 0))
    cx, cy = LARGURA // 2, ALTURA // 2
    pygame.draw.ellipse(img, (200, 190, 170), (cx - 220, cy - 260, 440, 520))
    for sx in (-90, 90):
        pygame.draw.circle(img, (0, 0, 0), (cx + sx, cy - 70), 55)
        pygame.draw.circle(img, (255, 0, 0), (cx + sx, cy - 70), 22)
    dentes = [(cx - 140, cy + 80)]
    for i in range(8):
        dentes.append((cx - 140 + i * 35 + 17, cy + (200 if i % 2 == 0 else 120)))
        dentes.append((cx - 140 + (i + 1) * 35, cy + 80))
    pygame.draw.polygon(img, (0, 0, 0), dentes)
    return img


def jumpscare(tela, relogio):
    img = carregar_susto()
    som = None
    if os.path.exists(SOM_SUSTO):
        try:
            som = pygame.mixer.Sound(SOM_SUSTO)
        except pygame.error:
            som = None
    if som:
        som.play()

    frames = 45
    for f in range(frames):
        pygame.event.pump()
        progresso = f / (frames - 1)
        escala = 0.3 + 0.7 * progresso ** 0.5          # cresce rápido no começo
        w, h = int(LARGURA * escala), int(ALTURA * escala)
        frame = pygame.transform.smoothscale(img, (max(w, 1), max(h, 1)))

        tremor = int(18 * (1 - progresso))
        ox = random.randint(-tremor, tremor)
        oy = random.randint(-tremor, tremor)

        tela.fill((0, 0, 0))
        tela.blit(frame, ((LARGURA - w) // 2 + ox, (ALTURA - h) // 2 + oy))

        if f % 6 < 2:                                   # flashes vermelhos
            flash = pygame.Surface((LARGURA, ALTURA))
            flash.fill((255, 0, 0))
            flash.set_alpha(90)
            tela.blit(flash, (0, 0))

        pygame.display.flip()
        relogio.tick(60)

    # segura a imagem cheia por um instante
    tela.blit(pygame.transform.smoothscale(img, (LARGURA, ALTURA)), (0, 0))
    pygame.display.flip()
    pygame.time.wait(900)


def tela_game_over(tela, relogio, fase):
    """Retorna 'tentar' (recomeça a fase do save), 'menu' ou 'sair'."""
    t1 = texto_pixel("VOCÊ MORREU", 24, (200, 0, 0), 4)
    t2 = texto_pixel(f"Fase {fase}", 16, (220, 220, 220), 3)
    t3 = texto_pixel("R = tentar de novo    M = menu    ESC = sair", 12, (150, 150, 150), 2)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "sair"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    return "tentar"
                if e.key == pygame.K_m:
                    return "menu"
                if e.key == pygame.K_ESCAPE:
                    return "sair"
        tela.fill((0, 0, 0))
        tela.blit(t1, t1.get_rect(center=(LARGURA // 2, ALTURA // 2 - 50)))
        tela.blit(t2, t2.get_rect(center=(LARGURA // 2, ALTURA // 2 + 20)))
        tela.blit(t3, t3.get_rect(center=(LARGURA // 2, ALTURA // 2 + 80)))
        pygame.display.flip()
        relogio.tick(30)


# ---------- gráficos pixel art (desenhados por código) ----------
ESC = T // 10          # cada "pixel" do sprite vira ESC x ESC pixels na tela
LANTERNA = False       # True = você só enxerga perto de si (mais clima, mais difícil)
RAIO_LUZ = 7 * T

TIJOLO = [
    "mmmmmmmmmm",
    "abbbmabbbm",
    "bbbbmbbbbm",
    "cccbmcccbm",
    "mmmmmmmmmm",
    "bmabbbmabb",
    "bmbbbbmbbb",
    "cmcccbmccc",
    "mmmmmmmmmm",
    "abbbmabbbm",
]
PAL_TIJOLO = {"m": (38, 36, 66), "a": (112, 112, 178), "b": (88, 88, 150), "c": (66, 66, 122)}

JOGADOR = [
    "...gggg...",
    "..gGGGGg..",
    ".gGskskGg.",
    "...gsssg..",
    "..bbbbbb..",
    ".sbbBBbbs.",
    ".sbbBBbbs.",
    "..bbbbbb..",
    "..oo..oo..",
    "..oo..oo..",
]
PAL_JOGADOR = {
    "g": (30, 120, 60), "G": (60, 190, 90), "s": (245, 200, 160), "k": (20, 20, 20),
    "b": (60, 90, 200), "B": (235, 200, 60), "o": (110, 60, 30),
}

MONSTRO_A = [
    "..r....r..",
    ".rrr..rrr.",
    ".rrrrrrrr.",
    "rrwwrrwwrr",
    "rrwkrrwkrr",
    "rrrrrrrrrr",
    "rkwkwkwkrr",
    "rrrrrrrrrr",
    "rr.rrrr.rr",
    "r..r..r..r",
]
MONSTRO_B = MONSTRO_A[:9] + [".r..rr..r."]
PAL_MONSTRO = {"r": (200, 40, 50), "w": (255, 255, 255), "k": (25, 0, 0)}


def sprite(linhas, paleta):
    h, w = len(linhas), len(linhas[0])
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, linha in enumerate(linhas):
        for x, c in enumerate(linha):
            if c in paleta:
                s.set_at((x, y), paleta[c])
    return pygame.transform.scale(s, (w * ESC, h * ESC))


def tijolo(brilho):
    s = sprite(TIJOLO, PAL_TIJOLO)
    if brilho > 0:
        s.fill((brilho,) * 3, special_flags=pygame.BLEND_RGB_ADD)
    elif brilho < 0:
        s.fill((-brilho,) * 3, special_flags=pygame.BLEND_RGB_SUB)
    return s


def chao():
    s = pygame.Surface((10, 10))
    s.fill((36, 34, 52))
    for i in range(10):
        s.set_at((i, 9), (28, 26, 42))
        s.set_at((9, i), (28, 26, 42))
        s.set_at((i, 0), (44, 42, 62))
        s.set_at((0, i), (44, 42, 62))
    for _ in range(random.randint(2, 5)):
        cor = (48, 46, 68) if random.random() < 0.6 else (30, 28, 44)
        s.set_at((random.randint(1, 8), random.randint(1, 8)), cor)
    return pygame.transform.scale(s, (T, T))


def portal(anim):
    s = pygame.Surface((10, 10), pygame.SRCALPHA)
    cores = [(255, 245, 140), (255, 200, 50), (235, 140, 25), (130, 70, 15)]
    for y in range(10):
        for x in range(10):
            d = math.hypot(x - 4.5, y - 4.5)
            if d <= 4.8:
                s.set_at((x, y), cores[(int(d) - anim) % 4])
    return pygame.transform.scale(s, (T, T))


def criar_luz():
    n = RAIO_LUZ * 2 // ESC
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    c = n / 2
    for y in range(n):
        for x in range(n):
            d = math.hypot(x - c, y - c) / c
            if d < 1:
                s.set_at((x, y), (0, 0, 0, int(235 * (1 - d) ** 0.7)))
    return pygame.transform.scale(s, (n * ESC, n * ESC))


def criar_brilho_monstro():
    r = int(T * 1.5)
    s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    for raio in range(r, 0, -4):
        alfa = int(80 * (1 - raio / r))
        pygame.draw.circle(s, (220, 30, 40, alfa), (r, r), raio)
    return s


def criar_graficos():
    sombra_chao = pygame.Surface((T, T // 2), pygame.SRCALPHA)
    pygame.draw.ellipse(sombra_chao, (0, 0, 0, 90), (6, 0, T - 12, T // 2 - 6))
    sombra_parede = pygame.Surface((T, ESC * 3), pygame.SRCALPHA)
    sombra_parede.fill((0, 0, 0, 110))
    return {
        "paredes": [tijolo(b) for b in (-10, 0, 8, 14)],
        "chaos": [chao() for _ in range(5)],
        "portal": [portal(i) for i in range(4)],
        "jogador": sprite(JOGADOR, PAL_JOGADOR),
        "monstro": [sprite(MONSTRO_A, PAL_MONSTRO), sprite(MONSTRO_B, PAL_MONSTRO)],
        "brilho": criar_brilho_monstro(),
        "sombra_chao": sombra_chao,
        "sombra_parede": sombra_parede,
        "luz": criar_luz() if LANTERNA else None,
        "escuro": pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA) if LANTERNA else None,
        "fonte": pygame.font.Font(None, 28),
    }


def montar_fundo(m, gfx):
    """Desenha o mapa todo uma vez só (chão, tijolos e sombras)."""
    fundo = pygame.Surface((LARGURA, ALTURA))
    for y in range(LINHAS):
        for x in range(COLS):
            pos = (x * T, y * T)
            if m[y][x]:
                fundo.blit(random.choice(gfx["paredes"]), pos)
                if y + 1 < LINHAS and m[y + 1][x] == 0:
                    pygame.draw.rect(fundo, (20, 18, 40), (x * T, y * T + T - ESC, T, ESC))
            else:
                fundo.blit(random.choice(gfx["chaos"]), pos)
                if y > 0 and m[y - 1][x]:
                    fundo.blit(gfx["sombra_parede"], pos)
    return fundo


def pos_suave(ant, atual, t0, duracao, agora):
    f = min(1.0, (agora - t0) / duracao)
    return (ant[0] + (atual[0] - ant[0]) * f) * T, (ant[1] + (atual[1] - ant[1]) * f) * T


# ---------- save e menu ----------
def ler_save():
    """Devolve a fase salva (int) ou None se não houver save válido."""
    try:
        with open(ARQ_SAVE, encoding="utf-8") as f:
            return max(1, int(json.load(f)["fase"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def gravar_save(fase):
    try:
        with open(ARQ_SAVE, "w", encoding="utf-8") as f:
            json.dump({"fase": fase}, f)
    except OSError:
        pass  # sem permissão de escrita: o jogo segue sem salvar


def texto_pixel(txt, tamanho, cor, escala):
    """Texto com cara de pixel: renderiza pequeno e amplia sem suavizar."""
    s = pygame.font.Font(None, tamanho).render(txt, False, cor)
    return pygame.transform.scale(s, (s.get_width() * escala, s.get_height() * escala))


def confirmar(tela, relogio, linhas):
    """Tela de confirmação. Enter/S = sim, ESC/N = não."""
    textos = [texto_pixel(l, 16, (235, 235, 255), 3) for l in linhas]
    dica = texto_pixel("ENTER = sim    ESC = voltar", 12, (150, 150, 170), 2)
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_s):
                    return True
                if e.key in (pygame.K_ESCAPE, pygame.K_n):
                    return False
        tela.fill((10, 10, 20))
        y = ALTURA // 2 - 40 * len(textos) // 2 - 20
        for t in textos:
            tela.blit(t, t.get_rect(center=(LARGURA // 2, y)))
            y += 50
        tela.blit(dica, dica.get_rect(center=(LARGURA // 2, ALTURA - 80)))
        pygame.display.flip()
        relogio.tick(30)


def aviso_checkpoint(tela, relogio, fase_nova):
    """Mensagem rápida ao passar de fase. Retorna False se fechou a janela."""
    t1 = texto_pixel("FASE CONCLUÍDA!", 24, (255, 220, 80), 4)
    t2 = texto_pixel(f"Progresso salvo - próxima: fase {fase_nova}", 14, (200, 200, 220), 3)
    t0 = pygame.time.get_ticks()
    while pygame.time.get_ticks() - t0 < 1400:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
        tela.fill((0, 0, 0))
        tela.blit(t1, t1.get_rect(center=(LARGURA // 2, ALTURA // 2 - 30)))
        tela.blit(t2, t2.get_rect(center=(LARGURA // 2, ALTURA // 2 + 40)))
        pygame.display.flip()
        relogio.tick(30)
    return True


def menu(tela, relogio, gfx):
    """Retorna 'iniciar', 'continuar' ou 'sair'."""
    save = ler_save()

    fundo = montar_fundo(gerar_labirinto(5), gfx)
    veu = pygame.Surface((LARGURA, ALTURA), pygame.SRCALPHA)
    veu.fill((0, 0, 10, 175))
    fundo.blit(veu, (0, 0))

    titulo = texto_pixel("LABIRINTO", 24, (230, 230, 255), 5)
    sombra = texto_pixel("LABIRINTO", 24, (0, 0, 0), 5)
    rodape = texto_pixel("CIMA/BAIXO + ENTER", 12, (130, 130, 160), 2)
    pers = pygame.transform.scale(gfx["jogador"], (T * 3, T * 3))
    mons = [pygame.transform.scale(f, (T * 3, T * 3)) for f in gfx["monstro"]]

    opcoes = [
        ("iniciar", "INICIAR", True),
        ("continuar", f"CONTINUAR - FASE {save}" if save else "CONTINUAR", save is not None),
        ("sair", "SAIR", True),
    ]
    # uma imagem para cada estado: normal, selecionada, desativada
    imgs, rects = [], []
    for i, (_, txt, ativo) in enumerate(opcoes):
        normal = texto_pixel(txt, 20, (225, 225, 245), 3)
        marcada = texto_pixel(txt, 20, (255, 220, 80), 3)
        apagada = texto_pixel(txt, 20, (85, 85, 105), 3)
        imgs.append((normal, marcada, apagada))
        rects.append(normal.get_rect(center=(LARGURA // 2, 300 + i * 70)))

    sel = 1 if save else 0

    def mover(d, atual):
        atual = (atual + d) % len(opcoes)
        while not opcoes[atual][2]:
            atual = (atual + d) % len(opcoes)
        return atual

    while True:
        agora = pygame.time.get_ticks()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "sair"
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    sel = mover(-1, sel)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    sel = mover(1, sel)
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    return opcoes[sel][0]
                elif e.key == pygame.K_ESCAPE:
                    return "sair"
            if e.type == pygame.MOUSEMOTION:
                for i, r in enumerate(rects):
                    if r.collidepoint(e.pos) and opcoes[i][2]:
                        sel = i
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                if rects[sel].collidepoint(e.pos):
                    return opcoes[sel][0]

        tela.blit(fundo, (0, 0))

        # título com o herói de um lado e o monstro do outro
        ty = 120
        tela.blit(sombra, sombra.get_rect(center=(LARGURA // 2 + 5, ty + 5)))
        tela.blit(titulo, titulo.get_rect(center=(LARGURA // 2, ty)))
        balanco = -ESC * 2 if (agora // 300) % 2 else 0
        tela.blit(pers, (LARGURA // 2 - titulo.get_width() // 2 - T * 3 - 20, ty - T * 3 // 2 + balanco))
        tela.blit(mons[(agora // 250) % 2],
                  (LARGURA // 2 + titulo.get_width() // 2 + 20, ty - T * 3 // 2 + balanco))

        for i, r in enumerate(rects):
            normal, marcada, apagada = imgs[i]
            if not opcoes[i][2]:
                tela.blit(apagada, r)
            elif i == sel:
                tela.blit(marcada, r)
                bal = -ESC if (agora // 250) % 2 else 0
                tela.blit(gfx["jogador"], (r.left - T - 16, r.centery - T // 2 + bal))
            else:
                tela.blit(normal, r)

        tela.blit(rodape, rodape.get_rect(center=(LARGURA // 2, ALTURA - 40)))
        pygame.display.flip()
        relogio.tick(60)


# ---------- jogo ----------
def jogar_fase(tela, relogio, fase, gfx):
    """Retorna 'venceu', 'morreu' ou 'sair'."""
    m = gerar_labirinto(fase)
    jogador = (1, 1)
    saida = (COLS - 2, LINHAS - 2)

    # monstro nasce longe do jogador e fora da saída
    dist = distancias(m, jogador)
    longe = [c for c, d in dist.items() if d >= 18 and c != saida]
    if not longe:
        longe = [c for c in dist if c not in (jogador, saida)]
    monstro = random.choice(longe)

    delay_jogador = 110                                  # ms entre passos (menor = mais ágil)
    delay_monstro = max(110, 150 - fase * 5)             # chega à sua velocidade na fase 8
    ultimo_j = ultimo_m = pygame.time.get_ticks()
    inicio = ultimo_j
    fundo = montar_fundo(m, gfx)
    j_ant, m_ant = jogador, monstro
    j_t = m_t = inicio
    olhando = 1
    pilha = []                   # direções seguradas, a mais recente por último
    buffer, buffer_t = None, 0   # última virada apertada (vale por BUFFER_MS)
    graca = 3000                                         # monstro espera 3s

    while True:
        agora = pygame.time.get_ticks()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "sair"
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                return "menu"
            if e.type == pygame.KEYDOWN and e.key in DIR_TECLAS:
                d = DIR_TECLAS[e.key]
                if d in pilha:
                    pilha.remove(d)
                pilha.append(d)
                buffer, buffer_t = d, agora

        # direções realmente seguradas agora (corrige teclas "presas" ou já seguradas)
        teclas = pygame.key.get_pressed()
        seguradas = {d for k, d in DIR_TECLAS.items() if teclas[k]}
        pilha = [d for d in pilha if d in seguradas]
        pilha = [d for d in seguradas if d not in pilha] + pilha

        if agora - ultimo_j >= delay_jogador:
            # tenta a tecla mais recente primeiro; se bater na parede, tenta as outras
            candidatas = pilha[::-1]
            if buffer and agora - buffer_t <= BUFFER_MS and buffer not in candidatas:
                candidatas.insert(0, buffer)
            for d in candidatas:
                if d[0]:
                    olhando = d[0]
                alvo = (jogador[0] + d[0], jogador[1] + d[1])
                if m[alvo[1]][alvo[0]] == 0:
                    j_ant, jogador, j_t = jogador, alvo, agora
                    ultimo_j = agora          # só "gasta" o tempo se realmente andou
                    if d == buffer:
                        buffer = None
                    break

        if agora - inicio > graca and agora - ultimo_m >= delay_monstro:
            m_ant, monstro, m_t = monstro, proximo_passo(m, monstro, jogador), agora
            ultimo_m = agora

        if jogador == monstro:
            return "morreu"
        if jogador == saida:
            return "venceu"

        tela.blit(fundo, (0, 0))

        # saída (portal animado)
        tela.blit(gfx["portal"][(agora // 150) % 4], (saida[0] * T, saida[1] * T))

        # posições suaves entre uma célula e outra
        jx, jy = pos_suave(j_ant, jogador, j_t, delay_jogador, agora)
        mx, my = pos_suave(m_ant, monstro, m_t, delay_monstro, agora)

        # monstro: brilho vermelho pulsando + sombra + sprite animado
        pulso = 0.6 + 0.4 * math.sin(agora / 200)
        gfx["brilho"].set_alpha(int(255 * pulso))
        tela.blit(gfx["brilho"], (mx + T // 2 - gfx["brilho"].get_width() // 2,
                                  my + T // 2 - gfx["brilho"].get_height() // 2))
        tela.blit(gfx["sombra_chao"], (mx, my + T - T // 4))
        flutua = int(math.sin(agora / 180) * ESC)
        tela.blit(gfx["monstro"][(agora // 250) % 2], (mx, my + flutua))

        # jogador: sombra + sprite virado para onde anda + balanço ao andar
        andando = agora - j_t < delay_jogador
        balanco = -ESC if andando and (agora // 100) % 2 else 0
        img_j = gfx["jogador"] if olhando > 0 else pygame.transform.flip(gfx["jogador"], True, False)
        tela.blit(gfx["sombra_chao"], (jx, jy + T - T // 4))
        tela.blit(img_j, (jx, jy + balanco))

        # lanterna (opcional)
        if LANTERNA:
            escuro = gfx["escuro"]
            escuro.fill((0, 0, 0, 235))
            escuro.blit(gfx["luz"], (jx + T // 2 - RAIO_LUZ, jy + T // 2 - RAIO_LUZ),
                        special_flags=pygame.BLEND_RGBA_SUB)
            tela.blit(escuro, (0, 0))

        # HUD
        txt = f"FASE {fase}"
        tela.blit(gfx["fonte"].render(txt, False, (0, 0, 0)), (11, 13))
        tela.blit(gfx["fonte"].render(txt, False, (230, 230, 255)), (10, 12))
        pygame.display.flip()
        relogio.tick(60)


def main():
    pygame.init()
    tela = pygame.display.set_mode((LARGURA, ALTURA))
    pygame.display.set_caption("Labirinto")
    relogio = pygame.time.Clock()
    gfx = criar_graficos()

    sair = False
    while not sair:
        escolha = menu(tela, relogio, gfx)
        if escolha == "sair":
            break

        if escolha == "iniciar":
            salvo = ler_save()
            if salvo and not confirmar(tela, relogio, [
                    "Começar um jogo novo?",
                    f"Seu save (fase {salvo}) será",
                    "substituído ao passar da fase 1."]):
                continue
            fase = 1
        else:
            fase = ler_save() or 1

        while True:
            resultado = jogar_fase(tela, relogio, fase, gfx)
            if resultado == "venceu":
                fase += 1
                gravar_save(fase)                      # ponto de save a cada fase passada
                if not aviso_checkpoint(tela, relogio, fase):
                    sair = True
                    break
            elif resultado == "morreu":
                jumpscare(tela, relogio)
                acao = tela_game_over(tela, relogio, fase)
                if acao == "tentar":
                    continue                           # recomeça a mesma fase
                sair = acao == "sair"
                break
            elif resultado == "menu":
                break
            else:
                sair = True
                break
    pygame.quit()


# Imagem do jumpscare embutida no script (funciona mesmo sem o arquivo susto.png)
IMAGEM_EMBUTIDA = (
    "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"
)


if __name__ == "__main__":
    main()
