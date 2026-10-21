"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, Screen, Section } from "@/components/ui/Screen";
import { ErrorState, FullScreenLoader } from "@/components/ui/States";
import { useResult, useRetryAnalysis, useRetryTraining, useTraining } from "@/features/queries";
import { errorText } from "@/lib/api";
import type { ResultResponse, Training } from "@/lib/schemas";

export default function ResultPage() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Result />
    </Suspense>
  );
}

function Result() {
  const id = useSearchParams().get("id");
  const router = useRouter();
  const result = useResult(id);
  const training = useTraining(id);
  const retryAnalysis = useRetryAnalysis();
  const retryTraining = useRetryTraining();
  const [showTranscript, setShowTranscript] = useState(false);

  if (!id) return <Screen back="/"><ErrorState title="Разбор не найден" message="Вернитесь на главную." /></Screen>;
  if (result.isPending) return <FullScreenLoader />;
  if (result.isError) {
    return (
      <Screen back="/">
        <ErrorState message={errorText(result.error)} onRetry={() => result.refetch()} />
      </Screen>
    );
  }

  const status = result.data.analysis_status;
  const data = result.data.result;

  const footer = (
    <div className="space-y-2">
      <Button
        loading={retryTraining.isPending}
        onClick={() =>
          retryTraining.mutate(id, { onSuccess: (t) => router.replace(`/chat/?id=${t.id}`) })
        }
      >
        Попробовать ещё раз
      </Button>
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={() => router.push("/scenarios/")}>
          Другая ситуация
        </Button>
        <Button variant="secondary" onClick={() => router.push("/")}>
          На главную
        </Button>
      </div>
      {retryTraining.isError ? (
        <p className="text-center text-caption text-danger">{errorText(retryTraining.error)}</p>
      ) : null}
    </div>
  );

  return (
    <Screen back="/" footer={footer}>
      <p className="text-small text-muted">
        {training.data ? `${training.data.scenario.title} · ${training.data.persona.name}` : "Разбор тренировки"}
      </p>

      {status === "pending" ? <Preparing /> : null}

      {status === "failed" ? (
        <div className="mt-6">
          <ErrorState
            title="Разбор не получился"
            message="Разговор сохранён. Запустите разбор ещё раз — обычно со второй попытки всё проходит."
            action={
              <Button loading={retryAnalysis.isPending} onClick={() => retryAnalysis.mutate(id)}>
                Повторить разбор
              </Button>
            }
          />
          {retryAnalysis.isError ? (
            <p className="mt-2 text-caption text-danger">{errorText(retryAnalysis.error)}</p>
          ) : null}
        </div>
      ) : null}

      {status === "none" ? (
        <div className="mt-6">
          <ErrorState title="Разбора нет" message="Тренировка закрыта без реплик, поэтому разбирать нечего." />
        </div>
      ) : null}

      {status === "done" && data ? (
        <Analysis data={data} disclaimer={result.data.disclaimer} training={training.data ?? null} />
      ) : null}

      {training.data && training.data.messages.length > 0 ? (
        <div className="mt-8">
          <button
            type="button"
            onClick={() => setShowTranscript((v) => !v)}
            aria-expanded={showTranscript}
            className="text-small font-medium text-accent"
          >
            {showTranscript ? "Скрыть разговор" : "Посмотреть разговор"}
          </button>
          {showTranscript ? <Transcript training={training.data} /> : null}
        </div>
      ) : null}
    </Screen>
  );
}

function Preparing() {
  return (
    <div className="mt-[10vh] flex flex-col items-center text-center" aria-busy>
      <div className="flex gap-1.5" aria-hidden>
        <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
        <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
        <span className="typing-dot h-2 w-2 rounded-full bg-accent" />
      </div>
      <p className="mt-4 text-body font-semibold">Готовим разбор</p>
      <p className="mt-1 max-w-xs text-small text-muted">Обычно это занимает 10–30 секунд. Можно закрыть приложение — разбор сохранится в профиле.</p>
    </div>
  );
}

type AnalysisData = NonNullable<ResultResponse["result"]>;

function Analysis({ data, disclaimer, training }: { data: AnalysisData; disclaimer: string; training: Training | null }) {
  const quote = (seq: number) => training?.messages.find((m) => m.sequence_number === seq)?.content;
  return (
    <div>
      <h1 className="mt-2 text-display font-semibold tracking-[-0.02em]">Разбор</h1>
      <p className="mt-3 text-body text-pretty">{data.summary}</p>

      <Section title="Оценки">
        <ul className="space-y-2">
          {data.scores.map((s) => (
            <li key={s.key}>
              <Card>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-small font-semibold">{s.title}</span>
                  <span className="text-small tabular-nums text-muted">
                    <span className="font-semibold text-text">{s.score}</span> из 5
                  </span>
                </div>
                <div className="mt-2.5 flex gap-1" aria-hidden>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <span key={n} className={`h-1 flex-1 rounded-full ${n <= s.score ? "bg-accent" : "bg-surface"}`} />
                  ))}
                </div>
                <p className="mt-2.5 text-small text-muted text-pretty">{s.comment}</p>
                <Evidence items={s.evidence} />
              </Card>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Что получилось">
        <ul className="space-y-2">
          {data.strengths.map((p, i) => (
            <li key={i}>
              <Card>
                <p className="text-small text-pretty">{p.text}</p>
                <Evidence items={p.evidence} />
              </Card>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Что улучшить">
        <ul className="space-y-2">
          {data.improvements.map((p, i) => (
            <li key={i}>
              <Card>
                <p className="text-small text-pretty">{p.text}</p>
                <p className="mt-2 text-small font-medium text-pretty">{p.suggestion}</p>
                <Evidence items={p.evidence} />
              </Card>
            </li>
          ))}
        </ul>
      </Section>

      {data.alternative_replies.length > 0 ? (
        <Section title="Как можно было сказать">
          <ul className="space-y-2">
            {data.alternative_replies.map((a, i) => (
              <li key={i}>
                <Card>
                  <p className="text-caption text-muted">Было</p>
                  <p className="mt-0.5 text-small text-muted text-pretty">{quote(a.message_seq) ?? a.original}</p>
                  <p className="mt-3 text-caption text-accent">Можно так</p>
                  <p className="mt-0.5 text-small font-medium text-pretty">{a.better}</p>
                  <p className="mt-2 text-caption text-muted text-pretty">{a.why}</p>
                </Card>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <p className="mt-8 text-caption text-muted text-pretty">{disclaimer}</p>
    </div>
  );
}

function Evidence({ items }: { items: { message_seq: number; quote: string }[] }) {
  const quoted = items.filter((e) => e.quote);
  if (quoted.length === 0) return null;
  return (
    <ul className="mt-2.5 space-y-1">
      {quoted.map((e, i) => (
        <li key={i} className="border-l-2 border-accent/40 pl-2.5 text-caption text-muted">
          «{e.quote}»
        </li>
      ))}
    </ul>
  );
}

function Transcript({ training }: { training: Training }) {
  return (
    <ol className="mt-4 space-y-2.5">
      {training.messages
        .filter((m) => m.status === "completed")
        .map((m) => (
          <li key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-[16px] px-3.5 py-2.5 text-small ${
                m.role === "user" ? "bg-surface" : "bg-card"
              }`}
            >
              {m.content}
            </div>
          </li>
        ))}
      <li className="pt-2 text-center">
        <Link href={`/chat/?id=${training.id}`} className="text-caption text-muted">
          Открыть разговор целиком
        </Link>
      </li>
    </ol>
  );
}
