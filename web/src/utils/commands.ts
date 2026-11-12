import type { CommandEventData, ControlEvent, Paged } from "../types";

/**
 * command.completed / command.failed 이벤트에는 표에 필요한 결과가 모두 들어 있으므로
 * 목록을 다시 불러오지 않고 해당 행만 바꾼다. 목록에 없으면 그대로 둔다.
 */
export function applyCommandEvent(page: Paged<ControlEvent> | undefined, data: CommandEventData): Paged<ControlEvent> | undefined {
  if (!page || !page.items.some((item) => item.command_id === data.command_id)) return page;
  return {
    ...page,
    items: page.items.map((item) =>
      item.command_id === data.command_id
        ? { ...item, status: data.status, result: data.result, error_code: data.error_code, latency_ms: data.latency_ms }
        : item,
    ),
  };
}
