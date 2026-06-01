# Youth Platform — Installation rapide

Petit guide pour démarrer le projet localement.

Prérequis
- Python 3.11
- Git

Installation (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Tests

```powershell
pytest
```

Notes
- La commande `seed_data` crée des utilisateurs `admin/supervisor/operator`.
- Si vous utilisez Docker, adaptez les variables d'environnement; un `Dockerfile` minimal est inclus.
