"""Boîte à idées de Joris -> tickets GitHub, et retour des réponses vers le carnet.

Lancé par .github/workflows/idees.yml (toutes les 15 minutes, chez GitHub).

1. Chaque idée « envoyee » de la ligne Supabase « idees_joris » devient un ticket,
   attribué au propriétaire du dépôt : GitHub le prévient par mail.
2. Pour chaque idée déjà en ticket : la dernière réponse d'Olivier (commentaire) est
   recopiée dans l'idée, et un ticket fermé la passe en « faite » (completed) ou
   « refusee » (not planned). Joris le voit dans sa boîte à idées.

Pourquoi un marqueur <!-- idee:ID --> dans chaque ticket : si l'écriture vers Supabase
échoue après la création du ticket, le passage suivant retrouve le ticket au lieu d'en
ouvrir un deuxième.

Pourquoi relire Supabase juste avant d'écrire : Joris peut avoir ajouté une idée pendant
que le robot travaillait. On ne modifie que les idées traitées, le reste de la ligne
est repris tel qu'il est dans le nuage à cet instant.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/carnet"
CLE = os.environ["SUPABASE_KEY"]
DEPOT = os.environ["GITHUB_REPOSITORY"]
GH = "https://api.github.com/repos/" + DEPOT
JETON = os.environ["GITHUB_TOKEN"]
PROPRIO = DEPOT.split("/")[0]
LIGNE = "idees_joris"
ETIQUETTE = "idée de Joris"


def http(url, methode="GET", corps=None, entetes=None):
    donnees = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode, headers=entetes or {})
    if donnees is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        brut = r.read()
        return json.loads(brut) if brut else None


def sb_lire():
    t = http(SB + "?id=eq." + LIGNE + "&select=data", entetes={"apikey": CLE, "Authorization": "Bearer " + CLE})
    if t and t[0].get("data") and isinstance(t[0]["data"].get("idees"), list):
        return t[0]["data"]["idees"]
    return []


def sb_ecrire(idees):
    http(SB, "POST", {"id": LIGNE, "data": {"idees": idees}, "updated_at": maintenant()},
         {"apikey": CLE, "Authorization": "Bearer " + CLE,
          "Prefer": "resolution=merge-duplicates,return=minimal"})


def gh(chemin, methode="GET", corps=None):
    return http(GH + chemin, methode, corps, {
        "Authorization": "Bearer " + JETON,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "carnet-joris-idees"})


def maintenant():
    # même format que toISOString() côté navigateur : les dates se comparent comme des textes
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def marqueur(id_idee):
    return "<!-- idee:" + id_idee + " -->"


def tickets_existants():
    """id de l'idée -> ticket, d'après le marqueur caché dans le texte du ticket."""
    carte, page = {}, 1
    etiq = urllib.parse.quote(ETIQUETTE)
    while True:
        lot = gh("/issues?state=all&per_page=100&page=" + str(page) + "&labels=" + etiq)
        for t in lot:
            corps = t.get("body") or ""
            debut = corps.find("<!-- idee:")
            if debut >= 0:
                fin = corps.find(" -->", debut)
                carte[corps[debut + 10:fin]] = t
        if len(lot) < 100:
            return carte
        page += 1


def creer_etiquette():
    try:
        gh("/labels", "POST", {"name": ETIQUETTE, "color": "ffd54a",
                               "description": "Envoyée depuis la boîte à idées du carnet"})
    except urllib.error.HTTPError as e:
        if e.code != 422:          # 422 = elle existe déjà
            raise


def creer_ticket(i):
    texte = (i.get("texte") or "").strip()
    titre = texte.splitlines()[0] if texte else "(idée vide)"
    if len(titre) > 70:
        titre = titre[:67].rstrip() + "…"
    date = (i.get("envoyee") or i.get("cree") or "")[:10]
    cite = "\n".join("> " + l for l in texte.splitlines()) or "> (vide)"
    corps = (
        f"**Idée de Joris**, depuis la page *{i.get('page') or '?'}*, envoyée le {date}.\n\n"
        f"{cite}\n\n---\n"
        "- **Pour la réaliser** : demande à Claude « fais l'idée de Joris, ticket n°… » (le numéro de ce ticket). "
        "Il prépare la modification en proposition (pull request) avec `Fixes #…` : "
        "quand tu la valides, ce ticket se ferme tout seul et Joris voit ✅.\n"
        "- **Pour répondre à Joris** : écris un commentaire ici, il le verra dans sa boîte à idées.\n"
        "- **Si tu ne la gardes pas** : ferme le ticket en choisissant *Close as not planned*.\n\n"
        + marqueur(i["id"]))
    return gh("/issues", "POST", {"title": "💡 " + titre, "body": corps,
                                  "labels": [ETIQUETTE], "assignees": [PROPRIO]})


def sans_citation(texte):
    """Une réponse envoyée depuis le mail de GitHub traîne tout le mail cité en dessous
    (« Le jeu. 1 oct. 2026, 13:27, … a écrit : » puis des lignes « > » pleines de liens).
    Joris ne doit voir que ce que papa a écrit."""
    lignes = texte.replace("\r\n", "\n").split("\n")
    for n, l in enumerate(lignes):
        if l.startswith(">") or l.strip() in ("--", "-- "):
            lignes = lignes[:n]
            break
    garde = "\n".join(lignes).strip()
    # le chapeau « Le … a écrit : » / « On … wrote: » juste avant la citation, parfois sur deux lignes
    blocs = garde.split("\n\n")
    if len(blocs) > 1 and blocs[-1].rstrip().endswith(("écrit :", "écrit:", "wrote:")):
        garde = "\n\n".join(blocs[:-1]).strip()
    return garde


def derniere_reponse(numero):
    """Le dernier commentaire écrit par Olivier sur le ticket (pas ceux des robots)."""
    coms = gh(f"/issues/{numero}/comments?per_page=100")
    siens = [c for c in coms if (c.get("user") or {}).get("login", "").lower() == PROPRIO.lower()]
    return sans_citation(siens[-1]["body"]) or None if siens else None


def main():
    idees = sb_lire()
    a_suivre = [i for i in idees if i.get("etat") in ("envoyee", "ticket")]
    if not a_suivre:
        print("Aucune idée à traiter.")
        return
    creer_etiquette()
    carte = tickets_existants()
    changements = {}      # id -> (état attendu dans le nuage, champs à écrire)

    for i in a_suivre:
        t = carte.get(i["id"])
        if i["etat"] == "envoyee":
            if not t:
                t = creer_ticket(i)
                print(f"Ticket n°{t['number']} créé pour l'idée {i['id']}")
            changements[i["id"]] = ("envoyee", {"etat": "ticket", "ticket": t["number"]})
            continue
        # etat == "ticket"
        if not t:
            try:
                t = gh(f"/issues/{i['ticket']}")
            except urllib.error.HTTPError:
                continue
        champs = {}
        if t.get("comments"):
            rep = derniere_reponse(t["number"])
            if rep and rep != i.get("reponse"):
                champs["reponse"] = rep[:2000]
        if t.get("state") == "closed":
            champs["etat"] = "refusee" if t.get("state_reason") == "not_planned" else "faite"
        if champs:
            changements[i["id"]] = ("ticket", champs)
            print(f"Idée {i['id']} (ticket n°{t['number']}) : {champs}")

    if not changements:
        print("Rien de neuf.")
        return
    frais = sb_lire()
    quand = maintenant()
    for x in frais:
        c = changements.get(x.get("id"))
        if c and x.get("etat") == c[0]:
            x.update(c[1])
            x["maj"] = quand
    sb_ecrire(frais)
    print(f"{len(changements)} idée(s) mise(s) à jour dans le carnet.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as e:
        print(f"Erreur HTTP {e.code} sur {e.url} : {e.read()[:500]!r}", file=sys.stderr)
        sys.exit(1)
