"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import { ConfirmSheet } from "@/components/ui/ConfirmSheet";
import { useTelegramBack } from "@/components/ui/Screen";
import { ErrorState, FullScreenLoader } from "@/components/ui/States";
import { keys, patchTraining, sendMessage, useFinishTraining, useTraining } from "@/features/queries";
import { errorCode, errorText, newId } from "@/lib/api";
import type { ChatMessage, Training } from "@/lib/schemas";
import { haptic, setClosingConfirmation } from "@/lib/telegram";

const MAX_CHARS = 1000;

type Pending = { cid: string; content: string; status: "sending" | "failed"; error?: string };

export default function ChatPage() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Chat />
    </Suspense>
  );
}

function Chat() {
  const id = useSearchParams().get("id");
  const training = useTraining(id);
  useTelegramBack("/");

  if (!id) return <Centered><ErrorState title="Тренировка не найдена" message="Вернитесь на главную." /></Centered>;
  if (training.isPending) return <FullScreenLoader label="Открываем разговор" />;
  if (training.isError) {
    return (
      <Centered>
        <ErrorState
          title={errorCode(training.error) === "not_found" ? "Тренировка не найдена" : "Не загрузилось"}
          message={errorText(training.error)}
          onRetry={errorCode(training.error) === "not_found" ? undefined : () => training.refetch()}
          action={<Link href="/" className="block py-2 text-center text-small text-muted">На главную</Link>}
        />
      </Centered>
    );
  }
  return <Conversation training={training.data} />;
}

