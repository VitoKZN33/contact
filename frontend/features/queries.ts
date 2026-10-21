"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import {
  activeSchema,
  categoriesSchema,
  deletedSchema,
  finishSchema,
  historySchema,
  profileSchema,
  resultSchema,
  scenarioDetailSchema,
  scenarioListSchema,
  sendResultSchema,
  trainingSchema,
  usageSchema,
  type Training,
} from "@/lib/schemas";

// Вся работа с сервером — здесь. Компоненты не знают путей API и не содержат
// бизнес-правил: лимиты, статусы и доступы решает backend.

export const keys = {
  categories: ["categories"] as const,
  scenarios: (category: string | null) => ["scenarios", category] as const,
  scenario: (id: string) => ["scenario", id] as const,
  active: ["training", "active"] as const,
  training: (id: string) => ["training", id] as const,
  result: (id: string) => ["result", id] as const,
  history: ["history"] as const,
  profile: ["profile"] as const,
  usage: ["usage"] as const,
};

export function useCategories() {
  return useQuery({ queryKey: keys.categories, queryFn: () => api("/api/v1/scenarios/categories", categoriesSchema) });
}

export function useScenarios(category: string | null) {
  return useQuery({
    queryKey: keys.scenarios(category),
    queryFn: () =>
      api(`/api/v1/scenarios${category ? `?category=${encodeURIComponent(category)}` : ""}`, scenarioListSchema),
  });
}

export function useScenario(id: string | null) {
  return useQuery({
    queryKey: keys.scenario(id ?? ""),
    queryFn: () => api(`/api/v1/scenarios/${id}`, scenarioDetailSchema),
    enabled: Boolean(id),
  });
}

export function useActiveTraining() {
  return useQuery({ queryKey: keys.active, queryFn: () => api("/api/v1/trainings/active", activeSchema), staleTime: 0 });
}

export function useTraining(id: string | null) {
  return useQuery({
    queryKey: keys.training(id ?? ""),
    queryFn: () => api(`/api/v1/trainings/${id}`, trainingSchema),
    enabled: Boolean(id),
    staleTime: 0,
    // Реплика, отправленная до перезагрузки страницы, ещё обрабатывается — опрашиваем
    refetchInterval: (query) =>
      query.state.data?.messages.some((m) => m.status === "accepted") ? 3000 : false,
  });
}

export type StartParams = {
  scenario_id: string;
  persona_type: string;
  persona_gender: string;
  difficulty: string;
  custom_situation: string | null;
};

export function useStartTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ params, idempotencyKey }: { params: StartParams; idempotencyKey: string }) =>
      api("/api/v1/trainings", trainingSchema, {
        method: "POST",
        body: { ...params, interaction_mode: "text" },
        headers: { "Idempotency-Key": idempotencyKey },
      }),
    onSuccess: (training) => {
      qc.setQueryData(keys.training(training.id), training);
      void qc.invalidateQueries({ queryKey: keys.active });
      void qc.invalidateQueries({ queryKey: keys.usage });
    },
  });
}

export function useRetryTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (trainingId: string) =>
      api(`/api/v1/trainings/${trainingId}/retry`, trainingSchema, { method: "POST" }),
    onSuccess: (training) => {
      qc.setQueryData(keys.training(training.id), training);
      void qc.invalidateQueries({ queryKey: keys.active });
    },
  });
}

export function sendMessage(trainingId: string, content: string, clientMessageId: string) {
  return api(`/api/v1/trainings/${trainingId}/messages`, sendResultSchema, {
    method: "POST",
    body: { content, client_message_id: clientMessageId },
  });
}

export function useFinishTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (trainingId: string) => api(`/api/v1/trainings/${trainingId}/finish`, finishSchema, { method: "POST" }),
    onSuccess: (_, trainingId) => {
      void qc.invalidateQueries({ queryKey: keys.active });
      void qc.invalidateQueries({ queryKey: keys.training(trainingId) });
      void qc.invalidateQueries({ queryKey: keys.history });
    },
  });
}

export function useResult(trainingId: string | null) {
  return useQuery({
    queryKey: keys.result(trainingId ?? ""),
    queryFn: () => api(`/api/v1/trainings/${trainingId}/result`, resultSchema),
    enabled: Boolean(trainingId),
    staleTime: 0,
    // Разбор готовится в фоне: опрос раз в 2 с, пока статус pending
    refetchInterval: (query) => (query.state.data?.analysis_status === "pending" ? 2000 : false),
  });
}

export function useRetryAnalysis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (trainingId: string) =>
      api(`/api/v1/trainings/${trainingId}/retry-analysis`, finishSchema, { method: "POST" }),
    onSuccess: (_, trainingId) => void qc.invalidateQueries({ queryKey: keys.result(trainingId) }),
  });
}

export function useHistory() {
  return useInfiniteQuery({
    queryKey: keys.history,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api(`/api/v1/trainings?limit=20${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`, historySchema),
    getNextPageParam: (last) => last.next_cursor,
  });
}

export function useProfile() {
  return useQuery({ queryKey: keys.profile, queryFn: () => api("/api/v1/profile", profileSchema) });
}

export function useUsage() {
  return useQuery({ queryKey: keys.usage, queryFn: () => api("/api/v1/profile/usage", usageSchema) });
}

export function useUpdateNotifications() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) =>
      api("/api/v1/profile", profileSchema, { method: "PATCH", body: { notifications_enabled: enabled } }),
    onSuccess: (profile) => qc.setQueryData(keys.profile, profile),
  });
}

export function useDeleteHistory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/api/v1/profile/trainings", deletedSchema, { method: "DELETE" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.history }),
  });
}

export function useDeleteAllData() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/api/v1/profile/data", null, { method: "DELETE", body: { confirm: "DELETE" } }),
    onSuccess: () => qc.clear(),
  });
}

/** Обновить тренировку в кэше после хода, не дожидаясь нового запроса. */
export function patchTraining(
  qc: ReturnType<typeof useQueryClient>,
  id: string,
  update: (t: Training) => Training,
): void {
  qc.setQueryData<Training>(keys.training(id), (old) => (old ? update(old) : old));
}
