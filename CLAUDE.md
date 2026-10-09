# Le carnet de Joris — mode d'emploi pour Claude Code

Quatre pages HTML autonomes pour suivre le football de district. Olivier les fait
évoluer, **Joris (son fils) est l'utilisateur** : tout ce qui s'affiche doit être
compréhensible par un enfant, en français simple, sans jargon.

Site : https://olika21110.github.io/carnet-joris/ — dépôt : `OLIKA21110/carnet-joris`.

---

## 1. La règle qui ne se négocie pas

**Chaque page est un seul fichier HTML**, CSS et JS inclus. Pas de build, pas de
framework, pas de bundler, pas de `node_modules`. Deux CDN autorisés, et seulement
ceux-là :

- `@supabase/supabase-js@2` (synchro)
- `jszip@3.10.1` (export ZIP, dans `index.html`)

Toute proposition qui commence par « on pourrait extraire le JS dans un fichier à
part » ou « on installe React » est hors sujet. Les fichiers font 2 000 à 4 700
lignes et c'est assumé.

| Fichier | Rôle | Lignes |
|---|---|---|
| `championnat-district.html` | championnats, poules, journées, classements, stats | ~4 700 |
| `coupes-district.html` | coupes à élimination directe, tours, tirages | ~3 900 |
| `mes-equipes.html` | bibliothèque des clubs, leurs équipes, leurs logos | ~1 700 |
| `journal.html` | le journal de Joris | ~1 100 |
| `index.html` | accueil + sauvegarde/restauration ZIP | ~250 |

---

## 2. Où vivent les données — et le piège central

`localStorage` sur l'appareil + une table Supabase `carnet` (une ligne par carnet,
colonne `data` en JSON) qui fait le lien entre le PC d'Olivier et le téléphone de Joris.

```
SUPABASE_URL = https://hoyxgmmbngrjigjqptnr.supabase.co
SUPABASE_KEY = sb_publishable_…   (clé publiable, déjà en clair dans les pages — c'est voulu)
```

Lignes : `champ_district_2627`, `coupes_district_2627`, `equipes_district`
(la bibliothèque, partagée), `annuaire_fff`, `journal_joris`, `idees_joris`
(la boîte à idées), plus `<carnet>:saisons` pour la liste des saisons.

### La synchro économe (depuis le 9 octobre 2026)

Le quota gratuit de Supabase (5,5 Go **sortis** du nuage par mois) a sauté le 9 octobre 2026 :
le « temps réel » (`postgres_changes`) renvoyait la ligne entière (540 Ko pour le championnat)
à chaque page ouverte à chaque score tapé, et `mes-equipes.html` écoutait **toute** la table
et relisait tous les carnets à chaque changement. **Ne pas remettre de temps réel.**

Désormais, dans les quatre pages :
- on demande d'abord `select('id,updated_at')` (quelques octets) ; la ligne n'est téléchargée
  que si sa date a changé. Vérification à l'ouverture, au retour sur l'onglet, puis chaque minute ;
- `<clé locale>:stamp` = date de la version du nuage que l'appareil connaît ;
- `<clé locale>:aEnvoyer` = changement fait ici pas encore parti : le nuage ne l'écrase jamais ;
- `<clé locale>:base` = dernière version commune ; quand l'appareil ET le nuage ont changé,
  `fusion3(base, ici, là)` reprend ce qui n'a changé que d'un côté (ajout, correction,
  suppression), listes à `id` fusionnées élément par élément ;
- sans base (premier passage), `fusionCarnets` / `fusionJournal` : le nuage fait foi, on
  ajoute seulement ce qu'il n'a pas ;
- lectures seules (historique, journal, Mes équipes, annuaire) : `nuageLireUne(id)` reprend la
  copie de l'appareil (`nuage_cache:<ligne>` ou la clé de la page propriétaire) si elle est à jour ;
