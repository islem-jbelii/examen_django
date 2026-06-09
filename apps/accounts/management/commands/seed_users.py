"""
Management command: seed_users
Creates the sample user accounts with properly hashed passwords.
Run: python manage.py seed_users
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

USERS = [
    {
        "username": "admin",
        "email": "admin@careerpathtn.tn",
        "password": "admin123",
        "first_name": "Admin",
        "last_name": "CareerPathTN",
        "role": "ADMIN",
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "counselor",
        "email": "counselor@careerpathtn.tn",
        "password": "counsel123",
        "first_name": "Sonia",
        "last_name": "Ben Ali",
        "role": "COUNSELOR",
    },
    {
        "username": "mentor1",
        "email": "mentor1@careerpathtn.tn",
        "password": "mentor123",
        "first_name": "Karim",
        "last_name": "Trabelsi",
        "role": "MENTOR",
    },
    {
        "username": "mentor2",
        "email": "mentor2@careerpathtn.tn",
        "password": "mentor234",
        "first_name": "Fatma",
        "last_name": "Chaabane",
        "role": "MENTOR",
    },
    {
        "username": "youth1",
        "email": "youth1@careerpathtn.tn",
        "password": "youth123",
        "first_name": "Ahmed",
        "last_name": "Mansouri",
        "role": "YOUTH",
    },
    {
        "username": "youth2",
        "email": "youth2@careerpathtn.tn",
        "password": "youth234",
        "first_name": "Mariem",
        "last_name": "Khelifi",
        "role": "YOUTH",
    },
]


class Command(BaseCommand):
    help = "Seed sample user accounts for CareerPathTN"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for data in USERS:
            password = data.pop("password")
            user, is_new = User.objects.update_or_create(
                username=data["username"],
                defaults=data,
            )
            user.set_password(password)
            user.save()
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {user.username} ({user.role})"))
            else:
                updated += 1
                self.stdout.write(f"  Updated: {user.username} ({user.role})")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created} created, {updated} updated."
        ))
