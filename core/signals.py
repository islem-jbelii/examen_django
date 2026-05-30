"""Signaux pour l'app `core`.

Ce module enregistre un receiver `post_save` sur le modèle `User` afin de
créer automatiquement un `UserProfile` lors de la création d'un utilisateur.

Pourquoi:
- Facilite la gestion des permissions et rôles: chaque utilisateur a un profil.
- Utiliser `get_or_create` rend l'opération idempotente (utile pour fixtures/imports).
"""
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model

from .models import UserProfile


User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée un `UserProfile` avec `role=OPERATOR` par défaut lors de la création d'un `User`.

    L'utilisation de `get_or_create` évite les erreurs si le profil existe déjà
    (par exemple lors d'imports massifs ou de fixtures de tests).
    """
    if created:
        UserProfile.objects.get_or_create(user=instance, defaults={'role': UserProfile.ROLE_OPERATOR})
