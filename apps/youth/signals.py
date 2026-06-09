"""
youth/signals.py — Post-save signal to recompute readiness score.

We import the model class directly inside the functions to avoid circular
imports at module load time.
"""
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver


def _update_score(youth):
    """Recompute and persist the readiness score without triggering recursion."""
    from apps.youth.services import compute_readiness_score
    from apps.youth.models import YouthProfile
    score, _ = compute_readiness_score(youth)
    # Use queryset update to avoid re-triggering post_save
    YouthProfile.objects.filter(pk=youth.pk).update(readiness_score=score)


def connect_signals():
    """
    Connect all youth signals. Called from YouthConfig.ready() after all
    models are fully loaded, so we can safely reference model classes.
    """
    from apps.youth.models import YouthProfile

    @receiver(post_save, sender=YouthProfile)
    def recompute_score_on_save(sender, instance, **kwargs):
        """Recompute readiness score whenever a YouthProfile is saved."""
        _update_score(instance)

    @receiver(m2m_changed, sender=YouthProfile.interests.through)
    def recompute_score_on_interests_change(sender, instance, **kwargs):
        """Recompute readiness score when interest sectors change."""
        if kwargs.get("action") in ("post_add", "post_remove", "post_clear"):
            _update_score(instance)
