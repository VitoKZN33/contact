"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmSheet } from "@/components/ui/ConfirmSheet";
import { Card, Screen, Section } from "@/components/ui/Screen";
import { EmptyState, ErrorState, SkeletonLines } from "@/components/ui/States";
import { useAuth, useUser } from "@/features/auth/AuthProvider";
import {
  useDeleteAllData,
  useDeleteHistory,
  useHistory,
  useProfile,
  useUpdateNotifications,
  useUsage,
} from "@/features/queries";
import { errorText } from "@/lib/api";
import { getWebApp } from "@/lib/telegram";

const ANALYSIS_LABEL: Record<string, string> = {
  done: "Разбор готов",
  pending: "Разбор готовится",
  failed: "Разбор не получился",
  none: "Без разбора",
};

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export default function ProfilePage() {
  const user = useUser();
  const { signOutLocal } = useAuth();
  const profile = useProfile();
  const usage = useUsage();
  const history = useHistory();
  const notifications = useUpdateNotifications();
  const deleteHistory = useDeleteHistory();
  const deleteAll = useDeleteAllData();
  const [confirm, setConfirm] = useState<"history" | "all" | null>(null);

  const items = history.data?.pages.flatMap((p) => p.items) ?? [];
  const notificationsOn = profile.data?.user.notifications_enabled ?? user.notifications_enabled;

  return (
    <Screen back="/" title={user.display_name ?? "Профиль"} subtitle={user.username ? `@${user.username} в Telegram` : undefined}>
      {usage.data ? (
        <Card className="flex justify-between gap-4">
          <div>
            <p className="text-caption text-muted">Тренировок сегодня</p>
            <p className="mt-0.5 text-title font-semibold tabular-nums">
              {usage.data.trainings_today}
              <span className="text-small font-normal text-muted"> из {usage.data.limits.trainings_per_day}</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-caption text-muted">Тариф</p>
            <p className="mt-0.5 text-title font-semibold">Бесплатный</p>
          </div>
        </Card>
      ) : null}

      <Section title="История">
        {history.isPending ? <SkeletonLines rows={3} /> : null}
        {history.isError ? <ErrorState message={errorText(history.error)} onRetry={() => history.refetch()} /> : null}
        {history.data && items.length === 0 ? (
          <EmptyState
            title="Пока пусто"
            message="Завершённые тренировки и разборы появятся здесь."
            action={
              <Link href="/scenarios/" className="text-small font-semibold text-accent">
                Выбрать ситуацию
              </Link>
            }
          />
        ) : null}
        <ul className="space-y-2">
          {items.map((t) => (
            <li key={t.id}>
              <Link href={`/result/?id=${t.id}`} className="block rounded-[var(--radius-card)] bg-card p-4 active:bg-surface">
                <span className="flex justify-between gap-3 text-caption text-muted">
                  <span>{formatDate(t.completed_at)}</span>
                  <span className={t.analysis_status === "failed" ? "text-danger" : ""}>
                    {ANALYSIS_LABEL[t.analysis_status] ?? t.analysis_status}
                  </span>
                </span>
                <span className="mt-1 block text-body font-semibold">{t.scenario_title}</span>
                <span className="mt-0.5 block text-caption text-muted">
                  {t.persona_name}, {t.persona_type_title.toLowerCase()} · {t.difficulty_title.toLowerCase()} · текст
                </span>
                {t.summary ? <span className="mt-2 block text-small text-muted text-pretty">{t.summary}</span> : null}
              </Link>
            </li>
          ))}
        </ul>
        {history.hasNextPage ? (
          <div className="mt-3">
            <Button variant="secondary" loading={history.isFetchingNextPage} onClick={() => history.fetchNextPage()}>
              Показать ещё
            </Button>
          </div>
        ) : null}
      </Section>

      <Section title="Настройки">
        <Card className="flex items-center justify-between gap-4">
          <div>
            <p className="text-small font-semibold">Уведомления в боте</p>
            <p className="mt-0.5 text-caption text-muted">Сообщим, когда разбор будет готов</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={notificationsOn}
            aria-label="Уведомления в боте"
            disabled={notifications.isPending}
            onClick={() => notifications.mutate(!notificationsOn)}
            className={`relative h-7 w-12 shrink-0 rounded-full transition-colors ${notificationsOn ? "bg-accent" : "bg-surface"}`}
          >
            <span
              className={`absolute top-1 h-5 w-5 rounded-full bg-text transition-[left] ${notificationsOn ? "left-6" : "left-1"}`}
            />
          </button>
        </Card>
        {notifications.isError ? <p className="mt-2 text-caption text-danger">{errorText(notifications.error)}</p> : null}
      </Section>

      <Section title="Данные">
        <div className="space-y-2">
          <Link href="/privacy/" className="block rounded-[var(--radius-card)] bg-card p-4 text-small font-semibold active:bg-surface">
            Что мы храним и зачем
          </Link>
          <Button variant="secondary" onClick={() => setConfirm("history")}>
            Очистить историю
          </Button>
          <Button variant="danger" onClick={() => setConfirm("all")}>
            Удалить все мои данные
          </Button>
        </div>
        {deleteHistory.isSuccess ? (
          <p className="mt-2 text-caption text-muted">Удалено тренировок: {deleteHistory.data.deleted_trainings}</p>
        ) : null}
      </Section>

      <ConfirmSheet
        open={confirm === "history"}
        title="Очистить историю?"
        message="Завершённые тренировки, реплики и разборы удалятся безвозвратно. Незавершённая тренировка останется."
        confirmLabel="Очистить"
        destructive
        loading={deleteHistory.isPending}
        onConfirm={() => deleteHistory.mutate(undefined, { onSettled: () => setConfirm(null) })}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmSheet
        open={confirm === "all"}
        title="Удалить все данные?"
        message={
          <>
            Удалятся профиль, все тренировки, реплики и разборы. Восстановить их будет нельзя.
            {deleteAll.isError ? <span className="mt-2 block text-danger">{errorText(deleteAll.error)}</span> : null}
          </>
        }
        confirmLabel="Удалить навсегда"
        destructive
        loading={deleteAll.isPending}
        onConfirm={() =>
          deleteAll.mutate(undefined, {
            onSuccess: () => {
              setConfirm(null);
              signOutLocal();
              setTimeout(() => getWebApp()?.close?.(), 1500);
            },
          })
        }
        onCancel={() => setConfirm(null)}
      />
    </Screen>
  );
}
