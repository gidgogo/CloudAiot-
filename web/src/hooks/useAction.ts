import { useCallback, useState } from "react";
import { errorMessage } from "../api/client";
import { useToast } from "../components/Toasts";

export interface ActionOptions {
  /** 실패 알림 제목 */
  failure: string;
  /** 성공 알림 제목(없으면 알리지 않음) */
  success?: string;
  /** 진행 중 표시를 구분할 키(예: 처리 중인 요청 ID) */
  key?: string;
}

/**
 * 저장·삭제 같은 사용자 동작의 공통 처리: 진행 중 표시, 성공·실패 알림.
 * run()은 성공하면 true, 실패하면(알림을 띄운 뒤) false를 돌려준다.
 */
export function useAction() {
  const { push } = useToast();
  const [pending, setPending] = useState<string | null>(null);

  const run = useCallback(
    async (action: () => Promise<unknown>, { failure, success, key = "action" }: ActionOptions): Promise<boolean> => {
      setPending(key);
      try {
        await action();
        if (success) push({ tone: "success", title: success });
        return true;
      } catch (error) {
        push({ tone: "danger", title: failure, message: errorMessage(error) });
        return false;
      } finally {
        setPending(null);
      }
    },
    [push],
  );

  return { run, pending, busy: pending !== null };
}
