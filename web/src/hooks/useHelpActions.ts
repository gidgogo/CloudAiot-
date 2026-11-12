import { api } from "../api/client";
import { useSession } from "../auth/AuthContext";
import type { HelpRequest, HelpStatus } from "../types";
import { canChangeHelpStatus } from "../utils/permissions";
import { useAction } from "./useAction";

/**
 * 도움 요청 생성·상태 변경. 서버가 돌려준 요청을 onSaved로 넘겨 화면 목록에 바로 반영한다.
 * (다른 화면에는 실시간 이벤트로 전달된다.)
 */
export function useHelpActions(onSaved: (request: HelpRequest) => void) {
  const session = useSession();
  const { run, pending } = useAction();

  const changeStatus = (request: HelpRequest, status: Exclude<HelpStatus, "CREATED">) =>
    run(async () => onSaved(await api.helpRequests.updateStatus(request.request_id, status)), {
      key: request.request_id,
      failure: "상태를 바꾸지 못했어요",
    });

  const create = (userId?: string) =>
    run(async () => onSaved(await api.helpRequests.create(userId)), {
      key: "create",
      success: userId ? "도움 요청을 대신 보냈어요" : "보호자에게 도움 요청을 보냈어요",
      failure: "도움 요청을 보내지 못했어요",
    });

  return {
    create,
    changeStatus,
    canChange: (request: HelpRequest) => canChangeHelpStatus(session, request),
    busyId: pending,
  };
}

/** 목록에 같은 요청이 있으면 바꾸고, 없으면 맨 앞에 넣는다. */
export function upsertHelpRequest(items: HelpRequest[], request: HelpRequest): HelpRequest[] {
  return items.some((item) => item.request_id === request.request_id)
    ? items.map((item) => (item.request_id === request.request_id ? request : item))
    : [request, ...items];
}
