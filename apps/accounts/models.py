"""
accounts/models.py — Custom User model with role system + AuditLog
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    YOUTH = "YOUTH", "Jeune"
    COUNSELOR = "COUNSELOR", "Conseiller d'orientation"
    MENTOR = "MENTOR", "Mentor"
    ADMIN = "ADMIN", "Administrateur"


class User(AbstractUser):
    """
    Custom user model. Role drives all permission logic across the platform.
    """
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.YOUTH,
        verbose_name="Rôle",
    )

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["username"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # ------------------------------------------------------------------
    # Convenience role checks
    # ------------------------------------------------------------------
    @property
    def is_youth(self):
        return self.role == UserRole.YOUTH

    @property
    def is_counselor(self):
        return self.role == UserRole.COUNSELOR

    @property
    def is_mentor(self):
        return self.role == UserRole.MENTOR

    @property
    def is_admin_role(self):
        return self.role == UserRole.ADMIN


class AuditLog(models.Model):
    """
    Immutable audit trail for all significant platform actions.
    """

    class Result(models.TextChoices):
        SUCCESS = "SUCCESS", "Succès"
        FAILURE = "FAILURE", "Échec"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Utilisateur",
    )
    action = models.CharField(max_length=100, verbose_name="Action")
    target_model = models.CharField(max_length=100, blank=True, verbose_name="Modèle cible")
    target_id = models.CharField(max_length=100, blank=True, verbose_name="ID cible")
    result = models.CharField(
        max_length=10,
        choices=Result.choices,
        default=Result.SUCCESS,
        verbose_name="Résultat",
    )
    reason = models.TextField(blank=True, verbose_name="Raison")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    # request_id injecté par le middleware RequestLoggingMiddleware (uuid4 hex)
    request_id = models.CharField(max_length=64, null=True, blank=True, verbose_name="Request ID", db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Horodatage")

    class Meta:
        verbose_name = "Journal d'audit"
        verbose_name_plural = "Journaux d'audit"
        ordering = ["-timestamp"]

    def __str__(self):
        user_str = self.user.username if self.user else "system"
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {user_str} — {self.action} ({self.result})"

    def save(self, *args, **kwargs):
        """Inject request_id from thread-local middleware if available."""
        # Avoid heavy imports at module load time; import here to prevent circular import issues.
        try:
            from apps.accounts.middleware import get_request_id

            if not self.request_id:
                rid = get_request_id()
                if rid and rid != "-":
                    self.request_id = rid
        except Exception:
            # If middleware or thread-local not available, proceed without request_id
            pass
        super().save(*args, **kwargs)
