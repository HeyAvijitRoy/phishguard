export async function hashId(input: string): Promise<string | undefined> {
  try {
    if (!input) return undefined;
    const enc = new TextEncoder().encode(input);
    const digest = await crypto.subtle.digest("SHA-256", enc);
    const bytes = Array.from(new Uint8Array(digest));
    return bytes.map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return undefined;
  }
}
