# Problème et contexte fonctionnel

## 1. Contexte

Les systèmes de suivi des jeunes en Tunisie sont souvent fragmentés entre établissements scolaires, centres de santé et ONG. Ils sont majoritairement réactifs : les interventions surviennent après la détection d'un problème majeur (absentéisme prolongé, crise sanitaire ou comportementale), plutôt que d'être proactives. Cette fragmentation entraîne des délais d'intervention importants, une perte d'information entre acteurs et une difficulté à prioriser les jeunes les plus à risque.

## 2. Population cible

- Jeunes âgés de 5 à 25 ans (éducation de base, secondaire, transition vers la formation/professionnel).
- Établissements scolaires (enseignants, conseillers pédagogiques, directions).
- Centres de santé et personnels médicaux/psychosociaux.
- Organisations non gouvernementales impliquées dans le suivi socioéducatif.

La plateforme vise à centraliser des indicateurs simples (absences, moyenne scolaire, séances santé manquées) et à fournir des alertes actionnables aux intervenants locaux.

## 3. Scénario 1 — Alerte scolaire

- Qui : enseignants et conseillers pédagogiques (opérateurs locaux) identifient des signaux faibles via les données scolaires.
- Quoi : détecter le décrochage scolaire ou la dégradation de la situation (absentéisme élevé, chute significative de la moyenne, signaux comportementaux) et créer des dossiers (cases) pour suivi.
- Valeur attendue : réduction du délai entre le début du risque et l'intervention (par ex. repérer et agir avant qu'un élève ne consomme 30 jours d'absence ou que sa moyenne chute sous un seuil critique).
- Validation : chaque alerte est classée (LOW / MEDIUM / HIGH / CRITICAL) et accompagnée d'une explication listant précisément les règles déclenchées (ex. "ABSENCES >= 20 → HIGH"). Le responsable pédagogique peut vérifier la logique des règles et retrouver l'historique des événements associés.

## 4. Scénario 2 — Suivi santé

- Qui : personnel médical, infirmiers scolaires, travailleurs sociaux et personnels psychosociaux.
- Quoi : suivre l'adhérence aux séances de santé et détecter les ruptures (séances manquées répétées), envoyer des rappels et générer des alertes quand un seuil est atteint.
- Valeur attendue : diminution des ruptures de suivi et meilleure continuité des prises en charge (moins d'abandons, meilleure observance aux rendez-vous).
- Validation : le système crée une `Alert` lorsque le nombre de séances manquées atteint le seuil configuré et écrit un `CaseEvent` de type `REMINDER_SENT` (ou équivalent) documentant qu'un rappel/procédure a été lancé.

## 5. Décideur

Le décideur opérationnel est le `SUPERVISOR` / conseiller ou responsable local (par exemple : chef de service, coordinateur éducatif). Ce rôle valide les transitions importantes du dossier (par exemple : `NEW → ASSESSMENT → INTERVENTION → FOLLOW_UP → CLOSED`) et priorise les actions. Les opérateurs peuvent remonter des signaux et proposer des actions ; le superviseur en confirme la pertinence et autorise les étapes suivant la politique locale.

## 6. Définition du "Done"

Critères testables que l'évaluateur peut vérifier pour considérer la fonctionnalité comme terminée :

1. Alertes automatiques : pour un ensemble de données synthétiques, les règles configurées déclenchent automatiquement des `Alert` avec le niveau attendu (ex. absences=22 → `HIGH`) et l'explication inclut la règle déclenchée.
2. Workflow validé : les transitions d'états `Case` respectent les chemins autorisés et un `CaseEvent` est créé pour chaque transition, avec `user`, `from_status`, `to_status` et `reason` remplis.
3. Suivi santé : lorsqu'un dossier a au moins le nombre de séances manquées configuré, le service de suivi crée une `Alert` et un `CaseEvent` documentant `REMINDER_SENT`.
4. Traçabilité et audit : pour chaque action critique (création de dossier, transition, génération d'alerte, import massif), une entrée `AuditLog` est enregistrée contenant l'utilisateur, l'action, le modèle affecté, l'identifiant de l'objet et un indicateur de succès/échec.

Ces critères doivent être vérifiables via tests automatisés (unitaires/intégration) et/ou via scénarios manuels documentés.

---

Fichier généré automatiquement pour servir de référence produit / base de discussion.
