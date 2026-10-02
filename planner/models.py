from django.conf import settings
from django.db import models


class Owned(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["id"]


class DayItem(Owned):
    """Пункт дневного списка в календаре."""

    date = models.DateField(db_index=True)
    text = models.CharField(max_length=500)
    done = models.BooleanField(default=False)

    class Meta(Owned.Meta):
        verbose_name = "пункт дня"
        verbose_name_plural = "пункты дня"
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.date}: {self.text}"


class Task(Owned):
    MAJOR, PROJECTS, SHORT, CHORES = "major", "projects", "short", "chores"
    CATEGORIES = [
        (MAJOR, "Крупные"),
        (PROJECTS, "Проекты"),
        (SHORT, "На неделю"),
        (CHORES, "Дом"),
    ]

    category = models.CharField(max_length=10, choices=CATEGORIES)
    text = models.CharField(max_length=500)
    done = models.BooleanField(default=False)

    class Meta(Owned.Meta):
        verbose_name = "задача"
        verbose_name_plural = "задачи"

    def __str__(self):
        return self.text


class ShopItem(Owned):
    BIG, SMALL = "big", "small"
    CATEGORIES = [(BIG, "Крупные"), (SMALL, "Мелкие")]

    category = models.CharField(max_length=10, choices=CATEGORIES)
    text = models.CharField(max_length=500)
    done = models.BooleanField(default=False)

    class Meta(Owned.Meta):
        verbose_name = "покупка"
        verbose_name_plural = "покупки"

    def __str__(self):
        return self.text


class WaitItem(Owned):
    WAITING, RECEIVED, ACCEPTED, REJECTED = "waiting", "received", "accepted", "rejected"
    STATUSES = [
        (WAITING, "Ожидание"),
        (RECEIVED, "Ответ"),
        (ACCEPTED, "Принято"),
        (REJECTED, "Отклонено"),
    ]

    title = models.CharField(max_length=300)
    date = models.DateField(null=True, blank=True, help_text="Дата подачи")
    status = models.CharField(max_length=10, choices=STATUSES, default=WAITING)
    notes = models.CharField(max_length=500, blank=True)

    class Meta(Owned.Meta):
        verbose_name = "заявка"
        verbose_name_plural = "ожидание"

    def __str__(self):
        return self.title
