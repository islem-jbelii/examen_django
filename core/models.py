"""
Modèles centraux pour Youth Platform.

Contient :
- `UserProfile` : extension minimale de l'utilisateur Django pour stocker le rôle et l'organisation.
- `AuditLog` : journal immuable des actions importantes de la plateforme.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
import logging


class UserProfile(models.Model):
    """Extension du modèle utilisateur Django.

    Champs:
    - user: relation OneToOne vers l'utilisateur Django
    - role: rôle de l'utilisateur (OPERATOR/SUPERVISOR/ADMIN)
    - organization: nom de l'organisation (facultatif)
    - created_at: horodatage de création

    Méthodes:
    - is_supervisor(): retourne True si l'utilisateur est `SUPERVISOR` ou `ADMIN`.
    """

    ROLE_OPERATOR = 'OPERATOR'
    ROLE_SUPERVISOR = 'SUPERVISOR'
    ROLE_ADMIN = 'ADMIN'

    ROLE_CHOICES = [
        (ROLE_OPERATOR, 'Operator'),
        (ROLE_SUPERVISOR, 'Supervisor'),
        (ROLE_ADMIN, 'Admin'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_OPERATOR)
    organization = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'User profile'
        verbose_name_plural = 'User profiles'

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def is_supervisor(self) -> bool:
        """Retourne True si le rôle est SUPERVISOR ou ADMIN."""
        return self.role in {self.ROLE_SUPERVISOR, self.ROLE_ADMIN}


class AuditLog(models.Model):
    """Journal immuable des actions utilisateur et système.

    Utilisez la méthode de classe `AuditLog.log(...)` pour créer une entrée
    et l'enregistrer également dans le logger `youth_platform`.
    """

    ACTION_CREATE = 'CREATE'
    ACTION_UPDATE = 'UPDATE'
    ACTION_DELETE = 'DELETE'
    ACTION_ACCESS_DENIED = 'ACCESS_DENIED'
    ACTION_ALERT = 'ALERT'
    ACTION_IMPORT = 'IMPORT'
    ACTION_EXPORT = 'EXPORT'

    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_ACCESS_DENIED, 'Access denied'),
        (ACTION_ALERT, 'Alert'),
        (ACTION_IMPORT, 'Import'),
        (ACTION_EXPORT, 'Export'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=255, blank=True, null=True)
    object_id = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    reason = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit log'
        verbose_name_plural = 'Audit logs'

    def __str__(self):
        user_repr = self.user.username if self.user else 'Anonymous'
        ts = timezone.localtime(self.timestamp).isoformat()
        return f"{ts} - {user_repr} - {self.action}"

    @classmethod
    def log(cls, user=None, action=None, description='', model_name=None, object_id=None, success=True, reason=None):
        """Crée une entrée d'audit et la réplique dans le logger 'youth_platform'.

        Arguments:
        - user: instance d'utilisateur (ou None)
        - action: une des constantes d'action
        - description: description libre
        - model_name: nom du modèle affecté (optionnel)
        - object_id: identifiant de l'objet (optionnel)
        - success: bool indiquant si l'action a réussi
        - reason: texte expliquant l'échec ou contexte
        """
        entry = cls.objects.create(
            user=user,
            action=action,
            description=description,
            model_name=model_name,
            object_id=object_id,
            success=success,
            reason=reason,
        )

        logger = logging.getLogger('youth_platform')
        user_repr = user.username if user else 'Anonymous'
        msg = {
            'timestamp': entry.timestamp.isoformat(),
            'user': user_repr,
            'action': action,
            'model': model_name,
            'object_id': object_id,
            'description': description,
            'success': success,
            'reason': reason,
        }

        # Log au niveau approprié
        if success:
            logger.info('Audit: %s', msg)
        else:
            logger.warning('Audit FAILURE: %s', msg)

        return entry
