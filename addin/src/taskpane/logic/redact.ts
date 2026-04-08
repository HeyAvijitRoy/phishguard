export function redactText(text: string): string {
  if (!text) return text;

  let t = text;

  // Emails
  t = t.replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[REDACTED_EMAIL]");

  // Phone-like patterns (simple heuristic)
  t = t.replace(/(\+?\d[\d\s().-]{7,}\d)/g, "[REDACTED_PHONE]");

  // Very rough account/ID patterns
  t = t.replace(/\b\d{6,}\b/g, "[REDACTED_NUMBER]");

  return t;
}
