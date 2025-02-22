import { z } from "zod";

const MessageSchema = z.object({
  date: z.string(),
  type: z.number(),
});

const ThreadSchema = z.object({
  address: z.string(),
  messages: z.array(MessageSchema),
  first_message: z.string(),
  last_message: z.string(),
});

export type Message = z.infer<typeof MessageSchema>;
export type Thread = z.infer<typeof ThreadSchema>;

const API_BASE = "http://localhost:8000/api";

export async function getThreads(
  offset: number = 0,
  limit: number = 50
): Promise<Thread[]> {
  const response = await fetch(
    `${API_BASE}/threads?offset=${offset}&limit=${limit}`
  );
  if (!response.ok) {
    throw new Error("Failed to fetch threads");
  }
  const data = await response.json();
  return z.array(ThreadSchema).parse(data);
}