- mémoire du navigateur ≈ 5,2 millions de caractères : `ecrireLocal()` jette les copies de
  confort si elle est pleine, pour que le carnet s'écrive toujours.

Banc d'essai utilisé : un faux PostgREST (route Playwright sur `*.supabase.co/rest/v1/carnet`)
avec la vraie bibliothèque supabase-js (`npm pack @supabase/supabase-js@2`, `dist/umd`),
deux contextes = deux appareils, compteur des octets sortis, mode « panne » (réponses 402).

### Le piège qui a déjà fait perdre des données deux fois

`save()` et `sauverBiblio()` **réécrivent l'objet entier**. Donc :

1. **Une routine de fond ne sauvegarde JAMAIS.** Les fonctions qui complètent des
   données toutes seules (numéros FFF, départements devinés…) modifient `biblio`/`state`
   en mémoire et appellent `redessinerSiPossible()`. Jamais `save()`.
   Sinon : l'appareil envoie quelques minutes plus tard un état périmé qui efface
   ce qui a été ajouté ailleurs entre-temps.
2. **`fusionnerAvantEnvoi()`** (dans `mes-equipes.html`) relit le nuage avant d'écrire
   et réinjecte ce qui manque localement.
3. **Les suppressions volontaires posent une pierre tombale** (`tombePoser('club', nom)`,
   `biblio._supprimes`) pour que la fusion ne les ressuscite pas. 60 jours.
4. **`enSaisie()` / `redessinerSiPossible()`** : ne jamais reconstruire la page pendant
   que Joris tape — le curseur sauterait.

Garde-fous de récupération, déjà en place :

- **Corbeille** (`state.corbeille`) : supprimer un championnat, une poule, une coupe
  ou un tour en garde une copie complète (scores, dates, pronos) 90 jours. Bouton
  « ♻️ Restaurer ». Max 12 entrées, 1,5 Mo.
- **Sauvegardes de la nuit** : GitHub Actions copie toute la base dans
  `sauvegardes/carnets_AAAA-MM-JJ.json` à 3 h 15 UTC, 30 jours d'historique,
  plus `index.json` et `carnets_derniere.json`. La fenêtre « Restaurer » les lit
  directement (même origine, pas de CORS) et propose soit « remettre ce qui manque »
  (fusion, n'écrase rien), soit « revenir à cette version » (l'actuel part en corbeille).

---

## 3. Travailler sur le projet

### Modifier

Les fichiers sont gros : **travailler par ancres exactes** (remplacement de chaîne
unique) plutôt que de réécrire un fichier entier. Vérifier systématiquement qu'une
ancre est unique avant de remplacer.

### Vérifier la syntaxe

```bash
python3 -c "
import io,re
s=io.open('championnat-district.html',encoding='utf-8').read()
open('/tmp/x.js','w',encoding='utf-8').write('\n'.join(re.findall(r'<script>(.*?)</script>',s,re.S)))
" && node --check /tmp/x.js
```

### Tester pour de vrai

Chromium est disponible. Charger la page en `file://`, bloquer le réseau externe,
injecter un `state` de test, appeler les fonctions directement :

```js
const ctx = await b.newContext();
for (const h of ['**supabase.co**','**cdn.jsdelivr.net**','**azureedge.net**'])
  await ctx.route(h, r=>r.abort());
page.on('pageerror', e=>err.push(e.message));   // toujours écouter les erreurs
await page.evaluate(()=>{ state = normalize({…}); save(); buildDivTabs(); buildBody(); });
```

Pour tester la lecture des sauvegardes, servir le dépôt sur un petit serveur local
(le dossier `sauvegardes/` doit être joignable en relatif).

**Ne jamais tester sur les vraies données en ligne sans neutraliser la sauvegarde** :
`window.__vraiSave = save; save = function(){};` puis recharger la page à la fin.

### Publier

