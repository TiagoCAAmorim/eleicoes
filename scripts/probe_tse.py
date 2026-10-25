"""Baixa amostras dos JSON do TSE para inspecionar a estrutura (roda no GitHub Actions)."""
import json, os, sys, urllib.request

BASE = "https://resultados.tse.jus.br/oficial"
OUT = sys.argv[1] if len(sys.argv) > 1 else "probe"
os.makedirs(OUT, exist_ok=True)

urls = [
    f"{BASE}/comum/config/ele-c.json",
    f"{BASE}/ele2022/544/config/mun-e000544-cm.json",
    f"{BASE}/ele2022/545/config/mun-e000545-cm.json",
    f"{BASE}/ele2022/544/dados-simplificados/br/br-c0001-e000544-r.json",
    f"{BASE}/ele2022/545/dados-simplificados/br/br-c0001-e000545-r.json",
    f"{BASE}/ele2022/545/dados-simplificados/ac/ac-c0001-e000545-r.json",
    f"{BASE}/ele2022/545/dados/ac/ac-c0001-e000545-v.json",
    f"{BASE}/ele2022/545/dados/ac/ac-c0001-e000545-u.json",
    f"{BASE}/ele2022/545/dados/br/br-c0001-e000545-v.json",
    f"{BASE}/ele2022/545/dados/ac/ac01392-c0001-e000545-v.json",
    f"{BASE}/ele2022/545/dados/ac/ac01392-c0001-e000545-u.json",
    f"{BASE}/ele2022/545/dados-simplificados/ac/ac01392-c0001-e000545-r.json",
]
for u in urls:
    name = u.replace(BASE + "/", "").replace("/", "__")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
        open(os.path.join(OUT, name), "wb").write(data)
        print("OK", len(data), u)
    except Exception as e:  # noqa: BLE001
        print("FAIL", u, e)
