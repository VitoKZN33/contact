"""Управление сценариями из терминала VPS.

docker compose run --rm backend python -m app.cli validate
docker compose run --rm backend python -m app.cli seed
docker compose run --rm backend python -m app.cli list
docker compose run --rm backend python -m app.cli disable coffee-queue
docker compose run --rm backend python -m app.cli enable coffee-queue

Доступ к командам есть только у того, кто имеет SSH-доступ к серверу.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db.session import dispose_engine, get_sessionmaker
from app.models import Scenario
from app.scenarios.loader import ScenarioFileError, load_dir, seed, set_active


def cmd_validate() -> int:
    try:
        scenarios = load_dir()
    except ScenarioFileError as exc:
        print(f"VALIDATION_FAILED\n{exc}")
        return 1
    print(f"VALIDATION_OK: {len(scenarios)} сценариев")
    return 0


async def cmd_seed() -> int:
    try:
        scenarios = load_dir()
    except ScenarioFileError as exc:
        print(f"VALIDATION_FAILED\n{exc}")
        return 1
    async with get_sessionmaker()() as db:
        try:
            report = await seed(db, scenarios)
        except ScenarioFileError as exc:
            await db.rollback()
            print(f"SEED_FAILED: {exc}")
            return 1
    print(
        f"SEED_OK: новых {len(report.created)}, обновлено {len(report.updated)}, "
        f"без изменений {len(report.unchanged)}, вкл/выкл {len(report.toggled)}"
    )
    for title, items in (("новые", report.created), ("обновлены", report.updated), ("вкл/выкл", report.toggled)):
        if items:
            print(f"  {title}: {', '.join(items)}")
    return 0


async def cmd_list() -> int:
    async with get_sessionmaker()() as db:
        rows = (
            await db.execute(select(Scenario).order_by(Scenario.sort_order, Scenario.slug, Scenario.version))
        ).scalars()
        for sc in rows:
            mark = "ON " if sc.is_active else "off"
            print(f"{mark}  v{sc.version:<3} {sc.slug:<32} {sc.title}")
    return 0


async def cmd_toggle(slug: str, active: bool) -> int:
    async with get_sessionmaker()() as db:
        found = await set_active(db, slug, active)
    if not found:
        print(f"NOT_FOUND: {slug}")
        return 1
    print(f"{'ENABLED' if active else 'DISABLED'}: {slug}")
    return 0


async def _run_async(coro) -> int:
    try:
        return await coro
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Сценарии «Контакта»")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="проверить YAML-файлы без записи в БД")
    sub.add_parser("seed", help="загрузить или обновить сценарии из YAML")
    sub.add_parser("list", help="показать сценарии в БД")
    for name in ("enable", "disable"):
        p = sub.add_parser(name, help=f"{'включить' if name == 'enable' else 'отключить'} сценарий")
        p.add_argument("slug")
    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate()
    if args.command == "seed":
        return asyncio.run(_run_async(cmd_seed()))
    if args.command == "list":
        return asyncio.run(_run_async(cmd_list()))
    return asyncio.run(_run_async(cmd_toggle(args.slug, args.command == "enable")))


if __name__ == "__main__":
    sys.exit(main())
