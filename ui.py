"""Tema e componentes compartilhados pelas abas (CustomTkinter).

As cores são pares (claro, escuro): o CustomTkinter escolhe o certo conforme o modo de aparência.
"""
import customtkinter as ctk

FUNDO = ("#f3f4f8", "#0d0f14")      # fundo geral e área da imagem
PAINEL = ("#ffffff", "#12151c")     # cabeçalho, painéis laterais, barra de status
CARTAO = ("#e8ebf2", "#1a1f2b")     # botões, campos e menus
BORDA = ("#cfd5e2", "#2b3245")
SEL = ("#d8e0f3", "#232a3a")        # item selecionado
TEXTO = ("#14171f", "#e8ebf2")
SUAVE = ("#566074", "#98a1b3")      # rótulos e textos secundários
ACENTO = ("#3b6fe0", "#3b6fe0")
ACENTO_H = ("#2f5fcc", "#4a80ee")
OK = ("#1f9d63", "#4ad08a")
ERRO = ("#c4382b", "#ff7a6b")
BRANCO = "#ffffff"


def fonte(tamanho=13, peso="normal"):
    return ctk.CTkFont(size=tamanho, weight=peso)


def fonte_mono(tamanho=12, peso="normal"):
    return ctk.CTkFont(family="Consolas", size=tamanho, weight=peso)


def botao(parent, texto, comando=None, estilo="padrao", **kw):
    """Botão com o visual do tema. `estilo`: 'primario', 'padrao' ou 'sutil'."""
    if estilo == "primario":
        cfg = dict(fg_color=ACENTO, hover_color=ACENTO_H, text_color=BRANCO, font=fonte(13, "bold"))
    elif estilo == "sutil":
        cfg = dict(fg_color="transparent", hover_color=CARTAO, text_color=TEXTO, font=fonte(13))
    else:
        cfg = dict(fg_color=CARTAO, hover_color=BORDA, text_color=TEXTO, border_width=1, border_color=BORDA,
                   font=fonte(13))
    cfg.update(height=36, corner_radius=8)
    cfg.update(kw)
    return ctk.CTkButton(parent, text=texto, command=comando, **cfg)


def menu(parent, valores, comando=None, **kw):
    return ctk.CTkOptionMenu(parent, values=valores, command=comando, height=34, corner_radius=8, fg_color=CARTAO,
                             button_color=BORDA, button_hover_color=ACENTO, text_color=TEXTO,
                             dropdown_fg_color=PAINEL, dropdown_text_color=TEXTO, dropdown_hover_color=SEL,
                             font=fonte(13), dropdown_font=fonte(13), **kw)


def segmentado(parent, valores, comando=None, **kw):
    """Controle segmentado (abas, modelo de projeção, visualização)."""
    return ctk.CTkSegmentedButton(parent, values=valores, command=comando, height=34, corner_radius=8,
                                  fg_color=FUNDO, selected_color=SEL, selected_hover_color=SEL,
                                  unselected_color=FUNDO, unselected_hover_color=CARTAO, text_color=TEXTO,
                                  font=fonte(13), border_width=3, **kw)


def entrada(parent, **kw):
    cfg = dict(height=32, corner_radius=8, fg_color=FUNDO, border_color=BORDA, text_color=TEXTO, font=fonte_mono(12))
    cfg.update(kw)
    return ctk.CTkEntry(parent, **cfg)


def rotulo_secao(parent, texto, **pack):
    """Título pequeno em maiúsculas, para agrupar controles."""
    ctk.CTkLabel(parent, text=texto.upper(), anchor="w", text_color=SUAVE, font=fonte(11, "bold")).pack(
        fill="x", **{"padx": 4, "pady": (10, 2), **pack})


def campo(parent, rotulo, largura=76, **kw_entrada):
    """Linha 'rótulo ........ [valor]' (o slider, se houver, vai embaixo). Devolve (bloco, entry)."""
    bloco = ctk.CTkFrame(parent, fg_color="transparent")
    bloco.pack(fill="x", pady=3)
    linha = ctk.CTkFrame(bloco, fg_color="transparent")
    linha.pack(fill="x")
    ctk.CTkLabel(linha, text=rotulo, anchor="w", text_color=SUAVE, font=fonte(12)).pack(side="left")
    e = entrada(linha, width=largura, justify="right", **kw_entrada)
    e.pack(side="right")
    return bloco, e


def slider(bloco, minimo, maximo, passos=None, comando=None):
    s = ctk.CTkSlider(bloco, from_=minimo, to=maximo, number_of_steps=passos, command=comando, height=16,
                      progress_color=ACENTO, button_color=ACENTO, button_hover_color=ACENTO_H, fg_color=BORDA)
    s.pack(fill="x", pady=(4, 0))
    return s


def barra_status(parent):
    """Rodapé com um ponto colorido e um texto. Devolve (frame, label); atualize com label.configure(text=...)."""
    frame = ctk.CTkFrame(parent, fg_color=PAINEL, corner_radius=0, height=34)
    ctk.CTkLabel(frame, text="●", text_color=OK, width=18, font=fonte(10)).pack(side="left", padx=(14, 0))
    rotulo = ctk.CTkLabel(frame, text="", anchor="w", text_color=SUAVE, font=fonte(12))
    rotulo.pack(side="left", fill="x", expand=True, padx=(2, 12), pady=6)
    return frame, rotulo


class Secao(ctk.CTkFrame):
    """Bloco recolhível: um cabeçalho clicável e um `corpo` onde se colocam os controles."""

    def __init__(self, parent, titulo, aberta=True):
        super().__init__(parent, fg_color=FUNDO, border_width=1, border_color=BORDA, corner_radius=12)
        self._titulo, self._aberta = titulo, aberta
        self.cabecalho = ctk.CTkButton(self, text="", anchor="w", height=40, corner_radius=10, fg_color="transparent",
                                       hover_color=CARTAO, text_color=TEXTO, font=fonte(13, "bold"),
                                       command=self.alternar)
        self.cabecalho.pack(fill="x", padx=4, pady=3)
        self.corpo = ctk.CTkFrame(self, fg_color="transparent")
        self._atualizar()

    def alternar(self):
        self._aberta = not self._aberta
        self._atualizar()

    def _atualizar(self):
        self.cabecalho.configure(text=("▾  " if self._aberta else "▸  ") + self._titulo)
        if self._aberta:
            self.corpo.pack(fill="x", padx=12, pady=(0, 12))
        else:
            self.corpo.pack_forget()
