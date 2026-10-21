import { z } from "zod";

// Схемы повторяют Pydantic-ответы backend (app/schemas/*). Ответ, не прошедший
// проверку, считается ошибкой — интерфейс не показывает непроверенные данные.

export const userSchema = z.object({
  id: z.string(),
  display_name: z.string().nullable(),
  username: z.string().nullable(),
  locale: z.string().nullable(),
  plan: z.string(),
  notifications_enabled: z.boolean(),
});
export type User = z.infer<typeof userSchema>;

export const limitsSchema = z.object({
  trainings_per_day: z.number(),
  analyses_per_day: z.number(),
  messages_per_minute: z.number(),
  max_user_turns: z.number(),
  max_message_chars: z.number(),
  max_custom_situation_chars: z.number(),
});
export type Limits = z.infer<typeof limitsSchema>;

export const loginSchema = z.object({ token: z.string(), expires_at: z.string(), user: userSchema });
export const meSchema = z.object({ user: userSchema, limits: limitsSchema });
export type Me = z.infer<typeof meSchema>;

const option = z.object({ key: z.string(), title: z.string() });
export type Option = z.infer<typeof option>;

export const scenarioItemSchema = z.object({
  id: z.string(),
  slug: z.string(),
  title: z.string(),
  description: z.string(),
  category: z.string(),
  category_title: z.string(),
  starts: z.enum(["persona", "user"]),
  requires_custom_situation: z.boolean(),
});
export type ScenarioItem = z.infer<typeof scenarioItemSchema>;

export const scenarioListSchema = z.object({ items: z.array(scenarioItemSchema) });

export const scenarioDetailSchema = scenarioItemSchema.extend({
  objective: z.string(),
  personas: z.array(option),
  difficulties: z.array(option),
  genders: z.array(option),
  criteria: z.array(z.object({ key: z.string(), title: z.string(), description: z.string() })),
});
export type ScenarioDetail = z.infer<typeof scenarioDetailSchema>;

export const categoriesSchema = z.object({
  items: z.array(z.object({ key: z.string(), title: z.string(), scenario_count: z.number() })),
});

export const messageSchema = z.object({
  id: z.string(),
  sequence_number: z.number(),
  role: z.enum(["user", "persona"]),
  content: z.string(),
  status: z.enum(["accepted", "completed", "failed"]),
  client_message_id: z.string().nullable(),
  created_at: z.string(),
});
export type ChatMessage = z.infer<typeof messageSchema>;

export const trainingSchema = z.object({
  id: z.string(),
  status: z.enum(["active", "completed", "abandoned", "expired"]),
  analysis_status: z.enum(["none", "pending", "done", "failed"]),
  scenario: z.object({
    id: z.string(),
    slug: z.string(),
    title: z.string(),
    description: z.string(),
    objective: z.string(),
    category: z.string(),
    category_title: z.string(),
  }),
  persona: z.object({ name: z.string(), gender: z.string(), type: z.string(), type_title: z.string() }),
  difficulty: z.string(),
  difficulty_title: z.string(),
  interaction_mode: z.string(),
  custom_situation: z.string().nullable(),
  user_turns: z.number(),
  max_user_turns: z.number(),
  started_at: z.string(),
  last_message_at: z.string(),
  completed_at: z.string().nullable(),
  messages: z.array(messageSchema),
});
export type Training = z.infer<typeof trainingSchema>;

export const activeSchema = z.object({ training: trainingSchema.nullable() });

export const sendResultSchema = z.object({
  user_message: messageSchema,
  reply: messageSchema,
  user_turns: z.number(),
  turns_left: z.number(),
});
export type SendResult = z.infer<typeof sendResultSchema>;

export const finishSchema = z.object({ id: z.string(), status: z.string(), analysis_status: z.string() });

const evidence = z.object({ message_seq: z.number(), quote: z.string() });

export const resultSchema = z.object({
  training_id: z.string(),
  analysis_status: z.enum(["none", "pending", "done", "failed"]),
  disclaimer: z.string(),
  result: z
    .object({
      summary: z.string(),
      strengths: z.array(z.object({ text: z.string(), evidence: z.array(evidence) })),
      improvements: z.array(z.object({ text: z.string(), suggestion: z.string(), evidence: z.array(evidence) })),
      alternative_replies: z.array(
        z.object({ message_seq: z.number(), original: z.string(), better: z.string(), why: z.string() }),
      ),
      scores: z.array(
        z.object({ key: z.string(), title: z.string(), score: z.number(), comment: z.string(), evidence: z.array(evidence) }),
      ),
      created_at: z.string(),
    })
    .nullable(),
});
export type ResultResponse = z.infer<typeof resultSchema>;

export const historySchema = z.object({
  items: z.array(
    z.object({
      id: z.string(),
      scenario_title: z.string(),
      category_title: z.string(),
      interaction_mode: z.string(),
      persona_name: z.string(),
      persona_type_title: z.string(),
      difficulty_title: z.string(),
      completed_at: z.string().nullable(),
      analysis_status: z.string(),
      summary: z.string().nullable(),
    }),
  ),
  next_cursor: z.string().nullable(),
});
export type HistoryPage = z.infer<typeof historySchema>;

export const profileSchema = z.object({ user: userSchema, stored_data: z.array(z.string()) });

export const usageSchema = z.object({
  trainings_today: z.number(),
  analyses_today: z.number(),
  limits: limitsSchema,
});

export const deletedSchema = z.object({ deleted_trainings: z.number() });
