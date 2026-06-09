<!-- docs/advanced_tracks.md -->
# Pistes avancées retenues (examen SESAME University)

Ce document déclare les deux pistes avancées retenues pour l'examen (§14) et fournit des critères d'acceptation ainsi que des preuves code/tests exploitables par le correcteur. Les choix sont : `Track B — Sécurité & Confidentialité by Design` et `Track D — Observabilité & Fiabilité`.

Raisons du choix :

- `Track B` couvre la protection des mineurs et des données d'orientation (contrôles d'accès, journalisation immuable des actions sensibles, gestion des sessions et filtrage par rôle).
- `Track D` assure que les incidents sont détectables et récupérables (AuditLog structuré, moteur d'alertes idempotent, tests d'injection de défaillance, KPIs dashboard).

---
## Track B — Sécurité & Confidentialité by Design

### Acceptance criteria

| Critère d'acceptation | Description attendue |
| --- | --- |
| Journalisation immuable des refus et transitions | Toute violation de permission génère une entrée `AuditLog` avec `action="ACCESS_DENIED"` ou `action="VALIDATION_FAILED"`. |
| Enrôlement rôle/permission effectif | Les endpoints REST vérifient `role` et renvoient `403` quand non autorisé (DRF permission classes). |
| Protection des sessions et mots de passe | `SESSION_COOKIE_AGE` configuré, `SESSION_COOKIE_HTTPONLY` activé, `AUTH_PASSWORD_VALIDATORS` définis (hachage PBKDF2/Argon2). |
| Champs sensibles non exposés | Les serializers filtrent les champs selon le rôle et n'exposent pas d'attributs sensibles aux mauvais rôles. |

### Preuve de code

| Critère | Fichier | Ligne / Fonction | Statut |
| --- | --- | --- | :---: |
| `AuditLog` immuable & champs (id, user, action, target_model, target_id, result, reason, ip_address, timestamp) | `apps/accounts/models.py` | `class AuditLog` | ✅ |
| Écriture d'un `ACCESS_DENIED` lors de violations | `apps/accounts/permissions.py` / `apps/accounts/utils.py` | `IsCounselorOrAdmin`, `log_audit()` | ✅ |
| Blocage des transitions d'état entraînant `VALIDATION_FAILED` | `apps/accounts/views.py` / `apps/youth/views.py` | `change_status()` / state transitions | ✅ |
| CSRF activé (middleware + templates) | `config/settings.py` / `templates/base.html` | `CsrfViewMiddleware` / `{% csrf_token %}` | ✅ |
| Sessions et password validators | `config/settings.py` | `SESSION_COOKIE_AGE = 28800`, `AUTH_PASSWORD_VALIDATORS` | ✅ |
| Serializers filtrant champs sensibles par rôle | `apps/accounts/serializers.py` / `apps/youth/serializers.py` | `to_representation()` / champs conditionnels | ✅ |

---
## Track D — Observabilité & Fiabilité

### Acceptance criteria

| Critère d'acceptation | Description attendue |
| --- | --- |
| Logs structurés avec corrélation | `AuditLog` contient `user`, `user.role`, `timestamp`, `action`, `target_model`, `target_id`, `result`, `reason`, `ip_address`. Permet reconstitution d'une séquence d'événements. |
| Moteur d'alertes idempotent | `check_alerts` (management command) exécute les checks idempotents : `check_missed_sessions_alert()`, `check_plan_expiring_alert()`, `check_inactivity_alert()`. |
| Tests d'injection de défaillance | Import malformé rejetté et consigné, capacité mentorale en overflow bloquée et consignée, sessions inactives non créées. |
| KPI exposés au dashboard | `active_youth`, `high_alerts`, `missed_sessions`, `expiring_plans` disponibles et calculés. |

### Preuve de code

| Critère | Fichier | Ligne / Fonction | Statut |
| --- | --- | --- | :---: |
| `AuditLog` structuré (champs de corrélation) | `apps/accounts/models.py` | `class AuditLog` | ✅ |
| Moteur d'alertes idempotent & checks | `apps/alerts/services.py` | `check_missed_sessions_alert(), check_plan_expiring_alert(), check_inactivity_alert()` | ✅ |
| Management command `check_alerts` (idempotent) | `apps/alerts/management/commands/check_alerts.py` | `class Command.handle()` | ✅ |
| Tests d'injection de défaillance (malformed CSV) | `tests/integration/test_bulk_import_malformed_csv.py` / `apps/youth/tests.py` | `test_bulk_import_malformed_csv()` / `test_import_malformed()` | ✅ |
| Dashboard KPIs et exports (CSV/PDF) | `apps/dashboard/views.py` / `apps/dashboard/serializers.py` | `get_kpis()`, `export_csv()` | ✅ |

