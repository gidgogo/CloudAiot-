import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { errorMessage } from "../api/client";

export interface Resource<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: Dispatch<SetStateAction<T | undefined>>;
}

/** 비동기 조회 결과와 다시 불러오기를 관리한다. 늦게 도착한 이전 응답은 버린다. */
export function useResource<T>(loader: () => Promise<T>, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);
  // 호출하는 쪽이 넘긴 deps가 바뀔 때만 loader를 새로 만든다.
  const load = useCallback(loader, deps);

  const reload = useCallback(async () => {
    const current = ++requestId.current;
    setLoading(true);
    try {
      const result = await load();
      if (current === requestId.current) {
        setData(result);
        setError(null);
      }
    } catch (caught) {
      if (current === requestId.current) setError(errorMessage(caught));
    } finally {
      if (current === requestId.current) setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}
