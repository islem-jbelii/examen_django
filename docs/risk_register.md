# Registre des risques

Ce registre identifie les principaux risques associés au déploiement et à l'exploitation de la plateforme, leur probabilité, leur impact, et des mesures techniques de mitigation.

| Catégorie | Risque | Probabilité | Impact | Mitigation technique |
|---|---|---:|---|---|
| Données | Fuite de données personnelles ou sensibles (ex. listes d'élèves) | Moyen | Élevé | Chiffrement in-transit et at-rest, contrôle d'accès (RBAC), MFA, journalisation centralisée (`AuditLog`), procédures d'incident, pseudonymisation des exports. |
| Données | Qualité des données (erreurs, incohérences, formats) | Élevé | Moyen | Validation stricte côté ingestion (forms/serializers), contraintes DB (validators), pipelines d'import avec `dry-run`, tests automatisés et monitoring de qualité (alerts). |
| Données | Données manquantes ou incomplètes (champs non remplis) | Moyen | Moyen | Champs obligatoires, valeurs par défaut raisonnables, UI guidée, validation pré-import et rapport d'erreurs par ligne (CSVImportService). |

| Décision | Faux positifs (alerte inutile) | Moyen | Moyen | Règles explicites, seuils paramétrables, human-in-the-loop (supervisor validation), score de confiance et batârge/statistiques sur taux FP/FN pour ré-étalonnage. |
| Décision | Faux négatifs (alerte manquée) | Moyen | Élevé | Multi-indicateurs (absences, moyenne, séances manquées), agrégation de règles, revue périodique des règles, procédure d'audit et tests de couverture des scénarios à risque. |
| Décision | Stigmatisation / étiquetage injuste d'un jeune | Moyen | Élevé | Limiter les vues détaillées aux rôles autorisés, anonymiser les rapports agrégés, explicabilité des règles déclenchées, processus d'appel et rectification par un superviseur humain. |
| Décision | «Boîte noire» / manque d'explicabilité | Moyen | Moyen | Utiliser des règles symboliques lisibles (RiskThresholds) plutôt que modèles opaques ; stocker et exposer les descriptions des règles déclenchées et la traçabilité dans `CaseEvent`. |

| Opérationnel | Accès non autorisé / compromission de comptes | Moyen | Élevé | Politiques RBAC strictes, MFA, rotation des clés, monitoring des connexions, revue des comptes, restriction d'IP/segmentation réseau en production. |
| Opérationnel | Actions hors audit (modification sans trace) | Faible | Élevé | Imposer l'enregistrement d'un `AuditLog` pour toutes les opérations sensibles, rendre les événements immuables et exportables pour revue, alerting sur suppressions/modifs massives. |
| Opérationnel | Échec / corruption lors d'import CSV | Moyen | Moyen | Validation en amont (CSVImportService), `dry-run` par défaut, transactions atomiques et rollback, journaux d'erreurs par ligne, notifications à l'opérateur. |
| Opérationnel | Perte de service / indisponibilité | Faible | Élevé | Sauvegardes régulières, health checks, monitoring et alerting (SLO/SLA), mécanismes de retry et file d'attente pour imports, redondance si nécessaire. |

## Limites reconnues

1. Indicateurs limités : la plate-forme s'appuie sur quelques indicateurs quantitatifs (absences, moyenne, séances manquées). Ces mesures ne capturent pas l'ensemble des dimensions sociales ou comportementales d'un jeune.
2. Heuristiques et seuils : les niveaux de risque sont basés sur des règles heuristiques (seuils) qui peuvent ne pas convenir à tous les contextes locaux ; un calibrage local est nécessaire.
3. Pas d'inférence causale : la plateforme signale des corrélations (absences ↑, moyenne ↓) mais ne peut établir de causalité ni remplacer l'analyse professionnelle.
4. Dépendance à la qualité des données : si la saisie est incomplète ou erronée, les alertes et priorités peuvent devenir non fiables.
5. Risque d'usage inapproprié : sans gouvernance, les alertes peuvent être utilisées pour stigmatiser ou prendre des décisions disciplinaires sans recours ; des règles de gouvernance et d'accès sont nécessaires.

---

Document concis destiné aux responsables produit, sécurité et aux équipes de déploiement.
