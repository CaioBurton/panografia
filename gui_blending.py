"""Aba "Blending (Pirâmides)": mistura de duas imagens com pirâmides Gaussiana/Laplaciana (Atividade 02)."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageDraw

import ui
from vc import piramides

PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "imagens")
PADROES = {"a": "512_burt_apple.png", "b": "512_burt_orange.png", "mascara": "512_mask.jpg"}
ROTULOS = {"a": "Imagem A (onde máscara = 1)", "b": "Imagem B (onde máscara = 0)", "mascara": "Máscara"}
NOMES_CURTOS = {"a": "Imagem A", "b": "Imagem B", "mascara": "Máscara"}
TIPOS = [("Imagens", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff")]
VISOES = ["Comparação", "Blending", "Justaposição", "Zoom da emenda", "Pirâmides"]
MAX_NIVEIS = 9   # 512 -> 4 pixels no último nível
MASCARA_ARQUIVO = "Arquivo"
MASCARA_ESQ = "Metade esquerda = A"
MASCARA_DIR = "Metade direita = A"


def _pil(arr):
    return Image.fromarray(np.clip(np.rint(arr), 0, 255).astype(np.uint8))


def _rotular(img, texto):
    img = img.copy()
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8 + 7 * len(texto), 18), fill=(0, 0, 0))
    d.text((4, 3), texto, fill=(255, 255, 255))
    return img


def _grade(imgs, colunas):
    w, h = imgs[0].size
    linhas = -(-len(imgs) // colunas)
    tela = Image.new("RGB", (w * colunas, h * linhas), "white")
    for i, im in enumerate(imgs):
        tela.paste(im, ((i % colunas) * w, (i // colunas) * h))
    return tela


class BlendingTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.caminhos = {k: None for k in PADROES}
        self.rotulos_arquivo = {}
        self.resultados = {}   # visão -> imagem PIL
        self._ctk_image = None
        self._atual = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_painel()
        self._build_area_imagem()
        self.usar_sugeridas()

    # ---------- interface ----------
    def _build_area_imagem(self):
        barra = ctk.CTkFrame(self, fg_color=ui.FUNDO, corner_radius=0)
        barra.grid(row=0, column=1, sticky="ew")
        self.visao = ui.segmentado(barra, VISOES, lambda _v: self._exibir())
        self.visao.set(VISOES[0])
        self.visao.pack(side="left", padx=16, pady=10)
        ui.botao(barra, "Salvar visualização", self.salvar, width=160).pack(side="right", padx=16, pady=10)

        self.image_label = ctk.CTkLabel(self, text="Escolha as imagens e clique em Aplicar blending",
                                        fg_color=ui.FUNDO, text_color=ui.SUAVE, font=ui.fonte(15), corner_radius=0)
        self.image_label.grid(row=1, column=1, sticky="nsew")
        self.image_label.bind("<Configure>", lambda _e: self._exibir())
        rodape, self.status = ui.barra_status(self)
        rodape.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _build_painel(self):
        p = ctk.CTkScrollableFrame(self, width=300, corner_radius=0, fg_color=ui.PAINEL)
        p.grid(row=0, column=0, rowspan=2, sticky="ns")

        c = ui.Secao(p, "1 · Imagens")
        c.pack(fill="x", pady=4)
        for chave in PADROES:
            linha = ctk.CTkFrame(c.corpo, fg_color=ui.PAINEL, corner_radius=10)
            linha.pack(fill="x", pady=3)
            linha.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(linha, text=NOMES_CURTOS[chave], anchor="w", text_color=ui.TEXTO,
                         font=ui.fonte(12, "bold")).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
            lbl = ctk.CTkLabel(linha, text="-", anchor="w", text_color=ui.SUAVE, font=ui.fonte(11))
            lbl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
            self.rotulos_arquivo[chave] = lbl
            ui.botao(linha, "Escolher", lambda c=chave: self.escolher(c), height=30, width=84).grid(
                row=0, column=1, rowspan=2, padx=8)
        ctk.CTkLabel(c.corpo, text="A aparece onde a máscara vale 1; B, onde vale 0.", anchor="w", justify="left",
                     wraplength=250, text_color=ui.SUAVE, font=ui.fonte(11)).pack(fill="x", pady=(4, 0))
        ui.botao(c.corpo, "Usar imagens sugeridas (maçã + laranja)", self.usar_sugeridas).pack(fill="x", pady=(8, 0))

        c = ui.Secao(p, "2 · Máscara e pirâmide")
        c.pack(fill="x", pady=4)
        ui.rotulo_secao(c.corpo, "Origem da máscara", padx=0, pady=(0, 2))
        self.modo_mascara = ui.menu(c.corpo, [MASCARA_ARQUIVO, MASCARA_ESQ, MASCARA_DIR])
        self.modo_mascara.pack(fill="x")
        bloco, self.niveis = ui.campo(c.corpo, "Níveis da pirâmide", largura=60)
        self.niveis.insert(0, "5")
        self.niveis.bind("<KeyRelease>", self._texto_niveis)
        self.slider_niveis = ui.slider(bloco, 1, MAX_NIVEIS, MAX_NIVEIS - 1, self._slider_niveis)
        self.slider_niveis.set(5)
        # o blending só é refeito ao soltar o slider (durante o arrasto só o número muda)
        self.slider_niveis.bind("<ButtonRelease-1>", lambda _e: self.aplicar() if self.resultados else None, add="+")

        ui.botao(p, "Aplicar blending", self.aplicar, "primario", height=44).pack(fill="x", pady=(10, 14))

    # ---------- níveis ----------
    def _slider_niveis(self, v):
        self.niveis.delete(0, "end")
        self.niveis.insert(0, str(int(round(v))))

    def _texto_niveis(self, _ev=None):
        try:
            self.slider_niveis.set(min(max(int(self.niveis.get()), 1), MAX_NIVEIS))
        except ValueError:
            pass

    # ---------- entrada ----------
    def _definir(self, chave, caminho):
        self.caminhos[chave] = caminho
        self.rotulos_arquivo[chave].configure(text=os.path.basename(caminho) if caminho else "-")

    def escolher(self, chave):
        caminho = filedialog.askopenfilename(title=ROTULOS[chave], filetypes=TIPOS)
        if caminho:
            self._definir(chave, caminho)
            if chave == "mascara":
                self.modo_mascara.set(MASCARA_ARQUIVO)

    def usar_sugeridas(self):
        for chave, nome in PADROES.items():
            c = os.path.normpath(os.path.join(PASTA_IMAGENS, nome))
            self._definir(chave, c if os.path.exists(c) else None)
        self.modo_mascara.set(MASCARA_ARQUIVO)
        if all(self.caminhos.values()):
            self.aplicar()

    # ---------- processamento ----------
    def _mascara(self, shape):
        h, w = shape
        modo = self.modo_mascara.get()
        if modo == MASCARA_ARQUIVO:
            if not self.caminhos["mascara"]:
                raise ValueError("Escolha a máscara ou use uma das máscaras automáticas.")
            m = np.asarray(Image.open(self.caminhos["mascara"]).convert("L").resize((w, h), Image.NEAREST), float)
            return (m / 255 > 0.5).astype(float)
        m = np.zeros((h, w))
        m[:, :w // 2] = 1
        return m if modo == MASCARA_ESQ else 1 - m

    def aplicar(self):
        try:
            if not (self.caminhos["a"] and self.caminhos["b"]):
                raise ValueError("Escolha as imagens A e B.")
            niveis = int(self.niveis.get())
            A = Image.open(self.caminhos["a"]).convert("RGB")
            a = np.asarray(A, float)
            b = np.asarray(Image.open(self.caminhos["b"]).convert("RGB").resize(A.size, Image.LANCZOS), float)
            m = self._mascara(a.shape[:2])
            maximo = int(np.log2(min(a.shape[:2]) / 4)) + 1
            if not 1 <= niveis <= maximo:
                raise ValueError(f"Níveis deve estar entre 1 e {maximo} para esta imagem.")
            mix = np.clip(piramides.blending(a, b, m, niveis), 0, 255)
            cola = piramides.justaposicao(a, b, m)
        except Exception as exc:
            return messagebox.showerror("Erro", str(exc))

        pa, pb, pm, pc, px = _pil(a), _pil(b), _pil(m * 255).convert("RGB"), _pil(cola), _pil(mix)
        diff = np.abs(mix - cola).mean(axis=2)
        pd = _pil(255 * (diff / diff.max() if diff.max() > 0 else diff)).convert("RGB")
        h, w = m.shape
        x = int(np.argmax(np.abs(np.diff(m.mean(axis=0))))) + 1 if m.min() != m.max() else w // 2
        box = (max(0, x - w // 4), h // 4, min(w, x + w // 4), 3 * h // 4)

        def zoom(im, t):
            return _rotular(im.crop(box).resize((w, h), Image.NEAREST), t)

        self.resultados = {
            "Comparação": _grade([_rotular(pa, "A"), _rotular(pb, "B"), _rotular(pm, "Máscara"),
                                  _rotular(pc, "Justaposição direta"),
                                  _rotular(px, f"Blending ({niveis} níveis)"),
                                  _rotular(pd, "|blending - justaposição|")], 3),
            "Blending": px, "Justaposição": pc,
            "Zoom da emenda": _grade([zoom(pc, "Justaposição"), zoom(px, "Blending")], 2),
            "Pirâmides": self._mosaico(a, m, niveis),
        }
        self.status.configure(text=f"Blending com {niveis} níveis  |  {w}x{h}")
        self._exibir()

    @staticmethod
    def _mosaico(a, m, niveis):
        """Pirâmide Gaussiana da máscara (cima) e Laplaciana de A (baixo), níveis lado a lado."""
        gm, la = piramides.piramide_gaussiana(m, niveis), piramides.piramide_laplaciana(a, niveis)
        linhas = [[_pil(g * 255).convert("RGB") for g in gm],
                  [_pil(l if i == niveis - 1 else l + 128) for i, l in enumerate(la)]]
        h = linhas[0][0].height
        tela = Image.new("RGB", (sum(i.width for i in linhas[0]), 2 * h), (60, 60, 60))
        for fila, linha in enumerate(linhas):
            x = 0
            for i, im in enumerate(linha):
                tela.paste(im, (x, fila * h))
                x += im.width
        return tela

    # ---------- exibição ----------
    def _exibir(self):
        img = self.resultados.get(self.visao.get())
        if img is None:
            return
        cw, ch = max(self.image_label.winfo_width(), 1), max(self.image_label.winfo_height(), 1)
        esc = min((cw - 40) / img.width, (ch - 40) / img.height)
        tam = (max(1, int(img.width * esc)), max(1, int(img.height * esc)))
        self._atual = img
        self._ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=tam)
        self.image_label.configure(image=self._ctk_image, text="")

    def salvar(self):
        if self._atual is None:
            return messagebox.showinfo("Aviso", "Aplique o blending primeiro.")
        caminho = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if caminho:
            self._atual.save(caminho)
