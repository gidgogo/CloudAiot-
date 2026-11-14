import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { useSession } from "../auth/AuthContext";
import { useAction } from "../hooks/useAction";
import { useDirectory } from "../hooks/useDirectory";
import { useResource } from "../hooks/useResource";
import type { GestureAction, GestureMapping, Role, User } from "../types";
import { ACTION_LABEL, formatTime, GESTURE_LABEL, ROLE_LABEL, ROLES } from "../utils/format";

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
