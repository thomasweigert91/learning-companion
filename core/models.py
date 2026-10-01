from django.conf import settings
from django.core.validators import MinValueValidator
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


class Goal(models.Model):
    """Ein Lernziel. Gehoert genau einem Nutzer."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Geplant"
        IN_PROGRESS = "in-progress", "In Arbeit"
        DONE = "done", "Erledigt"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="goals",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:goal_detail", args=[self.pk])


class LearningSession(models.Model):
    """Eine einzelne Lernsitzung zu genau einem Goal.

    Der Besitzer wird bewusst nicht redundant gespeichert, sondern immer ueber
    goal__user aufgeloest -- so koennen Goal und Session nicht auseinanderlaufen.
    """

    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField()
    duration = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Dauer in Minuten",
    )
    notes = models.TextField(blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="sessions")

    class Meta:
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.goal.title} am {self.date:%d.%m.%Y}"

    def get_absolute_url(self):
        return reverse("core:session_detail", args=[self.pk])
