export interface UrlValidationError {
  url: string;
  message: string;
}

/** Client-side shape check — mirrors backend validate_url_shape (no DNS). */
export function validateUrlShape(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return "URL is empty";

  try {
    const parsed = new URL(trimmed);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "Use http or https";
    }
    if (!parsed.hostname) {
      return "URL has no host";
    }
    return null;
  } catch {
    return "Invalid URL format";
  }
}

export function validateUrlList(urls: string[]): UrlValidationError[] {
  return urls.flatMap((url) => {
    const message = validateUrlShape(url);
    return message ? [{ url, message }] : [];
  });
}
