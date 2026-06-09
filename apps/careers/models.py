"""
careers/models.py — CareerSector and CareerPath
"""
import uuid
from django.db import models


class DemandLevel(models.TextChoices):
    LOW = "LOW", "Faible"
    MEDIUM = "MEDIUM", "Moyen"
    HIGH = "HIGH", "Élevé"


class CareerSector(models.Model):
    """
    A broad professional sector (e.g. Informatique, Santé, Agriculture).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom du secteur")
    description = models.TextField(verbose_name="Description")
    demand_level = models.CharField(
        max_length=10,
        choices=DemandLevel.choices,
        default=DemandLevel.MEDIUM,
        verbose_name="Niveau de demande",
    )
    average_salary_range = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Fourchette salariale moyenne",
    )
    required_education_level = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Niveau d'éducation requis",
    )
    relevance_weight = models.IntegerField(
        default=2,
        verbose_name="Poids de pertinence (1-3)",
        help_text="Utilisé dans le calcul du score de préparation (1=faible, 3=élevé)",
    )

    class Meta:
        verbose_name = "Secteur professionnel"
        verbose_name_plural = "Secteurs professionnels"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        if not (1 <= self.relevance_weight <= 3):
            raise ValidationError({"relevance_weight": "Le poids doit être entre 1 et 3."})


class CareerPath(models.Model):
    """
    A specific career within a sector (e.g. Développeur Web in Informatique).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sector = models.ForeignKey(
        CareerSector,
        on_delete=models.CASCADE,
        related_name="career_paths",
        verbose_name="Secteur",
    )
    title = models.CharField(max_length=200, verbose_name="Intitulé du métier")
    description = models.TextField(verbose_name="Description")
    required_skills = models.TextField(verbose_name="Compétences requises")
    training_duration_months = models.IntegerField(
        verbose_name="Durée de formation (mois)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Parcours professionnel"
        verbose_name_plural = "Parcours professionnels"
        ordering = ["sector", "title"]

    def __str__(self):
        return f"{self.title} ({self.sector.name})"
