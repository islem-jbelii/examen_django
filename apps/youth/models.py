"""
youth/models.py — YouthProfile and InterestAssessment
"""
import uuid
from datetime import date

from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import User, UserRole
from apps.careers.models import CareerSector


class Governorate(models.TextChoices):
    TUNIS = "TUNIS", "Tunis"
    ARIANA = "ARIANA", "Ariana"
    BEN_AROUS = "BEN_AROUS", "Ben Arous"
    MANOUBA = "MANOUBA", "Manouba"
    NABEUL = "NABEUL", "Nabeul"
    ZAGHOUAN = "ZAGHOUAN", "Zaghouan"
    BIZERTE = "BIZERTE", "Bizerte"
    BEJA = "BEJA", "Béja"
    JENDOUBA = "JENDOUBA", "Jendouba"
    KEF = "KEF", "Le Kef"
    SILIANA = "SILIANA", "Siliana"
    SOUSSE = "SOUSSE", "Sousse"
    MONASTIR = "MONASTIR", "Monastir"
    MAHDIA = "MAHDIA", "Mahdia"
    SFAX = "SFAX", "Sfax"
    KAIROUAN = "KAIROUAN", "Kairouan"
    KASSERINE = "KASSERINE", "Kasserine"
    SIDI_BOUZID = "SIDI_BOUZID", "Sidi Bouzid"
    GABES = "GABES", "Gabès"
    MEDNINE = "MEDNINE", "Médenine"
    TATAOUINE = "TATAOUINE", "Tataouine"
    GAFSA = "GAFSA", "Gafsa"
    TOZEUR = "TOZEUR", "Tozeur"
    KEBILI = "KEBILI", "Kébili"


class EducationLevel(models.TextChoices):
    COLLEGE = "COLLEGE", "Collège"
    LYCEE = "LYCEE", "Lycée"
    BAC = "BAC", "Baccalauréat"
    BAC_PLUS_2 = "BAC_PLUS_2", "Bac+2"
    LICENCE = "LICENCE", "Licence"
    MASTER = "MASTER", "Master"
    DROPOUT = "DROPOUT", "Décrochage scolaire"


class YouthStatus(models.TextChoices):
    REGISTERED = "REGISTERED", "Inscrit"
    ASSESSED = "ASSESSED", "Évalué"
    PLAN_ACTIVE = "PLAN_ACTIVE", "Plan actif"
    IN_MENTORSHIP = "IN_MENTORSHIP", "En mentorat"
    COMPLETED = "COMPLETED", "Parcours complété"
    INACTIVE = "INACTIVE", "Inactif"


def _counselor_limit():
    return {"role": UserRole.COUNSELOR}


def _mentor_limit():
    return {"role": UserRole.MENTOR}


class YouthProfile(models.Model):
    """
    Core profile for a young person registered on the platform.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="youth_profile",
        verbose_name="Utilisateur",
    )
    date_of_birth = models.DateField(verbose_name="Date de naissance")
    gender = models.CharField(
        max_length=1,
        choices=[("M", "Masculin"), ("F", "Féminin")],
        verbose_name="Genre",
    )
    governorate = models.CharField(
        max_length=20,
        choices=Governorate.choices,
        verbose_name="Gouvernorat",
    )
    education_level = models.CharField(
        max_length=20,
        choices=EducationLevel.choices,
        verbose_name="Niveau d'éducation",
    )
    current_school_or_institution = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="École / Institution actuelle",
    )
    interests = models.ManyToManyField(
        CareerSector,
        blank=True,
        related_name="interested_youth",
        verbose_name="Secteurs d'intérêt",
    )
    assigned_counselor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_youth",
        limit_choices_to=_counselor_limit,
        verbose_name="Conseiller assigné",
    )
    assigned_mentor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mentored_youth",
        limit_choices_to=_mentor_limit,
        verbose_name="Mentor assigné",
    )
    status = models.CharField(
        max_length=20,
        choices=YouthStatus.choices,
        default=YouthStatus.REGISTERED,
        verbose_name="Statut",
    )
    readiness_score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Score de préparation",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil jeune"
        verbose_name_plural = "Profils jeunes"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.get_governorate_display()}"

    def clean(self):
        """Validate age between 15 and 25."""
        if self.date_of_birth:
            today = date.today()
            age = (
                today.year - self.date_of_birth.year
                - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            )
            if not (15 <= age <= 25):
                raise ValidationError(
                    {"date_of_birth": f"L'âge doit être entre 15 et 25 ans (âge actuel : {age} ans)."}
                )

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return (
            today.year - self.date_of_birth.year
            - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        )


class AssessmentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    COMPLETED = "COMPLETED", "Complété"


class InterestAssessment(models.Model):
    """
    Formal interest/aptitude assessment conducted by a counselor.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    youth = models.ForeignKey(
        YouthProfile,
        on_delete=models.CASCADE,
        related_name="assessments",
        verbose_name="Jeune",
    )
    conducted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="conducted_assessments",
        limit_choices_to=_counselor_limit,
        verbose_name="Conduit par (conseiller)",
    )
    assessment_date = models.DateField(verbose_name="Date d'évaluation")
    responses = models.JSONField(
        default=dict,
        verbose_name="Réponses",
        help_text="Dictionnaire question → réponse",
    )
    recommended_sectors = models.ManyToManyField(
        CareerSector,
        blank=True,
        related_name="recommended_in_assessments",
        verbose_name="Secteurs recommandés",
    )
    score_breakdown = models.JSONField(
        default=dict,
        verbose_name="Détail du score",
    )
    status = models.CharField(
        max_length=20,
        choices=AssessmentStatus.choices,
        default=AssessmentStatus.DRAFT,
        verbose_name="Statut",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Évaluation des intérêts"
        verbose_name_plural = "Évaluations des intérêts"
        ordering = ["-assessment_date"]

    def __str__(self):
        return f"Évaluation de {self.youth} — {self.assessment_date}"

    def clean(self):
        """Only the assigned counselor can conduct the assessment."""
        if self.conducted_by and self.youth_id:
            if (
                self.youth.assigned_counselor
                and self.conducted_by != self.youth.assigned_counselor
            ):
                raise ValidationError(
                    {"conducted_by": "Seul le conseiller assigné peut conduire cette évaluation."}
                )
