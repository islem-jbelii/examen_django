# Éthique et limitations — CareerPathTN

## Données synthétiques

**Toutes les données de démonstration sont 100% synthétiques.**

- Les noms, emails, dates de naissance et profils sont générés par la commande `generate_sample_data`
- Aucune donnée réelle de jeunes tunisiens n'est utilisée
- Les données synthétiques sont identifiables par le préfixe `synth_` sur les noms d'utilisateur

## Score de préparation — Avertissement

Le score de préparation (0-100) est un **outil d'aide à la décision**, pas un jugement automatique.

> ⚠️ **Ce score ne remplace pas un bilan professionnel approfondi conduit par un conseiller qualifié.**

Limitations connues :
- Basé sur 10 questions simplifiées (évaluation des intérêts)
- La pondération des secteurs (`relevance_weight`) est configurable mais subjective
- Ne prend pas en compte les compétences réelles, le contexte familial ou les contraintes géographiques

## Recommandations générées

Chaque recommandation de secteur affichée dans l'interface est accompagnée d'un avertissement :
> "Cette recommandation est générée automatiquement à titre indicatif."

## Biais potentiels

1. **Biais de secteur** : Les secteurs avec `demand_level=HIGH` et `relevance_weight=3` (Informatique, Santé, Ingénierie) obtiennent des scores plus élevés, ce qui peut orienter les jeunes vers ces secteurs indépendamment de leurs aptitudes réelles.

2. **Biais éducatif** : Le bonus de +15 pour les niveaux BAC et supérieurs pénalise les jeunes en décrochage scolaire, qui peuvent avoir d'autres compétences non mesurées.

3. **Biais de disponibilité mentor** : Les secteurs avec plus de mentors vérifiés ont plus de chances d'être recommandés indirectement.

## Conformité RGPD (recommandations)

Pour un déploiement en production :
- Obtenir le consentement explicite des jeunes pour le traitement de leurs données
- Implémenter le droit à l'effacement (suppression de compte)
- Nommer un DPO (Délégué à la Protection des Données)
- Chiffrer les données sensibles au repos
- Limiter la durée de conservation des AuditLogs (recommandé : 2 ans)
