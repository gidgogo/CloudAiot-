import { useRef, type MouseEvent } from "react";
import type { Device } from "../types";
import { DEVICE_STATE_LABEL, deviceIcon } from "../utils/format";
import { clamp, round } from "../utils/geometry";

interface RoomMapProps {
  devices: Device[];
  title?: string;
  /** 실시간 device.selected 이벤트로 선택된 기기 */
  highlightedId?: string | null;
  /** 편집 중인 기기 */
  selectedId?: string | null;
  onSelect?: (deviceId: string) => void;
  /** 편집 모드: 배치도를 누르면 그 위치(0~1)를 알려준다. */
  onPick?: (position: { x: number; y: number }) => void;
  /** 편집 중 아직 저장하지 않은 위치 */
  draftPosition?: { x: number; y: number } | null;
}

/** 웹 배치도. map_position(0~1)을 방 평면에 표시한다. 포인팅 판정과는 별개다. */
export function RoomMap({ devices, title, highlightedId, selectedId, onSelect, onPick, draftPosition }: RoomMapProps) {
  const area = useRef<HTMLDivElement>(null);

  const handleClick = (event: MouseEvent<HTMLDivElement>) => {
    if (!onPick || !area.current) return;
    // 아이콘이 가장자리에서 잘리지 않도록 안쪽 영역(area) 기준으로 0~1 좌표를 계산한다.
    const rect = area.current.getBoundingClientRect();
    onPick({
      x: round(clamp((event.clientX - rect.left) / rect.width, 0, 1)),
      y: round(clamp((event.clientY - rect.top) / rect.height, 0, 1)),
    });
  };

  return (
    <figure className="room-map-figure">
      <div
        className={`room-map${onPick ? " editable" : ""}`}
        onClick={handleClick}
        role={onPick ? "button" : undefined}
        aria-label={onPick ? "배치도를 눌러 기기 위치 지정" : `${title ?? "방"} 배치도`}
        tabIndex={onPick ? 0 : undefined}
      >
        {title && <span className="room-map-title">{title}</span>}
        {devices.length === 0 && !draftPosition && <span className="room-map-empty">등록된 기기가 없습니다</span>}
        <div className="room-map-area" ref={area}>
        {devices.map((device) => {
          const classes = [
            "map-device",
            `state-${device.state.toLowerCase()}`,
            device.device_id === highlightedId ? "highlighted" : "",
            device.device_id === selectedId ? "selected" : "",
            device.enabled ? "" : "disabled",
          ].join(" ");
          return (
            <button
              key={device.device_id}
              type="button"
              className={classes}
              style={{ left: `${device.map_position.x * 100}%`, top: `${device.map_position.y * 100}%` }}
              title={`${device.name} · ${DEVICE_STATE_LABEL[device.state]}`}
              onClick={(event) => {
                event.stopPropagation();
                onSelect?.(device.device_id);
              }}
            >
              <span className="map-device-icon" aria-hidden="true">{deviceIcon(device.device_type)}</span>
              <span className="map-device-name">{device.name}</span>
            </button>
          );
        })}
        {draftPosition && (
          <span
            className="map-draft"
            style={{ left: `${draftPosition.x * 100}%`, top: `${draftPosition.y * 100}%` }}
            aria-label="새 위치"
          />
        )}
        </div>
      </div>
      {onPick && <figcaption className="muted">배치도를 눌러 위치를 정합니다. 웹 표시용이며 포인팅 판정에는 쓰지 않습니다.</figcaption>}
    </figure>
  );
}
