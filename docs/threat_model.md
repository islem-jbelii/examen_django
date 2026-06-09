<!-- docs/threat_model.md -->
# Modèle de menace — CareerPathTN

Ce document synthétique (PDF §14, Track B) présente le périmètre, les actifs, les cas d'abus et les mitigations spécifiques à CareerPathTN, une plateforme multi-acteurs pour l'orientation des jeunes tunisiens (population sensible : mineurs 15–17 ans inclus).

## 1. Périmètre et hypothèses

- Périmètre protégé : données d'identité et de profil des jeunes (`apps/youth`), évaluations/assessments, plans d'action, notes de mentorat, accès API REST (`/api/`), mécanismes d'authentification et contrôles de rôle, journal d'audit (`AuditLog`).
- Hors périmètre : sécurité physique et infrastructure (serveurs, réseau, pare-feu) déléguée à l'hébergeur ; sauvegardes hors application et chiffrement disque côté infra.
- Hypothèses : environnement de développement utilise SQLite, production PostgreSQL ; authentification via sessions Django + email/password ; toutes les données utilisateurs sont synthétiques pour l'examen.

## 2. Actifs (Assets)

| Actif | Sensibilité | Justification |
| --- | ---: | --- |
| Profils des jeunes (âge, gouvernorat, niveau d'études, intérêts) | Haute | Contient des informations personnelles sur mineurs ; même si synthétiques, exigence de protection élevée. |
| Résultats d'évaluations / assessments | Haute | Données sensibles pouvant influencer orientation & décisions ; doivent rester confidentielles. |
| Plans d'action individuels | Moyenne | Contiennent objectifs et notes personnelles ; confidentialité nécessaire. |
| Notes de sessions de mentorat | Haute | Échanges potentiellement sensibles, parfois personnels. |
| Identifiants utilisateurs (mots de passe, sessions) | Haute | Compromission mène à usurpation de compte et accès aux actifs ci‑dessus. |
| `AuditLog` (journal d'actions privilégiées) | Moyenne | Intégrité critique pour traçage et preuve d'abus ; confidentialité modérée mais intégrité élevée. |
| Exports dashboard (CSV/PDF) | Moyenne | Copies dérivées pouvant être partagées ; risque de fuite de lots de profils. |

## 3. Acteurs et cas d'abus (Abuse cases)

| Acteur menaçant | Scénario d'abus | Vecteur |
| --- | --- | --- |
| Attaquant externe | Credential stuffing → usurpation de comptes d'`YOUTH`/`MENTOR` | Credentials volés/réutilisés via formulaire de connexion (`/accounts/login/`) |
| Attaquant externe | Injection SQL ciblée sur points vulnérables | Entrées non filtrées dans endpoints non paramétrés (risque faible si ORM utilisé) |
| Attaquant externe | CSRF pour déclencher actions côté utilisateur authentifié | Formulaire ou requête cross-site si token CSRF absent/mal utilisé |
| Malicious `YOUTH` | URL tampering pour lire profil d'un autre jeune | Modifications d'ID dans l'URL d'un endpoint (`/youth/<id>/`) sans filtrage par ownership |
| Malicious `MENTOR` | Accès à profils de jeunes non assignés | API non filtrant par `assigned_mentor` / permissions incomplètes |
| Malicious `COUNSELOR` | Export massif hors périmètre (exfiltration) | Endpoint d'export/dashboard accessible sans vérification scope |
| Insider `ADMIN` | Abus d'accès administratif (lecture/altération) | Compte admin utilisé pour extraire/modifier données sans contrôle |
| Session compromise | Utilisation d'une session hijackée pour actions privilégiées | Session cookie volé (XSS, interception si pas HTTPS) |

## 4. Mitigations (liées au code du projet)

| Menace | Mitigation technique | Fichier / code de référence | Statut |
| --- | --- | --- | :---: |
| Credential stuffing / password compromise | Mots de passe hachés (PBKDF2 par défaut), politique de mot de passe configurable | `config/settings.py` (Django password hashing / validators) ; `apps/accounts/models.py` (User model) | ✅ |
| CSRF (falsification de requête) | Middleware CSRF activé, tokens inclus dans templates/forms | `config/settings.py` (MIDDLEWARE), `templates/base.html` (csrf_token) | ✅ |
| SQL injection | Utilisation de l'ORM Django et requêtes paramétrées ; validation d'entrée dans serializers | `apps/*/serializers.py`, `apps/*/views.py` (QuerySets) | ✅ |
| URL tampering / accès à profil non autorisé | Filtrage au niveau des querysets par `assigned_counselor` / `assigned_mentor` et vérifications dans permissions | `apps/youth/views.py`, `apps/youth/models.py`, `apps/accounts/permissions.py` | ✅ |
| Accès mentor/counselor hors scope (export/exfiltration) | Contrôles de scope et permissions DRF ; limites sur endpoints d'export | `apps/accounts/permissions.py`, `apps/dashboard/views.py`, `apps/alerts/services.py` (logging d'exports) | ✅ |
| Abus par ADMIN / preuve & dissuasion | `AuditLog` enregistre toutes actions privilégiées (ACCESS_DENIED, STATUS_TRANSITION, VALIDATION_FAILED) | `apps/accounts/models.py` (AuditLog) — consulté par `apps/accounts/utils.py` | ✅ |
| Session compromise (hijack) | Session expiry, HttpOnly cookies, recommander HTTPS en prod (SECURE_SSL_REDIRECT) ; audit des actions sensibles | `config/settings.py` (SESSION_COOKIE_HTTPONLY, SESSION_EXPIRE_AT_BROWSER_CLOSE, SECURE_SSL_REDIRECT) ; `apps/accounts/models.py` (AuditLog) | ✅ |
| Validation côté application | Validation stricte dans serializers empêche données malformées et vecteurs d'injection | `apps/*/serializers.py` (ex. `apps/youth/serializers.py`) | ✅ |

_Statut `✅` indique mitigation implémentée ou configurée dans le code du dépôt cité. Certaines protections (WAF, rate limiting, 2FA) sont attendues côté infra/application future)._ 

