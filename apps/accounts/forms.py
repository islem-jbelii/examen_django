"""
accounts/forms.py — Authentication forms
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d'utilisateur ou email",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Votre identifiant",
            "autofocus": True,
        }),
    )
    password = forms.PasswordInput(
        attrs={"class": "form-control", "placeholder": "Mot de passe"}
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Mot de passe",
        }),
    )
