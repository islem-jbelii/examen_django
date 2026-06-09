"""
guidance/models.py — ActionPlan
"""
import uuid
from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import User, UserRole
from apps.careers.models import CareerSector, CareerPath
from apps.youth.models import YouthProfile


class ActionPlanStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    VALIDATED = "VALIDATED", "Validé"
    ACTIVE = "ACTIVE", "Actif"
    COMPLETED = "COMPLETED", "Complété"
    CANCELLED = "CANCELLED", "Annulé"


class ActionPlan(models.Model):
    """
    Orientation action plan created by a counselor for a youth.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youth = models.ForeignKey(
        YouthProfile,
        on_delete=models.CASCADE,
        related_name="action_plans",
        verbose_name="Jeune",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_plans",
        limit_choices_to={"role": UserRole.COUNSELOR},
        verbose_name="Créé par (conseiller)",
    )
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_plans",
        verbose_name="Validé par",
    )
    validated_at = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    status = models.CharField(
        max_length=15,
        choices=ActionPlanStatus.choices,
        default=ActionPlanStatus.DRAFT,
        verbose_name="Statut",
    )
    objectives = models.TextField(verbose_name="Objectifs")
    target_sector = models.ForeignKey(
        CareerSector,
        on_delete=models.SET_NULL,
        null=True,
        related_name="action_plans",
        verbose_name="Secteur cible",
    )
    target_career = models.ForeignKey(
        CareerPath,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_plans",
        verbose_name="Parcours cible",
    )
    start_date = models.DateField(verbose_name="Date de début")
    end_date = models.DateField(verbose_name="Date de fin")
    milestones = models.JSONField(
        default=list,
        verbose_name="Jalons",
        help_text='Liste d\'objets: [{"title": "...", "due_date": "YYYY-MM-DD", "done": false}]',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plan d'action"
        verbose_name_plural = "Plans d'action"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Plan d'action — {self.youth} ({self.get_status_display()})"

    def clean(self):
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError(
                    {"end_date": "La date de fin doit être postérieure à la date de début."}
                )
