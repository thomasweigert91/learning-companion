from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Tag(models.Model):
    """Eine Focus Area, z. B. "Python" oder "Machine Learning".

    Bewusst als eigenes Modell statt als ArrayField: ArrayField gibt es nur
    unter PostgreSQL, die Entwicklung laeuft aber gegen SQLite.
    """

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Profile(models.Model):
    """Profil eines Nutzers; wird beim Anlegen des Users automatisch erzeugt."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    name = models.CharField(max_length=150, blank=True)
    cohort = models.CharField(max_length=100, blank=True)
    focus_areas = models.ManyToManyField(Tag, blank=True, related_name="profiles")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return self.name or self.user.get_username()

    def get_absolute_url(self):
        return reverse("core:profile_detail")
