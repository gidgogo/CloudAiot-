import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useSession } from "../auth/AuthContext";
import { useDirectory } from "../hooks/useDirectory";
import { useRealtimeEvent, useRealtimeStatus } from "../realtime/RealtimeContext";
import { canWatchHelp } from "../utils/permissions";
import { useToast } from "./Toasts";

const BASE_TITLE = "CloudAIoT 대시보드";

function beep(): void {
  try {
    const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const context = new AudioCtx();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = 880;
    gain.gain.setValueAtTime(0.15, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.6);
    oscillator.connect(gain).connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.6);
    oscillator.onended = () => void context.close();
  } catch {
    // 브라우저가 소리 재생을 막으면 무시한다.
  }
}

/**
 * 보호자·관리자에게 새 도움 요청을 즉시 알린다.
 * 화면 알림(닫을 때까지 유지), 소리, 브라우저 알림(허용한 경우), 탭 제목의 대기 건수.
 * 대기 건수는 접속·재접속할 때만 서버에서 받고, 그 사이에는 이벤트로 더하고 뺀다.
 */
export function HelpAlerts() {
  const session = useSession();
  const { userName } = useDirectory();
  const { status } = useRealtimeStatus();
  const { push } = useToast();
  const navigate = useNavigate();
  const [openCount, setOpenCount] = useState(0);
  const watching = canWatchHelp(session.user.role);
  const connected = status === "open";

  useEffect(() => {
    if (!watching || !connected) return;
    api.helpRequests
      .list({ status: "CREATED", limit: 1 })
      .then((page) => setOpenCount(page.meta.total))
      .catch(() => undefined);
  }, [watching, connected, session.user.user_id]);

  useEffect(() => {
    document.title = openCount > 0 ? `(${openCount}) 도움 요청 · ${BASE_TITLE}` : BASE_TITLE;
    return () => {
      document.title = BASE_TITLE;
    };
  }, [openCount]);

  useRealtimeEvent(["help.created", "help.updated"], (event) => {
    if (!watching) return;
    if (event.event_type === "help.updated") {
      // 확인 대기에서 벗어나는 변화는 CREATED → CONFIRMED 뿐이다.
      if (event.data.status === "CONFIRMED") setOpenCount((count) => Math.max(0, count - 1));
      return;
    }
    setOpenCount((count) => count + 1);
    const name = userName(event.data.user_id);
    push({
      tone: "danger",
      title: `🚨 ${name}님이 도움을 요청했습니다`,
      message: "도움 요청 화면에서 확인해 주세요.",
      sticky: true,
      action: { label: "확인하러 가기", onClick: () => navigate("/help") },
    });
    beep();
    if ("Notification" in window && Notification.permission === "granted") {
      try {
        new Notification("도움 요청", { body: `${name}님이 도움을 요청했습니다.`, tag: event.data.request_id });
      } catch {
        // 일부 브라우저는 페이지에서 직접 알림을 만들 수 없다.
      }
    }
  });

  return null;
}