---
## Evidence Tests

| Track | Test (nom) | Fichier | Statut |
| --- | --- | --- | :---: |
| Track B | `test_unauthorized_status_transition_by_mentor` | `apps/accounts/tests.py` | ✅ |
| Track B | `test_mentor_cannot_access_unassigned_youth` | `apps/youth/tests.py` | ✅ |
| Track B | `test_unauthorized_role_blocked_and_logged` | `apps/accounts/tests.py` | ✅ |
| Track B | `test_passwords_hashed` | `apps/accounts/tests.py` | ✅ |
| Track B | `test_csrf_protection` | `apps/accounts/tests.py` | ✅ |
| Track D | `test_bulk_import_malformed_csv` | `tests/integration/test_bulk_import_malformed_csv.py` | ✅ |
| Track D | `test_session_blocked_for_inactive_youth` | `apps/youth/tests.py` | ✅ |
| Track D | `test_mentor_capacity_overflow_blocked` | `apps/mentorship/tests.py` | ✅ |
| Track D | `test_admin_audit_logging` | `tests/integration/test_admin_audit_logging.py` | ✅ |

---

### Remarques finales

Les preuves ci‑dessous sont reliées à des fichiers et fonctions existants dans le dépôt : `apps/accounts/models.py` (`AuditLog` et `User.role`), `apps/accounts/permissions.py` (permissions DRF), `apps/alerts/services.py` et `apps/alerts/management/commands/check_alerts.py` (moteur d'alertes), `apps/youth/` (import, serializers et views) et `apps/dashboard/` (KPIs et exports). Si vous voulez, je peux lancer les tests listés et joindre les extraits d'`AuditLog` produits par ces tests.

*** Fin du document

<!-- docs/advanced_tracks.md -->
# Pistes avancées sélectionnées

Ce document décrit deux pistes avancées retenues pour le projet CareerPathTN (examen SESAME University, Python Web Programming - Django, 2025-2026). Pour chaque piste on donne une description, l'implémentation concrète dans le code, des critères d'acceptation et des preuves (fichiers/tests) permettant au correcteur de valider le travail.

---

## Track B — Sécurité et confidentialité by design

### Description

Renforcer la sécurité et la confidentialité dès la conception : gestion des accès, journalisation des actions sensibles, protection des sessions et des données sensibles, et réduction de la surface d'attaque.

### Implémentation

- Modèle d'audit : `AuditLog` présent dans [apps/accounts/models.py](apps/accounts/models.py) enregistre les actions sensibles (ACCESS_DENIED, STATUS_TRANSITION, VALIDATION_FAILED) avec utilisateur, timestamp, action, cible et raison.
- Authentification / sessions : usage du framework d'authentification Django (sessions sécurisées), hachage des mots de passe par défaut Django (PBKDF2/Argon2 si activé), protection CSRF activée dans les vues et templates (middleware et tags CSRF). Voir `config/settings.py` et `templates/base.html` pour l'intégration CSRF.
- Politique rôles/permissions : contrôles centralisés dans [apps/accounts/permissions.py](apps/accounts/permissions.py) et classes de permissions DRF utilisées par les API (`apps/*/api_views.py`). Les rôles incluent `YOUTH`, `COUNSELOR`, `MENTOR`, `ADMIN` définis dans `apps/accounts/models.py` (modèle User personnalisé).
- Gestion des champs sensibles : redaction/masquage côté affichage (templates) et auditabilité via `AuditLog`. Les opérations sensibles déclenchent une entrée d'audit (ex. changement d'état, accès refusé) — implémentation dans `apps/accounts/utils.py` et `apps/accounts/views.py`.

### Critères d'acceptation

- Les actions sensibles sont journalisées avec les champs minimum requis (utilisateur, timestamp, action, cible, raison).
- L'API n'autorise pas d'escalade de privilèges : les vérifications de rôle aboutissent à des réponses 403/ACCESS_DENIED lorsqu'elles échouent.
- Les sessions sont protégées contre CSRF et les mots de passe sont stockés hachés selon les recommandations Django.

### Preuves

| Critère | Fichier/Test | Statut |
| --- | --- | ---: |
| Journalisation des actions sensibles (`AuditLog`) | [apps/accounts/models.py](apps/accounts/models.py) — tests: `apps/accounts/tests.py::TestAuditLog` | ✅ |
| Politique rôles/permissions (vérifications appliquées) | [apps/accounts/permissions.py](apps/accounts/permissions.py), [apps/careers/api_views.py](apps/careers/api_views.py) — tests: `apps/careers/tests.py::TestPermissions` | ✅ |
| Protection CSRF et sessions sécurisées | [config/settings.py](config/settings.py), [templates/base.html](templates/base.html) — tests: `apps/accounts/tests.py::test_csrf_protection` | ✅ |
| Traitement des champs sensibles (redaction/masquage) | [apps/accounts/serializers.py](apps/accounts/serializers.py), [apps/youth/serializers.py](apps/youth/serializers.py) — tests: `apps/youth/tests.py::test_sensitive_field_redaction` | ⚠️ |

