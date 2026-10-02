import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DayItem, Task, WaitItem

User = get_user_model()


class PlannerApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("anna", password="pass12345")
        self.client.login(username="anna", password="pass12345")
        self.today = timezone.localdate()

    def post(self, kind, data):
        return self.client.post(f"/api/{kind}/", json.dumps(data), content_type="application/json")

    def patch(self, kind, pk, data):
        return self.client.patch(f"/api/{kind}/{pk}/", json.dumps(data), content_type="application/json")

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertEqual(self.client.get("/api/state/").status_code, 302)

    def test_day_crud_today(self):
        r = self.post("day", {"date": self.today.isoformat(), "text": "  Купить хлеб "})
        self.assertEqual(r.status_code, 201)
        pk = r.json()["id"]
        self.assertEqual(r.json()["text"], "Купить хлеб")
        self.assertEqual(self.patch("day", pk, {"done": True}).json()["done"], True)
        state = self.client.get("/api/state/").json()
        self.assertEqual(state["calendar"][self.today.isoformat()]["items"][0]["done"], True)
        self.assertEqual(self.client.delete(f"/api/day/{pk}/").status_code, 204)
        self.assertEqual(DayItem.objects.count(), 0)

    def test_past_days_are_locked(self):
        past = self.today - timedelta(days=1)
        self.assertEqual(self.post("day", {"date": past.isoformat(), "text": "x"}).status_code, 403)
        old = DayItem.objects.create(user=self.user, date=past, text="old")
        self.assertEqual(self.patch("day", old.pk, {"done": True}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/day/{old.pk}/").status_code, 403)
        old.refresh_from_db()
        self.assertFalse(old.done)

    def test_tasks_shop_wait(self):
        t = self.post("task", {"category": "major", "text": "Диплом"})
        self.assertEqual(t.status_code, 201)
        self.assertEqual(self.post("task", {"category": "nope", "text": "x"}).status_code, 400)
        self.assertEqual(self.post("task", {"category": "major", "text": "   "}).status_code, 400)
        self.assertEqual(self.post("shop", {"category": "small", "text": "Молоко"}).status_code, 201)
        w = self.post("wait", {"title": "Türk Forum", "date": "2026-09-20", "status": "received", "notes": "ждём"})
        self.assertEqual(w.status_code, 201)
        self.assertEqual(w.json()["date"], "2026-09-20")
        w2 = self.post("wait", {"title": "Без даты"})
        self.assertEqual(w2.json()["status"], "waiting")
        self.assertEqual(w2.json()["date"], "")
        self.assertEqual(self.patch("wait", w.json()["id"], {"status": "accepted"}).json()["status"], "accepted")
        self.assertEqual(self.patch("wait", w.json()["id"], {"status": "bogus"}).status_code, 400)
        state = self.client.get("/api/state/").json()
        self.assertEqual(len(state["tasks"]["major"]), 1)
        self.assertEqual(len(state["shopping"]["small"]), 1)
        self.assertEqual(len(state["waiting"]), 2)

    def test_users_are_isolated(self):
        t = Task.objects.create(user=self.user, category="major", text="моё")
        other = User.objects.create_user("boris", password="pass12345")
        self.client.logout()
        self.client.login(username="boris", password="pass12345")
        self.assertEqual(self.client.get("/api/state/").json()["tasks"]["major"], [])
        self.assertEqual(self.patch("task", t.pk, {"done": True}).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/task/{t.pk}/").status_code, 404)
        self.assertEqual(WaitItem.objects.filter(user=other).count(), 0)

    def test_unknown_kind(self):
        self.assertEqual(self.post("hack", {}).status_code, 404)

    def test_import_legacy_localstorage(self):
        legacy = {
            "calendar": {"2026-09-10": {"items": [{"id": "a", "name": "Старое дело", "done": True}]}},
            "tasks": {"major": [{"id": "b", "text": "Цель", "done": False}], "chores": []},
            "shopping": {"big": [{"id": "c", "text": "Ноутбук", "done": False}], "small": []},
            "waiting": [{"id": "d", "title": "Заявка", "date": "2026-09-01", "status": "waiting", "notes": ""}],
        }
        r = self.post("import", legacy)
        self.assertEqual(r.json(), {"imported": True, "count": 4})
        # повторный импорт не дублирует данные
        self.assertEqual(self.post("import", legacy).json()["imported"], False)
        state = self.client.get("/api/state/").json()
        self.assertEqual(state["calendar"]["2026-09-10"]["items"][0]["text"], "Старое дело")
        self.assertTrue(state["calendar"]["2026-09-10"]["items"][0]["done"])

    def test_export(self):
        Task.objects.create(user=self.user, category="short", text="x")
        r = self.client.get(reverse("export"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertEqual(json.loads(r.content)["tasks"]["short"][0]["text"], "x")

    def test_pages_render(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "planner/app.js")
        self.client.logout()
        self.assertEqual(self.client.get("/login/").status_code, 200)
        self.assertEqual(self.client.get("/signup/").status_code, 200)

    def test_signup_creates_user_and_logs_in(self):
        self.client.logout()
        r = self.client.post("/signup/", {"username": "newuser", "password1": "Str0ngPass!77", "password2": "Str0ngPass!77"})
        self.assertRedirects(r, "/")
        self.assertEqual(self.client.get("/api/state/").status_code, 200)
