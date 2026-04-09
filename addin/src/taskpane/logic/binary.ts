import * as ort from "onnxruntime-web";

type Assets = {
  vocab: Map<string, number>;
};

let session: ort.InferenceSession | null = null;
let assets: Assets | null = null;

const MAX_LEN = 256;

function sigmoid(x: number) {
  return 1 / (1 + Math.exp(-x));
}

async function loadText(url: string): Promise<string> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load ${url}`);
  return await res.text();
}

async function ensureAssets(): Promise<Assets> {
  if (assets) return assets;

  const vocabText = await loadText("/models/vocab.txt");
  const vocab = new Map<string, number>();
  vocabText.split(/\r?\n/).forEach((tok, idx) => {
    if (tok) vocab.set(tok.trim(), idx);
  });

  assets = { vocab };
  return assets;
}

async function ensureSession(): Promise<ort.InferenceSession> {
  if (session) return session;

  ort.env.wasm.wasmPaths = "/ort/";

  // Temporary ONNX runtime inspection artifact: uncomment to verify browser-side WASM config.
  // console.log("[PhishGuard ONNX] wasmPaths:", ort.env.wasm.wasmPaths);
  // console.log("[PhishGuard ONNX] versions:", ort.env.versions);

  session = await ort.InferenceSession.create("/models/phish_binary.onnx", {
    executionProviders: ["wasm"]
  });

  return session;
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

function buildInputs(text: string, vocab: Map<string, number>) {
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

  const feeds = buildInputs(text, a.vocab);
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
}
