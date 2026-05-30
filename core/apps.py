"""Configuration de l'application `core`.

La classe `CoreConfig` importe `core.signals` dans `ready()` afin d'activer
les receivers au démarrage de Django. Sans cet import, les signaux risquent de
ne pas être enregistrés si l'app n'est pas explicitement importée ailleurs.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'
    verbose_name = 'Core'

    def ready(self):
        # Importer les signaux ici pour les enregistrer lorsque Django charge l'app.
        # Cela évite les effets de bord lors de l'import global au module level.
        import core.signals  # noqa: F401
