"use client";

import { Card, Screen } from "@/components/ui/Screen";
import { ErrorState, SkeletonLines } from "@/components/ui/States";
import { useProfile } from "@/features/queries";
import { errorText } from "@/lib/api";

export default function PrivacyPage() {
  const profile = useProfile();
  return (
    <Screen back="/profile/" title="Ваши данные" subtitle="Храним только то, без чего тренажёр не работает.">
      {profile.isPending ? <SkeletonLines rows={3} /> : null}
      {profile.isError ? <ErrorState message={errorText(profile.error)} onRetry={() => profile.refetch()} /> : null}
      {profile.data ? (
        <ul className="space-y-2">
          {profile.data.stored_data.map((line) => (
            <li key={line}>
              <Card>
                <p className="text-small text-pretty">{line}</p>
              </Card>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="mt-6 text-small text-muted text-pretty">
        Удалить историю или все данные можно в профиле. Удаление выполняется сразу и без возможности восстановления.
        Разборы делает ИИ по репликам конкретного разговора — это не психологическая оценка.
      </p>
    </Screen>
  );
}
