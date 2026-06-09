"""
mentorship/models.py — MentorProfile and MentorshipSession
"""
import uuid
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import User, UserRole
from apps.careers.models import CareerSector
from apps.youth.models import YouthProfile, YouthStatus


class MentorAvailability(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Disponible"
    BUSY = "BUSY", "Occupé"
    UNAVAILABLE = "UNAVAILABLE", "Indisponible"


class MentorProfile(models.Model):
    """
    Extended profile for a mentor user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="mentor_profile",
        verbose_name="Utilisateur",
    )
    sector = models.ForeignKey(
        CareerSector,
        on_delete=models.SET_NULL,
        null=True,
        related_name="mentors",
        verbose_name="Secteur d'expertise",
    )
    company_name = models.CharField(max_length=200, blank=True, verbose_name="Entreprise")
    years_of_experience = models.IntegerField(verbose_name="Années d'expérience")
    bio = models.TextField(verbose_name="Biographie")
    availability = models.CharField(
        max_length=15,
        choices=MentorAvailability.choices,
        default=MentorAvailability.AVAILABLE,
        verbose_name="Disponibilité",
    )
    max_youth_capacity = models.IntegerField(default=3, verbose_name="Capacité maximale")
    current_youth_count = models.IntegerField(default=0, verbose_name="Nombre de jeunes actuels")
    is_verified = models.BooleanField(default=False, verbose_name="Vérifié")

    class Meta:
        verbose_name = "Profil mentor"
        verbose_name_plural = "Profils mentors"
        ordering = ["user__last_name"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.sector}"

    def clean(self):
        if self.current_youth_count > self.max_youth_capacity:
            raise ValidationError(
                {"current_youth_count": "Le nombre de jeunes dépasse la capacité maximale."}
            )


class SessionType(models.TextChoices):
    DISCOVERY = "DISCOVERY", "Découverte"
    SKILLS_REVIEW = "SKILLS_REVIEW", "Revue des compétences"
    CV_REVIEW = "CV_REVIEW", "Revue de CV"
    MOCK_INTERVIEW = "MOCK_INTERVIEW", "Entretien simulé"
    FOLLOW_UP = "FOLLOW_UP", "Suivi"


class SessionStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Planifiée"
    COMPLETED = "COMPLETED", "Complétée"
    MISSED = "MISSED", "Manquée"
    CANCELLED = "CANCELLED", "Annulée"


class MentorshipSession(models.Model):
    """
    A single mentorship session between a mentor and a youth.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youth = models.ForeignKey(
        YouthProfile,
        on_delete=models.CASCADE,
        related_name="mentorship_sessions",
        verbose_name="Jeune",
    )
    mentor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mentor_sessions",
        limit_choices_to={"role": UserRole.MENTOR},
        verbose_name="Mentor",
    )
    session_date = models.DateField(verbose_name="Date de la séance")
    session_type = models.CharField(
        max_length=20,
        choices=SessionType.choices,
        verbose_name="Type de séance",
    )
    status = models.CharField(
        max_length=15,
        choices=SessionStatus.choices,
        default=SessionStatus.SCHEDULED,
        verbose_name="Statut",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    recommendations = models.TextField(blank=True, verbose_name="Recommandations")
    counselor_notified = models.BooleanField(default=False, verbose_name="Conseiller notifié")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Séance de mentorat"
        verbose_name_plural = "Séances de mentorat"
        ordering = ["-session_date"]

    def __str__(self):
        return f"Séance {self.get_session_type_display()} — {self.youth} avec {self.mentor.get_full_name() or self.mentor.username}"

    def clean(self):
        errors = {}

        # Rule: session date cannot be more than 30 days in the future
        if self.session_date:
            max_future = date.today() + timedelta(days=30)
            if self.session_date > max_future:
                errors["session_date"] = (
                    "La date de séance ne peut pas être à plus de 30 jours dans le futur."
                )

        # Rule: cannot create session for INACTIVE youth
        if self.youth_id:
            try:
                youth = self.youth
                if youth.status == YouthStatus.INACTIVE:
                    errors["youth"] = (
                        "Impossible de créer une séance pour un jeune avec le statut INACTIF."
                    )
            except YouthProfile.DoesNotExist:
                pass

        if errors:
            raise ValidationError(errors)
