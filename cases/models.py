"""
Modèles pour l'app `cases`.

Ce fichier définit les modèles suivants (dans l'ordre demandé) :
1. Student
2. RiskThreshold
3. Case
4. CaseEvent
5. HealthRecord
6. Alert

Les docstrings et messages d'erreur sont en français.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import operator
from decimal import Decimal


def validate_student_code(value):
    if not isinstance(value, str) or not value.startswith('STU-'):
        raise ValidationError('Le code étudiant doit commencer par "STU-".')


def validate_age(value):
    if value is None:
        return
    if not (5 <= int(value) <= 25):
        raise ValidationError('L\'âge doit être compris entre 5 et 25 ans.')


class Student(models.Model):
    """Représente un jeune suivi par la plateforme.

    Champs clés:
    - `student_code`: identifiant unique commençant par 'STU-'
    - `first_name`, `last_name`, `age`, `gender`, `region`
    - `school_name`, `grade_level`
    - `created_at`, `created_by`

    Méthodes:
    - `get_full_name()` renvoie le nom complet.
    """

    GENDER_M = 'M'
    GENDER_F = 'F'
    GENDER_X = 'X'
    GENDER_CHOICES = [
        (GENDER_M, 'Masculin'),
        (GENDER_F, 'Féminin'),
        (GENDER_X, 'Autre'),
    ]

    REGION_TUNIS = 'TUNIS'
    REGION_SFAX = 'SFAX'
    REGION_SOUSSE = 'SOUSSE'
    REGION_MONASTIR = 'MONASTIR'
    REGION_BIZERTE = 'BIZERTE'
    REGION_GABES = 'GABES'
    REGION_AUTRE = 'AUTRE'
    REGION_CHOICES = [
        (REGION_TUNIS, 'Tunis'),
        (REGION_SFAX, 'Sfax'),
        (REGION_SOUSSE, 'Sousse'),
        (REGION_MONASTIR, 'Monastir'),
        (REGION_BIZERTE, 'Bizerte'),
        (REGION_GABES, 'Gabès'),
        (REGION_AUTRE, 'Autre'),
    ]

    student_code = models.CharField(max_length=64, unique=True, validators=[validate_student_code])
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    age = models.PositiveSmallIntegerField(validators=[validate_age])
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    region = models.CharField(max_length=32, choices=REGION_CHOICES, default=REGION_AUTRE)
    school_name = models.CharField(max_length=255, blank=True)
    grade_level = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.get_full_name()} ({self.student_code})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


class RiskThreshold(models.Model):
    """Seuils de risque utilisés pour évaluer un dossier.

    - `indicator`: type d'indicateur (ABSENCES, GRADE_AVG, MISSED_SESSIONS)
    - `operator`: GTE/LTE/GT/LT
    - `threshold_value`: valeur numérique
    - `risk_level`: LOW/MEDIUM/HIGH/CRITICAL
    - `evaluate(value)`: retourne True si la valeur déclenche le seuil
    """

    IND_ABSENCES = 'ABSENCES'
    IND_GRADE_AVG = 'GRADE_AVG'
    IND_MISSED = 'MISSED_SESSIONS'
    INDICATOR_CHOICES = [
        (IND_ABSENCES, 'Absences'),
        (IND_GRADE_AVG, 'Moyenne des notes'),
        (IND_MISSED, 'Séances manquées'),
    ]

    OP_GTE = 'GTE'
    OP_LTE = 'LTE'
    OP_GT = 'GT'
    OP_LT = 'LT'
    OPERATOR_CHOICES = [
        (OP_GTE, '>= (GTE)'),
        (OP_LTE, '<= (LTE)'),
        (OP_GT, '> (GT)'),
        (OP_LT, '< (LT)'),
    ]

    RISK_LOW = 'LOW'
    RISK_MEDIUM = 'MEDIUM'
    RISK_HIGH = 'HIGH'
    RISK_CRITICAL = 'CRITICAL'
    RISK_CHOICES = [
        (RISK_LOW, 'Low'),
        (RISK_MEDIUM, 'Medium'),
        (RISK_HIGH, 'High'),
        (RISK_CRITICAL, 'Critical'),
    ]

    indicator = models.CharField(max_length=32, choices=INDICATOR_CHOICES)
    operator = models.CharField(max_length=8, choices=OPERATOR_CHOICES)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2)
    risk_level = models.CharField(max_length=16, choices=RISK_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.indicator} {self.operator} {self.threshold_value} -> {self.risk_level}"

    def evaluate(self, value) -> bool:
        """Évalue le seuil pour une valeur donnée.

        La valeur est comparée selon `operator`. Retourne True si le
        seuil est déclenché.
        """
        if value is None:
            return False
        op_map = {
            self.OP_GTE: operator.ge,
            self.OP_LTE: operator.le,
            self.OP_GT: operator.gt,
            self.OP_LT: operator.lt,
        }
        func = op_map.get(self.operator)
        if func is None:
            return False
        try:
            left = Decimal(value)
            right = Decimal(self.threshold_value)
        except Exception:
            return False
        return func(left, right)


class Case(models.Model):
    """Modèle central représentant un dossier de suivi.

    Le modèle gère les transitions d'état via `VALID_TRANSITIONS` et fournit
    des helpers pour vérifier et effectuer des transitions de façon atomique.
    """

    STATUS_NEW = 'NEW'
    STATUS_ASSESSMENT = 'ASSESSMENT'
    STATUS_INTERVENTION = 'INTERVENTION'
    STATUS_FOLLOW_UP = 'FOLLOW_UP'
    STATUS_CLOSED = 'CLOSED'

    STATUS_CHOICES = [
        (STATUS_NEW, 'Nouveau'),
        (STATUS_ASSESSMENT, 'Évaluation'),
        (STATUS_INTERVENTION, 'Intervention'),
        (STATUS_FOLLOW_UP, 'Suivi'),
        (STATUS_CLOSED, 'Clôturé'),
    ]

    # Définition explicite des transitions valides
    VALID_TRANSITIONS = {
        STATUS_NEW: [STATUS_ASSESSMENT],
        STATUS_ASSESSMENT: [STATUS_INTERVENTION, STATUS_CLOSED],
        STATUS_INTERVENTION: [STATUS_FOLLOW_UP, STATUS_CLOSED],
        STATUS_FOLLOW_UP: [STATUS_CLOSED],
        STATUS_CLOSED: [],
    }

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='cases')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='cases_created')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='cases_assigned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Champs supplémentaires potentiels pour le calcul de risque (optionnels)
    absences = models.PositiveIntegerField(default=0)
    grade_avg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    missed_sessions = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dossier #{self.pk} - {self.title} [{self.status}]"

    def can_transition_to(self, new_status: str) -> bool:
        """Retourne True si `new_status` est une transition valide depuis l'état courant."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status: str, user=None, reason: str = ''):
        """Effectue une transition si elle est valide, crée un `CaseEvent`.

        Lève `ValidationError` avec un message en français si la transition est invalide.
        """
        if new_status == self.status:
            raise ValidationError(_('La transition demandée correspond déjà au statut courant.'))

        if not self.can_transition_to(new_status):
            msg = f"Transition invalide: impossible de passer de {self.status} à {new_status}."
            raise ValidationError(msg)

        from_status = self.status
        with transaction.atomic():
            self.status = new_status
            self.save()
            CaseEvent.objects.create(
                case=self,
                user=user,
                from_status=from_status,
                to_status=new_status,
                reason=reason,
            )

    def compute_risk(self):
        """Parcourt les `RiskThreshold` actifs et retourne le niveau maximum déclenché.

        Retourne un tuple `(risk_level, explanation_list)` où `risk_level` est
        l'un des niveaux définis dans `RiskThreshold` (ou `LOW` si aucun seuil)
        et `explanation_list` est une liste des descriptions des règles déclenchées.

        Note: les indicateurs sont lus depuis les champs `absences`, `grade_avg`,
        et `missed_sessions` du `Case`. Si votre logique métier stocke ces
        valeurs ailleurs, adaptez `get_indicator_value`.
        """
        active_thresholds = RiskThreshold.objects.filter(is_active=True)
        triggered = []
        level_order = [RiskThreshold.RISK_LOW, RiskThreshold.RISK_MEDIUM, RiskThreshold.RISK_HIGH, RiskThreshold.RISK_CRITICAL]

        def level_index(lvl):
            try:
                return level_order.index(lvl)
            except ValueError:
                return 0

        max_level = RiskThreshold.RISK_LOW

        for thr in active_thresholds:
            value = self.get_indicator_value(thr.indicator)
            if thr.evaluate(value):
                triggered.append(f"{thr.indicator} {thr.operator} {thr.threshold_value} -> {thr.risk_level}: {thr.description}")
                if level_index(thr.risk_level) > level_index(max_level):
                    max_level = thr.risk_level

        return max_level, triggered

    def get_indicator_value(self, indicator):
        """Retourne la valeur de l'indicateur pour ce dossier.

        Par défaut, lit `absences`, `grade_avg`, `missed_sessions` depuis le modèle.
        """
        if indicator == RiskThreshold.IND_ABSENCES:
            return self.absences
        if indicator == RiskThreshold.IND_GRADE_AVG:
            return self.grade_avg
        if indicator == RiskThreshold.IND_MISSED:
            return self.missed_sessions
        return None


