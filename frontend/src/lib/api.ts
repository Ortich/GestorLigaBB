"use client";

const TOKEN_KEY = "bb.token";
const TEAM_KEY = "bb.teamId";
const TEAM_NAME_KEY = "bb.teamName";
const MASTER_KEY = "bb.masterKey";

/**
 * En `next dev` las llamadas van al proxy de next.config.mjs; en el build
 * estatico servido por FastAPI comparten origen. NEXT_PUBLIC_API_URL permite
 * apuntar a otro host si se despliegan por separado.
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code = "error") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const session = {
  get token() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TOKEN_KEY);
  },
  get teamId(): number | null {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem(TEAM_KEY);
    return raw ? Number(raw) : null;
  },
  get teamName() {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(TEAM_NAME_KEY);
  },
  save(token: string, teamId: number, teamName: string) {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.localStorage.setItem(TEAM_KEY, String(teamId));
    window.localStorage.setItem(TEAM_NAME_KEY, teamName);
  },
  clear() {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(TEAM_KEY);
    window.localStorage.removeItem(TEAM_NAME_KEY);
  },
  get masterKey() {
    if (typeof window === "undefined") return null;
    return window.sessionStorage.getItem(MASTER_KEY);
  },
  saveMasterKey(key: string) {
    window.sessionStorage.setItem(MASTER_KEY, key);
  },
  clearMasterKey() {
    window.sessionStorage.removeItem(MASTER_KEY);
  },
};

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  master?: boolean;
  masterKey?: string;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false, master = false, masterKey } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = session.token;
    if (!token) throw new ApiError("Tu sesion ha caducado. Vuelve a entrar con tu PIN.", 401, "unauthorized");
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (master) {
    const key = masterKey ?? session.masterKey;
    if (!key) throw new ApiError("Introduce la clave de comisario.", 403, "forbidden");
    headers["X-Master-Key"] = key;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("No se puede contactar con el servidor de la liga.", 0, "network");
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg ?? "Dato invalido").join(". ")
          : "Ha ocurrido un error inesperado.";
    throw new ApiError(message, response.status, payload?.code ?? "error");
  }

  return payload as T;
}

export const formatGold = (amount: number | null | undefined) =>
  `${(amount ?? 0).toLocaleString("es-ES")} mo`;

export const formatShortGold = (amount: number | null | undefined) =>
  `${Math.round((amount ?? 0) / 1000).toLocaleString("es-ES")}k`;
