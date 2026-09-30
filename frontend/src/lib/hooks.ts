"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "./api";

/** Lectura siempre desde la API: el frontend no guarda logica de Blood Bowl. */
export function useApi<T>(path: string | null, options: { auth?: boolean } = {}) {
  const { auth = false } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);

  const reload = useCallback(async () => {
    if (path === null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setData(await api<T>(path, { auth }));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [path, auth]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/** Refresco periodico: el partido puede llevarlo el rival desde otro movil. */
export function usePoll(callback: () => void, intervalMs: number, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(callback, intervalMs);
    return () => window.clearInterval(id);
  }, [callback, intervalMs, enabled]);
}
