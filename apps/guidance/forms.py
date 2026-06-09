"""
guidance/forms.py
"""
import json
from django import forms
from apps.guidance.models import ActionPlan
from apps.careers.models import CareerSector, CareerPath
from apps.youth.models import YouthProfile


class ActionPlanForm(forms.ModelForm):
    milestones_json = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial="[]",
    )

    class Meta:
        model = ActionPlan
        fields = [
            "youth", "objectives", "target_sector", "target_career",
            "start_date", "end_date",
        ]
        widgets = {
            "youth": forms.Select(attrs={"class": "form-select"}),
            "objectives": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "target_sector": forms.Select(attrs={"class": "form-select", "id": "id_target_sector"}),
            "target_career": forms.Select(attrs={"class": "form-select", "id": "id_target_career"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, counselor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if counselor:
            self.fields["youth"].queryset = YouthProfile.objects.filter(
                assigned_counselor=counselor
            ).select_related("user")
            self.fields["youth"].label_from_instance = (
                lambda obj: obj.user.get_full_name() or obj.user.username
            )
        self.fields["target_career"].queryset = CareerPath.objects.select_related("sector").filter(is_active=True)
        self.fields["target_career"].required = False

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end <= start:
            raise forms.ValidationError(
                {"end_date": "La date de fin doit être postérieure à la date de début."}
            )
        return cleaned

    def clean_milestones_json(self):
        raw = self.cleaned_data.get("milestones_json", "[]")
        try:
            data = json.loads(raw or "[]")
            if not isinstance(data, list):
                raise forms.ValidationError("Format de jalons invalide.")
            return data
        except (json.JSONDecodeError, ValueError):
            return []

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.milestones = self.cleaned_data.get("milestones_json", [])
        if commit:
            instance.save()
        return instance