## 5. Limites et risques résiduels

- Absence de mécanisme de limitation de débit (rate limiting) applicatif : risque d'attaques par force brute/credential stuffing non atténué côté app.
- Pas d'authentification multifactorielle (2FA) actuelle — un compte compromis peut toujours être utilisé même si la session est expirée.
- Pas de chiffrement champ‑à‑champ au repos dans la base (field‑level encryption) — protection des backups/infrastructure requise.
- Les contrôles d'export massifs nécessitent des revues opérationnelles : le code limite via permissions mais n'empêche pas sortie hors du périmètre si credentials valides.
- Détection d'attaques avancées (anomalie comportementale, détection d'IP malveillantes) non implémentée dans l'application — dépend de la stack d'hébergement/infra.

## 6. Tests de sécurité couvrants (exemples présents dans le dépôt)

- `apps/youth/tests.py::test_cannot_access_other_profile` — vérifie que l'`YOUTH` ne peut lire un profil non-assigné.
- `apps/accounts/tests.py::test_unauthorized_role_blocked_and_logged` — contrôle que les accès non autorisés renvoient 403 et créent une entrée `AuditLog` (ACCESS_DENIED).
- `apps/accounts/tests.py::test_passwords_hashed` — confirme que les mots de passe ne sont pas stockés en clair.
- `apps/accounts/tests.py::test_csrf_protection` — vérification que les vues protégées exigent un token CSRF.
- `tests/integration/test_admin_audit_logging.py::test_admin_actions_are_audited` — assure que les actions admin importantes sont consignées dans `AuditLog`.

---

Pour toute preuve supplémentaire (extraits d'entrées `AuditLog`, commandes `curl` reproduisant des essais, ou ajout de tests d'attaque automatisés), je peux générer les artefacts et les ajouter au dépôt sur demande.
