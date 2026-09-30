export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  token?: string | null;
  admin?: boolean;
};

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const key = options.admin ? "bb_admin_token" : "bb_token";
  const token = options.token === undefined ? window.localStorage.getItem(key) : options.token;
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: string | undefined;
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  const response = await fetch(path, {
    method: options.method || (body ? "POST" : "GET"),
    headers,
    body,
  });
  const text = await response.text();
  const parsed = text ? JSON.parse(text) : null;
  if (!response.ok) {
    let detail = "No se ha podido completar la acción.";
    if (typeof parsed?.detail === "string") detail = parsed.detail;
    else if (Array.isArray(parsed?.detail)) {
      detail = parsed.detail.map((item: { msg?: string }) => item.msg || "Dato no válido").join(" ");
    }
    throw new ApiError(detail, response.status);
  }
  return parsed as T;
}

export function gold(value: number): string {
  return `${new Intl.NumberFormat("es-ES").format(value)} mo`;
}

export function signed(value: number): string {
  if (value > 0) return `+${value}`;
  return `${value}`;
}

export const RACE_COLOR: Record<string, string> = {
  human: "#e0b15a",
  orc: "#8fb56a",
  elf: "#79d3b8",
  dwarf: "#e08a3c",
  skaven: "#d2b48c",
  delf: "#c4a6ff",
  undead: "#b7c6cc",
  chaos: "#ef6d5e",
};

export function raceColor(key: string): string {
  return RACE_COLOR[key] || "#f0c14d";
}

export const STATUS_LABEL: Record<string, string> = {
  SCHEDULED: "Programado",
  READY_CHECK: "Comprobando",
  PRE_MATCH: "Prepartido",
  IN_PROGRESS: "En juego",
  COMPLETED: "Cerrado",
  ACTIVE: "En juego",
  MNG: "Se pierde el próximo",
  DEAD: "Muerto",
};

export const EVENT_LABEL: Record<string, string> = {
  TD: "Touchdown",
  CAS: "Baja",
  PASS: "Pase",
  FOUL: "Falta",
  INT: "Intercepción",
  MVP: "MVP",
};
