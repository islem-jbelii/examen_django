"""
mentorship/forms.py
"""
from datetime import date, timedelta
from django import forms
from apps.mentorship.models import MentorshipSession, SessionType, SessionStatus
from apps.youth.models import YouthProfile, YouthStatus


class MentorshipSessionForm(forms.ModelForm):
    class Meta:
        model = MentorshipSession
        fields = ["youth", "session_date", "session_type", "notes", "recommendations"]
        widgets = {
            "session_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "session_type": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "recommendations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "youth": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, mentor_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if mentor_user:
            # Only show youth assigned to this mentor
            self.fields["youth"].queryset = YouthProfile.objects.filter(
                assigned_mentor=mentor_user
            ).select_related("user")
            self.fields["youth"].label_from_instance = (
                lambda obj: obj.user.get_full_name() or obj.user.username
            )

    def clean_session_date(self):
        d = self.cleaned_data.get("session_date")
        if d:
            max_future = date.today() + timedelta(days=30)
            if d > max_future:
                raise forms.ValidationError(
                    "La date ne peut pas être à plus de 30 jours dans le futur."
                )
        return d

    def clean(self):
        cleaned = super().clean()
        youth = cleaned.get("youth")
        if youth and youth.status == YouthStatus.INACTIVE:
            raise forms.ValidationError(
                "Impossible de créer une séance pour un jeune avec le statut INACTIF."
            )
        return cleaned


class SessionStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = MentorshipSession
        fields = ["status", "notes", "recommendations"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "recommendations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
