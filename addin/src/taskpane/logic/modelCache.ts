const LOCAL_MODEL_ROOT = "/models";
const REMOTE_MODEL_ROOT = "[url]/models";
const MODEL_CACHE_PREFIX = "phishguard-model-cache";
const MODEL_CACHE_VERSION = "v1";

let cachePromise: Promise<Cache | null> | null = null;

function hasCacheStorage(): boolean {
  return typeof caches !== "undefined";
}

async function openModelCache(): Promise<Cache | null> {
  if (!hasCacheStorage()) {
    return null;
  }

  if (!cachePromise) {
    cachePromise = (async () => {
      const cacheName = `${MODEL_CACHE_PREFIX}-${MODEL_CACHE_VERSION}`;

      try {
        const keys = await caches.keys();
        await Promise.all(
          keys
            .filter((key) => key.startsWith(MODEL_CACHE_PREFIX) && key !== cacheName)
            .map((key) => caches.delete(key))
        );

        return await caches.open(cacheName);
      } catch (error) {
        console.warn("[PhishGuard] Model cache unavailable; falling back to network fetches", error);
        return null;
      }
    })();
  }

  return cachePromise;
}

async function getCachedResponse(url: string): Promise<Response> {
  const cache = await openModelCache();
  if (cache) {
    const hit = await cache.match(url);
    if (hit) {
      return hit;
    }
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`);
  }

  if (cache) {
    try {
      await cache.put(url, response.clone());
    } catch (error) {
      console.warn(`[PhishGuard] Failed to persist model asset: ${url}`, error);
    }
  }

  return response;
}

export function modelUrl(fileName: string): string {
  return modelUrls(fileName)[0];
}

function modelUrls(fileName: string): string[] {
  const localUrl = `${LOCAL_MODEL_ROOT}/${fileName}`;
  const remoteUrl = `${REMOTE_MODEL_ROOT}/${fileName}`;
  return [localUrl, remoteUrl];
}

async function loadModelResponse(fileName: string): Promise<Response> {
  const urls = modelUrls(fileName);
  const errors: string[] = [];

  for (const url of urls) {
    try {
      return await getCachedResponse(url);
    } catch (error: any) {
      errors.push(`${url} -> ${error?.message ?? String(error)}`);
    }
  }

  throw new Error(`Failed to load model asset ${fileName}. Attempts: ${errors.join(" | ")}`);
}

export async function loadCachedModelText(fileName: string): Promise<string> {
  return (await loadModelResponse(fileName)).text();
}

export async function loadCachedModelJson<T>(fileName: string): Promise<T> {
  return (await loadModelResponse(fileName)).json() as Promise<T>;
}

export async function loadCachedModelBytes(fileName: string): Promise<Uint8Array> {
  return new Uint8Array(await (await loadModelResponse(fileName)).arrayBuffer());
}

export async function loadCachedText(url: string): Promise<string> {
  return (await getCachedResponse(url)).text();
}

export async function loadCachedJson<T>(url: string): Promise<T> {
  return (await getCachedResponse(url)).json() as Promise<T>;
}

export async function loadCachedBytes(url: string): Promise<Uint8Array> {
  return new Uint8Array(await (await getCachedResponse(url)).arrayBuffer());
}
