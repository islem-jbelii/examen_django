"""
youth/forms.py
"""
import csv
import io
from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from apps.careers.models import CareerSector
from apps.youth.models import YouthProfile, Governorate, EducationLevel


class YouthProfileForm(forms.ModelForm):
    interests = forms.ModelMultipleChoiceField(
        queryset=CareerSector.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Secteurs d'intérêt",
        error_messages={"required": "Sélectionnez au moins un secteur d'intérêt."},
    )

    class Meta:
        model = YouthProfile
        fields = [
            "user", "date_of_birth", "gender", "governorate",
            "education_level", "current_school_or_institution",
            "interests", "notes",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "governorate": forms.Select(attrs={"class": "form-select"}),
            "education_level": forms.Select(attrs={"class": "form-select"}),
            "current_school_or_institution": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "user": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if not (15 <= age <= 25):
                raise ValidationError(
                    f"L'âge doit être entre 15 et 25 ans (âge calculé : {age} ans)."
                )
        return dob

    def clean_interests(self):
        interests = self.cleaned_data.get("interests")
        if not interests:
            raise ValidationError("Sélectionnez au moins un secteur d'intérêt.")
        return interests


class YouthProfileUpdateForm(YouthProfileForm):
    class Meta(YouthProfileForm.Meta):
        fields = [
            "date_of_birth", "gender", "governorate",
            "education_level", "current_school_or_institution",
            "interests", "notes",
        ]


class BulkImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Fichier CSV",
        help_text=(
            "Colonnes requises : first_name, last_name, date_of_birth (YYYY-MM-DD), "
            "gender (M/F), governorate, education_level, interests (noms séparés par virgules)"
        ),
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv"}),
    )

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise ValidationError("Le fichier doit être au format CSV (.csv).")
        return f
