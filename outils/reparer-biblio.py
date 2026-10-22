"""Réparation ponctuelle de la bibliothèque des clubs (ligne equipes_district).

Le 18/10/2026, des pierres tombales restées sur les clubs remis à la main la veille ont
fait retirer 110 clubs, recréés ensuite sans leurs équipes. Ce script repart de la
version ACTUELLE du nuage (rien de ce qui a été fait depuis n'est perdu) et :
  - remet à chaque club de la sauvegarde de référence ses équipes s'il n'en a plus,
    et complète les cases vides (ville, stade, logo…) ;
  - rajoute les clubs de la référence qui manqueraient ;
  - lève les pierres tombales des clubs et équipes présents (_supprimes / _revenus).
APPLIQUER=1 pour écrire ; sinon simple essai à blanc.
"""
import json, os, sys, time, urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/carnet"
CLE = os.environ["SUPABASE_KEY"]
REF = os.environ.get("REFERENCE", "sauvegardes/carnets_2026-10-17.json")
APPLIQUER = os.environ.get("APPLIQUER") == "1"
H = {"apikey": CLE, "Authorization": "Bearer " + CLE}

def http(url, methode="GET", corps=None, entetes=None):
    donnees = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode, headers=dict(H, **(entetes or {})))
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

def compter(b):
    eq = b.get("equipes", {})
    return len(eq), sum(len(v.get("equipes") or []) for v in eq.values() if isinstance(v, dict))

ref = {r["id"]: r for r in json.load(open(REF))}["equipes_district"]["data"]["equipes"]
cur = json.loads(http(SB + "?id=eq.equipes_district&select=data,updated_at"))[0]
b = cur["data"]; b.pop("_src", None)
avant = compter(b)
remis_eq = ajoutes = completes = 0
for nom, r in ref.items():
    if not isinstance(r, dict):
        continue
    c = b["equipes"].get(nom)
    if not isinstance(c, dict):
        b["equipes"][nom] = r; ajoutes += 1
        continue
    if not c.get("equipes") and r.get("equipes"):
        c["equipes"] = r["equipes"]; remis_eq += 1
    for k, v in r.items():
        if k != "equipes" and (c.get(k) is None or c.get(k) == "") and v not in (None, ""):
            c[k] = v; completes += 1

maintenant = int(time.time() * 1000)
sup = b.get("_supprimes") or {}
rev = b.setdefault("_revenus", {})
leves = 0
for nom, c in b["equipes"].items():
    cles = ["club:" + nom] + ["eq:%s/%s" % (nom, e["id"]) for e in (c.get("equipes") or []) if isinstance(e, dict) and e.get("id")]
    for k in cles:
        if k in sup:
            del sup[k]; rev[k] = maintenant; leves += 1

apres = compter(b)
print("::notice::Nuage (%s) : %d clubs / %d equipes -> %d clubs / %d equipes. Equipes remises a %d clubs, %d clubs rajoutes, %d cases completees, %d pierres tombales levees. %s"
      % (cur["updated_at"][:16], avant[0], avant[1], apres[0], apres[1], remis_eq, ajoutes, completes, leves,
         "ECRIT" if APPLIQUER else "essai a blanc, rien ecrit"))
if APPLIQUER:
    b["_src"] = "reparation-2026-10-22"
    http(SB, "POST", {"id": "equipes_district", "data": b, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())},
         {"Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})
    relu = json.loads(http(SB + "?id=eq.equipes_district&select=data"))[0]["data"]
    print("::notice::Relu dans le nuage : %d clubs / %d equipes" % compter(relu))
