"""
alerts/models.py — Alert engine
"""
import uuid
from django.db import models
from apps.youth.models import YouthProfile


class AlertType(models.TextChoices):
    MISSED_SESSIONS = "MISSED_SESSIONS", "Séances manquées"
    PLAN_EXPIRING = "PLAN_EXPIRING", "Plan expirant"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS", "Accès non autorisé"
    ASSESSMENT_REQUIRED = "ASSESSMENT_REQUIRED", "Évaluation requise"
    INACTIVITY = "INACTIVITY", "Inactivité"
    MENTOR_RECOMMENDATION = "MENTOR_RECOMMENDATION", "Recommandation mentor"


class AlertSeverity(models.TextChoices):
    LOW = "LOW", "Faible"
    MEDIUM = "MEDIUM", "Moyen"
    HIGH = "HIGH", "Élevé"


class Alert(models.Model):
    """
    Platform alert linked to a youth profile.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youth = models.ForeignKey(
        YouthProfile,
        on_delete=models.CASCADE,
        related_name="alerts",
        verbose_name="Jeune",
    )
    alert_type = models.CharField(
        max_length=30,
        choices=AlertType.choices,
        verbose_name="Type d'alerte",
    )
    severity = models.CharField(
        max_length=10,
        choices=AlertSeverity.choices,
        default=AlertSeverity.MEDIUM,
        verbose_name="Sévérité",
    )
    message = models.TextField(verbose_name="Message")
    triggered_by = models.CharField(
        max_length=200,
        default="system",
        verbose_name="Déclenché par",
        help_text='"system" ou email de l\'utilisateur',
    )
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerte"
        verbose_name_plural = "Alertes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.get_alert_type_display()} — {self.youth}"
