"""Aba "Formação de Imagem": projeção perspectiva x ortográfica escalada de um cubo."""
import math

import customtkinter as ctk
import numpy as np

import ui
from vc import formacao_imagem as fi

PERSPECTIVA, ORTOGRAFICA = "Perspectiva", "Ortográfica escalada"

# Faixa do slider de cada parâmetro (o campo de texto aceita qualquer valor).
LIMITES = {"fx": (100, 3000), "fy": (100, 3000), "cx": (0, 1280), "cy": (0, 720), "skew": (-500, 500),
           "escala": (10, 500), "tx": (-10, 10), "ty": (-10, 10), "tz": (0, 20),
           "rx": (-180, 180), "ry": (-180, 180), "rz": (-180, 180)}


class FormacaoImagemTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.vars = {}
        self._atualizando = False   # evita recursão ao sincronizar fx=fy
        self._ctk_image = None
        self._ultima = None         # última imagem PIL gerada

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_painel()

        self.image_label = ctk.CTkLabel(self, text="", fg_color=ui.FUNDO, corner_radius=0)
        self.image_label.grid(row=0, column=1, sticky="nsew")
        self.image_label.bind("<Configure>", lambda _e: self._exibir())
        self._arrasto = None   # (x, y) do último ponto do arrasto com o mouse
        self._esc = 1.0        # fator de exibição (pixels da tela / pixels do sensor)
        for ev, fn in (("<ButtonPress-1>", self._mouse_inicio), ("<ButtonPress-3>", self._mouse_inicio),
                       ("<B1-Motion>", self._mouse_gira), ("<B3-Motion>", self._mouse_translada),
                       ("<ButtonRelease-1>", self._mouse_fim), ("<ButtonRelease-3>", self._mouse_fim),
                       ("<MouseWheel>", self._mouse_roda)):
            self.image_label.bind(ev, fn)
        rodape, self.status = ui.barra_status(self)
        rodape.grid(row=1, column=0, columnspan=2, sticky="ew")

        self._trocar_modelo()

    # ---------- interface ----------
    def _campo(self, parent, chave, rotulo, valor):
        minimo, maximo = LIMITES[chave]
        bloco, entry = ui.campo(parent, rotulo, textvariable=(var := ctk.StringVar(value=f"{valor:g}")))
        slider = ui.slider(bloco, minimo, maximo, comando=lambda v: var.set(f"{round(v, 2):g}"))
        slider.set(valor)

        def ao_digitar(*_):
            try:
                slider.set(min(max(self._numero(var.get()), minimo), maximo))
            except ValueError:
                pass
            self._ao_alterar(chave)
        var.trace_add("write", ao_digitar)
        self.vars[chave] = var

    def _secao(self, titulo, aberta=True, pai=None):
        s = ui.Secao(pai or self.painel, titulo, aberta)
        s.pack(fill="x", pady=4)
        return s

    def _build_painel(self):
        self.painel = ctk.CTkScrollableFrame(self, width=300, corner_radius=0, fg_color=ui.PAINEL)
        self.painel.grid(row=0, column=0, sticky="ns")

        ui.rotulo_secao(self.painel, "Modelo de projeção", pady=(4, 4))
        self.modelo = ui.segmentado(self.painel, [PERSPECTIVA, ORTOGRAFICA], lambda _m: self._trocar_modelo())
        self.modelo.set(PERSPECTIVA)
        self.modelo.pack(fill="x", pady=(0, 6))

        ui.rotulo_secao(self.painel, "Resolução do sensor", pady=(8, 4))
        self.resolucao = ui.menu(self.painel, list(fi.RESOLUCOES), lambda _m: self._ao_trocar_resolucao())
        self.resolucao.pack(fill="x", pady=(0, 6))

        # Parâmetros específicos de cada modelo (apenas um fica visível por vez)
        self.area_modelo = ctk.CTkFrame(self.painel, fg_color="transparent")
        self.area_modelo.pack(fill="x")

        self.frame_persp = ui.Secao(self.area_modelo, "Parâmetros intrínsecos")
        corpo = self.frame_persp.corpo
        p = fi.PADRAO_PERSPECTIVA
        for chave, rot in (("fx", "fx"), ("fy", "fy"), ("cx", "cx"), ("cy", "cy"), ("skew", "skew")):
            self._campo(corpo, chave, rot, p[chave])
        self.igualar = ctk.CTkCheckBox(corpo, text="Manter fx = fy", command=self._ao_igualar,
                                       text_color=ui.TEXTO, fg_color=ui.ACENTO, hover_color=ui.ACENTO_H)
        self.igualar.select()
        self.igualar.pack(anchor="w", pady=8)
        ui.rotulo_secao(corpo, "Matriz K", padx=0, pady=(4, 2))
        self.k_label = ctk.CTkLabel(corpo, text="", justify="left", anchor="w", fg_color=ui.PAINEL,
                                    corner_radius=8, text_color=ui.TEXTO, font=ui.fonte_mono(12))
        self.k_label.pack(fill="x", ipadx=8, ipady=6)

        self.frame_orto = ui.Secao(self.area_modelo, "Parâmetros da ortográfica")
        self._campo(self.frame_orto.corpo, "escala", "Escala", fi.PADRAO_ESCALA)

        e = fi.PADRAO_EXTRINSECOS
        corpo = self._secao("Translação (extrínsecos)").corpo
        for chave, rot in (("tx", "tx"), ("ty", "ty"), ("tz", "tz")):
            self._campo(corpo, chave, rot, e[chave])
        corpo = self._secao("Rotação em graus (extrínsecos)").corpo
        for chave, rot in (("rx", "Rot. X (°)"), ("ry", "Rot. Y (°)"), ("rz", "Rot. Z (°)")):
            self._campo(corpo, chave, rot, e[chave])

        ui.botao(self.painel, "Restaurar valores iniciais", self.restaurar).pack(fill="x", pady=(10, 14))

    # ---------- eventos ----------
    def _trocar_modelo(self):
        self.frame_persp.pack_forget()
        self.frame_orto.pack_forget()
        (self.frame_persp if self.modelo.get() == PERSPECTIVA else self.frame_orto).pack(fill="x", pady=4)
        self._atualizar()

    def _ao_trocar_resolucao(self):
        """Move o ponto principal (cx, cy) para o centro do novo sensor."""
        w, h = fi.RESOLUCOES[self.resolucao.get()]
        self._atualizando = True
        self.vars["cx"].set(f"{w / 2:g}")
        self.vars["cy"].set(f"{h / 2:g}")
        self._atualizando = False
        self._atualizar()

    def _ao_igualar(self):
        if self.igualar.get():
            self.vars["fy"].set(self.vars["fx"].get())
        self._atualizar()

    def _ao_alterar(self, chave):
        if self._atualizando:
            return
        if self.igualar.get() and chave in ("fx", "fy"):
            outro = "fy" if chave == "fx" else "fx"
            self._atualizando = True
            self.vars[outro].set(self.vars[chave].get())
            self._atualizando = False
        self._atualizar()

    def restaurar(self):
        self._atualizando = True
        valores = {**fi.PADRAO_PERSPECTIVA, **fi.PADRAO_EXTRINSECOS, "escala": fi.PADRAO_ESCALA}
        for chave, v in valores.items():
            self.vars[chave].set(f"{v:g}")
        self._atualizando = False
        self.modelo.set(PERSPECTIVA)
        self.resolucao.set("640 x 480")
        self.igualar.select()
        self._trocar_modelo()

    # ---------- interação com o mouse na imagem ----------
    # esquerdo: arrastar gira (X/Y), Shift+arrastar gira em Z | direito: arrasta transladando X/Y
    # roda: aproxima/afasta (tz)
    def _mouse_inicio(self, e):
        self._arrasto = (e.x, e.y)

    def _mouse_fim(self, _e):
        self._arrasto = None

    def _delta(self, e):
        if self._arrasto is None:
            return None
        dx, dy = (e.x - self._arrasto[0]) / self._esc, (e.y - self._arrasto[1]) / self._esc
        self._arrasto = (e.x, e.y)
        return dx, dy

    def _somar(self, **incrementos):
        """Soma incrementos aos parâmetros e atualiza a imagem uma única vez."""
        self._atualizando = True
        try:
            for chave, inc in incrementos.items():
                v = self._valor(chave) + inc
                if chave in ("rx", "ry", "rz"):
                    v = (v + 180) % 360 - 180
                self.vars[chave].set(f"{round(v, 3):g}")
        except ValueError:
            pass
        finally:
            self._atualizando = False
        self._atualizar()

    def _mouse_gira(self, e):
        d = self._delta(e)
        if d is None:
            return
        k = 0.4  # graus por pixel
        if e.state & 0x1:  # Shift
            self._somar(rz=d[0] * k)
        else:
            self._somar(ry=-d[0] * k, rx=d[1] * k)

    def _mouse_translada(self, e):
        d = self._delta(e)
        if d is None:
            return
        try:
            if self.modelo.get() == PERSPECTIVA:
                m = self._valor("tz") / self._valor("fx")   # unidades do mundo por pixel na profundidade tz
            else:
                m = 1 / self._valor("escala")
        except (ValueError, ZeroDivisionError):
            return
        self._somar(tx=d[0] * m, ty=d[1] * m)

    def _mouse_roda(self, e):
        self._somar(tz=-0.5 if e.delta > 0 else 0.5)

    @staticmethod
    def _numero(texto):
        """Converte o texto em float finito; levanta ValueError para vazio, texto, nan ou inf."""
        v = float(texto.replace(",", "."))
        if not math.isfinite(v):
            raise ValueError("valor não finito")
        return v

    def _valor(self, chave):
        return self._numero(self.vars[chave].get())

    # ---------- geração da imagem ----------
    def _atualizar(self):
        if not hasattr(self, "frame_orto"):
            return
        persp = self.modelo.get() == PERSPECTIVA
        try:
            ext = {k: self._valor(k) for k in fi.PADRAO_EXTRINSECOS}
            if persp:
                intr = {k: self._valor(k) for k in fi.PADRAO_PERSPECTIVA}
                K = fi.matriz_intrinseca(**intr)
                self.k_label.configure(text=np.array2string(K, precision=2, suppress_small=True))
                escala = None
            else:
                intr, escala = None, self._valor("escala")
        except ValueError:
            self.status.configure(text="Valor inválido: use apenas números.")
            return
        res = fi.RESOLUCOES[self.resolucao.get()]
        v2d, segs = fi.projetar_cubo("perspectiva" if persp else "ortografica", res, ext, intr,
                                     escala if escala is not None else fi.PADRAO_ESCALA)
        self._ultima = fi.renderizar(v2d, segs, res)
        self.status.configure(text=f"{self.modelo.get()}  |  sensor {res[0]}x{res[1]} px")
        self._exibir()

    def _exibir(self):
        if self._ultima is None:
            return
        cw, ch = max(self.image_label.winfo_width(), 1), max(self.image_label.winfo_height(), 1)
        w, h = self._ultima.size
        esc = self._esc = min((cw - 40) / w, (ch - 40) / h, 1.0)
        tam = (max(int(w * esc), 1), max(int(h * esc), 1))
        self._ctk_image = ctk.CTkImage(light_image=self._ultima, dark_image=self._ultima, size=tam)
        self.image_label.configure(image=self._ctk_image)
