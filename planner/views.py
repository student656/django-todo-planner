import json
from datetime import date

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from .models import DayItem, ShopItem, Task, WaitItem

TASK_CATS = [c for c, _ in Task.CATEGORIES]
SHOP_CATS = [c for c, _ in ShopItem.CATEGORIES]
STATUSES = [s for s, _ in WaitItem.STATUSES]


# ---------- сериализация ----------

def ser_simple(o):
    return {"id": o.id, "text": o.text, "done": o.done}


def ser_wait(o):
    return {
        "id": o.id,
        "title": o.title,
        "date": o.date.isoformat() if o.date else "",
        "status": o.status,
        "notes": o.notes,
    }


def build_state(user):
    calendar = {}
    for it in DayItem.objects.filter(user=user):
        calendar.setdefault(it.date.isoformat(), {"items": []})["items"].append(ser_simple(it))

    tasks = {c: [] for c in TASK_CATS}
    for it in Task.objects.filter(user=user):
        tasks.setdefault(it.category, []).append(ser_simple(it))

    shopping = {c: [] for c in SHOP_CATS}
    for it in ShopItem.objects.filter(user=user):
        shopping.setdefault(it.category, []).append(ser_simple(it))

    waiting = [ser_wait(it) for it in WaitItem.objects.filter(user=user)]

    return {
        "today": timezone.localdate().isoformat(),
        "calendar": calendar,
        "tasks": tasks,
        "shopping": shopping,
        "waiting": waiting,
    }


# ---------- валидация полей ----------

class BadValue(Exception):
    pass


def clean_text(v, limit=500, required=True):
    if not isinstance(v, str):
        raise BadValue("text")
    v = v.strip()[:limit]
    if required and not v:
        raise BadValue("text")
    return v


def clean_bool(v):
    if not isinstance(v, bool):
        raise BadValue("done")
    return v


def clean_date(v, required=False):
    if v in (None, ""):
        if required:
            raise BadValue("date")
        return None
    try:
        return date.fromisoformat(v)
    except (TypeError, ValueError):
        raise BadValue("date")


def clean_choice(choices):
    def fn(v):
        if v not in choices:
            raise BadValue("choice")
        return v
    return fn


# kind -> (модель, сериализатор, поля для создания, поля для изменения)
KINDS = {
    "day": {
        "model": DayItem,
        "ser": ser_simple,
        "create": {"date": lambda v: clean_date(v, True), "text": clean_text},
        "update": {"text": clean_text, "done": clean_bool},
    },
    "task": {
        "model": Task,
        "ser": ser_simple,
        "create": {"category": clean_choice(TASK_CATS), "text": clean_text},
        "update": {"text": clean_text, "done": clean_bool},
    },
    "shop": {
        "model": ShopItem,
        "ser": ser_simple,
        "create": {"category": clean_choice(SHOP_CATS), "text": clean_text},
        "update": {"text": clean_text, "done": clean_bool},
    },
    "wait": {
        "model": WaitItem,
        "ser": ser_wait,
        "defaults": {"date": None, "status": WaitItem.WAITING, "notes": ""},
        "create": {
            "title": lambda v: clean_text(v, 300),
            "date": clean_date,
            "status": clean_choice(STATUSES),
            "notes": lambda v: clean_text(v, 500, required=False),
        },
        "update": {
            "title": lambda v: clean_text(v, 300),
            "date": clean_date,
            "status": clean_choice(STATUSES),
            "notes": lambda v: clean_text(v, 500, required=False),
        },
    },
}


def get_kind(kind):
    cfg = KINDS.get(kind)
    if not cfg:
        raise Http404
    return cfg


