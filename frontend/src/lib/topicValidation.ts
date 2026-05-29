export const MAX_TOPICS = 3;
export const MAX_TOPIC_LEN = 120;

const ILLEGAL_TOPIC_CHARS = /[\n\r\x00]/;

export interface TopicValidationError {
  topic: string;
  message: string;
}

/** Client-side topic check — mirrors backend RunCreateRequest topic rules. */
export function validateTopicDraft(raw: string): string | null {
  if (ILLEGAL_TOPIC_CHARS.test(raw)) {
    return "Topic cannot contain line breaks";
  }
  const trimmed = raw.trim();
  if (!trimmed) return null;
  if (trimmed.length > MAX_TOPIC_LEN) {
    return `Keep topics under ${MAX_TOPIC_LEN} characters (${trimmed.length}/${MAX_TOPIC_LEN})`;
  }
  return null;
}

export function validateTopicList(topics: string[]): TopicValidationError[] {
  return topics.flatMap((topic) => {
    const message = validateTopicDraft(topic);
    return message ? [{ topic, message }] : [];
  });
}
