"""Baixa amostras dos JSON do TSE para inspecionar a estrutura (roda no GitHub Actions)."""
import json, os, sys, urllib.request

BASE = "https://resultados.tse.jus.br/oficial"
OUT = sys.argv[1] if len(sys.argv) > 1 else "probe"
os.makedirs(OUT, exist_ok=True)


def get(u, save=True, head=False):
    name = u.split("//", 1)[1].replace("/", "__")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD" if head else "GET")
        r = urllib.request.urlopen(req, timeout=60)
        if head:
            print("OK HEAD", r.headers.get("Content-Length"), u)
            return None
        data = r.read()
        if save and len(data) < 3_000_000:
            open(os.path.join(OUT, name), "wb").write(data)
        print("OK", len(data), u)
        return data
    except Exception as e:  # noqa: BLE001
        print("FAIL", u, e)
        return None


cfg = None
for e in ["6257", "6258"]:
    d = get(f"{BASE}/ele2026/{e}/config/mun-e00{e}-cm.json")
    if d and cfg is None:
        cfg = json.loads(d)
    get(f"{BASE}/ele2026/{e}/dados-simplificados/br/br-c0001-e00{e}-r.json")
    get(f"{BASE}/ele2026/{e}/dados-simplificados/ac/ac-c0001-e00{e}-r.json")
    for suf in ["v", "u", "ab", "e", "f"]:
        get(f"{BASE}/ele2026/{e}/dados/ac/ac-c0001-e00{e}-{suf}.json")
        get(f"{BASE}/ele2026/{e}/dados/br/br-c0001-e00{e}-{suf}.json")

mu = None
if cfg:
    print(json.dumps(cfg, ensure_ascii=False)[:1500])
    try:
        for a in cfg["abr"]:
            if a["cd"].lower() == "ac":
                mu = a["mu"][0]
                print("MU", mu)
    except Exception as ex:  # noqa: BLE001
        print("cfg parse", ex)
if mu:
    cd = mu["cd"]
    for e in ["6257"]:
        for suf in ["v", "u", "ab"]:
            get(f"{BASE}/ele2026/{e}/dados/ac/ac{cd}-c0001-e00{e}-{suf}.json")
        get(f"{BASE}/ele2026/{e}/dados-simplificados/ac/ac{cd}-c0001-e00{e}-r.json")
        for z in mu.get("z", [])[:1]:
            get(f"{BASE}/ele2026/{e}/dados/ac/ac{cd}{z}-c0001-e00{e}-v.json")

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
for u in [
    f"{CDN}/votacao_secao/votacao_secao_2022_BR.zip",
    f"{CDN}/votacao_secao/votacao_secao_2022_AC.zip",
    f"{CDN}/detalhe_votacao_secao/detalhe_votacao_secao_2022.zip",
    f"{CDN}/votacao_candidato_munzona/votacao_candidato_munzona_2022.zip",
    f"{CDN}/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip",
    f"{CDN}/votacao_partido_munzona/votacao_partido_munzona_2022.zip",
]:
    get(u, head=True)
