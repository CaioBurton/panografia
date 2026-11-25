# panografia

Aplicação em CustomTkinter sobre a biblioteca `vc` (filtros, geometria, câmera, etc.).

## Executar

```
pip install -r requirements.txt
python app.py
```

Testes: `python -m unittest discover -s tests`

No Windows com Anaconda, rode os comandos no *Anaconda Prompt* (o `python` do PATH pode apontar para o
atalho da Microsoft Store). Abas da interface: **Imagem**, **Funções**, **Formação de Imagem** (Atividade 01),
**Blending (Pirâmides)** (Atividade 02) e **Panografia** (Atividade 03).

## Aba "Imagem"

Abra uma imagem (Ctrl+O) e aplique filtros, transformações, reamostragem, distorção radial, composição
(over), imagem integral e segmentação (k-means, ICM). Os parâmetros numéricos têm campo de texto e
**slider** sincronizados (o campo aceita valores fora da faixa do slider).

A chave **Aplicar ao mover o slider** (ligada por padrão) refaz a operação sempre a partir da imagem anterior
ao ajuste, sem acumular efeitos. Durante o arrasto as chamadas são agrupadas (~80 ms) e as operações
pesadas (mediana, média α-cortada, mediana ponderada, k-means, ICM) só rodam ao soltar o slider. Média e
gaussiano usam filtro separável (O(k) por pixel). Fator r e α do Over não reaplicam sozinhos
(usam botão/diálogo de arquivo).

## Aba "Formação de Imagem" (Atividade 01)

Projeção de um cubo (vértices P1–P8 no mundo) com modelo **perspectiva** ou **ortográfica escalada**,
sensor 640×480, 800×600 ou 1280×720, parâmetros intrínsecos (fx, fy, cx, cy, skew, matriz K),
escala (ortográfica) e parâmetros extrínsecos (translação e rotação em X, Y, Z). A imagem é atualizada a
cada alteração; use os campos, os sliders ou o mouse sobre a imagem:

- botão esquerdo + arrastar: gira em X/Y (Shift: gira em Z)
- botão direito + arrastar: transla em X/Y
- roda do mouse: aproxima/afasta (tz)

Equações (código em `vc/formacao_imagem.py`): `Xc = R·Xw + t`, `R = Rz·Ry·Rx`;
perspectiva `x̃ = K·Xc`, `u = x̃₁/x̃₃`, `v = x̃₂/x̃₃`; ortográfica `u = s·Xc + cx`, `v = s·Yc + cy`
com (cx, cy) no centro do sensor. Na perspectiva, cx e cy não mudam ao trocar a resolução.

## Atividade 02 - Blending com pirâmides

`vc/piramides.py`: `reduzir`/`expandir` (núcleo binomial 5x5), `piramide_gaussiana`, `piramide_laplaciana`,
`colapsar`, `blending` (Burt e Adelson, 1983) e `justaposicao`. Para cada nível,
`L_blend = Gm·La + (1−Gm)·Lb`, com `Gm` a pirâmide Gaussiana da máscara; a pirâmide é então colapsada.

`python blending.py [pasta_imagens] [pasta_saida] [niveis]` gera em `resultados_blending/` o blending,
a justaposição direta, a comparação, o zoom da emenda e as pirâmides.

Na interface, a aba **Blending (Pirâmides)** carrega por padrão a maçã, a laranja e a máscara sugeridas;
é possível escolher outras imagens A/B (a B é redimensionada para o tamanho da A), uma máscara em arquivo
ou uma máscara automática (metade esquerda/direita), e o número de níveis (campo ou **slider** de 1 a 9; o
blending é refeito ao soltar o slider; o máximo real depende do tamanho da imagem A). As visões são: comparação,
blending, justaposição, zoom da emenda e pirâmides (salvar com "Salvar visualização").

## Atividade 03 - Panografia (costura por translação)

`vc/panografia.py`: cantos de **Harris** (`detectar_cantos`), descritores por retalho normalizado
(`descritores`), correspondência por correlação mútua com teste da razão (`correspondencias`),
**RANSAC** para o modelo `p1 = p2 + t` (`estimar_translacao`: uma correspondência já define `t`, então todas as
hipóteses são testadas; `t` é refinado pela média dos inliers) e `mosaico` (blending linear com pesos que
decaem para a borda, ou média simples, na sobreposição). `justaposicao` põe as imagens lado a lado sem alinhar.

`python costura.py [img1] [img2] [pasta_saida]` usa `images/img1` e `images/img2` por padrão (`.jpg` ou
`.png`), imprime `t = (tx, ty)` e o número de inliers e gera em `resultados_panografia/` o `mosaico.jpg`, a
justaposição, as correspondências (verde = inlier, vermelho = outlier) e a comparação. Nas imagens
fornecidas: `t ≈ (361.9, −0.4)` com 136 inliers de 144 correspondências.

Na interface, a aba **Panografia** carrega `images/img1` e `images/img2` por padrão e permite escolher outras
imagens, ajustar o máximo de cantos, o NCC mínimo, o limiar do RANSAC e o modo do mosaico. As visões são:
comparação, mosaico, justaposição e correspondências.
