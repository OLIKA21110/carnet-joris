#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Constitue l'archive des saisons passees, une fois pour toutes.

Pourquoi ce detour : l'API de la Federation ne donne les matchs d'un club QUE pour la
saison en cours. Les matchs d'une saison passee restent lisibles, mais seulement par
competition, et l'identifiant d'une competition change a chaque saison sans qu'on puisse
le deduire. En revanche ces identifiants sont GROUPES par district et par saison : on
balaie donc une plage de numeros et on garde ce qui nous concerne.

Ce script tourne chez GitHub Actions, jamais dans le navigateur de Joris : la Federation
coupe l'acces quand on l'interroge trop vite (constate le 31/08/2026, une centaine
d'appels rapproches suffisent). D'ou la pause entre chaque appel.

Sortie : archives/clubs/<cl_no>.json, un fichier par club suivi, fusionne avec l'existant.
"""
import json, os, sys, time, urllib.request, urllib.error

API      = "https://api-dofa.fff.fr"
PAUSE    = float(os.environ.get("PAUSE", "0.40"))     # secondes entre deux appels
BUDGET   = int(os.environ.get("BUDGET", "6000"))      # garde-fou : appels maximum
DEBUT    = int(os.environ["DEBUT"])
FIN      = int(os.environ["FIN"])
PAS      = int(os.environ.get("PAS", "1"))   # >1 : mode reperage, on ne lit aucun match
RACINE   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER  = os.path.join(RACINE, "archives")

appels = 0

def get(chemin):
    """Un appel, poli, avec un seul rattrapage. Renvoie None si ca ne repond pas."""
    global appels
    if appels >= BUDGET:
        raise SystemExit("Budget d'appels epuise (%d) — on s'arrete proprement." % BUDGET)
    for essai in (1, 2):
        appels += 1
        try:
            req = urllib.request.Request(API + chemin, headers={"Accept": "application/ld+json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.loads(r.read().decode("utf-8"))
            time.sleep(PAUSE)
            return d
        except urllib.error.HTTPError as e:
            time.sleep(PAUSE)
            if e.code == 404:
                return None          # la competition n'existe pas : normal, on balaie
            if essai == 2:
                return None
            time.sleep(5)            # 429 ou 5xx : on souffle avant de reessayer
        except Exception:
            time.sleep(PAUSE)
            if essai == 2:
                return None
            time.sleep(5)
    return None

def pages(chemin, maxi=8):
    """Toutes les pages d'une collection Hydra."""
    tout, page = [], 1
    while page <= maxi:
        d = get(chemin + ("&" if "?" in chemin else "?") + "page=%d" % page)
        if not d:
            break
        tout += d.get("hydra:member", [])
        if not (d.get("hydra:view") or {}).get("hydra:next"):
            break
        page += 1
    return tout

def clno(cote):
    return ((cote or {}).get("club") or {}).get("cl_no")

def joue(m):
    return m.get("home_score") is not None

# ---------------------------------------------------------------- les clubs suivis
suivis = json.load(open(os.path.join(DOSSIER, "clubs-suivis.json"), encoding="utf-8"))
NOS = set(suivis.values())
print("Clubs suivis : %d" % len(NOS), flush=True)

# ---------------------------------------------------------------- le balayage
#
# ATTENTION — piege coute 800 appels le 01/09/2026 : on filtrait d'abord sur
# /api/engagements?competition.cp_no=..., pour ne lire les matchs que des competitions
# ou l'un de nos clubs joue. Or CET ENDPOINT NE REPOND QUE POUR LA SAISON EN COURS :
# sur une competition passee il renvoie totalItems 0. Le pre-filtre ecartait donc
# exactement ce qu'on venait chercher. On lit maintenant les matchs directement et on
# trie dessus. C'est la plage de numeros qui delimite le travail, rien d'autre.
#
trouvees, saisons = [], {}
carte = {}     # (saison, district) -> [premier vu, dernier vu, combien]
print("Balayage des identifiants %d a %d (pas de %d)" % (DEBUT, FIN, PAS), flush=True)
for cp in range(DEBUT, FIN, PAS):
    d = get("/api/compets/%d" % cp)
    if not d or not d.get("cp_no"):
        continue
    saison = d.get("season")
    saisons[saison] = saisons.get(saison, 0) + 1
    cdg = d.get("cdg") or {}
    cle = (saison, cdg.get("cg_no"), cdg.get("name"))
    if cle in carte:
        carte[cle][1] = cp; carte[cle][2] += 1
    else:
        carte[cle] = [cp, cp, 1]
    trouvees.append(d)

print("\n%d competitions trouvees. Saisons rencontrees : %s"
      % (len(trouvees), dict(sorted(saisons.items(), key=lambda x: str(x[0])))), flush=True)

print("\n=== Carte des blocs : saison / district / plage observee ===", flush=True)
for (sa, cg, nom), (a, b, n) in sorted(carte.items(), key=lambda x: (str(x[0][0]), x[1][0])):
    print("  saison %-6s  cg %-5s  %-40s  %d -> %d  (%d vues)"
          % (sa, cg, (nom or "")[:40], a, b, n), flush=True)

if PAS > 1:
    print("\nMode reperage : on s'arrete la, aucun match n'est lu.", flush=True)
    raise SystemExit(0)

# ---------------------------------------------------------------- les matchs
retenues = []
moisson = {}   # cl_no -> liste de matchs allegés
for d in trouvees:
    cp = d["cp_no"]
    pris = 0
    for ph in (d.get("phases") or []):
        for gr in (ph.get("groups") or []):
            ms = pages("/api/compets/%d/phases/%s/poules/%s/matchs"
                       % (cp, ph.get("number"), gr.get("stage_number")), maxi=6)
            for m in ms:
                if not joue(m):
                    continue
                a, b = clno(m.get("home")), clno(m.get("away"))
                if not (a in NOS or b in NOS):
                    continue
                pris += 1
                leger = {
                    "id":   m.get("ma_no"),
                    "date": (m.get("date") or "")[:10],
                    "sa":   d.get("season"),
                    "cp":   d.get("name"),
                    "dom":  (m.get("home") or {}).get("short_name"),
                    "ext":  (m.get("away") or {}).get("short_name"),
                    "cd":   a, "ce": b,
                    "bd":   m.get("home_score"), "be": m.get("away_score"),
                }
                for c in (a, b):
                    if c in NOS:
                        moisson.setdefault(c, []).append(leger)
    if pris:
        retenues.append(d)
        print("  %s  %-34s (%s, saison %s) — %d matchs pour nous"
              % (cp, (d.get("name") or "")[:34], d.get("type"), d.get("season"), pris), flush=True)

# ---------------------------------------------------------------- fusion et ecriture
os.makedirs(os.path.join(DOSSIER, "clubs"), exist_ok=True)
total_neufs = 0
for cl, liste in moisson.items():
    chemin = os.path.join(DOSSIER, "clubs", "%d.json" % cl)
    anciens = []
    if os.path.exists(chemin):
        try:
            anciens = json.load(open(chemin, encoding="utf-8"))
        except Exception:
            anciens = []
    vus = {m.get("id") for m in anciens}
    neufs = [m for m in liste if m.get("id") not in vus]
    total_neufs += len(neufs)
    fusion = sorted(anciens + neufs, key=lambda m: (m.get("date") or ""), reverse=True)
    json.dump(fusion, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

index = {}
chemin_index = os.path.join(DOSSIER, "index.json")
if os.path.exists(chemin_index):
    try:
        index = json.load(open(chemin_index, encoding="utf-8"))
    except Exception:
        index = {}
index.setdefault("passages", []).append({
    "le": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    "plage": [DEBUT, FIN],
    "competitions_retenues": len(retenues),
    "clubs_touches": len(moisson),
    "matchs_nouveaux": total_neufs,
    "appels": appels,
})
index["clubs"] = sorted(int(f[:-5]) for f in os.listdir(os.path.join(DOSSIER, "clubs")) if f.endswith(".json"))
json.dump(index, open(chemin_index, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print("\n=== Termine ===")
print("Competitions trouvees : %d" % len(trouvees))
print("Dont utiles           : %d" % len(retenues))
print("Clubs touches         : %d" % len(moisson))
print("Matchs nouveaux       : %d" % total_neufs)
print("Appels a la FFF       : %d" % appels)
