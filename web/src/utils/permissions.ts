import type { HelpRequest, Role, Session } from "../types";

/**
 * 화면에서 쓰는 권한 판단. 서버(server/security/permissions.py)와 같은 규칙이며,
 * 최종 판단은 서버가 한다. 화면은 버튼·메뉴를 보일지만 정한다.
 */

/** 도움 요청을 받아 처리하는 역할(실시간 알림 대상) */
export function canWatchHelp(role: Role): boolean {
  return role === "GUARDIAN" || role === "ADMIN";
}

export function canChangeHelpStatus(session: Session, request: HelpRequest): boolean {
  if (session.user.role === "ADMIN") return true;
  return session.user.role === "GUARDIAN" && session.linked_user_ids.includes(request.user_id);
}

export function hasAnyRole(role: Role, roles?: readonly Role[]): boolean {
  return !roles || roles.includes(role);
}
