# Le carnet de Joris

Quatre carnets de football de district, en pages HTML autonomes : championnat, coupes,
mes équipes et journal. Aucun cadre, aucune compilation — chaque page se suffit à elle-même.

Site en ligne : voir l'onglet Pages du dépôt.

## Les pages

| Fichier | Rôle |
|---|---|
| `index.html` | l'accueil, et la sauvegarde/restauration de tous les carnets en un ZIP |
| `championnat-district.html` | championnats, poules, calendrier, classements, buteurs, stats |
| `coupes-district.html` | coupes en élimination directe, tours, tirages, qualifiés |
| `mes-equipes.html` | la bibliothèque des clubs, leurs équipes et leurs logos |
| `journal.html` | le journal de Joris, jour par jour, branché sur ses matchs |

## Où vivent les données

Dans le navigateur (`localStorage`) et dans une base Supabase qui sert de trait d'union
entre le PC et le téléphone. Les fichiers de ce dépôt ne contiennent aucune donnée de match.

Le dossier `sauvegardes/` reçoit un instantané quotidien de la base, déposé automatiquement.
