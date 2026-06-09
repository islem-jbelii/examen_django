# Matrice des permissions par rôle — CareerPathTN

| Action | YOUTH | COUNSELOR | MENTOR | ADMIN |
|--------|-------|-----------|--------|-------|
| Voir son propre profil | ✅ | — | — | ✅ |
| Voir les profils des jeunes assignés | — | ✅ | ✅ | ✅ |
| Voir tous les profils | ❌ | ❌ | ❌ | ✅ |
| Créer un profil jeune | ❌ | ✅ | ❌ | ✅ |
| Modifier un profil jeune | ❌ | ✅ (assignés) | ❌ | ✅ |
| Importer des profils CSV | ❌ | ✅ | ❌ | ✅ |
| Conduire une évaluation | ❌ | ✅ (assignés) | ❌ | ✅ |
| Voir son évaluation | ✅ | ✅ | ❌ | ✅ |
| Créer un plan d'action | ❌ | ✅ | ❌ | ✅ |
| Valider un plan d'action | ❌ | ✅ | ❌ | ✅ |
| Voir son plan d'action | ✅ | ✅ | ❌ | ✅ |
| Créer une séance de mentorat | ❌ | ❌ | ✅ (assignés) | ✅ |
| Modifier une séance | ❌ | ✅ (assignés) | ✅ (propres) | ✅ |
| Voir les séances | ✅ (propres) | ✅ (assignés) | ✅ (propres) | ✅ |
| Assigner un mentor | ❌ | ✅ | ❌ | ✅ |
| Voir les alertes | ❌ | ✅ (assignés) | ❌ | ✅ |
| Marquer une alerte comme lue | ❌ | ✅ | ❌ | ✅ |
| Tableau de bord de suivi | ❌ | ✅ | ❌ | ✅ |
| Exporter CSV/PDF | ❌ | ✅ | ❌ | ✅ |
| Accès Django Admin | ❌ | ❌ | ❌ | ✅ |
| Gérer le catalogue secteurs/métiers | ❌ | ❌ | ❌ | ✅ |
| Voir le catalogue secteurs/métiers | ✅ | ✅ | ✅ | ✅ |

## Notes
- **COUNSELOR** : accès limité aux jeunes qui lui sont assignés (`assigned_counselor = request.user`)
- **MENTOR** : accès limité aux jeunes qui lui sont assignés (`assigned_mentor = request.user`)
- **YOUTH** : accès uniquement à ses propres données
- Toute violation de permission est enregistrée dans `AuditLog` avec `action=ACCESS_DENIED`
