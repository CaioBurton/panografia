"""Interface gráfica de visão computacional (CustomTkinter) sobre a biblioteca `vc`."""
import ast
import os
import time
from tkinter import filedialog, messagebox

import customtkinter as ctk
import numpy as np
from PIL import Image

import ui
from gui_blending import BlendingTab
from gui_formacao import FormacaoImagemTab
from registro import FUNCOES
from vc import aprendizado, filtros, otimizacao, transformacoes

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PESADOS = ("Mediana", "Média α-cortada", "Mediana ponderada")
FILTROS = ["Média (box)", "Média (imagem integral)", "Gaussiano", "Corner (separável)",
           "Mediana", "Média α-cortada", "Mediana ponderada"]
ABAS = ["Imagem", "Funções", "Formação de Imagem", "Blending (Pirâmides)"]
TEMAS = {"Escuro": "dark", "Claro": "light", "Sistema": "system"}
VISTAS = ["Resultado", "Original", "Lado a lado"]
TIPOS_IMAGEM = [("Imagens", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif"), ("Todos", "*.*")]


def formatar(res):
    if isinstance(res, tuple):
        return "\n\n".join(formatar(r) for r in res)
    if isinstance(res, np.ndarray) or isinstance(res, (list, float, np.floating)):
        return np.array2string(np.asarray(res), precision=4, suppress_small=True)
    return str(res)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Panografia — Visão Computacional")
        self.geometry("1280x820")
        self.minsize(960, 640)
        self.configure(fg_color=ui.FUNDO)

        self.original = None   # imagem original (PIL), nunca modificada
        self.current = None    # imagem atual (PIL)
        self._ctk_image = None
        self.entries = {}
        self.auto_var = ctk.BooleanVar(value=True)
        self.operacao_de = {}   # parâmetro -> operação reaplicada ao mover o slider
        self._base = None       # imagem de partida enquanto se arrastam sliders
        self._resultado = None  # última imagem produzida por um slider
        self._pendente = None   # id do after() do próximo reprocessamento agendado
        self.fun_atual = None
        self.fun_campos = []

        self._build_cabecalho()
        corpo = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        corpo.pack(fill="both", expand=True)
        corpo.grid_columnconfigure(0, weight=1)
        corpo.grid_rowconfigure(0, weight=1)
        self.paginas = {}
        for nome in ABAS:
            pagina = ctk.CTkFrame(corpo, fg_color="transparent", corner_radius=0)
            pagina.grid(row=0, column=0, sticky="nsew")
            self.paginas[nome] = pagina

        tab_img = self.paginas["Imagem"]
        tab_img.grid_columnconfigure(1, weight=1)
        tab_img.grid_rowconfigure(1, weight=1)
        self._build_sidebar(tab_img)
        self._build_area_imagem(tab_img)

        self._build_funcoes(self.paginas["Funções"])

        FormacaoImagemTab(self.paginas["Formação de Imagem"]).pack(fill="both", expand=True)
        BlendingTab(self.paginas["Blending (Pirâmides)"]).pack(fill="both", expand=True)

        self.mostrar_aba("Imagem")
        self.bind("<Control-o>", lambda _e: self.load_image())
        self.bind("<Control-s>", lambda _e: self.save_image())
        self.bind("<Control-r>", lambda _e: self.restore_image())

    # ---------- construção da interface ----------
    def _build_cabecalho(self):
        cab = ctk.CTkFrame(self, fg_color=ui.PAINEL, corner_radius=0)
        cab.pack(fill="x")
        marca = ctk.CTkFrame(cab, fg_color="transparent")
        marca.pack(side="left", padx=(16, 12), pady=10)
        ctk.CTkLabel(marca, text="P", width=30, height=30, corner_radius=8, fg_color=ui.ACENTO,
                     text_color=ui.BRANCO, font=ui.fonte(15, "bold")).pack(side="left")
        ctk.CTkLabel(marca, text="Panografia", font=ui.fonte(15, "bold"), text_color=ui.TEXTO).pack(
            side="left", padx=(10, 0))

        self.nav = ui.segmentado(cab, ABAS, self.mostrar_aba)
        self.nav.pack(side="left", padx=8, pady=10)

        self.tema_menu = ui.menu(cab, list(TEMAS), lambda t: ctk.set_appearance_mode(TEMAS[t]), width=100)
        self.tema_menu.pack(side="right", padx=(6, 16), pady=10)
        ui.botao(cab, "Salvar  Ctrl+S", self.save_image, "primario", width=130).pack(side="right", padx=4, pady=10)
        ui.botao(cab, "Abrir  Ctrl+O", self.load_image, width=120).pack(side="right", padx=4, pady=10)
        ctk.CTkFrame(self, height=1, fg_color=ui.BORDA, corner_radius=0).pack(fill="x")

    def mostrar_aba(self, nome):
        self.paginas[nome].tkraise()
        self.nav.set(nome)

    def _build_area_imagem(self, tab):
        barra = ctk.CTkFrame(tab, fg_color=ui.FUNDO, corner_radius=0)
        barra.grid(row=0, column=1, sticky="ew")
        self.arquivo_label = ctk.CTkLabel(barra, text="Nenhuma imagem", anchor="w", text_color=ui.TEXTO,
                                          font=ui.fonte(13, "bold"))
        self.arquivo_label.pack(side="left", padx=16, pady=10)
        self.info_label = ctk.CTkLabel(barra, text="", anchor="w", text_color=ui.SUAVE, font=ui.fonte_mono(12))
        self.info_label.pack(side="left")
        self.vista = ui.segmentado(barra, VISTAS, lambda _v: self.show())
        self.vista.set(VISTAS[0])
        self.vista.pack(side="right", padx=16, pady=8)

        self.image_label = ctk.CTkLabel(tab, text="Abra uma imagem (Ctrl+O) para começar", fg_color=ui.FUNDO,
                                        text_color=ui.SUAVE, font=ui.fonte(15), corner_radius=0)
        self.image_label.grid(row=1, column=1, sticky="nsew")
        self.image_label.bind("<Configure>", lambda _e: self.show())

        rodape, self.status = ui.barra_status(tab)
        rodape.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status.configure(text="Nenhuma imagem carregada.")

    def _botao(self, parent, texto, cmd, estilo="padrao", **kw):
        ui.botao(parent, texto, cmd, estilo, **kw).pack(fill="x", pady=(8, 0))

    def _campo(self, parent, chave, rotulo, padrao, faixa=None, passos=None):
        """Campo de texto; com `faixa=(min, max)` ganha também um slider sincronizado.
        `passos` = número de divisões do slider (None = contínuo)."""
        bloco, e = ui.campo(parent, rotulo, largura=76 if faixa else 150)
        e.insert(0, padrao)
        self.entries[chave] = e
        if faixa is None:
            return
        lo, hi = faixa
        sl = ui.slider(bloco, lo, hi, passos)
        try:
            sl.set(min(max(float(padrao), lo), hi))
        except ValueError:
            pass

        def do_slider(v):
            e.delete(0, "end")
            e.insert(0, f"{round(v, 3):g}")
            self._agendar(chave)

        def do_texto(_ev=None):
            try:
                sl.set(min(max(float(e.get().replace(",", ".")), lo), hi))
            except ValueError:
                pass
        sl.configure(command=do_slider)
        sl.bind("<ButtonRelease-1>", lambda _e: self._agendar(chave, final=True), add="+")
        e.bind("<KeyRelease>", do_texto)

    def _pesado(self, chave):
        """Operações cujo custo cresce muito com o parâmetro: só são refeitas ao soltar o slider."""
        if chave in ("kc", "icm_s"):
            return True
        return chave in ("k", "alpha") and self.filtro_menu.get() in PESADOS

    def _agendar(self, chave, final=False):
        """Com 'Aplicar ao mover' ligado, refaz a operação. Durante o arrasto as chamadas são agrupadas
        (no máximo uma a cada ~80 ms) e as operações pesadas esperam o slider ser solto."""
        if not self.auto_var.get() or self.operacao_de.get(chave) is None:
            return
        if self._pendente is not None:
            self.after_cancel(self._pendente)
            self._pendente = None
        if final:
            self._reaplicar(chave)
        elif not self._pesado(chave):
            self._pendente = self.after(80, lambda: (setattr(self, "_pendente", None), self._reaplicar(chave)))

    def _reaplicar(self, chave):
        """Refaz a operação do parâmetro a partir da imagem anterior ao ajuste."""
        op = self.operacao_de.get(chave)
        if op is None or self.current is None:
            return
        if self.current is not self._resultado:   # a imagem mudou por outra operação: novo ponto de partida
            self._base = self.current
        self.current = self._base
        op()
        self._resultado = self.current
        self.update_idletasks()

    def _build_sidebar(self, parent):
        side = ctk.CTkScrollableFrame(parent, width=300, corner_radius=0, fg_color=ui.PAINEL)
        side.grid(row=0, column=0, rowspan=2, sticky="ns")

        acoes = ctk.CTkFrame(side, fg_color="transparent")
        acoes.pack(fill="x", pady=(4, 8))
        for col, (txt, cmd) in enumerate((("Restaurar", self.restore_image), ("Cinza", self.op_cinza),
                                          ("Zerar", self.zero_image))):
            acoes.grid_columnconfigure(col, weight=1, uniform="acoes")
            ui.botao(acoes, txt, cmd, height=40).grid(row=0, column=col, sticky="ew", padx=3)

        card = ctk.CTkFrame(side, fg_color=ui.FUNDO, border_width=1, border_color=ui.BORDA, corner_radius=12)
        card.pack(fill="x", pady=(0, 8))
        ctk.CTkSwitch(card, text="Aplicar ao mover o slider", variable=self.auto_var, text_color=ui.TEXTO,
                      progress_color=ui.ACENTO, font=ui.fonte(13)).pack(fill="x", padx=14, pady=12)

        def secao(titulo, aberta=False):
            s = ui.Secao(side, titulo, aberta)
            s.pack(fill="x", pady=4)
            return s.corpo

        c = secao("Filtros", True)
        self.filtro_menu = ui.menu(c, FILTROS)
        self.filtro_menu.pack(fill="x", pady=(0, 4))
        self._campo(c, "k", "Janela k", "3", (3, 31), 14)
        self._campo(c, "alpha", "α (cortada)", "2", (0, 24), 12)
        self._botao(c, "Aplicar filtro", self.op_filtro, "primario")

        c = secao("Transformação geométrica", True)
        self._campo(c, "s", "Escala", "1.0", (0.1, 4))
        self._campo(c, "theta", "Ângulo (°)", "0", (-180, 180))
        self._campo(c, "tx", "Transl. x", "0", (-300, 300))
        self._campo(c, "ty", "Transl. y", "0", (-300, 300))
        self.interp_menu = ui.menu(c, ["bilinear", "vizinho"])
        self.interp_menu.pack(fill="x", pady=(6, 0))
        self._botao(c, "Aplicar transformação", self.op_transformar, "primario")

        c = secao("Reamostragem")
        self._campo(c, "r", "Fator r", "2", (2, 8), 6)
        self._botao(c, "Aumentar resolução", lambda: self.op_reamostrar(True))
        self._botao(c, "Diminuir resolução", lambda: self.op_reamostrar(False))

        c = secao("Distorção radial")
        self._campo(c, "k1", "k1", "0.1", (-1, 1))
        self._campo(c, "k2", "k2", "0.0", (-1, 1))
        self._botao(c, "Corrigir distorção", self.op_distorcao, "primario")

        c = secao("Composição (Over)")
        self._campo(c, "over_a", "α", "0.5", (0, 1))
        self._botao(c, "Compor com imagem de frente...", self.op_over)

        c = secao("Imagem integral")
        self._campo(c, "ret", "i0,j0,i1,j1", "0,0,10,10")
        self._botao(c, "Soma no retângulo", self.op_soma_retangulo)

        c = secao("Segmentação / MRF")
        self._campo(c, "kc", "Clusters k", "3", (2, 10), 8)
        self._botao(c, "Segmentar (k-means)", self.op_kmeans)
        self._campo(c, "icm_s", "Suavidade s", "0.3", (0, 2))
        self._botao(c, "Binarizar + limpar (ICM)", self.op_icm)

        for chaves, op in ((("k", "alpha"), self.op_filtro), (("s", "theta", "tx", "ty"), self.op_transformar),
                           (("k1", "k2"), self.op_distorcao), (("kc",), self.op_kmeans), (("icm_s",), self.op_icm)):
            for ch in chaves:
                self.operacao_de[ch] = op

    # ---------- aba Funções ----------
    def _build_funcoes(self, parent):
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        lateral = ctk.CTkFrame(parent, fg_color=ui.PAINEL, corner_radius=0, width=310)
        lateral.grid(row=0, column=0, sticky="ns")
        lateral.pack_propagate(False)
        self.busca = ctk.StringVar()
        self.busca.trace_add("write", lambda *_: self._listar_funcoes())
        ctk.CTkEntry(lateral, textvariable=self.busca, placeholder_text="Buscar função…", height=38,
                     corner_radius=10, fg_color=ui.FUNDO, border_color=ui.BORDA, text_color=ui.TEXTO,
                     font=ui.fonte(13)).pack(fill="x", padx=14, pady=(14, 8))
        categorias = []
        for cat, *_ in FUNCOES:
            if cat not in categorias:
                categorias.append(cat)
        self.cat_menu = ui.menu(lateral, ["Todas as categorias"] + categorias, lambda _c: self._listar_funcoes())
        self.cat_menu.pack(fill="x", padx=14, pady=(0, 8))
        self.fun_lista = ctk.CTkScrollableFrame(lateral, fg_color="transparent", corner_radius=0)
        self.fun_lista.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        direita = ctk.CTkFrame(parent, fg_color=ui.FUNDO, corner_radius=0)
        direita.grid(row=0, column=1, sticky="nsew")
        direita.grid_columnconfigure(0, weight=1)
        direita.grid_rowconfigure(4, weight=1)
        self.fun_categoria = ctk.CTkLabel(direita, text="", anchor="w", fg_color=ui.CARTAO, corner_radius=10,
                                          text_color=ui.SUAVE, font=ui.fonte(11, "bold"), padx=10)
        self.fun_categoria.grid(row=0, column=0, sticky="w", padx=28, pady=(26, 4))
        self.fun_titulo = ctk.CTkLabel(direita, text="Selecione uma função", anchor="w", text_color=ui.TEXTO,
                                       font=ui.fonte_mono(22, "bold"))
        self.fun_titulo.grid(row=1, column=0, sticky="ew", padx=28)
        self.fun_doc = ctk.CTkLabel(direita, text="Escolha uma função na lista para ver os parâmetros.",
                                    anchor="w", justify="left", wraplength=760, text_color=ui.SUAVE,
                                    font=ui.fonte(13))
        self.fun_doc.grid(row=2, column=0, sticky="ew", padx=28, pady=(4, 14))
        self.fun_params = ctk.CTkFrame(direita, fg_color=ui.PAINEL, border_width=1, border_color=ui.BORDA,
                                       corner_radius=14)
        self.fun_params.grid(row=3, column=0, sticky="ew", padx=28)
        self.fun_params.grid_columnconfigure(1, weight=1)

        res = ctk.CTkFrame(direita, fg_color=ui.PAINEL, border_width=1, border_color=ui.BORDA, corner_radius=14)
        res.grid(row=4, column=0, sticky="nsew", padx=28, pady=14)
        res.grid_columnconfigure(0, weight=1)
        res.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(res, text="Resultado", anchor="w", text_color=ui.TEXTO, font=ui.fonte(13, "bold")).grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 4))
        ui.botao(res, "Copiar", self.copiar_resultado, height=30, width=80).grid(
            row=0, column=1, padx=14, pady=(14, 4))
        self.fun_saida = ctk.CTkTextbox(res, font=ui.fonte_mono(14), fg_color=ui.FUNDO, text_color=ui.OK,
                                        border_width=1, border_color=ui.BORDA, corner_radius=10)
        self.fun_saida.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=14, pady=4)
        self.fun_status = ctk.CTkLabel(res, text="", anchor="w", text_color=ui.SUAVE, font=ui.fonte(12))
        self.fun_status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(2, 12))
        self._listar_funcoes()

    def _listar_funcoes(self):
        """Refaz a lista lateral aplicando a busca, a categoria e o destaque da função atual."""
        for w in self.fun_lista.winfo_children():
            w.destroy()
        termo = self.busca.get().strip().lower()
        so_cat = self.cat_menu.get()
        cat = None
        for i, (categoria, nome, _fn, _p) in enumerate(FUNCOES):
            if (so_cat != "Todas as categorias" and categoria != so_cat) or termo not in nome.lower():
                continue
            if categoria != cat:
                cat = categoria
                ui.rotulo_secao(self.fun_lista, categoria, padx=8, pady=(12, 2))
            ativo = i == self.fun_atual
            ctk.CTkButton(self.fun_lista, text=nome, anchor="w", height=34, corner_radius=8,
                          fg_color=ui.SEL if ativo else "transparent", hover_color=ui.CARTAO,
                          text_color=ui.TEXTO, font=ui.fonte_mono(12, "bold" if ativo else "normal"),
                          command=lambda i=i: self.selecionar_funcao(i)).pack(fill="x", pady=1)

    def selecionar_funcao(self, i):
        categoria, nome, fn, params = FUNCOES[i]
        self.fun_atual = i
        self.fun_categoria.configure(text=categoria.upper())
        self.fun_titulo.configure(text=nome)
        self.fun_doc.configure(text=(fn.__doc__ or "").strip() or "Sem descrição.")
        for w in self.fun_params.winfo_children():
            w.destroy()
        self.fun_campos = []
        for r, (pnome, padrao) in enumerate(params):
            ctk.CTkLabel(self.fun_params, text=pnome, anchor="w", width=110, text_color=ui.SUAVE,
                         font=ui.fonte_mono(12)).grid(row=r, column=0, padx=(18, 8), pady=(14 if r == 0 else 4, 4))
            e = ui.entrada(self.fun_params, height=36)
            e.insert(0, padrao)
            e.grid(row=r, column=1, sticky="ew", padx=(0, 18), pady=(14 if r == 0 else 4, 4))
            self.fun_campos.append(e)
        botoes = ctk.CTkFrame(self.fun_params, fg_color="transparent")
        botoes.grid(row=len(params), column=0, columnspan=2, sticky="w", padx=18, pady=(10, 16))
        ui.botao(botoes, "▶  Calcular", self.calcular_funcao, "primario", width=130, height=38).pack(side="left")
        ui.botao(botoes, "Limpar", self._limpar_saida, width=90, height=38).pack(side="left", padx=8)
        self._limpar_saida()
        self._listar_funcoes()

    def _limpar_saida(self):
        self.fun_saida.delete("1.0", "end")
        self.fun_status.configure(text="", text_color=ui.SUAVE)

    def copiar_resultado(self):
        texto = self.fun_saida.get("1.0", "end").strip()
        if texto:
            self.clipboard_clear()
            self.clipboard_append(texto)
            self.fun_status.configure(text="Resultado copiado.", text_color=ui.SUAVE)

    def calcular_funcao(self):
        if self.fun_atual is None:
            return
        _cat, _nome, fn, params = FUNCOES[self.fun_atual]
        try:
            args = [ast.literal_eval(e.get().strip()) for e in self.fun_campos]
            res = fn(*args)
            texto, ok = formatar(res), True
        except Exception as exc:
            texto, ok = f"Erro: {exc}", False
        self.fun_saida.delete("1.0", "end")
        self.fun_saida.insert("end", texto)
        self.fun_saida.configure(text_color=ui.OK if ok else ui.ERRO)
        self.fun_status.configure(text="● Executado sem erros" if ok else "● A função falhou",
                                  text_color=ui.OK if ok else ui.ERRO)

    # ---------- arquivo e operações básicas ----------
    def load_image(self):
        path = filedialog.askopenfilename(
            title="Abrir imagem",
            filetypes=TIPOS_IMAGEM,
        )
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível abrir a imagem:\n{exc}")
            return
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        self.original = img
        self.current = img.copy()
        self.arquivo_label.configure(text=os.path.basename(path))
        self.info_label.configure(text=f"{img.width} × {img.height} · {img.mode}")
        self.status.configure(text=f"{path}  |  {img.width}x{img.height}  |  modo {img.mode}")
        self._mostrar_resultado()

    def save_image(self):
        if not self._has_image():
            return
        path = filedialog.asksaveasfilename(
            title="Salvar imagem",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"), ("BMP", "*.bmp"), ("TIFF", "*.tif *.tiff")],
        )
        if not path:
            return
        try:
            self.current.save(path)
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível salvar:\n{exc}")
            return
        self.status.configure(text=f"Imagem salva em {path}")

    def zero_image(self):
        """Atribui intensidade zero a todos os pixels."""
        if not self._has_image():
            return
        self.current = Image.new(self.current.mode, self.current.size, 0)
        self.status.configure(text="Todos os pixels com intensidade 0.")
        self._mostrar_resultado()

    def restore_image(self):
        """Retorna à imagem original."""
        if not self._has_image():
            return
        self.current = self.original.copy()
        self.status.configure(text="Imagem original restaurada.")
        self._mostrar_resultado()

    # ---------- operações com a biblioteca ----------
    def _num(self, chave, tipo=float):
        return tipo(self.entries[chave].get().replace(",", "."))

    def _array(self):
        return np.asarray(self.current, dtype=float)

    def _aplicar(self, fn, msg, normalizar=False):
        """Executa fn(array) -> array e exibe o resultado como imagem."""
        if not self._has_image():
            return
        t0 = time.perf_counter()
        try:
            res = np.asarray(fn(self._array()), float)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        if normalizar:
            res = np.abs(res)
            res = res * (255 / res.max()) if res.max() > 0 else res
        self.current = Image.fromarray(np.clip(np.rint(res), 0, 255).astype(np.uint8))
        self.status.configure(text=f"{msg}  |  {self.current.width}x{self.current.height}  |  "
                                   f"{time.perf_counter() - t0:.2f} s")
        self._mostrar_resultado()

    def op_cinza(self):
        if not self._has_image():
            return
        self.current = self.current.convert("L")
        self.status.configure(text="Convertida para escala de cinza.")
        self._mostrar_resultado()

    def op_filtro(self):
        nome = self.filtro_menu.get()
        try:
            k, alpha = self._num("k", int), self._num("alpha", int)
        except ValueError:
            return messagebox.showerror("Erro", "Parâmetros inválidos.")
        if k % 2 == 0 and nome != "Corner (separável)":
            return messagebox.showerror("Erro", "A janela k deve ser ímpar.")
        # modo "reflect" evita escurecimento nas bordas
        def f(a):
            if nome == "Média (box)":
                h = np.full(k, 1.0 / k)   # média é separável: O(k) por pixel em vez de O(k²)
                return filtros.filtro_separavel(a, h, h, "reflect")
            if nome == "Média (imagem integral)":
                return filtros.filtro_media_integral(a, k)
            if nome == "Gaussiano":
                h = filtros.nucleo_gaussiano(k).sum(axis=1)   # núcleo 1D (o 2D é h hᵀ)
                return filtros.filtro_separavel(a, h, h, "reflect")
            if nome == "Corner (separável)":
                return filtros.filtro_separavel(a, filtros.H_CORNER, filtros.H_CORNER, "reflect")
            if nome == "Mediana":
                return filtros.mediana(a, k, "reflect")
            if nome == "Média α-cortada":
                return filtros.media_alfa_cortada(a, k, alpha, "reflect")
            return filtros.mediana_ponderada(a, filtros.nucleo_binomial(k) * (2 ** (2 * (k - 1))), "reflect")
        self._aplicar(f, f"Filtro: {nome}", normalizar=(nome == "Corner (separável)"))

    def op_transformar(self):
        try:
            s, th, tx, ty = (self._num(c) for c in ("s", "theta", "tx", "ty"))
        except ValueError:
            return messagebox.showerror("Erro", "Parâmetros inválidos.")
        interp = self.interp_menu.get()
        if not self._has_image():
            return
        M = transformacoes.similaridade_centrada(self._array().shape[:2], s, th, (tx, ty))
        self._aplicar(lambda a: transformacoes.transformar_imagem(a, M, interpolacao=interp),
                      f"Similaridade s={s:g}, θ={th:g}°, t=({tx:g},{ty:g})")

    def op_reamostrar(self, aumentar):
        try:
            r = self._num("r", int)
            if r < 2:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Erro", "O fator r deve ser um inteiro >= 2.")
        fn = transformacoes.aumentar_resolucao if aumentar else transformacoes.diminuir_resolucao
        self._aplicar(lambda a: fn(a, r), f"{'Aumento' if aumentar else 'Redução'} de resolução (r={r})")

    def op_distorcao(self):
        try:
            k1, k2 = self._num("k1"), self._num("k2")
        except ValueError:
            return messagebox.showerror("Erro", "Parâmetros inválidos.")
        self._aplicar(lambda a: transformacoes.corrigir_distorcao_radial(a, k1, k2),
                      f"Distorção radial k1={k1:g}, k2={k2:g}")

    def op_over(self):
        if not self._has_image():
            return
        try:
            alpha = self._num("over_a")
        except ValueError:
            return messagebox.showerror("Erro", "α inválido.")
        path = filedialog.askopenfilename(title="Imagem de frente",
                                          filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif")])
        if not path:
            return
        try:
            frente = Image.open(path).convert(self.current.mode).resize(self.current.size)
        except Exception as exc:
            return messagebox.showerror("Erro", f"Não foi possível abrir a imagem:\n{exc}")
        F = np.asarray(frente, float)
        self._aplicar(lambda a: transformacoes.composicao_over(F, a, alpha), f"Over (α={alpha:g})")

    def op_soma_retangulo(self):
        if not self._has_image():
            return
        try:
            i0, j0, i1, j1 = (int(v) for v in self.entries["ret"].get().split(","))
            g = np.asarray(self.current.convert("L"), float)
            if not (0 <= i0 <= i1 < g.shape[0] and 0 <= j0 <= j1 < g.shape[1]):
                raise ValueError("Retângulo fora da imagem.")
            soma = filtros.soma_retangulo(filtros.imagem_integral(g), i0, j0, i1, j1)
        except Exception as exc:
            return messagebox.showerror("Erro", f"Use 'i0,j0,i1,j1' (linha, coluna) dentro da imagem.\n{exc}")
        self.status.configure(text=f"Soma dos pixels (cinza) em [{i0},{j0}]-[{i1},{j1}] = {soma:g}")

    def op_kmeans(self):
        try:
            k = self._num("kc", int)
        except ValueError:
            return messagebox.showerror("Erro", "k inválido.")
        self._aplicar(lambda a: aprendizado.segmentar_imagem_kmeans(a, k), f"K-means (k={k})")

    def op_icm(self):
        try:
            s = self._num("icm_s")
        except ValueError:
            return messagebox.showerror("Erro", "s inválido.")

        def f(a):
            g = a if a.ndim == 2 else a.mean(axis=2)
            return otimizacao.restaurar_icm(g > g.mean(), s=s) * 255
        self._aplicar(f, f"Binarização + ICM (s={s:g})")

    # ---------- utilitários ----------
    def _has_image(self):
        if self.current is None:
            messagebox.showinfo("Aviso", "Carregue uma imagem primeiro.")
            return False
        return True

    def _mostrar_resultado(self):
        """Volta à vista 'Resultado' e exibe a imagem atual (chamado após cada operação)."""
        self.vista.set(VISTAS[0])
        self.show()

    def _imagem_da_vista(self):
        vista = self.vista.get()
        if vista == "Original" and self.original is not None:
            return self.original
        if vista == "Lado a lado" and self.original is not None:
            h = max(self.original.height, self.current.height)
            lados = [im.convert("RGB").resize((max(1, round(im.width * h / im.height)), h))
                     for im in (self.original, self.current)]
            tela = Image.new("RGB", (lados[0].width + lados[1].width + 8, h), (45, 50, 66))
            tela.paste(lados[0], (0, 0))
            tela.paste(lados[1], (lados[0].width + 8, 0))
            return tela
        return self.current

    def show(self):
        """Exibe a imagem da vista escolhida ajustada ao tamanho da área central."""
        if self.current is None:
            return
        img = self._imagem_da_vista()
        cw, ch = max(self.image_label.winfo_width(), 1), max(self.image_label.winfo_height(), 1)
        scale = min((cw - 40) / img.width, (ch - 40) / img.height, 1.0)
        size = (max(int(img.width * scale), 1), max(int(img.height * scale), 1))
        self._ctk_image = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        self.image_label.configure(image=self._ctk_image, text="")


if __name__ == "__main__":
    App().mainloop()
