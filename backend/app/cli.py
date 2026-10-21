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


async def cmd_eval(case_name: str | None) -> int:
    from app.ai.eval_suite import CASES, MANUAL_CHECKLIST, run_case
    from app.ai.factory import get_llm_provider
    from app.core.config import get_settings

    settings = get_settings()
    cases = [c for c in CASES if case_name in (None, c.name)]
    if not cases:
        print(f"NOT_FOUND: {case_name}. Доступны: {', '.join(c.name for c in CASES)}")
        return 1
    provider = get_llm_provider()
    print(f"Модель диалога: {settings.deepseek_model_dialog}, разбора: {settings.deepseek_model_analysis}\n")
    total_cost, failed = 0, 0
    for case in cases:
        report = await run_case(case, provider, settings)
        total_cost += report.cost
        status = "FAIL" if report.problems else "OK"
        failed += bool(report.problems)
        print(f"===== {case.name} [{status}] — {case.persona}/{case.difficulty} · {case.focus}")
        for role, content in report.transcript:
            print(f"  {'ВЫ' if role == 'user' else 'ПЕРСОНАЖ'}: {content}")
        if report.analysis_summary:
            print(f"  РАЗБОР: {report.analysis_summary}")
        for p in report.problems:
            print(f"  ✗ {p}")
        for w in report.warnings:
            print(f"  ! {w}")
        print(f"  токены: {report.tokens}, стоимость: ${report.cost}\n")
    print(MANUAL_CHECKLIST)
    print(f"\nEVAL_DONE: {len(cases) - failed}/{len(cases)} без автоматических проблем, стоимость прогона ${total_cost}")
    return 0 if failed == 0 else 2


async def cmd_usage(days: int) -> int:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import case, func

    from app.models import AIUsage, TrainingSession

    since = datetime.now(UTC) - timedelta(days=days)
    day = func.date_trunc("day", AIUsage.created_at).label("day")
    async with get_sessionmaker()() as db:
        rows = (
            await db.execute(
                select(
                    day,
                    func.count(),
                    func.sum(AIUsage.cost_usd),
                    func.count(func.distinct(AIUsage.session_id)),
                    func.count(func.distinct(AIUsage.user_id)),
                    func.sum(case((AIUsage.success.is_(False), 1), else_=0)),
                )
                .where(AIUsage.created_at >= since)
                .group_by(day)
                .order_by(day)
            )
        ).all()
        print(f"{'день':<12}{'вызовов':>9}{'ошибок':>8}{'тренировок':>12}{'польз.':>8}{'$':>12}")
        for day, calls, cost, sessions, users, errors in rows:
            print(f"{day:%Y-%m-%d}  {calls:>9}{errors or 0:>8}{sessions:>12}{users:>8}{(cost or 0):>12.4f}")

        per_training_sq = (
            select(func.sum(AIUsage.cost_usd).label("cost"))
            .join(TrainingSession, TrainingSession.id == AIUsage.session_id)
            .where(TrainingSession.status == "completed", TrainingSession.completed_at >= since)
            .group_by(AIUsage.session_id)
            .subquery()
        )
        per_training = (await db.execute(select(func.avg(per_training_sq.c.cost)))).scalar_one_or_none()
        per_user_sq = (
            select(func.sum(AIUsage.cost_usd).label("cost"))
            .where(AIUsage.user_id.is_not(None), AIUsage.created_at >= since)
            .group_by(AIUsage.user_id)
            .subquery()
        )
        per_user = (await db.execute(select(func.avg(per_user_sq.c.cost)))).scalar_one_or_none()
    print(f"\nСредняя себестоимость завершённой тренировки: ${(per_training or 0):.4f}")
    print(f"Средние расходы на пользователя за {days} дн.: ${(per_user or 0):.4f}")
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
    p_eval = sub.add_parser("eval", help="проверка качества персонажей на реальной модели (тратит токены)")
    p_eval.add_argument("--case", default=None, help="запустить один кейс по имени")
    p_usage = sub.add_parser("usage", help="расходы на AI по дням и себестоимость")
    p_usage.add_argument("--days", type=int, default=14)
    args = parser.parse_args(argv)

    if args.command == "eval":
        return asyncio.run(_run_async(cmd_eval(args.case)))
    if args.command == "usage":
        return asyncio.run(_run_async(cmd_usage(args.days)))

    if args.command == "validate":
        return cmd_validate()
    if args.command == "seed":
        return asyncio.run(_run_async(cmd_seed()))
    if args.command == "list":
        return asyncio.run(_run_async(cmd_list()))
    return asyncio.run(_run_async(cmd_toggle(args.slug, args.command == "enable")))


if __name__ == "__main__":
    sys.exit(main())
