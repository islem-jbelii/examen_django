# Matrice des rôles et permissions

Ce tableau récapitule les actions principales et les rôles qui y ont accès.

| Action | OPERATOR | SUPERVISOR | ADMIN |
|---|---:|---:|---:|
| Créer / éditer Student | X | X | X |
| Créer / éditer Case (proposition) | X | X | X |
| Valider transition de Case |  | X | X |
| Gérer RiskThresholds |  | X | X |
| Résoudre Alert |  | X | X |
| Accès admin / migrations |  |  | X |

Les contrôles sont implémentés via `UserProfile.role` et vérifiés dans les views/APIs.