function Conversation({ training }: { training: Training }) {
  const router = useRouter();
  const qc = useQueryClient();
  const finish = useFinishTraining();
  const [pending, setPending] = useState<Pending | null>(null);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const isActive = training.status === "active";
  const serverInFlight = training.messages.some((m) => m.role === "user" && m.status === "accepted");
  const sending = pending?.status === "sending" || serverInFlight;
  const lastServer = training.messages[training.messages.length - 1];
  const serverFailed = lastServer && lastServer.role === "user" && lastServer.status === "failed" ? lastServer : null;
  const turnLimitReached = training.user_turns >= training.max_user_turns;

  // Пока идёт активный разговор, Telegram спросит подтверждение перед закрытием
  useEffect(() => {
    setClosingConfirmation(isActive && training.messages.length > 0);
    return () => setClosingConfirmation(false);
  }, [isActive, training.messages.length]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [training.messages.length, pending?.status]);

  const deliver = async (content: string, cid: string) => {
    setNotice(null);
    setPending({ cid, content, status: "sending" });
    haptic("tap");
    try {
      const result = await sendMessage(training.id, content, cid);
      patchTraining(qc, training.id, (t) => ({
        ...t,
        user_turns: result.user_turns,
        messages: mergeMessages(t.messages, [result.user_message, result.reply]),
      }));
      setPending(null);
    } catch (error) {
      const code = errorCode(error);
      if (code === "training_not_active" || code === "turn_limit" || code === "message_in_progress") {
        setPending(null);
        setNotice(errorText(error));
        void qc.invalidateQueries({ queryKey: keys.training(training.id) });
        return;
      }
      haptic("error");
      setPending({ cid, content, status: "failed", error: errorText(error) });
      void qc.invalidateQueries({ queryKey: keys.training(training.id) });
    }
  };

  const onSend = () => {
    const content = draft.trim();
    if (!content || sending) return;
    setDraft("");
    void deliver(content, newId());
  };

  const onFinish = () => {
    finish.mutate(training.id, {
      onSuccess: (res) => {
        setClosingConfirmation(false);
        haptic("success");
        if (res.status === "abandoned") router.replace("/");
        else router.replace(`/result/?id=${training.id}`);
      },
      onError: () => setConfirmOpen(false),
    });
  };

  // Сообщение, отправленное, но ещё не подтверждённое сервером, показываем как своё
  const shown: ChatMessage[] = [...training.messages];
  const pendingVisible = pending && !training.messages.some((m) => m.client_message_id === pending.cid && m.status === "completed");
  const retryTarget = pending?.status === "failed" ? pending : serverFailed && !pending ? { cid: serverFailed.client_message_id ?? newId(), content: serverFailed.content } : null;

  return (
    <div className="mx-auto flex h-dvh w-full max-w-lg flex-col">
      <header className="flex items-center gap-3 border-b border-line/60 px-4 py-3">
        <button
          type="button"
          onClick={() => setBriefOpen((v) => !v)}
          aria-expanded={briefOpen}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <Avatar name={training.persona.name} active={sending} />
          <span className="min-w-0">
            <span className="block truncate text-body font-semibold leading-tight">{training.persona.name}</span>
            <span className="block truncate text-caption text-muted">
              {sending ? "печатает…" : `${training.persona.type_title} · ${training.difficulty_title.toLowerCase()}`}
            </span>
          </span>
        </button>
        {isActive ? (
          <button
            type="button"
            onClick={() => setConfirmOpen(true)}
            disabled={sending}
            className="h-9 shrink-0 rounded-full bg-surface px-3.5 text-caption font-semibold disabled:opacity-40"
          >
            Завершить
          </button>
        ) : null}
      </header>

      {briefOpen ? (
        <div className="border-b border-line/60 bg-card px-4 py-3 text-small">
          <p className="font-semibold">{training.scenario.title}</p>
          <p className="mt-1 text-muted text-pretty">{training.scenario.description}</p>
          <p className="mt-2 text-caption text-muted">Цель</p>
          <p className="text-pretty">{training.scenario.objective}</p>
          {training.custom_situation ? (
            <>
              <p className="mt-2 text-caption text-muted">Ваше описание</p>
              <p className="whitespace-pre-wrap text-pretty">{training.custom_situation}</p>
            </>
          ) : null}
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto px-4 py-4" aria-live="polite">
        {training.messages.length === 0 && !pending ? (
          <div className="mx-auto mt-[10vh] max-w-xs text-center">
            <p className="text-body font-semibold">Начните разговор</p>
            <p className="mt-1 text-small text-muted text-pretty">{training.scenario.description}</p>
          </div>
        ) : null}

        <ol className="space-y-2.5">
          {shown.map((m) =>
            m.role === "user" && m.status === "failed" && pending ? null : (
              <Bubble key={m.id} message={m} failed={m.status === "failed"} />
            ),
          )}
          {pendingVisible && pending ? (
            <li className="message-in flex justify-end">
              <div className="max-w-[82%]">
                <div
                  className={`whitespace-pre-wrap rounded-[18px] rounded-br-[6px] px-3.5 py-2.5 text-body ${
                    pending.status === "failed" ? "bg-surface text-muted" : "bg-surface text-text"
                  }`}
                >
                  {pending.content}
                </div>
              </div>
            </li>
          ) : null}
          {sending ? <TypingIndicator /> : null}
        </ol>

        {retryTarget ? (
          <div className="mt-3 flex items-center justify-end gap-3 text-caption" role="alert">
            <span className="text-danger">{pending?.error ?? "Не отправлено"}</span>
            <button
              type="button"
              onClick={() => void deliver(retryTarget.content, retryTarget.cid)}
              className="font-semibold text-accent"
            >
              Повторить
            </button>
          </div>
        ) : null}

        {notice ? <p className="mt-3 text-center text-caption text-muted">{notice}</p> : null}
        <div ref={bottomRef} />
      </div>

      {isActive ? (
        turnLimitReached ? (
          <Footer>
            <p className="mb-3 text-center text-small text-muted">Лимит реплик в этом разговоре исчерпан.</p>
            <Button onClick={() => setConfirmOpen(true)}>Завершить и получить разбор</Button>
          </Footer>
        ) : (
          <Composer
            value={draft}
            onChange={setDraft}
            onSend={onSend}
            disabled={sending}
            turnsLeft={training.max_user_turns - training.user_turns}
          />
        )
      ) : (
        <Footer>
          <p className="mb-3 text-center text-small text-muted">
            {training.status === "completed"
              ? "Тренировка завершена."
              : training.status === "expired"
                ? "Тренировка закрылась из-за долгой паузы."
                : "Тренировка закрыта без разбора."}
          </p>
          {training.status === "completed" ? (
            <Button onClick={() => router.push(`/result/?id=${training.id}`)}>К разбору</Button>
          ) : (
            <Button variant="secondary" onClick={() => router.push("/")}>
              На главную
            </Button>
          )}
        </Footer>
      )}

      <ConfirmSheet
        open={confirmOpen}
        title="Завершить тренировку?"
        message={
          training.user_turns > 0
            ? "Продолжить этот разговор будет нельзя. Сразу после завершения начнётся разбор."
            : "Вы ещё ничего не написали — тренировка закроется без разбора."
        }
        confirmLabel="Завершить"
        loading={finish.isPending}
        onConfirm={onFinish}
        onCancel={() => setConfirmOpen(false)}
      />
      {finish.isError ? <p className="px-4 pb-2 text-center text-caption text-danger">{errorText(finish.error)}</p> : null}
    </div>
  );
}

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  const bySeq = new Map(current.map((m) => [m.sequence_number, m]));
  for (const m of incoming) bySeq.set(m.sequence_number, m);
  return [...bySeq.values()].sort((a, b) => a.sequence_number - b.sequence_number);
}

function Avatar({ name, active }: { name: string; active: boolean }) {
  return (
    <span
      aria-hidden
      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent-soft text-small font-semibold text-accent ring-1 ring-inset transition-shadow ${
        active ? "ring-accent" : "ring-accent/30"
      }`}
    >
      {name.replace(/^(дядя|тётя)\s+/i, "").charAt(0).toUpperCase()}
    </span>
  );
}

function Bubble({ message, failed }: { message: ChatMessage; failed: boolean }) {
  const mine = message.role === "user";
  return (
    <li className={`message-in flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[82%] whitespace-pre-wrap px-3.5 py-2.5 text-body ${
          mine
            ? `rounded-[18px] rounded-br-[6px] bg-surface ${failed ? "text-muted" : "text-text"}`
            : "rounded-[18px] rounded-bl-[6px] bg-card text-text"
        }`}
      >
        {message.content}
      </div>
    </li>
  );
}

function TypingIndicator() {
  return (
    <li className="flex justify-start" aria-label="Собеседник печатает">
      <div className="flex gap-1.5 rounded-[18px] rounded-bl-[6px] bg-card px-4 py-3.5">
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-accent" />
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-accent" />
      </div>
    </li>
  );
}

function Composer({
  value,
  onChange,
  onSend,
  disabled,
  turnsLeft,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
  turnsLeft: number;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [value]);
  const canSend = value.trim().length > 0 && !disabled;
  return (
    <div className="border-t border-line/60 bg-bg px-3 pb-[max(10px,env(safe-area-inset-bottom))] pt-2.5">
      <div className="flex items-end gap-2">
        <label className="sr-only" htmlFor="composer">
          Ваша реплика
        </label>
        <textarea
          id="composer"
          ref={ref}
          rows={1}
          value={value}
          maxLength={MAX_CHARS}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            // На компьютере Enter отправляет, Shift+Enter — новая строка
            if (e.key === "Enter" && !e.shiftKey && !("ontouchstart" in window)) {
              e.preventDefault();
              onSend();
            }
          }}
          placeholder="Ваша реплика"
          className="max-h-[140px] min-h-[44px] flex-1 resize-none rounded-[22px] bg-card px-4 py-2.5 text-body text-text placeholder:text-muted/70 focus:outline-none focus:ring-1 focus:ring-accent/60"
        />
        <button
          type="button"
          onClick={onSend}
          disabled={!canSend}
          aria-label="Отправить"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink transition-opacity disabled:opacity-35"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M12 19V5M12 5l-6 6M12 5l6 6" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      {turnsLeft <= 5 ? (
        <p className="mt-1.5 px-2 text-caption text-muted">Осталось реплик: {turnsLeft}</p>
      ) : null}
    </div>
  );
}

function Footer({ children }: { children: ReactNode }) {
  return <div className="border-t border-line/60 px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3">{children}</div>;
}

function Centered({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-4">{children}</div>;
}
