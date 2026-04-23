import type { NlpSignals } from "../../shared/types";
type OrtModule = typeof import("onnxruntime-web");
type OrtSession = Awaited<ReturnType<OrtModule["InferenceSession"]["create"]>>;

import { loadCachedModelBytes, loadCachedModelJson, loadCachedModelText, modelUrl } from "./modelCache";

type Assets = {
  vocab: Map<string, number>;
  labels: string[];
};

let ortPromise: Promise<OrtModule> | null = null;
let session: OrtSession | null = null;
let assets: Assets | null = null;

const MAX_LEN = 256;
const ORT_ROOT = "/ort/";

function sigmoid(x: number) {
  return 1 / (1 + Math.exp(-x));
}

async function loadText(url: string): Promise<string> {
  try {
    return await loadCachedModelText(url.slice(url.lastIndexOf("/") + 1));
  } catch (error) {
    console.error(`[PhishGuard] Failed to load text asset: ${url}`, error);
    throw error;
  }
}

async function loadJson<T>(url: string): Promise<T> {
  try {
    return await loadCachedModelJson<T>(url.slice(url.lastIndexOf("/") + 1));
  } catch (error) {
    console.error(`[PhishGuard] Failed to load JSON asset: ${url}`, error);
    throw error;
  }
}

async function ensureAssets(): Promise<Assets> {
  if (assets) return assets;

  const vocabText = await loadText(modelUrl("vocab.txt"));
  const vocab = new Map<string, number>();
  vocabText.split(/\r?\n/).forEach((tok, idx) => {
    if (tok) vocab.set(tok.trim(), idx);
  });

  const labels = await loadJson<string[]>(modelUrl("labels.json"));

  assets = { vocab, labels };
  return assets;
}

async function ensureSession(): Promise<OrtSession> {
  if (session) return session;

  const ort = await getOrt();
  ort.env.wasm.wasmPaths = ORT_ROOT;

  try {
    session = await ort.InferenceSession.create(await loadCachedModelBytes("phish_intent.onnx"), {
      executionProviders: ["wasm"]
    });
    return session;
  } catch (error) {
    console.error(`[PhishGuard] Failed to create intent ONNX session from ${modelUrl("phish_intent.onnx")}`, error);
    throw error;
  }
}

async function getOrt(): Promise<OrtModule> {
  if (!ortPromise) {
    ortPromise = import("onnxruntime-web");
  }

  return ortPromise;
}

function basicNormalize(text: string): string {
  return text
    .replace(/\u00A0/g, " ")
    .replace(/[^\w\s@.:-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function wordpieceTokenize(text: string, vocab: Map<string, number>): string[] {
  const unk = "[UNK]";
  const tokens: string[] = [];
  const words = text.split(" ").filter(Boolean);

  for (const word of words) {
    if (vocab.has(word)) {
      tokens.push(word);
      continue;
    }

    let start = 0;
    const subTokens: string[] = [];
    let isBad = false;

    while (start < word.length) {
      let end = word.length;
      let curSub: string | null = null;

      while (start < end) {
        let piece = word.slice(start, end);
        if (start > 0) piece = `##${piece}`;

        if (vocab.has(piece)) {
          curSub = piece;
          break;
        }
        end -= 1;
      }

      if (!curSub) {
        isBad = true;
        break;
      }

      subTokens.push(curSub);
      start = end;
    }

    if (isBad) tokens.push(unk);
    else tokens.push(...subTokens);
  }

  return tokens;
}

async function buildInputs(text: string, vocab: Map<string, number>) {
  const ort = await getOrt();
  const clsId = vocab.get("[CLS]") ?? 101;
  const sepId = vocab.get("[SEP]") ?? 102;
  const padId = vocab.get("[PAD]") ?? 0;
  const unkId = vocab.get("[UNK]") ?? 100;

  const wp = wordpieceTokenize(text, vocab);
  const unkCount = wp.filter((t) => t === "[UNK]").length;
  const tokenCount = wp.length;
  const ids: number[] = [clsId];

  for (const t of wp) ids.push(vocab.get(t) ?? unkId);
  ids.push(sepId);

  const inputIds = ids.slice(0, MAX_LEN);
  const attentionMask = new Array(inputIds.length).fill(1);

  while (inputIds.length < MAX_LEN) {
    inputIds.push(padId);
    attentionMask.push(0);
  }

  const inputIds64 = BigInt64Array.from(inputIds.map(BigInt));
  const attn64 = BigInt64Array.from(attentionMask.map(BigInt));

  return {
    feeds: {
      input_ids: new ort.Tensor("int64", inputIds64, [1, MAX_LEN]),
      attention_mask: new ort.Tensor("int64", attn64, [1, MAX_LEN])
    },
    unkCount,
    tokenCount
  };
}

export function nlpToPoints(nlp: NlpSignals): number {
  return (
    nlp.intentCredential * 30 +
    nlp.intentPayment * 25 +
    nlp.intentThreat * 15 +
    nlp.intentImpersonation * 10
  );
}

export async function computeNlpSignals(subject: string, bodyText: string): Promise<NlpSignals> {
  const a = await ensureAssets();
  const s = await ensureSession();

  const text = basicNormalize(`${subject}\n${bodyText}`).slice(0, 8000);
  if (!text) {
    return {
      intentCredential: 0,
      intentPayment: 0,
      intentThreat: 0,
      intentImpersonation: 0,
      semanticSuspicion: 0
    };
  }

  const { feeds, unkCount, tokenCount } = await buildInputs(text, a.vocab);

  try {
    const outputs = await s.run(feeds);
    const out = outputs["logits"] ?? Object.values(outputs)[0];
    const raw = out.data as unknown;
    const logits = Array.isArray(raw)
      ? raw.map((v) => Number(v))
      : Array.from(raw as Float32Array);

    const unkRatio = tokenCount > 0 ? unkCount / tokenCount : 0;
    console.log("[PhishGuard] tokenization stats", { unkRatio, unkCount, tokenCount, outputKeys: Object.keys(outputs) });

    const probs = logits.map(sigmoid);
    const idx = (name: string) => Math.max(0, a.labels.indexOf(name));

    const intentCredential = probs[idx("credential")] ?? 0;
    const intentPayment = probs[idx("payment")] ?? 0;
    const intentThreat = probs[idx("threat")] ?? 0;
    const intentImpersonation = probs[idx("impersonation")] ?? 0;

    const semanticSuspicion = Math.max(intentCredential, intentPayment, intentThreat, intentImpersonation);

    return {
      intentCredential,
      intentPayment,
      intentThreat,
      intentImpersonation,
      semanticSuspicion
    };
  } catch (error) {
    console.error("[PhishGuard] Intent model inference failed", error);
    throw error;
  }
}
