"""Aba "Panografia": costura de duas imagens por translação (Atividade 03)."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np
from PIL import Image

from costura import costurar, localizar, visoes

PASTA_IMAGENS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
ROTULOS = {"a": "Imagem 1 (referência)", "b": "Imagem 2 (deslocada)"}
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
        self.grid_rowconfigure(0, weight=1)
        self._build_painel()
        self.image_label = ctk.CTkLabel(self, text="Escolha as imagens e clique em Costurar")
        self.image_label.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.image_label.bind("<Configure>", lambda _e: self._exibir())
        self.status = ctk.CTkLabel(self, text="", anchor="w")
        self.status.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
        self.usar_sugeridas()

    # ---------- interface ----------
    def _build_painel(self):
        p = ctk.CTkScrollableFrame(self, width=270, corner_radius=0)
        p.grid(row=0, column=0, sticky="ns")

        def secao(t):
            ctk.CTkLabel(p, text=t, anchor="w", text_color="gray").pack(fill="x", padx=10, pady=(14, 2))

        def campo(chave, rotulo, padrao):
            linha = ctk.CTkFrame(p, fg_color="transparent")
            linha.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(linha, text=rotulo, width=130, anchor="w").pack(side="left")
            e = ctk.CTkEntry(linha)
            e.insert(0, padrao)
            e.pack(side="left", fill="x", expand=True)
            self.campos[chave] = e

        secao("IMAGENS")
        for chave in ROTULOS:
            ctk.CTkButton(p, text=f"Escolher {ROTULOS[chave]}",
                          command=lambda c=chave: self.escolher(c)).pack(fill="x", padx=10, pady=(3, 0))
            lbl = ctk.CTkLabel(p, text="-", anchor="w", text_color="gray", font=ctk.CTkFont(size=11))
            lbl.pack(fill="x", padx=12)
            self.rotulos_arquivo[chave] = lbl
        ctk.CTkButton(p, text="Usar imagens sugeridas (images/)", fg_color="gray30", hover_color="gray40",
                      command=self.usar_sugeridas).pack(fill="x", padx=10, pady=(8, 3))

        secao("DETECÇÃO E CORRESPONDÊNCIA")
        campo("max_pontos", "Máx. cantos", "800")
        campo("ncc_min", "NCC mínimo", "0.85")
        campo("limiar", "Limiar RANSAC (px)", "3")

        secao("MOSAICO")
        self.modo = ctk.CTkOptionMenu(p, values=list(MODOS))
        self.modo.pack(fill="x", padx=10, pady=3)
        ctk.CTkButton(p, text="Costurar", command=self.aplicar).pack(fill="x", padx=10, pady=(10, 3))

        secao("VISUALIZAÇÃO")
        self.visao = ctk.CTkOptionMenu(p, values=VISOES, command=lambda _v: self._exibir())
        self.visao.pack(fill="x", padx=10, pady=3)
        ctk.CTkButton(p, text="Salvar visualização", command=self.salvar).pack(fill="x", padx=10, pady=(10, 3))

    # ---------- entrada ----------
    def _definir(self, chave, caminho):
        self.caminhos[chave] = caminho
        self.rotulos_arquivo[chave].configure(text=os.path.basename(caminho) if caminho else "-")

    def escolher(self, chave):
        caminho = filedialog.askopenfilename(title=ROTULOS[chave], filetypes=TIPOS)
        if caminho:
            self._definir(chave, caminho)

    def usar_sugeridas(self):
        for chave, nome in (("a", "img1"), ("b", "img2")):
            try:
                self._definir(chave, localizar(PASTA_IMAGENS, nome))
            except FileNotFoundError:
                self._definir(chave, None)
        if all(self.caminhos.values()):
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
        esc = min(cw / img.width, ch / img.height)
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
