# Ежедневник (Django)

Ваш TODO.html, превращённый в полноценное приложение: календарь с дневными списками, задачи, покупки и «Ожидание».
Данные хранятся в базе SQLite (`data/db.sqlite3`), а не в браузере, поэтому не пропадают при очистке кэша,
смене браузера или телефона.

## Запуск (Windows / macOS / Linux)

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# macOS/Linux:  source venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Откройте http://127.0.0.1:8000/ , нажмите «Регистрация» и создайте свой аккаунт. Готово.

Если раньше вы вводили данные в TODO.html, откройте новый сайт **в том же браузере**: данные из старой версии
(localStorage) один раз автоматически перенесутся в базу.

## Правила, как в оригинале

* Дни в календаре: редактировать можно только сегодняшний, прошлые закрыты для изменений (только просмотр),
  будущие недоступны. Правило проверяется и на сервере.
* Квадрат дня заполняется по доле выполненных пунктов.
* Задачи (Крупные / Проекты / На неделю / Дом), Покупки (Крупные / Мелкие), Ожидание (4 статуса).
* У каждого пользователя свои данные.

## Сохранность данных

* Вся база — один файл `data/db.sqlite3`. Копируйте папку `data/`, и это уже резервная копия.
* Кнопка **«⬇ Резервная копия»** вверху страницы скачивает все ваши данные в JSON.
* Команда `python manage.py backup_db` делает консистентную копию базы в `data/backups/`
  (хранятся последние 30). Её удобно поставить на ежедневный запуск:
  * Linux/macOS (cron): `0 3 * * * cd /путь/к/проекту && venv/bin/python manage.py backup_db`
  * Windows: «Планировщик заданий» → запуск `venv\Scripts\python.exe manage.py backup_db`.
* Админка Django: `python manage.py createsuperuser`, затем http://127.0.0.1:8000/admin/ .

## Выкладка на сервер (кратко)

```bash
export DJANGO_DEBUG=0
export DJANGO_SECRET_KEY='длинная-случайная-строка'
export DJANGO_ALLOWED_HOSTS='example.com'
export DJANGO_CSRF_TRUSTED_ORIGINS='https://example.com'
# export DJANGO_ALLOW_SIGNUP=0     # закрыть регистрацию после создания своего аккаунта
# export DJANGO_HTTPS=0            # только если сайт по обычному http
# export DATA_DIR=/var/lib/ezhednevnik   # где лежит база (по умолчанию ./data)

python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi --bind 0.0.0.0:8000
```

Статика отдаётся через WhiteNoise, отдельный nginx для неё не нужен. Для HTTPS поставьте перед gunicorn
nginx или Caddy. Можно также разместить на PythonAnywhere и подобных хостингах.

Переменные окружения: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
`DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_ALLOW_SIGNUP`, `DJANGO_HTTPS`, `DJANGO_TIME_ZONE`
(по умолчанию `Asia/Bishkek`), `DATA_DIR`.

## Структура

```
manage.py
config/            настройки, urls, wsgi
planner/
  models.py        DayItem, Task, ShopItem, WaitItem
  views.py         страницы + JSON API (/api/...)
  tests.py         автотесты: python manage.py test
  static/planner/  app.css, app.js (интерфейс из TODO.html)
  templates/       index.html, вход, регистрация
  management/commands/backup_db.py
```
