"""Formulaires Django pour l'app `cases`.

Contient :
- `StudentForm`, `CaseForm`, `CaseTransitionForm`, `HealthRecordForm`,
- `RiskThresholdForm`, `CSVImportForm`.

Les messages d'erreur sont en français.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.forms import widgets

from .models import Student, Case, HealthRecord, RiskThreshold


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['student_code', 'first_name', 'last_name', 'age', 'gender', 'region', 'school_name', 'grade_level']

    def clean_student_code(self):
        code = (self.cleaned_data.get('student_code') or '').strip()
        if not code.upper().startswith('STU-'):
            raise ValidationError('Le code étudiant doit commencer par "STU-" (insensible à la casse).')
        return code

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is None:
            raise ValidationError('L\'âge est requis.')
        try:
            age_int = int(age)
        except Exception:
            raise ValidationError('L\'âge doit être un nombre entier.')
        if not (5 <= age_int <= 25):
            raise ValidationError('L\'âge doit être compris entre 5 et 25 ans.')
        return age_int


class CaseForm(forms.ModelForm):
    # Champs supplémentaires / alias pour la forme
    case_type = forms.CharField(required=False, max_length=100)
    absences_days = forms.IntegerField(required=False)
    grade_average = forms.DecimalField(required=False, max_digits=5, decimal_places=2)
    behavior_notes = forms.CharField(required=False, widget=forms.Textarea)

    class Meta:
        model = Case
        # Inclure student et assigned_to ; autres champs sont mappés manuellement
        fields = ['student', 'assigned_to']

    def clean_grade_average(self):
        val = self.cleaned_data.get('grade_average')
        if val in (None, ''):
            return val
        try:
            dec = Decimal(val)
        except (InvalidOperation, TypeError):
            raise ValidationError('La moyenne doit être un nombre valide (0-20).')
        if not (Decimal('0') <= dec <= Decimal('20')):
            raise ValidationError('La moyenne doit être comprise entre 0 et 20.')
        return dec

    def clean_absences_days(self):
        val = self.cleaned_data.get('absences_days')
        if val in (None, ''):
            return 0
        try:
            ival = int(val)
        except Exception:
            raise ValidationError('Le nombre de jours d\'absence doit être un entier.')
        if ival < 0:
            raise ValidationError('Le nombre de jours d\'absence ne peut pas être négatif.')
        return ival

    def save(self, commit=True):
        instance: Case = super().save(commit=False)
        absences = self.cleaned_data.get('absences_days')
        if absences is not None:
            instance.absences = absences
        grade = self.cleaned_data.get('grade_average')
        if grade is not None and grade != '':
            instance.grade_avg = grade
        notes = self.cleaned_data.get('behavior_notes')
        if notes:
            # Concaténer avec la description existante
            existing = (instance.description or '')
            instance.description = (existing + '\n' + notes).strip()
        if commit:
            instance.save()
        return instance


class CaseTransitionForm(forms.Form):
    new_status = forms.ChoiceField(choices=Case.STATUS_CHOICES, label='Nouveau statut')
    reason = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Justification de la transition'}), required=True, label='Justification')
    recommendation = forms.CharField(widget=forms.Textarea, required=False)
    recommendation_explanation = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self) -> dict:
        cleaned = super().clean()
        rec = cleaned.get('recommendation')
        expl = cleaned.get('recommendation_explanation')
        if rec and not expl:
            raise ValidationError('Si une recommandation est fournie, son explication est requise.')
        return cleaned


class HealthRecordForm(forms.ModelForm):
    # champs additionnels demandés par la spec
    session_type = forms.CharField(required=False, max_length=128)
    practitioner = forms.CharField(required=False, max_length=255)

    class Meta:
        model = HealthRecord
        fields = ['session_date', 'status', 'notes']
        widgets = {
            'session_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def save(self, commit=True):
        instance: HealthRecord = super().save(commit=False)
        session_type = self.cleaned_data.get('session_type')
        practitioner = self.cleaned_data.get('practitioner')
        if session_type or practitioner:
            extra = []
            if session_type:
                extra.append(f"Type: {session_type}")
            if practitioner:
                extra.append(f"Praticien: {practitioner}")
            if instance.notes:
                instance.notes = instance.notes + '\n' + '\n'.join(extra)
            else:
                instance.notes = '\n'.join(extra)
        if commit:
            instance.save()
        return instance


class RiskThresholdForm(forms.ModelForm):
    class Meta:
        model = RiskThreshold
        fields = ['indicator', 'operator', 'threshold_value', 'risk_level', 'description', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_description(self):
        desc = (self.cleaned_data.get('description') or '').strip()
        if len(desc) < 10:
            raise ValidationError('La description doit contenir au moins 10 caractères.')
        return desc


class CSVImportForm(forms.Form):
    IMPORT_CHOICES = [
        ('EDUCATION', 'Education'),
        ('HEALTH', 'Health'),
    ]

    csv_file = forms.FileField(label='Fichier CSV')
    import_type = forms.ChoiceField(choices=IMPORT_CHOICES)
    dry_run = forms.BooleanField(initial=True, required=False, label='Simuler (dry-run)')

    def clean_csv_file(self):
        f = self.cleaned_data.get('csv_file')
        if not f:
            raise ValidationError('Aucun fichier fourni.')
        name = f.name or ''
        if not name.lower().endswith('.csv'):
            raise ValidationError('Seuls les fichiers .csv sont acceptés.')
        max_bytes = 5 * 1024 * 1024
        if f.size > max_bytes:
            raise ValidationError('Le fichier est trop volumineux (maximum 5 MB).')
        return f
