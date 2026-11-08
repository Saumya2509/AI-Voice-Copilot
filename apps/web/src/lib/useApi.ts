import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

/** Load data once (and when deps change) with loading, error and reload. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const live = useRef(0);
  const load = useCallback(() => {
    const id = ++live.current;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => id === live.current && setData(d))
      .catch((e: unknown) => id === live.current && setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => id === live.current && setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(load, [load]);
  return { data, error, loading, reload: load, setData };
}
