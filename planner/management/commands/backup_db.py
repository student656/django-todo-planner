import sqlite3
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Делает резервную копию базы SQLite в data/backups/ и хранит последние N копий."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=30, help="Сколько копий хранить (по умолчанию 30)")

    def handle(self, *args, **opts):
        src_path = settings.DATABASES["default"]["NAME"]
        backups = settings.DATA_DIR / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        dst_path = backups / f"db-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"

        src = sqlite3.connect(src_path)
        dst = sqlite3.connect(dst_path)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        old = sorted(backups.glob("db-*.sqlite3"))[: -opts["keep"]]
        for f in old:
            f.unlink()
        self.stdout.write(self.style.SUCCESS(f"Резервная копия: {dst_path}"))
