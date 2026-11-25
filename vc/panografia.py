"""Panografia por translação: detecção de cantos (Harris), correspondência, RANSAC e mosaico.

As imagens são arrays NumPy (H, W) ou (H, W, C). Convenção: um ponto p2 da imagem 2 corresponde a
p1 = p2 + t no quadro da imagem 1, com pontos em coordenadas (x, y) = (coluna, linha) e t = (tx, ty).
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from . import filtros


def cinza(img):
    a = np.asarray(img, float)
    return a if a.ndim == 2 else a[..., :3] @ np.array([0.299, 0.587, 0.114])


# ---------- detecção ----------
def resposta_harris(img, sigma=1.5, k=0.04):
    """R = det(M) - k·tr(M)², com M = G_sigma * [Ix² IxIy; IxIy Iy²] e gradientes por diferença central."""
    g = cinza(img)
    iy, ix = np.gradient(g)
    n = int(2 * np.ceil(3 * sigma) + 1)
    w = filtros.nucleo_gaussiano(n, sigma)
    sxx, syy, sxy = (filtros.convolucao(v, w, "reflect") for v in (ix * ix, iy * iy, ix * iy))
    return sxx * syy - sxy ** 2 - k * (sxx + syy) ** 2


def detectar_cantos(img, max_pontos=800, raio_nms=6, margem=8, limiar_rel=0.01, sigma=1.5):
    """Pontos (x, y) de máximos locais de Harris (R > limiar_rel·Rmax), ordenados do mais forte ao mais fraco."""
    r = resposta_harris(img, sigma)
    H, W = r.shape
    t = 2 * raio_nms + 1
    maximo = sliding_window_view(np.pad(r, raio_nms, constant_values=-np.inf), (t, t)).max(axis=(-1, -2))
    ys, xs = np.nonzero((r >= maximo) & (r > limiar_rel * r.max()))
    dentro = (xs >= margem) & (xs < W - margem) & (ys >= margem) & (ys < H - margem)
    xs, ys = xs[dentro], ys[dentro]
    ordem = np.argsort(-r[ys, xs])[:max_pontos]
    return np.stack([xs[ordem], ys[ordem]], axis=1)


# ---------- descritores e correspondência ----------
def descritores(img, pontos, raio=7):
    """Retalhos (2·raio+1)² em torno dos pontos, com média zero e norma 1 (a correlação vira produto interno)."""
    g = filtros.convolucao(cinza(img), filtros.nucleo_gaussiano(5, 1.0), "reflect")
    p = np.pad(g, raio, mode="reflect")
    t = 2 * raio + 1
    jan = sliding_window_view(p, (t, t))
    d = jan[pontos[:, 1], pontos[:, 0]].reshape(len(pontos), -1)
    d = d - d.mean(axis=1, keepdims=True)
    return d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)


def correspondencias(d1, d2, ncc_min=0.85, razao=0.9):
    """Pares (i, j) com melhor correlação mútua, NCC >= ncc_min e teste da razão (2º melhor / melhor)."""
    if len(d1) == 0 or len(d2) == 0:
        return np.zeros((0, 2), int)
    c = d1 @ d2.T
    j = c.argmax(axis=1)
    i = c.argmax(axis=0)
    ok = i[j] == np.arange(len(d1))
    melhor = c[np.arange(len(d1)), j]
    ok &= melhor >= ncc_min
    if c.shape[1] > 1:
        c2 = c.copy()
        c2[np.arange(len(d1)), j] = -np.inf
        ok &= (1 - melhor) < razao * (1 - c2.max(axis=1))   # distância ~ 1 - NCC
    idx = np.nonzero(ok)[0]
    return np.stack([idx, j[idx]], axis=1)


# ---------- translação robusta ----------
def estimar_translacao(p1, p2, limiar=3.0):
    """RANSAC para o modelo p1 = p2 + t. Uma correspondência já define t, então todas as hipóteses são testadas
    (determinístico). Retorna (t, máscara de inliers); t é refinado pela média dos inliers."""
    p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
    if len(p1) == 0:
        raise ValueError("Nenhuma correspondência para estimar a translação.")
    d = p1 - p2
    contagem = (np.linalg.norm(d[:, None] - d[None], axis=2) <= limiar).sum(axis=1)
    t = d[contagem.argmax()]
    for _ in range(3):
        inl = np.linalg.norm(d - t, axis=1) <= limiar
        t = d[inl].mean(axis=0)
    return t, np.linalg.norm(d - t, axis=1) <= limiar


def alinhar(img1, img2, max_pontos=800, ncc_min=0.85, limiar=3.0):
    """Detecta, corresponde e estima t. Retorna dict com t, pontos, correspondências e máscara de inliers."""
    k1, k2 = detectar_cantos(img1, max_pontos), detectar_cantos(img2, max_pontos)
    m = correspondencias(descritores(img1, k1), descritores(img2, k2), ncc_min)
    q1, q2 = k1[m[:, 0]], k2[m[:, 1]]
    t, inl = estimar_translacao(q1, q2, limiar)
    return {"t": t, "pontos1": k1, "pontos2": k2, "p1": q1, "p2": q2, "inliers": inl}


# ---------- mosaico ----------
def _peso_borda(h, w):
    """Peso linear: cresce do contorno para o centro da imagem (feathering)."""
    y = np.minimum(np.arange(h) + 1, h - np.arange(h))
    x = np.minimum(np.arange(w) + 1, w - np.arange(w))
    return np.minimum(y[:, None], x[None, :]).astype(float)


def mosaico(img1, img2, t, modo="linear"):
    """Põe a imagem 2 deslocada de t (arredondado) sobre a 1 num quadro comum.
    modo: "linear" (pesos que decaem para a borda na sobreposição) ou "media" (média simples).
    Fora da sobreposição vale a imagem que existe; pixels sem nenhuma imagem ficam pretos."""
    a1, a2 = np.asarray(img1, float), np.asarray(img2, float)
    tx, ty = (int(round(v)) for v in t)
    x0, y0 = min(0, tx), min(0, ty)
    W = max(a1.shape[1], tx + a2.shape[1]) - x0
    H = max(a1.shape[0], ty + a2.shape[0]) - y0
    forma = (H, W) + a1.shape[2:]
    soma, peso = np.zeros(forma), np.zeros((H, W))
    for a, (dx, dy) in ((a1, (-x0, -y0)), (a2, (tx - x0, ty - y0))):
        h, w = a.shape[:2]
        p = _peso_borda(h, w) if modo == "linear" else np.ones((h, w))
        pa = p[..., None] if a.ndim == 3 else p
        soma[dy:dy + h, dx:dx + w] += a * pa
        peso[dy:dy + h, dx:dx + w] += p
    pw = peso[..., None] if a1.ndim == 3 else peso
    return np.where(pw > 0, soma / np.maximum(pw, 1e-12), 0)


def justaposicao(img1, img2):
    """Imagens lado a lado, sem alinhamento (altura completada com preto)."""
    a1, a2 = np.asarray(img1, float), np.asarray(img2, float)
    H = max(a1.shape[0], a2.shape[0])

    def pad(a):
        return np.pad(a, [(0, H - a.shape[0]), (0, 0)] + [(0, 0)] * (a.ndim - 2))
    return np.concatenate([pad(a1), pad(a2)], axis=1)
