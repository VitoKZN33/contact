"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Screen } from "@/components/ui/Screen";
import { useUser } from "@/features/auth/AuthProvider";
import { useActiveTraining } from "@/features/queries";
import { errorText } from "@/lib/api";

export default function HomePage() {
  const user = useUser();
  const router = useRouter();
  const active = useActiveTraining();
  const training = active.data?.training ?? null;
  const firstName = user.display_name?.split(" ")[0];

  return (
    <Screen
      footer={
        <Button onClick={() => router.push("/scenarios/")}>{training ? "Новая тренировка" : "Начать тренировку"}</Button>
      }
    >
      <div className="pt-[12vh]">
        <p className="text-small text-muted">{firstName ? `Привет, ${firstName}` : "Привет"}</p>
        <h1 className="mt-3 text-[2.375rem] font-semibold leading-[1.08] tracking-[-0.03em] text-balance">
          Отрепетируйте разговор до того, как он случится
        </h1>
        <p className="mt-4 max-w-sm text-body text-muted text-pretty">
          Собеседник с характером, живой диалог и разбор после — что сработало и как сказать иначе.
        </p>
      </div>

      {training ? (
        <Link
          href={`/chat/?id=${training.id}`}
          className="mt-10 block rounded-[var(--radius-card)] bg-card p-4 ring-1 ring-inset ring-accent/50 active:bg-surface"
        >
          <span className="flex items-center gap-2 text-caption text-accent">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            Незавершённая тренировка
          </span>
          <span className="mt-2 block text-body font-semibold">{training.scenario.title}</span>
          <span className="mt-0.5 block text-small text-muted">
            {training.persona.name}, {training.persona.type_title.toLowerCase()} · реплик: {training.user_turns}
          </span>
          <span className="mt-3 inline-flex h-10 items-center rounded-[12px] bg-accent px-4 text-small font-semibold text-accent-ink">
            Продолжить
          </span>
        </Link>
      ) : null}

      {active.isError ? <p className="mt-6 text-caption text-muted">{errorText(active.error)}</p> : null}

      <nav className="mt-10 grid grid-cols-2 gap-2" aria-label="Разделы">
        <Link href="/profile/" className="rounded-[var(--radius-card)] bg-card p-4 active:bg-surface">
          <span className="block text-small font-semibold">Профиль</span>
          <span className="mt-1 block text-caption text-muted">История и данные</span>
        </Link>
        <Link href="/help/" className="rounded-[var(--radius-card)] bg-card p-4 active:bg-surface">
          <span className="block text-small font-semibold">Как пользоваться</span>
          <span className="mt-1 block text-caption text-muted">Три шага и советы</span>
        </Link>
      </nav>
    </Screen>
  );
}
