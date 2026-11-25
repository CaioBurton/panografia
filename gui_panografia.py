"""Aba "Panografia": costura de duas imagens por translação (Atividade 03)."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np
from PIL import Image

import ui
from costura import costurar, localizar, visoes

_BASE = os.path.dirname(os.path.abspath(__file__))
# Pastas onde img1/img2 são procuradas (as imagens não são versionadas nem entregues no zip).
PASTAS_IMAGENS = [os.path.join(_BASE, "images"), os.path.join(_BASE, "imagens")]
ROTULOS = {"a": "Imagem 1 (referência)", "b": "Imagem 2 (deslocada)"}
NOMES_CURTOS = {"a": "Imagem 1", "b": "Imagem 2"}
TIPOS = [("Imagens", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff")]
VISOES = ["Comparação", "Mosaico", "Justaposição", "Correspondências"]
MODOS = {"Blending linear": "linear", "Média simples": "media"}


class PanografiaTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.caminhos = {"a": None, "b": None}
        self.rotulos_arquivo = {}
        self.campos = {}
        self.resultados = {}
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

        self.image_label = ctk.CTkLabel(self, text="Escolha as imagens e clique em Costurar", fg_color=ui.FUNDO,
                                        text_color=ui.SUAVE, font=ui.fonte(15), corner_radius=0)
        self.image_label.grid(row=1, column=1, sticky="nsew")
        self.image_label.bind("<Configure>", lambda _e: self._exibir())
        rodape, self.status = ui.barra_status(self)
        rodape.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _build_painel(self):
        p = ctk.CTkScrollableFrame(self, width=300, corner_radius=0, fg_color=ui.PAINEL)
        p.grid(row=0, column=0, rowspan=2, sticky="ns")

        c = ui.Secao(p, "1 · Imagens")
        c.pack(fill="x", pady=4)
        for chave in ROTULOS:
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
        ctk.CTkLabel(c.corpo, text="A imagem 2 é deslocada por translação até coincidir com a imagem 1.",
                     anchor="w", justify="left", wraplength=250, text_color=ui.SUAVE,
                     font=ui.fonte(11)).pack(fill="x", pady=(4, 0))
        ui.botao(c.corpo, "Usar imagens sugeridas (img1 + img2)",
                 lambda: self.usar_sugeridas(perguntar=True)).pack(fill="x", pady=(8, 0))

        c = ui.Secao(p, "2 · Detecção e correspondência")
        c.pack(fill="x", pady=4)
        for chave, rotulo, padrao in (("max_pontos", "Máx. cantos", "800"), ("ncc_min", "NCC mínimo", "0.85"),
                                      ("limiar", "Limiar RANSAC (px)", "3")):
            _, e = ui.campo(c.corpo, rotulo)
            e.insert(0, padrao)
            self.campos[chave] = e

        c = ui.Secao(p, "3 · Mosaico")
        c.pack(fill="x", pady=4)
        ui.rotulo_secao(c.corpo, "Mescla na sobreposição", padx=0, pady=(0, 2))
        self.modo = ui.menu(c.corpo, list(MODOS))
        self.modo.pack(fill="x")

        ui.botao(p, "Costurar", self.aplicar, "primario", height=44).pack(fill="x", pady=(10, 14))

    # ---------- entrada ----------
    def _definir(self, chave, caminho):
        self.caminhos[chave] = caminho
        self.rotulos_arquivo[chave].configure(text=os.path.basename(caminho) if caminho else "-")

    def escolher(self, chave):
        caminho = filedialog.askopenfilename(title=ROTULOS[chave], filetypes=TIPOS)
        if caminho:
            self._definir(chave, caminho)

    @staticmethod
    def _achar(pastas):
        """Devolve {'a': img1, 'b': img2} se alguma das pastas tiver as duas imagens, senão None."""
        for pasta in pastas:
            try:
                return {"a": localizar(pasta, "img1"), "b": localizar(pasta, "img2")}
            except FileNotFoundError:
                continue
        return None

    def usar_sugeridas(self, perguntar=False):
        c = self._achar(PASTAS_IMAGENS)
        if c is None and perguntar:
            pasta = filedialog.askdirectory(title="Pasta com img1 e img2 (.jpg ou .png)")
            if pasta:
                c = self._achar([pasta])
                if c is None:
                    messagebox.showwarning("Imagens não encontradas",
                                           "A pasta escolhida não contém img1 e img2 (.jpg ou .png).")
        if c is None:
            self.image_label.configure(
                text="Imagens sugeridas não encontradas.\nColoque img1 e img2 na pasta 'images' ao lado do programa,\n"
                     "ou use 'Escolher' para selecionar as imagens 1 e 2.")
            return
        for chave, caminho in c.items():
            self._definir(chave, caminho)
        self.aplicar()

    # ---------- processamento ----------
    def aplicar(self):
        try:
            if not all(self.caminhos.values()):
                raise ValueError("Escolha as imagens 1 e 2.")
            a = np.asarray(Image.open(self.caminhos["a"]).convert("RGB"), float)
            b = np.asarray(Image.open(self.caminhos["b"]).convert("RGB"), float)
            res, mos, cola = costurar(a, b, MODOS[self.modo.get()], max_pontos=int(self.campos["max_pontos"].get()),
                                      ncc_min=float(self.campos["ncc_min"].get()),
                                      limiar=float(self.campos["limiar"].get()))
        except Exception as exc:
            return messagebox.showerror("Erro", str(exc))
        self.resultados = visoes(a, b, res, mos, cola)
        tx, ty = res["t"]
        self.status.configure(text=f"t = ({tx:.2f}, {ty:.2f})  |  inliers: {int(res['inliers'].sum())} de "
                                   f"{len(res['p1'])} correspondências  |  mosaico {mos.shape[1]}x{mos.shape[0]}")
        self._exibir()

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
            return messagebox.showinfo("Aviso", "Costure as imagens primeiro.")
        caminho = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if caminho:
            self._atual.save(caminho)
