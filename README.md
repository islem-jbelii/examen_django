# CareerPathTN — Plateforme d'orientation professionnelle pour les jeunes tunisiens

Plateforme multi-acteurs de suivi et d'orientation professionnelle pour les jeunes tunisiens de 15 à 25 ans.
Développée avec Django 4.2, Django REST Framework, Bootstrap 5 et Chart.js.

---

## Prérequis

- Python 3.11+
- PostgreSQL 14+ (ou SQLite pour le développement local)
- pip

---

## Installation

```bash
# 1. Cloner le dépôt
git clone <url-du-depot>
cd careerpathtn

# 2. Créer et activer l'environnement virtuel
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env selon votre environnement

# 5. Appliquer les migrations
python manage.py migrate

# 6. Charger les données initiales (secteurs, parcours, comptes de démo)
python manage.py loaddata fixtures/initial_data.json
python manage.py seed_users

# 7. Générer des données synthétiques depuis les fichiers CSV
python manage.py generate_sample_data

# Pour effacer et recharger
python manage.py generate_sample_data --clear

# 8. Lancer le serveur de développement
python manage.py runserver
```

Accéder à l'application : http://127.0.0.1:8000/

---

## Comptes de test

| Email | Mot de passe | Rôle |
|-------|-------------|------|
| admin@careerpathtn.tn | admin123 | Administrateur |
| counselor@careerpathtn.tn | counsel123 | Conseiller d'orientation |
| mentor1@careerpathtn.tn | mentor123 | Mentor (Informatique) |
| mentor2@careerpathtn.tn | mentor234 | Mentor (Santé) |
| youth1@careerpathtn.tn | youth123 | Jeune (18 ans) |
| youth2@careerpathtn.tn | youth234 | Jeune (20 ans) |

---

## Lancer les tests

```bash
# Tous les tests (40 tests)
pytest --ds=config.settings -v

# Avec couverture de code
pytest --ds=config.settings --cov=apps --cov-report=html -v

# Tests unitaires uniquement
pytest tests/unit/ -v

# Tests d'intégration uniquement
pytest tests/integration/ -v
```

---

## Commandes de gestion

```bash
# Générer des données synthétiques réalistes depuis les CSV
python manage.py generate_sample_data

# Effacer et régénérer les données synthétiques
python manage.py generate_sample_data --clear

# Lancer toutes les vérifications d'alertes (idempotent)
python manage.py check_alerts

# Créer les comptes de démo avec mots de passe hachés
python manage.py seed_users
```

---

## Structure du projet

```
careerpathtn/
├── config/                  # Settings, URLs racine, WSGI
├── apps/
│   ├── accounts/            # Modèle User personnalisé, rôles, AuditLog
│   │   └── management/commands/
│   │       ├── seed_users.py
│   │       └── generate_sample_data.py
│   ├── youth/               # YouthProfile, InterestAssessment, score de préparation
│   ├── careers/             # CareerSector, CareerPath
│   ├── mentorship/          # MentorProfile, MentorshipSession
│   ├── guidance/            # ActionPlan
│   ├── alerts/              # Moteur d'alertes
│   │   └── management/commands/check_alerts.py
│   └── dashboard/           # Tableaux de bord, exports CSV/PDF, API KPIs
├── templates/               # Templates Bootstrap 5
│   ├── base.html
│   ├── accounts/
│   ├── youth/
│   ├── mentorship/
│   ├── guidance/
│   ├── alerts/
│   ├── dashboard/
│   └── errors/              # 403, 404, 500
├── tests/
│   ├── conftest.py          # Fixtures partagées
│   ├── unit/                # 20 tests unitaires
│   └── integration/         # 20 tests d'intégration
├── docs/                    # Documentation
├── fixtures/
│   └── initial_data.json    # Secteurs, parcours, comptes de démo
├── static/
│   └── samples/
│       └── malformed_youth.csv  # CSV de test avec erreurs intentionnelles
├── .env.example
├── pytest.ini
└── requirements.txt
```

---

## Architecture et rôles

### Rôles utilisateurs

| Rôle | Description | Accès |
|------|-------------|-------|
| **YOUTH** | Jeune tunisien 15-25 ans | Son propre profil, ses plans, ses séances |
| **COUNSELOR** | Conseiller d'orientation | Jeunes assignés, plans, évaluations, alertes |
| **MENTOR** | Professionnel bénévole | Jeunes assignés, ses propres séances |
| **ADMIN** | Administrateur | Accès complet + Django Admin |

### Score de préparation (0-100)

| Condition | Points |
|-----------|--------|
| Évaluation complétée | +30 |
| Plan d'action ACTIF | +25 |
| Secteurs d'intérêt (× poids) | +N×10 |
| Niveau BAC ou supérieur | +15 |
| Mentor assigné + séance complétée | +20 |
| Statut INACTIF | -30 |

---

## API REST

Base URL : `/api/`

| Endpoint | Méthodes | Permission |
|----------|---------|------------|
| `/api/youth/profiles/` | GET, POST | Conseiller/Admin |
| `/api/youth/profiles/<uuid>/` | GET, PUT | Filtré par rôle |
| `/api/mentorship/sessions/` | GET, POST | Mentor/Conseiller/Admin |
| `/api/mentorship/sessions/<uuid>/` | GET, PUT | Filtré par rôle |
| `/api/careers/sectors/` | GET | Tous authentifiés |
| `/api/careers/paths/` | GET | Tous authentifiés |
| `/api/alerts/` | GET | Conseiller/Admin |
| `/api/alerts/<uuid>/read/` | POST | Conseiller/Admin |
| `/api/dashboard/kpis/` | GET | Conseiller/Admin |

---

## Tableau de bord de suivi

Accessible à `/dashboard/monitoring/` (Conseiller et Admin uniquement).

**KPIs** : Jeunes actifs, alertes HIGH, séances manquées, plans expirant, mentors disponibles, parcours complétés.

**Graphiques Chart.js** :
1. Barres : Jeunes par statut
2. Camembert : Top 5 secteurs d'intérêt
3. Lignes : Séances par semaine (8 semaines)
4. Barres horizontales : Top 10 gouvernorats
5. Donut : Distribution du score de préparation

**Exports** : CSV filtré (`/dashboard/export/csv/`) et PDF ReportLab (`/dashboard/export/pdf/`).

---

## Documentation

- [`docs/problem_statement.md`](docs/problem_statement.md) — Énoncé du problème
- [`docs/roles_matrix.md`](docs/roles_matrix.md) — Matrice des permissions
- [`docs/state_machine.md`](docs/state_machine.md) — Machine à états YouthProfile
- [`docs/risk_register.md`](docs/risk_register.md) — Registre des risques
- [`docs/ethics_and_limitations.md`](docs/ethics_and_limitations.md) — Éthique et limitations

---

## Configuration PostgreSQL (production)

Dans `.env` :
```
USE_SQLITE=False
DB_NAME=careerpathtn_db
DB_USER=postgres
DB_PASSWORD=votre_mot_de_passe
DB_HOST=localhost
DB_PORT=5432
SECRET_KEY=votre-cle-secrete-longue-et-aleatoire
DEBUG=False
ALLOWED_HOSTS=votre-domaine.tn
```

Créer la base de données :
```bash
createdb careerpathtn_db
python manage.py migrate
```
