# Machine à états — YouthProfile.status

## Diagramme des transitions

```
                    ┌─────────────────────────────────────────────────────┐
                    │                                                     │
                    ▼                                                     │
            ┌─────────────┐                                              │
            │  REGISTERED │  ← Statut initial à la création du profil   │
            └──────┬──────┘                                              │
                   │                                                     │
                   │ [Évaluation complétée]                              │
                   │ Bouton: "Lancer l'évaluation"                       │
                   ▼                                                     │
            ┌─────────────┐                                              │
            │   ASSESSED  │  ← InterestAssessment.status = COMPLETED    │
            └──────┬──────┘                                              │
                   │                                                     │
                   │ [Plan d'action validé]                              │
                   │ Bouton: "Activer le plan d'action"                  │
                   ▼                                                     │
            ┌─────────────┐                                              │
            │ PLAN_ACTIVE │  ← ActionPlan.status = VALIDATED            │
            └──────┬──────┘                                              │
                   │                                                     │
                   │ [Mentor assigné]                                    │
                   │ Bouton: "Démarrer le mentorat"                      │
                   ▼                                                     │
            ┌───────────────┐                                            │
            │ IN_MENTORSHIP │  ← assigned_mentor != null                │
            └──────┬────────┘                                            │
                   │                                                     │
                   │ [Parcours terminé]                                  │
                   │ Bouton: "Clôturer le parcours"                      │
                   ▼                                                     │
            ┌─────────────┐                                              │
            │  COMPLETED  │  ← Fin du parcours d'orientation            │
            └─────────────┘                                              │
                                                                         │
  ┌──────────────────────────────────────────────────────────────────┐  │
  │  INACTIVE  ← Depuis n'importe quel statut (sauf COMPLETED)       │──┘
  │            Bouton: "Marquer inactif"                             │
  └──────────────────────────────────────────────────────────────────┘
```

## Règles de transition

| De | Vers | Condition | Bouton |
|----|------|-----------|--------|
| REGISTERED | ASSESSED | `InterestAssessment` complétée existe | "Lancer l'évaluation" |
| ASSESSED | PLAN_ACTIVE | `ActionPlan` avec status=VALIDATED existe | "Activer le plan d'action" |
| PLAN_ACTIVE | IN_MENTORSHIP | `assigned_mentor` non null | "Démarrer le mentorat" |
| IN_MENTORSHIP | COMPLETED | (aucune condition) | "Clôturer le parcours" |
| Tout statut | INACTIVE | (aucune condition) | "Marquer inactif" |

## Effets de bord
- Chaque transition crée une entrée `AuditLog` (action=STATUS_TRANSITION)
- Les transitions bloquées créent une entrée `AuditLog` (action=VALIDATION_FAILED)
- Le score de préparation est recalculé après chaque changement de statut
- Le statut INACTIVE applique une pénalité de -30 au score de préparation
