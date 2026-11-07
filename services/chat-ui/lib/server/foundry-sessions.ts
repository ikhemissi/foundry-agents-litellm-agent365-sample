// Foundry mode: the hosted agent's session for each chat thread, so that a conversation's later messages reuse the
// agent's running session (a warm container) instead of starting a new one (about 5-8 s each). Kept in this server's
// memory, by user and thread: a user never reuses another user's session. A lost entry (a restart, an old thread) only
// costs a new session. The agent keeps no user data in its session: the user's tokens live for one request.
const maxSessions = 1_000;
// Foundry suspends an idle session after 15 minutes by default; a later request would start it cold anyway.
const maxIdleMs = 15 * 60_000;

interface RememberedSession {
  id: string;
  lastUsed: number;
}

const sessions = new Map<string, RememberedSession>();

export function sessionKey(userId: string, threadId: string): string {
  return `${userId}:${threadId}`;
}

export function rememberedSession(key: string, now = Date.now()): string | undefined {
  const session = sessions.get(key);
  if (!session || now - session.lastUsed > maxIdleMs) {
    sessions.delete(key);
    return undefined;
  }
  return session.id;
}

export function rememberSession(key: string, id: string, now = Date.now()): void {
  // A Map keeps insertion order: re-inserting moves the key last, so the first key is the least recently used.
  sessions.delete(key);
  sessions.set(key, { id, lastUsed: now });
  if (sessions.size > maxSessions) sessions.delete(sessions.keys().next().value!);
}

export function forgetAllSessions(): void {
  sessions.clear();
}
