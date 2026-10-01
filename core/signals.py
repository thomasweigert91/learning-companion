from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Legt zu jedem neuen User genau ein Profil an.

    get_or_create statt create: so loesen Fixtures oder ein mehrfaches
    Speichern desselben Users keine IntegrityError aus.
    """
    if created:
        Profile.objects.get_or_create(user=instance)
