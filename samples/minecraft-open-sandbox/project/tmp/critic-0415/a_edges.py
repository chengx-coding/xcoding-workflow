import json, os
import numpy as np
from PIL import Image

ROOT = r"C:\dev\xcoding-workflow-dev\wf-iterations\emberdeep-visual-0414\visual\critic-input-0415"
man = json.load(open(os.path.join(ROOT, "manifest.json"), encoding="utf-8"))

def edge_report(path):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    h, w, _ = a.shape
    out = {"size": (w, h)}
    # rows / cols that are near-constant and dark => band
    rowmean = a.mean(axis=(1, 2))
    colmean = a.mean(axis=(0, 2))
    rowstd = a.std(axis=1).mean(axis=1)
    colstd = a.std(axis=0).mean(axis=1)
    # count uniform edge bands
    def band(mean, std, n):
        k = 0
        for i in range(n):
            if std[i] < 3.0:
                k += 1
            else:
                break
        return k
    top = band(rowmean, rowstd, h)
    bot = band(rowmean[::-1], rowstd[::-1], h)
    left = band(colmean, colstd, w)
    right = band(colmean[::-1], colstd[::-1], w)
    out["top_uniform_rows"] = top
    out["bottom_uniform_rows"] = bot
    out["left_uniform_cols"] = left
    out["right_uniform_cols"] = right
    out["top_row_mean"] = [round(float(a[0].mean()), 1), [int(v) for v in a[0].mean(axis=0).round()]]
    out["bottom_row_mean"] = [round(float(a[-1].mean()), 1), [int(v) for v in a[-1].mean(axis=0).round()]]
    out["left_col_mean"] = [round(float(a[:, 0].mean()), 1), [int(v) for v in a[:, 0].mean(axis=1).round()]]
    out["right_col_mean"] = [round(float(a[:, -1].mean()), 1), [int(v) for v in a[:, -1].mean(axis=1).round()]]
    return out

for group in ("candidate", "baseline"):
    print("=" * 20, group)
    for e in man[group]:
        r = edge_report(os.path.join(ROOT, e["path"]))
        print(f'{e["viewport"]:>9} {e["state"]:<11} {r["size"]!s:<12} '
              f'T{r["top_uniform_rows"]:>3} B{r["bottom_uniform_rows"]:>3} '
              f'L{r["left_uniform_cols"]:>3} R{r["right_uniform_cols"]:>3}  '
              f'top{tuple(r["top_row_mean"][1])} bot{tuple(r["bottom_row_mean"][1])} '
              f'left{tuple(r["left_col_mean"][1])} right{tuple(r["right_col_mean"][1])}')
