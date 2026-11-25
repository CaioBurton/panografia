"""Testes da panografia por translação (python -m unittest discover -s tests)."""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vc import filtros, panografia  # noqa: E402

RNG = np.random.default_rng(0)


def cena(h=160, w=240):
    """Textura suave com muitos cantos (ruído filtrado + retângulos)."""
    img = filtros.convolucao(RNG.random((h, w)) * 255, filtros.nucleo_gaussiano(5, 1.2), "reflect")
    for _ in range(40):
        y, x = RNG.integers(0, h - 20), RNG.integers(0, w - 20)
        img[y:y + RNG.integers(6, 20), x:x + RNG.integers(6, 20)] = RNG.random() * 255
    return np.stack([img, img * 0.8 + 20, 255 - img], axis=-1)


class TestPanografia(unittest.TestCase):
    def test_translacao_conhecida(self):
        c = cena()
        a, b = c[:, :170], c[10:150, 70:]          # b é a janela de c deslocada de (70, 10)
        res = panografia.alinhar(a, b)
        np.testing.assert_allclose(res["t"], (70, 10), atol=1)
        self.assertGreater(res["inliers"].sum(), 10)

    def test_ransac_ignora_outliers(self):
        p2 = RNG.random((60, 2)) * 200
        p1 = p2 + np.array([30.0, -12.0])
        p1[:15] = RNG.random((15, 2)) * 200        # 25% de correspondências erradas
        t, inl = panografia.estimar_translacao(p1, p2, 1.0)
        np.testing.assert_allclose(t, (30, -12), atol=1e-6)
        self.assertGreaterEqual(inl.sum(), 45)
        self.assertFalse(inl[:15].all())

    def test_sem_correspondencias(self):
        with self.assertRaises(ValueError):
            panografia.estimar_translacao(np.zeros((0, 2)), np.zeros((0, 2)))

    def test_forma_do_mosaico(self):
        a, b = np.full((50, 80, 3), 100.0), np.full((60, 70, 3), 200.0)
        self.assertEqual(panografia.mosaico(a, b, (60, 5)).shape, (65, 130, 3))
        self.assertEqual(panografia.mosaico(a, b, (-10, -20)).shape, (70, 90, 3))   # t negativo estende para cima/esquerda

    def test_mosaico_preserva_regioes_exclusivas_e_mistura_sobreposicao(self):
        a, b = np.full((40, 40), 100.0), np.full((40, 40), 200.0)
        for modo in ("linear", "media"):
            m = panografia.mosaico(a, b, (20, 0), modo)
            self.assertEqual(m.shape, (40, 60))
            self.assertTrue(np.all(m[:, :20] == 100) and np.all(m[:, 40:] == 200))
            self.assertTrue(np.all((m[:, 20:40] >= 100) & (m[:, 20:40] <= 200)))
        np.testing.assert_allclose(panografia.mosaico(a, b, (20, 0), "media")[:, 20:40], 150)

    def test_blending_linear_e_monotono(self):
        a, b = np.full((40, 40), 100.0), np.full((40, 40), 200.0)
        faixa = panografia.mosaico(a, b, (20, 0), "linear")[20, 20:40]
        self.assertTrue(np.all(np.diff(faixa) >= 0))   # de a para b, sem salto

    def test_justaposicao(self):
        j = panografia.justaposicao(np.ones((30, 40, 3)), np.ones((50, 20, 3)))
        self.assertEqual(j.shape, (50, 60, 3))
        self.assertTrue(np.all(j[30:, :40] == 0))


if __name__ == "__main__":
    unittest.main()
