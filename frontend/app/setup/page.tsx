"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Choice } from "@/components/ui/Choice";
import { Card, Screen } from "@/components/ui/Screen";
import { ErrorState, FullScreenLoader, SkeletonLines } from "@/components/ui/States";
import { useActiveTraining, useScenario, useStartTraining } from "@/features/queries";
import { errorCode, errorText, newId } from "@/lib/api";

const DIFFICULTY_HINTS: Record<string, string> = {
  easy: "Собеседник помогает разговору",
  medium: "Ведёт себя как обычно",
  hard: "Инициатива на вас",
};

const PERSONA_HINTS: Record<string, string> = {
  friendly: "Открыт и подхватывает темы",
  neutral: "Вежлив, но без инициативы",
  reserved: "Раскрывается не сразу",
  shy: "Робеет, нужна поддержка",
  sociable: "Говорит много сам",
  skeptical: "Проверяет ваши слова",
  demanding: "Ждёт конкретики",
  unpredictable: "Меняет настроение",
};

export default function SetupPage() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <Setup />
    </Suspense>
  );
}

function Setup() {
  const router = useRouter();
  const scenarioId = useSearchParams().get("id");
  const scenario = useScenario(scenarioId);
  const active = useActiveTraining();
  const start = useStartTraining();

  const [gender, setGender] = useState<string | null>("female");
  const [persona, setPersona] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState<string | null>("medium");
  const [situation, setSituation] = useState("");
  const [showDetails, setShowDetails] = useState(false);
  // Один ключ на экран: повторное нажатие не создаст вторую тренировку
  const idempotencyKey = useMemo(() => newId(), []);

  const data = scenario.data;
  useEffect(() => {
    if (data && !persona) setPersona(data.personas[0]?.key ?? null);
  }, [data, persona]);

  const situationLimit = 1500;
  const needsSituation = data?.requires_custom_situation ?? false;
  const situationOk = !needsSituation || situation.trim().length >= 20;
  const canStart = Boolean(data && gender && persona && difficulty && situationOk) && !start.isPending;
  const activeTraining = active.data?.training ?? null;

  const onStart = () => {
    if (!data || !gender || !persona || !difficulty) return;
    start.mutate(
      {
        params: {
          scenario_id: data.id,
          persona_type: persona,
          persona_gender: gender,
          difficulty,
          custom_situation: situation.trim() || null,
        },
        idempotencyKey,
      },
      { onSuccess: (training) => router.replace(`/chat/?id=${training.id}`) },
    );
  };

  if (!scenarioId) {
    return (
      <Screen back="/scenarios/">
        <ErrorState title="Сценарий не выбран" message="Вернитесь к списку и выберите ситуацию." />
      </Screen>
    );
  }

  return (
    <Screen
      back="/scenarios/"
      title={data?.title}
      footer={
        data ? (
          <Button onClick={onStart} disabled={!canStart} loading={start.isPending}>
            Начать разговор
          </Button>
        ) : undefined
      }
    >
      {scenario.isPending ? <SkeletonLines rows={4} /> : null}
      {scenario.isError ? (
        <ErrorState message={errorText(scenario.error)} onRetry={() => scenario.refetch()} />
      ) : null}

      {data ? (
        <div className="space-y-7">
          <Card>
            <p className="text-small text-pretty">{data.description}</p>
            <p className="mt-3 text-caption text-muted">Ваша цель</p>
            <p className="mt-0.5 text-small font-medium text-pretty">{data.objective}</p>
          </Card>

          {activeTraining ? (
            <div className="rounded-[var(--radius-card)] bg-accent-soft p-4 text-small" role="note">
              У вас есть незавершённая тренировка «{activeTraining.scenario.title}». Новую можно начать, когда завершите её.
              <Link href={`/chat/?id=${activeTraining.id}`} className="mt-2 block font-semibold text-accent">
                Перейти к ней
              </Link>
            </div>
          ) : null}

          {needsSituation ? (
            <SituationField value={situation} onChange={setSituation} limit={situationLimit} required />
          ) : null}

          <Choice label="Собеседник" layout="segments" options={data.genders} value={gender} onChange={setGender} />
          <Choice label="Характер" options={data.personas} value={persona} onChange={setPersona} hints={PERSONA_HINTS} />
          <Choice
            label="Сложность"
            options={data.difficulties}
            value={difficulty}
            onChange={setDifficulty}
            hints={DIFFICULTY_HINTS}
          />

          {!needsSituation ? (
            showDetails ? (
              <SituationField value={situation} onChange={setSituation} limit={situationLimit} />
            ) : (
              <button type="button" onClick={() => setShowDetails(true)} className="text-small font-medium text-accent">
                Добавить детали своими словами
              </button>
            )
          ) : null}

          <div>
            <p className="mb-2 text-small font-semibold">Что будет в разборе</p>
            <ul className="space-y-2">
              {data.criteria.map((c) => (
                <li key={c.key} className="text-small">
                  <span className="font-medium">{c.title}.</span> <span className="text-muted">{c.description}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-caption text-muted">Режим — текстовый диалог. Голос появится позже.</p>
          </div>

          {start.isError ? (
            <ErrorState
              title={errorCode(start.error) === "conflict" ? "Есть незавершённая тренировка" : "Не получилось начать"}
              message={errorText(start.error)}
            />
          ) : null}
        </div>
      ) : null}
    </Screen>
  );
}

function SituationField({
  value,
  onChange,
  limit,
  required = false,
}: {
  value: string;
  onChange: (v: string) => void;
  limit: number;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-small font-semibold">{required ? "Опишите ситуацию" : "Детали ситуации"}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, limit))}
        rows={5}
        placeholder={
          required
            ? "Кто собеседник, где вы, о чём нужно поговорить. Например: прошу у руководителя прибавку после года работы, он занят и сомневается."
            : "Например: мы уже виделись на прошлой неделе"
        }
        className="w-full resize-none rounded-[var(--radius-control)] bg-card p-3.5 text-small text-text placeholder:text-muted/70 focus:outline-none focus:ring-1 focus:ring-accent"
      />
      <span className="mt-1 flex justify-between text-caption text-muted">
        <span>{required && value.trim().length < 20 ? "Хотя бы пару предложений" : "Это описание — только контекст для собеседника"}</span>
        <span>
          {value.length}/{limit}
        </span>
      </span>
    </label>
  );
}
