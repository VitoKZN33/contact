"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { Card, Screen } from "@/components/ui/Screen";

const STEPS = [
  {
    title: "Выберите ситуацию",
    text: "Знакомство, отказ, сложный разговор — или опишите свою. Затем характер собеседника и сложность.",
  },
  {
    title: "Поговорите",
    text: "Собеседник не подсказывает и не оценивает — отвечает как живой человек со своими интересами.",
  },
  {
    title: "Получите разбор",
    text: "Нажмите «Завершить»: что сработало, что мешало и как можно было сказать иначе — с вашими цитатами.",
  },
];

const TIPS = [
  "Пишите так, как сказали бы вслух. Короткие реплики — нормально.",
  "Ошибаться можно: собеседник не обидится, а разбор покажет, что поправить.",
  "Повторите тот же сценарий на сложности выше, когда станет легко.",
  "Разговор сохраняется: можно закрыть приложение и вернуться в течение суток.",
];

export default function HelpPage() {
  const router = useRouter();
  return (
    <Screen
      back="/"
      title="Как пользоваться"
      footer={<Button onClick={() => router.push("/scenarios/")}>Выбрать ситуацию</Button>}
    >
      <ol className="space-y-2">
        {STEPS.map((s, i) => (
          <li key={s.title}>
            <Card className="flex gap-3.5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-caption font-semibold text-accent">
                {i + 1}
              </span>
              <span>
                <span className="block text-small font-semibold">{s.title}</span>
                <span className="mt-0.5 block text-small text-muted text-pretty">{s.text}</span>
              </span>
            </Card>
          </li>
        ))}
      </ol>
      <h2 className="mt-8 text-title font-semibold">Советы</h2>
      <ul className="mt-3 space-y-2.5">
        {TIPS.map((t) => (
          <li key={t} className="text-small text-muted text-pretty">
            {t}
          </li>
        ))}
      </ul>
    </Screen>
  );
}
