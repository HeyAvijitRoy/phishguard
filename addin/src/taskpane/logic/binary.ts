type OrtModule = typeof import("onnxruntime-web");
type OrtSession = Awaited<ReturnType<OrtModule["InferenceSession"]["create"]>>;

import { loadCachedModelBytes, loadCachedModelText, modelUrl } from "./modelCache";

type Assets = {
  vocab: Map<string, number>;
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

async function ensureAssets(): Promise<Assets> {
  if (assets) return assets;

  const vocabText = await loadText(modelUrl("vocab.txt"));
  const vocab = new Map<string, number>();
  vocabText.split(/\r?\n/).forEach((tok, idx) => {
    if (tok) vocab.set(tok.trim(), idx);
  });

  assets = { vocab };
  return assets;
}

async function ensureSession(): Promise<OrtSession> {
  if (session) return session;

  const ort = await getOrt();
  ort.env.wasm.wasmPaths = ORT_ROOT;

  try {
    session = await ort.InferenceSession.create(await loadCachedModelBytes("phish_binary.onnx"), {
      executionProviders: ["wasm"]
    });
    return session;
  } catch (error) {
    console.error(`[PhishGuard] Failed to create binary ONNX session from ${modelUrl("phish_binary.onnx")}`, error);
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

async function buildFeeds(text: string, vocab: Map<string, number>) {
  const ort = await getOrt();
  const clsId = vocab.get("[CLS]") ?? 101;
  const sepId = vocab.get("[SEP]") ?? 102;
  const padId = vocab.get("[PAD]") ?? 0;
  const unkId = vocab.get("[UNK]") ?? 100;

  const wp = wordpieceTokenize(text, vocab);
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
    input_ids: new ort.Tensor("int64", inputIds64, [1, MAX_LEN]),
    attention_mask: new ort.Tensor("int64", attn64, [1, MAX_LEN])
  };
}

export async function scoreBinaryPhish(subject: string, bodyText: string): Promise<number> {
  const a = await ensureAssets();
  const s = await ensureSession();

  const text = basicNormalize(`${subject}\n${bodyText}`).slice(0, 8000);
  if (!text) return 0;

  const feeds = await buildFeeds(text, a.vocab);

  try {
    const outputs = await s.run(feeds);
    const out = outputs["logits"] ?? Object.values(outputs)[0];
    const raw = out.data as unknown;
    const logits = Array.isArray(raw) ? raw.map((v) => Number(v)) : Array.from(raw as Float32Array);

    let pPhish = 0;
    if (logits.length === 1) {
      pPhish = sigmoid(logits[0]);
    } else {
      const maxLogit = Math.max(...logits);
      const exps = logits.map((v) => Math.exp(v - maxLogit));
      const sum = exps.reduce((acc, v) => acc + v, 0);
      const probs = exps.map((v) => v / sum);
      pPhish = probs[1] ?? 0;
    }

    return Math.max(0, Math.min(1, pPhish));
  } catch (error) {
    console.error("[PhishGuard] Binary model inference failed", error);
    throw error;
  }
}
