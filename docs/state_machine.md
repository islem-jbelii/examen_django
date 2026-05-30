# Diagramme et description de la machine d'état des `Case`

La machine d'état du modèle `Case` est la suivante :

- `NEW` → `ASSESSMENT`
- `ASSESSMENT` → `INTERVENTION` ou `CLOSED`
- `INTERVENTION` → `FOLLOW_UP` ou `CLOSED`
- `FOLLOW_UP` → `CLOSED`

Chaque transition est validée par `Case.can_transition_to()` et effectuée
via `Case.transition_to(...)` qui crée un `CaseEvent` horodaté contenant
`user`, `from_status`, `to_status` et `reason`.

Bonnes pratiques :

- Toujours fournir une `reason` explicite pour tracer la décision.
- Les transitions critiques doivent être validées par un `SUPERVISOR`.
- Conserver les événements d'historique pour audit et réversibilité.
