import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Device, Role, Room, User } from "../types";

interface DirectoryValue {
  users: User[];
  rooms: Room[];
  devices: Device[];
  loading: boolean;
  userName: (userId: string | null | undefined) => string;
  roomName: (roomId: string | null | undefined) => string;
  deviceName: (deviceId: string | null | undefined) => string;
  usersByRole: (role: Role) => User[];
  reload: () => Promise<void>;
  /** 저장·삭제 API가 돌려준 결과를 목록에 바로 반영한다(다시 불러오지 않음). */
  upsertUser: (user: User) => void;
  removeUser: (userId: string) => void;
  upsertRoom: (room: Room) => void;
  removeRoom: (roomId: string) => void;
  upsertDevice: (device: Device) => void;
  removeDevice: (deviceId: string) => void;
  patchDevice: (deviceId: string, changes: Partial<Device>) => void;
}

const DirectoryContext = createContext<DirectoryValue | null>(null);

function upsert<T>(items: T[], item: T, key: (value: T) => string): T[] {
  const id = key(item);
  return items.some((value) => key(value) === id) ? items.map((value) => (key(value) === id ? item : value)) : [...items, item];
}

/** 로그인 사용자가 볼 수 있는 사용자·방·기기 목록을 한 번 불러와 화면 곳곳에서 쓴다. */
export function DirectoryProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const userId = session?.user.user_id;

  const reload = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const [nextUsers, nextRooms, nextDevices] = await Promise.all([api.users.list(), api.rooms.list(), api.devices.list()]);
      setUsers(nextUsers);
      setRooms(nextRooms);
      setDevices(nextDevices);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (!userId) {
      setUsers([]);
      setRooms([]);
      setDevices([]);
      return;
    }
    reload().catch(() => undefined);
  }, [userId, reload]);

  const value = useMemo<DirectoryValue>(() => {
    const userMap = new Map(users.map((user) => [user.user_id, user]));
    const roomMap = new Map(rooms.map((room) => [room.room_id, room]));
    const deviceMap = new Map(devices.map((device) => [device.device_id, device]));
    return {
      users,
      rooms,
      devices,
      loading,
      reload,
      userName: (id) => (id ? (userMap.get(id)?.name ?? id) : "-"),
      roomName: (id) => (id ? (roomMap.get(id)?.name ?? id) : "-"),
      deviceName: (id) => (id ? (deviceMap.get(id)?.name ?? id) : "-"),
      usersByRole: (role) => users.filter((user) => user.role === role),
      upsertUser: (user) => setUsers((current) => upsert(current, user, (item) => item.user_id)),
      removeUser: (id) => setUsers((current) => current.filter((item) => item.user_id !== id)),
      upsertRoom: (room) => setRooms((current) => upsert(current, room, (item) => item.room_id)),
      removeRoom: (id) => setRooms((current) => current.filter((item) => item.room_id !== id)),
      upsertDevice: (device) => setDevices((current) => upsert(current, device, (item) => item.device_id)),
      removeDevice: (id) => setDevices((current) => current.filter((item) => item.device_id !== id)),
      patchDevice: (id, changes) =>
        setDevices((current) => current.map((item) => (item.device_id === id ? { ...item, ...changes } : item))),
    };
  }, [users, rooms, devices, loading, reload]);

  return <DirectoryContext.Provider value={value}>{children}</DirectoryContext.Provider>;
}

export function useDirectory(): DirectoryValue {
  const value = useContext(DirectoryContext);
  if (!value) throw new Error("useDirectory must be used inside DirectoryProvider");
  return value;
}