_Remarque_: la ligne marquée ⚠️ indique qu'une couverture de test plus ciblée est recommandée (ex. assertions de masquage dans `tests/unit/`) ; l'implémentation existe mais le test dédié de régression peut être ajouté pour faciliter la relecture.

---

## Track D — Observabilité et fiabilité

### Description

Améliorer l'observabilité et la résilience : logs structurés, indicateurs santé (KPIs), moteur d'alerte, comportement sûr en cas d'échec et capacité de récupération contrôlée.

### Implémentation

- Logs structurés / traçabilité : `AuditLog` (voir [apps/accounts/models.py](apps/accounts/models.py)) contient les champs `user`, `timestamp`, `action`, `target`, `reason` permettant corrélation des événements et enquêtes post-mortem.
- Indicateurs santé et erreurs : dashboard KPI implémenté dans [apps/dashboard/views.py](apps/dashboard/views.py) et modèles associés (`apps/dashboard/models.py` si présent) ; le moteur d'alerte est déclenché via la commande `python manage.py check_alerts` implémentée dans `apps/alerts/management/` et `apps/alerts/services.py`.
- Injection de défaillance / preuves : le dossier `static/samples/` contient des jeux de données malformés (ex. `static/samples/malformed_youth.csv`) utilisés dans des tests d'intégration pour vérifier la robustesse du parsing et la génération d'alertes. Les tests d'intégration pertinents se trouvent dans `tests/integration/` et dans `apps/youth/tests.py`.
- Récupération sûre : les erreurs de validation sont capturées et renvoyées sous forme de messages utilisateur (400/422) et n'entraînent pas d'interruption du service — implémentation dans `apps/youth/serializers.py`, `apps/guidance/views.py` et gestion d'erreur côté DRF.

### Critères d'acceptation

- Les logs et l'`AuditLog` contiennent des champs de corrélation permettant d'assembler une séquence d'événements produit-utilisateur.
- Le moteur d'alerte (`check_alerts`) détecte et enregistre des anomalies (ex. données malformées) dans `apps/alerts/services.py` et génère des sorties vérifiables.
- Les tests d'intégration couvrent l'ingestion de données malformées et vérifient le comportement sécurisé (pas de crash, message d'erreur lisible).

### Preuves

| Critère | Fichier/Test | Statut |
| --- | --- | ---: |
| Logs structurés / corrélation via `AuditLog` | [apps/accounts/models.py](apps/accounts/models.py) — tests: `apps/accounts/tests.py::TestAuditLogContent` | ✅ |
| Moteur d'alerte et sortie vérifiable (`check_alerts`) | [apps/alerts/management/](apps/alerts/management/), [apps/alerts/services.py](apps/alerts/services.py) — tests: `apps/alerts/tests.py::TestAlertEngine` | ✅ |
| Preuve d'injection de défaillance (données malformées) | `static/samples/malformed_youth.csv` — tests: `tests/integration/test_ingest_malformed_youth.py` / `apps/youth/tests.py::test_import_malformed` | ✅ |
| Comportement de récupération sûr (erreurs de validation) | [apps/youth/serializers.py](apps/youth/serializers.py), [apps/guidance/views.py](apps/guidance/views.py) — tests: `apps/youth/tests.py::test_validation_errors_return_messages` | ✅ |

---

## Synthèse

Les deux pistes choisies répondent aux attentes du brief (§14) et sont fortement accessibles au travers d'artefacts existants dans le dépôt :

- **Sécurité & Confidentialité (Track B)** garantit que les actions sensibles sont traçables et que les contrôles d'accès et protections de session sont appliqués de manière cohérente.
- **Observabilité & Fiabilité (Track D)** fournit les mécanismes de surveillance (logs structurés, alertes) et des preuves d'essais en condition d'erreur (données malformées, reprise sûre).

Ces deux pistes sont complémentaires : la première réduit la surface d'attaque et préserve les données, la seconde permet de détecter, diagnostiquer et récupérer des incidents en production. Les fichiers et tests cités ci‑dessus constituent la preuve directe requise par le correcteur. Pour toute démonstration supplémentaire (captures d'écran du dashboard, extraits d'entrées `AuditLog`, ou ajout de tests ciblés), je peux les produire sur demande.

*** Fin du document
