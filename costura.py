"""Atividade 03 - panografia por translação (costura de duas imagens).

Uso:  python costura.py [img1] [img2] [pasta_saida]
Imprime t = (tx, ty) e o número de inliers; gera mosaico.jpg, justaposicao.png, correspondencias.png e
comparacao.png. Por padrão usa images/img1 e images/img2 (.jpg ou .png).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

from vc import panografia

BASE = os.path.dirname(os.path.abspath(__file__))


def pil(arr):
    return Image.fromarray(np.clip(np.rint(arr), 0, 255).astype(np.uint8))


def rotular(img, texto):
    img = img.copy()
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8 + 7 * len(texto), 18), fill=(0, 0, 0))
    d.text((4, 3), texto, fill=(255, 255, 255))
    return img


def desenhar_correspondencias(img1, img2, res):
    """Imagens lado a lado; inliers em verde e outliers em vermelho."""
    a, b = np.asarray(img1, float), np.asarray(img2, float)
    tela = pil(panografia.justaposicao(a, b))
    d = ImageDraw.Draw(tela)
    w = a.shape[1]
    for p, q, ok in zip(res["p1"], res["p2"], res["inliers"]):
        d.line((p[0], p[1], q[0] + w, q[1]), fill=(0, 220, 0) if ok else (255, 0, 0), width=1)
    return tela


def costurar(a, b, modo="linear", **kw):
    """Roda o pipeline completo; retorna (resultado do alinhamento, mosaico, justaposição) em arrays."""
    res = panografia.alinhar(a, b, **kw)
    return res, panografia.mosaico(a, b, res["t"], modo), panografia.justaposicao(a, b)


def visoes(a, b, res, mos, cola):
    """Dicionário visão -> imagem PIL (usado pela linha de comando e pela interface)."""
    tx, ty = res["t"]
    pm, pc, pk = pil(mos), pil(cola), desenhar_correspondencias(a, b, res)
    largura = max(pm.width, pc.width, pk.width)
    comp = Image.new("RGB", (largura, pm.height + pc.height + pk.height), "white")
    y = 0
    for im, t in ((pm, f"Mosaico  t = ({tx:.2f}, {ty:.2f})  inliers = {int(res['inliers'].sum())}"),
                  (pc, "Justaposição direta (sem alinhamento)"),
                  (pk, "Correspondências (verde = inlier, vermelho = outlier)")):
        comp.paste(rotular(im, t), (0, y))
        y += im.height
    return {"Comparação": comp, "Mosaico": pm, "Justaposição": pc, "Correspondências": pk}


def localizar(base, nome):
    for ext in (".jpg", ".png", ".jpeg"):
        c = os.path.join(base, nome + ext)
        if os.path.exists(c):
            return c
    raise FileNotFoundError(f"{nome}.jpg/.png não encontrado em {base}")


def main(c1, c2, saida):
    os.makedirs(saida, exist_ok=True)
    a = np.asarray(Image.open(c1).convert("RGB"), float)
    b = np.asarray(Image.open(c2).convert("RGB"), float)
    res, mos, cola = costurar(a, b)
    tx, ty = res["t"]
    print(f"Pontos detectados: {len(res['pontos1'])} (img1), {len(res['pontos2'])} (img2)")
    print(f"Correspondências candidatas: {len(res['p1'])}")
    print(f"Translação estimada: t = (tx, ty) = ({tx:.2f}, {ty:.2f})")
    print(f"Inliers: {int(res['inliers'].sum())} de {len(res['p1'])}")
    v = visoes(a, b, res, mos, cola)
    pil(mos).save(os.path.join(saida, "mosaico.jpg"), quality=95)
    v["Justaposição"].save(os.path.join(saida, "justaposicao.png"))
    v["Correspondências"].save(os.path.join(saida, "correspondencias.png"))
    v["Comparação"].save(os.path.join(saida, "comparacao.png"))
    print(f"Resultados em {saida}")


if __name__ == "__main__":
    pasta = os.path.join(BASE, "images")
    main(sys.argv[1] if len(sys.argv) > 1 else localizar(pasta, "img1"),
         sys.argv[2] if len(sys.argv) > 2 else localizar(pasta, "img2"),
         sys.argv[3] if len(sys.argv) > 3 else os.path.join(BASE, "resultados_panografia"))
