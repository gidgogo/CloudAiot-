import { type FormEvent, useEffect, useMemo, useState } from "react";
import { api, useDirectory, useResource, useSession } from "../api/client";
import { useAction, useToast } from "../components/HelpRequestList";
import { findOverlaps, isValidRegion, PointingRegionEditor, RoomMap } from "../components/RoomMap";
import {
  ACTION_LABEL,
  type Device,
  DEVICE_TYPES,
  deviceIcon,
  type DeviceInput,
  deviceTypeLabel,
  formatTime,
  GESTURE_LABEL,
  type GestureAction,
  type GestureMapping,
  type Role,
  ROLE_LABEL,
  ROLES,
  type Room,
  type User,
} from "../types";

const ID_PATTERN = "[A-Za-z0-9_\\-]{1,64}";

type DeviceDraft = Omit<DeviceInput, "device_id"> & { device_id: string };

function emptyDraft(roomId: string): DeviceDraft {
  return {
    device_id: "",
    room_id: roomId,
    name: "",
    device_type: "LIGHT",
    map_position: { x: 0.5, y: 0.5 },
    pointing_region: { min_angle_deg: -20, max_angle_deg: 20 },
    enabled: true,
  };
}

function draftFrom(device: Device): DeviceDraft {
  return {
    device_id: device.device_id,
    room_id: device.room_id,
    name: device.name,
    device_type: device.device_type,
    map_position: { ...device.map_position },
    pointing_region: { ...device.pointing_region },
    enabled: device.enabled,
  };
}

function RoomForm({ room, onDone }: { room?: Room; onDone: (room?: Room) => void }) {
  const { usersByRole, upsertRoom } = useDirectory();
  const { run, busy } = useAction();
  const [name, setName] = useState(room?.name ?? "");
  const [roomId, setRoomId] = useState("");
  const [description, setDescription] = useState(room?.description ?? "");
  const [resident, setResident] = useState(room?.resident_user_id ?? "");
  const residents = usersByRole("USER");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const body = { name: name.trim(), description: description.trim() || null, resident_user_id: resident || null };
    let saved: Room | undefined;
    const ok = await run(
      async () => {
        saved = room
          ? await api.rooms.update(room.room_id, body)
          : await api.rooms.create({ ...body, room_id: roomId.trim() || undefined });
        upsertRoom(saved);
      },
      { success: room ? "방 정보를 저장했어요" : "방을 추가했어요", failure: "방을 저장하지 못했어요" },
    );
    if (ok) onDone(saved);
  };

  return (
    <form className="form" onSubmit={submit}>
      {!room && (
        <label>
          방 ID <small className="muted">(비우면 자동 생성)</small>
          <input value={roomId} pattern={ID_PATTERN} placeholder="room-01" onChange={(event) => setRoomId(event.target.value)} />
        </label>
      )}
      <label>
        이름
        <input required maxLength={100} value={name} onChange={(event) => setName(event.target.value)} placeholder="안방" />
      </label>
      <label>
        설명
        <input maxLength={500} value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <label>
        방 사용자 <small className="muted">(HELP 손동작을 이 사용자의 요청으로 기록)</small>
        <select value={resident} onChange={(event) => setResident(event.target.value)}>
          <option value="">지정 안 함</option>
          {residents.map((user) => (
            <option key={user.user_id} value={user.user_id}>
              {user.name} ({user.email})
            </option>
          ))}
        </select>
      </label>
      <div className="row">
        <button type="submit" className="button primary" disabled={busy}>
          {busy ? "저장 중…" : "저장"}
        </button>
        <button type="button" className="button ghost" onClick={() => onDone()}>
          취소
        </button>
      </div>
    </form>
  );
}

