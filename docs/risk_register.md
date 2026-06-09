# Registre des risques — CareerPathTN

## Risques liés aux données

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Données personnelles de jeunes exposées | Moyen | Élevé | Permissions strictes par rôle, AuditLog complet, accès limité aux données assignées |
| Données synthétiques confondues avec données réelles | Faible | Moyen | Préfixe `synth_` sur tous les comptes générés, commande `--clear` disponible |
| Perte de données en cas de panne | Faible | Élevé | Sauvegardes PostgreSQL régulières recommandées |

## Risques liés aux décisions

| Risque | Description | Mitigation |
|--------|-------------|------------|
| Score de maturité mal interprété | Le score 0-100 pourrait être utilisé comme décision automatique | Avertissement UI sur chaque page de score : "Outil d'aide, pas de décision automatique" |
| Biais dans la pondération des secteurs | Les poids `relevance_weight` reflètent une vision subjective du marché | Révision périodique par des experts ANETI recommandée |
| Recommandations de secteurs non adaptées | L'algorithme d'évaluation est basé sur 10 questions simplifiées | Compléter avec un bilan professionnel approfondi |

## Risques opérationnels

| Risque | Description | Mitigation |
|--------|-------------|------------|
| Accès non autorisé | Un utilisateur tente d'accéder aux données d'un autre | Permissions vérifiées à chaque vue + AuditLog ACCESS_DENIED |
| Alertes silencieuses | Les alertes ne sont pas consultées par les conseillers | Badge de comptage dans la navbar, email futur recommandé |
| Surcharge du conseiller | Un conseiller avec trop de jeunes assignés | Pas de limite actuelle — recommander max 20 jeunes/conseiller |
| Mentor à capacité maximale | Assignation impossible si mentor complet | Vérification de capacité avant assignation + message d'erreur clair |

## Risques techniques

| Risque | Description | Mitigation |
|--------|-------------|------------|
| Injection SQL | Requêtes non paramétrées | Django ORM utilisé exclusivement |
| CSRF | Formulaires non protégés | `CsrfViewMiddleware` activé sur tous les formulaires |
| Mots de passe faibles | Comptes de démo avec mots de passe simples | Changer avant déploiement en production |
| DEBUG=True en production | Exposition des traces d'erreur | Variable d'environnement `DEBUG=False` obligatoire en prod |