def read_json(request):
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def bad(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


# ---------- страницы ----------

@login_required
@ensure_csrf_cookie
def index(request):
    return render(request, "planner/index.html")


def signup(request):
    if not settings.ALLOW_SIGNUP:
        raise Http404
    if request.user.is_authenticated:
        return redirect("index")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("index")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def export(request):
    """Скачать все данные пользователя одним JSON-файлом (резервная копия)."""
    payload = json.dumps(build_state(request.user), ensure_ascii=False, indent=2)
    resp = HttpResponse(payload, content_type="application/json; charset=utf-8")
    stamp = timezone.localdate().isoformat()
    resp["Content-Disposition"] = f'attachment; filename="ezhednevnik-{stamp}.json"'
    return resp


# ---------- API ----------

@login_required
@require_http_methods(["GET"])
def api_state(request):
    return JsonResponse(build_state(request.user))


@login_required
@require_POST
def api_create(request, kind):
    cfg = get_kind(kind)
    data = read_json(request)
    if data is None:
        return bad("bad json")
    values = dict(cfg.get("defaults", {}))
    try:
        for field, cleaner in cfg["create"].items():
            if field in data:
                values[field] = cleaner(data[field])
            elif field not in values:
                raise BadValue(field)
    except BadValue as e:
        return bad(f"invalid {e}")

    if kind == "day" and values["date"] != timezone.localdate():
        return bad("Можно добавлять задачи только в сегодняшний день", 403)

    obj = cfg["model"].objects.create(user=request.user, **values)
    return JsonResponse(cfg["ser"](obj), status=201)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def api_item(request, kind, pk):
    cfg = get_kind(kind)
    try:
        obj = cfg["model"].objects.get(pk=pk, user=request.user)
    except cfg["model"].DoesNotExist:
        raise Http404

    if kind == "day" and obj.date != timezone.localdate():
        return bad("Прошлые дни закрыты — только просмотр", 403)

    if request.method == "DELETE":
        obj.delete()
        return HttpResponse(status=204)

    data = read_json(request)
    if data is None:
        return bad("bad json")
    changed = []
    try:
        for field, cleaner in cfg["update"].items():
            if field in data:
                setattr(obj, field, cleaner(data[field]))
                changed.append(field)
    except BadValue as e:
        return bad(f"invalid {e}")
    if changed:
        obj.save(update_fields=changed)
    return JsonResponse(cfg["ser"](obj))


@login_required
@require_POST
def api_import(request):
    """Разовый перенос данных из localStorage старой версии (TODO.html) в базу."""
    data = read_json(request)
    if data is None:
        return bad("bad json")

    user = request.user
    if any(m.objects.filter(user=user).exists() for m in (DayItem, Task, ShopItem, WaitItem)):
        return JsonResponse({"imported": False, "reason": "not empty"})

    def text_of(item, *keys):
        for k in keys:
            if isinstance(item, dict) and isinstance(item.get(k), str) and item[k].strip():
                return item[k].strip()[:500]
        return None

    day_objs, task_objs, shop_objs, wait_objs = [], [], [], []

    cal = data.get("calendar") or {}
    if isinstance(cal, dict):
        for key, entry in cal.items():
            try:
                d = date.fromisoformat(key)
            except (TypeError, ValueError):
                continue
            for it in (entry or {}).get("items", []) if isinstance(entry, dict) else []:
                t = text_of(it, "text", "name")
                if t:
                    day_objs.append(DayItem(user=user, date=d, text=t, done=bool(it.get("done"))))

    for store, cats, out, model in (
        (data.get("tasks"), TASK_CATS, task_objs, Task),
        (data.get("shopping"), SHOP_CATS, shop_objs, ShopItem),
    ):
        if not isinstance(store, dict):
            continue
        for cat in cats:
            for it in store.get(cat) or []:
                t = text_of(it, "text", "name")
                if t:
                    out.append(model(user=user, category=cat, text=t, done=bool(it.get("done"))))

    for it in data.get("waiting") or []:
        title = text_of(it, "title")
        if not title:
            continue
        try:
            d = clean_date(it.get("date"))
        except BadValue:
            d = None
        status = it.get("status") if it.get("status") in STATUSES else WaitItem.WAITING
        notes = it.get("notes") if isinstance(it.get("notes"), str) else ""
        wait_objs.append(WaitItem(user=user, title=title[:300], date=d, status=status, notes=notes[:500]))

    with transaction.atomic():
        DayItem.objects.bulk_create(day_objs)
        Task.objects.bulk_create(task_objs)
        ShopItem.objects.bulk_create(shop_objs)
        WaitItem.objects.bulk_create(wait_objs)

    total = len(day_objs) + len(task_objs) + len(shop_objs) + len(wait_objs)
    return JsonResponse({"imported": True, "count": total})