GitHub Pages sert `main` : commit + push, puis compter **40 à 60 secondes** avant
que la nouvelle version soit servie. Toujours vérifier en ligne avec un
cache-buster (`?v=42`) et contrôler le badge de version dans le `<h1>`.

Chaque page porte ce badge, à mettre à jour à chaque livraison :

```html
<span style="…background:#2ea043…">version 29 sept · réserve ✓</span>
```

---

## 4. Conventions de code

- **Tout en français** : noms de fonctions, de variables, commentaires. `classement()`,
  `estReporte()`, `corbeilleDeposer()`.
- Les commentaires expliquent **pourquoi**, pas quoi — souvent une règle de la
  Fédération ou un piège déjà rencontré.
- **Vérifier par `grep` qu'un nom de fonction n'existe pas déjà avant de le créer.**
  Une collision ne lève aucune erreur, elle écrase silencieusement : c'est arrivé
  avec `htmlFaceAFace` (fonctionnalité invisible) et avec un double `formeEquipe`
  (bandeau rouge d'erreur en production).
- Les textes affichés s'adressent à Joris : « Coche les clubs à effacer »,
  « il ne compte pas dans les résultats à mettre ».

---

## 5. Ce que le carnet sait faire (et où)

**Marqueurs sur un match** — tous dans `state.scores[idMatch]` :

| Champ | Sens | Effet |
|---|---|---|
| `forfh` / `forfa` | forfait simple | −1 point à l'équipe |
| `rep` | match reporté | sort des rappels et de « À voir » ; s'efface si un score est saisi |
| `arr` = `'garde'` | arrêté, score homologué | compte normalement |
| `arr` = `'rejouer'` | arrêté, à rejouer | ne compte pas au classement, ne qualifie personne |
| `resv` = `'dom'`/`'ext'` | réserve déposée | purement informatif, le score compte |

`rep` et `arr` s'excluent. Inverser domicile/extérieur fait suivre `resv`.

**Forfait général** (`poule.ffgen[equipe]` = `'aller'` ou `'retour'`) : règle FFF —
déclaré pendant les matchs aller, tous les résultats de l'équipe sont annulés ;
pendant les retours, ses résultats restent et les matchs suivants sont perdus 0-3.
L'équipe est toujours classée dernière. Un rappel apparaît à partir de 3 forfaits.

**Équipes exemptes** : championnat → `poule.exempts[journée]` (liste d'équipes ; l'exempt
ne marque aucun point, le classement n'est pas touché ; la liste propose les équipes de la poule
sans match à cette journée). Coupes → `tour.exempts` (liste ; qualifiées d'office, affichées
dans « Résultats »). Choix par la fenêtre « Ajouter un match », en mode une seule équipe.

**Récap des journées** (onglet « 📅 Journées ») : par journée, les dates, l'état, et
le détail de ce qui manque. Un match est « en retard » si sa date est passée et que
le score est vide. Un bandeau en haut de page résume toutes poules confondues.

**Face à face FFF** : historique des confrontations entre deux équipes, avec une
estimation de l'issue (lissage de Laplace + écart de buts + récence). Fonctions
préfixées `ff`/`fff` dans les deux carnets.

---

**Boîte à idées** (bouton 💡 en bas à droite de chaque page) : Joris écrit une idée,
la garde en brouillon ou l'envoie. Le même bloc `<script>` est collé à la fin des cinq
pages (fonction fermée, classes `ij-`) : **le modifier partout à la fois**. Ligne Supabase
`idees_joris`, écrite seulement sur un geste de Joris, fusion par `id` (le `maj` le plus
récent gagne), pierre tombale `etat:'effacee'` 60 jours. États : `brouillon` → `envoyee`
→ `ticket` → `faite` / `refusee`.

Le robot `.github/workflows/idees.yml` + `outils/idees-github.py` passe toutes les
15 minutes : chaque idée `envoyee` devient un ticket (étiquette « idée de Joris »,
attribué à Olivier, qui reçoit un mail), marqué `<!-- idee:ID -->` pour ne jamais le
créer deux fois. Le dernier commentaire d'Olivier sur le ticket devient la « réponse de
papa » ; ticket fermé = `faite`, fermé *not planned* = `refusee`.

**Réaliser une idée** (« fais l'idée de Joris, ticket n°12 ») : lire le ticket, faire la
modification, publier comme d'habitude avec `Fixes #12` dans le message de commit (ou
de la pull request) : le ticket se ferme et Joris voit ✅ au passage suivant du robot.

> ⚠️ En test : ouvrir la boîte envoie au nuage les idées restées sur l'appareil. Une
> idée de test dans le `localStorage` de `localhost` part donc dans la vraie base dès
> qu'on ouvre la boîte sans `fetch` intercepté — c'est arrivé. Intercepter `fetch`
> dans **chaque** page ouverte (iframes comprises) et vider `idees_joris_v1` après.

## 6. L'API de la Fédération

`https://api-dofa.fff.fr` — ouverte, sans clé, CORS autorisé, 30 résultats par page
(Hydra / API Platform). Utilisée depuis le navigateur pour relier les clubs et
chercher les confrontations.

Deux identifiants à ne pas confondre : **`cl_no`** est la clé interne de l'API,
**`affiliation_number`** est le numéro officiel affiché sur fff.fr.

> ⚠️ **Le piège qui a corrompu 40 clubs** : `/api/clubs?affiliation_number=X`
> **ne filtre pas**. Il renvoie la première page des 15 000 clubs. Toujours vérifier
> le résultat :
> ```js
> const bon = liste.find(c => +c.affiliation_number === +num);
> ```

Autres limites connues : les requêtes depuis un datacenter (runners GitHub, conteneurs)
reçoivent un 403 — seul le navigateur d'Olivier passe. Et le pré-filtre par
`competition.cp_no` sur `/api/engagements` ne marche que pour la saison en cours.

Le fichier `claude/api-fff-ce-qui-marche.md`, dans le projet claude.ai, détaille
les points d'entrée vérifiés. `outils/archive-fff.py` + `.github/workflows/archive-fff.yml`
moissonnent les archives (3 saisons récoltées, bloqué depuis).

---

## 7. Travailler avec Olivier

- Il signale un besoin en une phrase, souvent au nom de Joris, parfois avec une photo
  de l'écran. Il attend que ce soit **en ligne et vérifié**, pas seulement écrit.
- Les questions de conception valent la peine d'être posées quand elles changent le
  résultat (ex. « le score d'un match arrêté compte-t-il ? ») — il tranche vite et bien.
- Il tient à la justesse des règles de la Fédération. Quand une règle existe, la suivre.
- Son PC n'est pas toujours allumé. Sans lui, pas de `git push` possible depuis une
  session Cowork : le proxy refuse d'écrire sur le dépôt. En Claude Code sur sa machine,
  ce problème disparaît.

---

## 8. Ce qui reste ouvert

- **Étages FFF / Ligue / District** : une barre pour choisir le niveau, avec la liste
  des 18 ligues et des 101 départements rangés par ligue. Développé et testé fin
  septembre, puis **mis de côté à la demande de Joris** — et la branche qui le gardait
  a été perdue avec le conteneur de la session. **À refaire si le sujet revient.**
- **Championnats internationaux** (Coupe du monde, Euro, Ligue des champions) :
  évoqué, repoussé.
- Cinq clubs (ententes) ne peuvent pas être reliés à la Fédération : ils n'y existent plus.
- L'archive des confrontations s'arrête à 3 saisons (blocage des IP de datacenter).
- Pages de redirection depuis l'ancien hébergement Free : générées, jamais envoyées en FTP.
- `actions/checkout@v4` affiche un avertissement Node 20 ; non traité faute de pouvoir tester.