export function RoomMappingPage() {
  const { rooms, devices, userName, upsertDevice, removeDevice, removeRoom } = useDirectory();
  const { push } = useToast();
  const { run, busy } = useAction();
  const [roomId, setRoomId] = useState<string | null>(null);
  const [roomMode, setRoomMode] = useState<"view" | "create" | "edit">("view");
  const [draft, setDraft] = useState<DeviceDraft | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);

  useEffect(() => {
    if (rooms.length === 0) setRoomId(null);
    else if (!roomId || !rooms.some((room) => room.room_id === roomId)) setRoomId(rooms[0].room_id);
  }, [rooms, roomId]);

  const room = rooms.find((item) => item.room_id === roomId);
  const roomDevices = useMemo(() => devices.filter((device) => device.room_id === roomId), [devices, roomId]);
  const overlaps = useMemo(() => findOverlaps(devices), [devices]);
  const others = devices.filter((device) => device.device_id !== editingId);

  const startCreate = () => {
    if (!roomId) return;
    setEditingId(null);
    setDraft(emptyDraft(roomId));
  };

  const startEdit = (deviceId: string) => {
    const device = devices.find((item) => item.device_id === deviceId);
    if (!device) return;
    setEditingId(device.device_id);
    setDraft(draftFrom(device));
  };

  const saveDevice = async (event: FormEvent) => {
    event.preventDefault();
    if (!draft) return;
    if (!isValidRegion(draft.pointing_region)) {
      push({ tone: "warning", title: "방향 영역을 확인하세요", message: "-180~180 범위에서 최소 각도가 최대 각도보다 작아야 합니다." });
      return;
    }
    const { device_id, ...fields } = draft;
    const ok = await run(
      async () =>
        upsertDevice(
          editingId
            ? await api.devices.update(editingId, fields)
            : await api.devices.create({ ...fields, device_id: device_id.trim() || undefined }),
        ),
      { success: editingId ? "기기 정보를 저장했어요" : "기기를 추가했어요", failure: "기기를 저장하지 못했어요" },
    );
    if (ok) closeEditor();
  };

  const closeEditor = () => {
    setDraft(null);
    setEditingId(null);
  };

  const deleteDevice = async (device: Device) => {
    if (!window.confirm(`${device.name} 기기를 삭제할까요? 제어 이력도 함께 삭제됩니다.`)) return;
    const ok = await run(
      async () => {
        await api.devices.remove(device.device_id);
        removeDevice(device.device_id);
      },
      { failure: "기기를 삭제하지 못했어요" },
    );
    if (ok && editingId === device.device_id) closeEditor();
  };

  const deleteRoom = async (target: Room) => {
    if (!window.confirm(`${target.name} 방을 삭제할까요?`)) return;
    await run(
      async () => {
        await api.rooms.remove(target.room_id);
        removeRoom(target.room_id);
      },
      { failure: "방을 삭제하지 못했어요" },
    );
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>방·기기 설정</h1>
          <p className="muted">방을 등록하고, 기기의 배치도 위치와 손가락 포인팅 방향 영역을 정합니다.</p>
        </div>
      </div>

      {overlaps.length > 0 && (
        <p className="warning-banner" role="alert">
          ⚠️ 방향 영역이 겹치는 기기가 있습니다:{" "}
          {overlaps.map(([a, b]) => `${a.name}·${b.name}`).join(", ")}. 겹치는 방향을 가리키면 대상을 정하지 못해 명령이 취소됩니다.
        </p>
      )}

      <div className="mapping-layout">
        <aside className="card" aria-labelledby="rooms-title">
          <div className="card-head">
            <h2 id="rooms-title">방</h2>
            <button type="button" className="button small" onClick={() => setRoomMode("create")}>
              + 방 추가
            </button>
          </div>
          {roomMode === "create" && (
            <RoomForm
              onDone={(saved) => {
                setRoomMode("view");
                if (saved) setRoomId(saved.room_id);
              }}
            />
          )}
          {rooms.length === 0 && roomMode !== "create" && <p className="empty">방을 먼저 추가하세요.</p>}
          <ul className="room-list">
            {rooms.map((item) => (
              <li key={item.room_id}>
                <button
                  type="button"
                  className={`room-item${item.room_id === roomId ? " active" : ""}`}
                  onClick={() => {
                    setRoomId(item.room_id);
                    setRoomMode("view");
                    closeEditor();
                  }}
                >
                  <strong>{item.name}</strong>
                  <small className="muted">
                    {item.room_id} · 기기 {devices.filter((device) => device.room_id === item.room_id).length}개
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <div className="mapping-main">
          {room && (
            <section className="card" aria-labelledby="room-detail-title">
              <div className="card-head">
                <h2 id="room-detail-title">{room.name}</h2>
                <div className="row">
                  <button type="button" className="button ghost small" onClick={() => setRoomMode(roomMode === "edit" ? "view" : "edit")}>
                    방 정보 수정
                  </button>
                  <button type="button" className="button ghost small danger-text" onClick={() => void deleteRoom(room)}>
                    방 삭제
                  </button>
                </div>
              </div>
              {roomMode === "edit" ? (
                <RoomForm
                  key={room.room_id}
                  room={room}
                  onDone={() => setRoomMode("view")}
                />
              ) : (
                <p className="muted small">
                  ID {room.room_id} · 방 사용자 {room.resident_user_id ? userName(room.resident_user_id) : "지정 안 함"}
                  {room.description ? ` · ${room.description}` : ""}
                </p>
              )}

              <RoomMap
                devices={roomDevices.filter((device) => device.device_id !== editingId)}
                title={room.name}
                selectedId={editingId}
                onSelect={startEdit}
                onPick={draft ? (position) => setDraft({ ...draft, map_position: position }) : undefined}
                draftPosition={draft?.map_position ?? null}
              />

              <div className="card-head">
                <h3>기기 {roomDevices.length}개</h3>
                <button type="button" className="button primary small" onClick={startCreate}>
                  + 기기 추가
                </button>
              </div>
              {roomDevices.length > 0 && (
                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">기기</th>
                        <th scope="col">ID</th>
                        <th scope="col">방향 영역</th>
                        <th scope="col">사용</th>
                        <th scope="col"><span className="sr-only">관리</span></th>
                      </tr>
                    </thead>
                    <tbody>
                      {roomDevices.map((device) => (
                        <tr key={device.device_id} className={device.device_id === editingId ? "row-active" : undefined}>
                          <td>
                            {deviceIcon(device.device_type)} {device.name}
                            <small className="muted"> {deviceTypeLabel(device.device_type)}</small>
                          </td>
                          <td><code>{device.device_id}</code></td>
                          <td>
                            {device.pointing_region.min_angle_deg}° ~ {device.pointing_region.max_angle_deg}°
                          </td>
                          <td>{device.enabled ? "사용" : "사용 안 함"}</td>
                          <td className="row-actions">
                            <button type="button" className="button ghost small" onClick={() => startEdit(device.device_id)}>
                              수정
                            </button>
                            <button type="button" className="button ghost small danger-text" onClick={() => void deleteDevice(device)}>
                              삭제
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {draft && (
            <section className="card" aria-labelledby="device-form-title">
              <h2 id="device-form-title">{editingId ? `기기 수정 · ${draft.name || editingId}` : "새 기기"}</h2>
              <form className="form device-form" onSubmit={saveDevice}>
                <div className="form-grid">
                  <label>
                    기기 ID {editingId ? "" : <small className="muted">(MQTT Topic의 device_id, 비우면 자동 생성)</small>}
                    <input
                      value={draft.device_id}
                      pattern={ID_PATTERN}
                      placeholder="fan-01"
                      disabled={!!editingId}
                      onChange={(event) => setDraft({ ...draft, device_id: event.target.value })}
                    />
                  </label>
                  <label>
                    이름
                    <input
                      required
                      maxLength={100}
                      value={draft.name}
                      placeholder="선풍기"
                      onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                    />
                  </label>
                  <label>
                    종류
                    <select value={draft.device_type} onChange={(event) => setDraft({ ...draft, device_type: event.target.value })}>
                      {DEVICE_TYPES.map((type) => (
                        <option key={type.value} value={type.value}>
                          {type.icon} {type.label}
                        </option>
                      ))}
                      {!DEVICE_TYPES.some((type) => type.value === draft.device_type) && (
                        <option value={draft.device_type}>{draft.device_type}</option>
                      )}
                    </select>
                  </label>
                  <label>
                    방
                    <select value={draft.room_id} onChange={(event) => setDraft({ ...draft, room_id: event.target.value })}>
                      {rooms.map((item) => (
                        <option key={item.room_id} value={item.room_id}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    배치도 X
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={draft.map_position.x}
                      onChange={(event) => setDraft({ ...draft, map_position: { ...draft.map_position, x: Number(event.target.value) } })}
                    />
                  </label>
                  <label>
                    배치도 Y
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={draft.map_position.y}
                      onChange={(event) => setDraft({ ...draft, map_position: { ...draft.map_position, y: Number(event.target.value) } })}
                    />
                  </label>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={draft.enabled}
                      onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
                    />
                    포인팅 대상으로 사용
                  </label>
                </div>

                <fieldset>
                  <legend>포인팅 방향 영역</legend>
                  <PointingRegionEditor
                    others={others}
                    region={draft.pointing_region}
                    label={draft.name || "이 기기"}
                    onChange={(region) => setDraft({ ...draft, pointing_region: region })}
                  />
                </fieldset>

                <div className="row">
                  <button type="submit" className="button primary" disabled={busy}>
                    {busy ? "저장 중…" : "저장"}
                  </button>
                  <button type="button" className="button ghost" onClick={closeEditor}>
                    취소
                  </button>
                </div>
              </form>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- AdminPage ----

function CreateUserForm() {
  const { upsertUser } = useDirectory();
  const { run, busy } = useAction();
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "USER" as Role });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const ok = await run(async () => upsertUser(await api.users.create(form)), {
      success: `${form.name} 계정을 만들었어요`,
      failure: "계정을 만들지 못했어요",
    });
    if (ok) setForm({ name: "", email: "", password: "", role: form.role });
  };

  return (
    <form className="form inline-form" onSubmit={submit} aria-label="새 계정">
      <label>
        이름
        <input required maxLength={100} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
      </label>
      <label>
        이메일
        <input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
      </label>
      <label>
        초기 비밀번호
        <input
          required
          type="password"
          minLength={8}
          maxLength={72}
          autoComplete="new-password"
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />
      </label>
      <label>
        역할
        <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as Role })}>
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABEL[role]}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="button primary" disabled={busy}>
        {busy ? "만드는 중…" : "계정 만들기"}
      </button>
    </form>
  );
}

function UsersSection() {
  const session = useSession();
  const { users, upsertUser, removeUser } = useDirectory();
  const { run } = useAction();
  const failure = "처리하지 못했어요";

  const resetPassword = (user: User) => {
    const password = window.prompt(`${user.name}의 새 비밀번호(8자 이상)`);
    if (!password) return;
    void run(() => api.users.update(user.user_id, { password }), { success: "비밀번호를 바꿨어요", failure });
  };

  return (
    <section className="card" aria-labelledby="users-title">
      <h2 id="users-title">사용자 계정</h2>
      <CreateUserForm />
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">이름</th>
              <th scope="col">이메일</th>
              <th scope="col">역할</th>
              <th scope="col">만든 날</th>
              <th scope="col"><span className="sr-only">관리</span></th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const self = user.user_id === session.user.user_id;
              return (
                <tr key={user.user_id}>
                  <td>
                    {user.name}
                    {self && <span className="badge muted">나</span>}
                  </td>
                  <td>{user.email}</td>
                  <td>
                    <select
                      aria-label={`${user.name} 역할`}
                      value={user.role}
                      disabled={self}
                      onChange={(event) => {
                        const role = event.target.value as Role;
                        if (window.confirm(`${user.name}의 역할을 ${ROLE_LABEL[role]}(으)로 바꿀까요? 보호자 연결은 해제됩니다.`)) {
                          void run(async () => upsertUser(await api.users.update(user.user_id, { role })), {
                            success: "역할을 바꿨어요",
                            failure,
                          });
                        }
                      }}
                    >
                      {ROLES.map((role) => (
                        <option key={role} value={role}>
                          {ROLE_LABEL[role]}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>{formatTime(user.created_at_ms)}</td>
                  <td className="row-actions">
                    <button type="button" className="button ghost small" onClick={() => resetPassword(user)}>
                      비밀번호 재설정
                    </button>
                    <button
                      type="button"
                      className="button ghost small danger-text"
                      disabled={self}
                      onClick={() => {
                        if (window.confirm(`${user.name} 계정을 삭제할까요? 도움 요청 기록도 삭제됩니다.`)) {
                          void run(
                            async () => {
                              await api.users.remove(user.user_id);
                              removeUser(user.user_id);
                            },
                            { success: "계정을 삭제했어요", failure },
                          );
                        }
                      }}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LinksSection() {
  const { users, usersByRole, userName } = useDirectory();
  const { run } = useAction();
  // 계정이 지워지거나 역할이 바뀌면 서버가 연결을 정리하므로 그때만 다시 불러온다.
  const accountsKey = users.map((user) => `${user.user_id}:${user.role}`).join(",");
  const links = useResource(() => api.guardianLinks.list(), [accountsKey]);
  const [guardianId, setGuardianId] = useState("");
  const [userId, setUserId] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await run(
      async () => {
        const link = await api.guardianLinks.create(guardianId, userId);
        links.setData((current = []) =>
          current.some((item) => item.guardian_id === link.guardian_id && item.user_id === link.user_id) ? current : [...current, link],
        );
      },
      { success: `${userName(guardianId)} ↔ ${userName(userId)} 연결했어요`, failure: "연결하지 못했어요" },
    );
  };

  const unlink = (guardian: string, user: string) =>
    run(
      async () => {
        await api.guardianLinks.remove(guardian, user);
        links.setData((current = []) => current.filter((item) => !(item.guardian_id === guardian && item.user_id === user)));
      },
      { failure: "연결을 해제하지 못했어요" },
    );

  return (
    <section className="card" aria-labelledby="links-title">
      <h2 id="links-title">보호자 연결</h2>
      <p className="muted small">보호자는 연결된 사용자의 도움 요청만 받고 처리할 수 있습니다.</p>
      <form className="form inline-form" onSubmit={submit}>
        <label>
          보호자
          <select required value={guardianId} onChange={(event) => setGuardianId(event.target.value)}>
            <option value="">선택</option>
            {usersByRole("GUARDIAN").map((user) => (
              <option key={user.user_id} value={user.user_id}>
                {user.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          사용자
          <select required value={userId} onChange={(event) => setUserId(event.target.value)}>
            <option value="">선택</option>
            {usersByRole("USER").map((user) => (
              <option key={user.user_id} value={user.user_id}>
                {user.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="button primary" disabled={!guardianId || !userId}>
          연결
        </button>
      </form>
      {links.error && <p className="error-text">{links.error}</p>}
      {(links.data ?? []).length === 0 ? (
        <p className="empty">연결된 보호자가 없습니다.</p>
      ) : (
        <ul className="link-list">
          {(links.data ?? []).map((link) => (
            <li key={`${link.guardian_id}-${link.user_id}`}>
              <span>
                <strong>{userName(link.guardian_id)}</strong> → {userName(link.user_id)}
              </span>
              <button type="button" className="button ghost small danger-text" onClick={() => void unlink(link.guardian_id, link.user_id)}>
                해제
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MappingsSection() {
  const { run } = useAction();
  const mappings = useResource(() => api.gestureMappings.list(), []);

  const update = async (mapping: GestureMapping, changes: { action?: GestureAction; enabled?: boolean }) => {
    const ok = await run(
      async () => {
        const saved = await api.gestureMappings.update(mapping.gesture, changes);
        mappings.setData((current = []) => current.map((item) => (item.gesture === saved.gesture ? saved : item)));
      },
      { failure: "매핑을 바꾸지 못했어요" },
    );
    if (!ok) await mappings.reload();
  };

  return (
    <section className="card" aria-labelledby="mapping-title">
      <h2 id="mapping-title">제스처·명령 매핑</h2>
      <p className="muted small">
        검지 포인팅으로 기기를 고른 뒤 아래 제스처를 유지하면 연결된 명령이 실행됩니다. 같은 명령을 두 제스처에 연결할 수 없습니다.
      </p>
      {mappings.error && <p className="error-text">{mappings.error}</p>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">제스처</th>
              <th scope="col">명령</th>
              <th scope="col">사용</th>
            </tr>
          </thead>
          <tbody>
            {(mappings.data ?? []).map((mapping) => (
              <tr key={mapping.gesture}>
                <td>{GESTURE_LABEL[mapping.gesture] ?? mapping.gesture}</td>
                <td>
                  <select
                    aria-label={`${mapping.gesture} 명령`}
                    value={mapping.action}
                    onChange={(event) => void update(mapping, { action: event.target.value as GestureAction })}
                  >
                    {(Object.keys(ACTION_LABEL) as GestureAction[]).map((action) => (
                      <option key={action} value={action}>
                        {ACTION_LABEL[action]}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={mapping.enabled}
                      onChange={(event) => void update(mapping, { enabled: event.target.checked })}
                    />
                    <span>{mapping.enabled ? "사용" : "사용 안 함"}</span>
                  </label>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function AdminPage() {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>사용자·매핑 관리</h1>
          <p className="muted">계정, 보호자 연결, 제스처와 명령의 연결을 관리합니다.</p>
        </div>
      </div>
      <UsersSection />
      <div className="grid-2">
        <LinksSection />
        <MappingsSection />
      </div>
    </div>
  );
}
