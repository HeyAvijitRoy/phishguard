import type { ExtractedEmail } from "../../shared/types";

function getItem(): any {
  const w: any = window as any;
  return w.Office?.context?.mailbox?.item;
}

function asString(v: any): string {
  return (v ?? "").toString();
}

function domainFromEmail(addr?: string): string | undefined {
  if (!addr) return undefined;
  const m = addr.match(/@([a-z0-9.-]+\.[a-z]{2,})/i);
  return m?.[1]?.toLowerCase();
}

function htmlToText(html: string): string {
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  return (tmp.textContent || tmp.innerText || "").trim();
}

export async function getCurrentEmail(): Promise<ExtractedEmail> {
  const item = getItem();
  if (!item) return { subject: "", bodyText: "" };

  const subject = asString(item.subject);
  const messageId = asString(item.itemId || item.internetMessageId);

  const fromEmail = item.from?.emailAddress || item.sender?.emailAddress;
  const fromName = item.from?.displayName || item.sender?.displayName;
  const from = fromEmail || fromName;

  const fromDomain = domainFromEmail(fromEmail);

  const toList: string[] = [];
  const to = item.to || item.toRecipients || [];
  for (const r of to) {
    if (r?.emailAddress) toList.push(r.emailAddress);
    else if (r?.displayName) toList.push(r.displayName);
  }

  // Get HTML first (for link extraction), fall back to text.
  const bodyHtml = await new Promise<string>((resolve) => {
    if (!item?.body?.getAsync) return resolve("");
    item.body.getAsync("html", (res: Office.AsyncResult<string>) => {
      if (res.status === Office.AsyncResultStatus.Succeeded) resolve(res.value || "");
      else resolve("");
    });
  });

  let bodyText = "";
  if (bodyHtml) {
    bodyText = htmlToText(bodyHtml);
  } else {
    bodyText = await new Promise<string>((resolve) => {
      if (!item?.body?.getAsync) return resolve("");
      item.body.getAsync("text", (res: Office.AsyncResult<string>) => {
        if (res.status === Office.AsyncResultStatus.Succeeded) resolve(res.value || "");
        else resolve("");
      });
    });
  }

  return {
    messageId: messageId || undefined,
    subject: subject || "",
    bodyText: bodyText || "",
    bodyHtml: bodyHtml || undefined,
    from: from || undefined,
    fromName: fromName || undefined,
    fromEmail: fromEmail || undefined,
    fromDomain,
    to: toList.length ? toList : undefined,
    conversationId: asString(item.conversationId || "") || undefined,
    internetHeaders: await new Promise<string | undefined>((resolve) => {
      if (typeof item?.getAllInternetHeadersAsync !== "function") return resolve(undefined);
      item.getAllInternetHeadersAsync((res: Office.AsyncResult<string>) => {
        if (res.status === Office.AsyncResultStatus.Succeeded) resolve(res.value || undefined);
        else resolve(undefined);
      });
    })
  };
}