class CaseEvent(models.Model):
    """Événement d'historique lié à une transition ou action sur un dossier.

    Contient qui, quand et pourquoi.
    """

    case = models.ForeignKey('Case', on_delete=models.CASCADE, related_name='events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    from_status = models.CharField(max_length=32, blank=True, null=True)
    to_status = models.CharField(max_length=32)
    reason = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        user_repr = self.user.username if self.user else 'Système'
        ts = timezone.localtime(self.timestamp).isoformat()
        return f"{ts} - {user_repr}: {self.from_status} -> {self.to_status}"


class HealthRecord(models.Model):
    """Séance santé associée à un `Student`.

    Statuts: SCHEDULED/ATTENDED/MISSED/CANCELLED
    """

    STATUS_SCHED = 'SCHEDULED'
    STATUS_ATT = 'ATTENDED'
    STATUS_MIS = 'MISSED'
    STATUS_CAN = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_SCHED, 'Planifié'),
        (STATUS_ATT, 'Présent'),
        (STATUS_MIS, 'Manqué'),
        (STATUS_CAN, 'Annulé'),
    ]

    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='health_records')
    session_date = models.DateTimeField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_SCHED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-session_date']

    def __str__(self):
        return f"Séance {self.student.get_full_name()} @ {self.session_date.date()} [{self.status}]"


class Alert(models.Model):
    """Alerte déclenchée pour transparence; peut référencer une règle déclenchée.

    Le champ `triggered_by_rule` permet de tracer quelle `RiskThreshold` a
    provoqué l'alerte.
    """

    LEVEL_INFO = 'info'
    LEVEL_WARNING = 'warning'
    LEVEL_CRITICAL = 'critical'
    LEVEL_CHOICES = [
        (LEVEL_INFO, 'Info'),
        (LEVEL_WARNING, 'Avertissement'),
        (LEVEL_CRITICAL, 'Critique'),
    ]

    case = models.ForeignKey('Case', on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    message = models.TextField()
    active = models.BooleanField(default=True)
    triggered_by_rule = models.ForeignKey(RiskThreshold, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = self.case or self.student or 'Général'
        return f"Alerte ({self.level}) pour {target}: {self.message[:60]}"
