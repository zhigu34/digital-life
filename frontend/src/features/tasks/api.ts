import { api } from "../../api";
import type { GroupItem, RepeatUnit, TaskCompletion, TaskGroup } from "../../types";

export interface ItemPayload {
  title: string;
  repeat_unit: RepeatUnit;
  start_date?: string;
}

export interface GroupPayload {
  title: string;
  notes?: string;
  items: ItemPayload[];
}

export const listGroups = () => api<TaskGroup[]>("/groups");

export const getGroup = (id: number) => api<TaskGroup>(`/groups/${id}`);

export const createGroup = (payload: GroupPayload) =>
  api<TaskGroup>("/groups", "POST", payload);

export const updateGroup = (id: number, payload: Record<string, unknown>) =>
  api<TaskGroup>(`/groups/${id}`, "PATCH", payload);

export const deleteGroup = (id: number) => api<void>(`/groups/${id}`, "DELETE");

export const createItem = (groupId: number, payload: ItemPayload) =>
  api<GroupItem>(`/groups/${groupId}/items`, "POST", payload);

export const updateItem = (groupId: number, itemId: number, payload: Record<string, unknown>) =>
  api<GroupItem>(`/groups/${groupId}/items/${itemId}`, "PATCH", payload);

export const deleteItem = (groupId: number, itemId: number) =>
  api<void>(`/groups/${groupId}/items/${itemId}`, "DELETE");

/** Records one completion; any completion inside the period satisfies it. */
export const checkItem = (groupId: number, itemId: number, payload: Record<string, unknown>) =>
  api<GroupItem>(`/groups/${groupId}/items/${itemId}/complete`, "POST", payload);

export const undoCompletion = (groupId: number, itemId: number, on: string) =>
  api<void>(`/groups/${groupId}/items/${itemId}/complete/${on}`, "DELETE");

export const listCompletions = (groupId: number, itemId: number, start: string, end: string) =>
  api<TaskCompletion[]>(
    `/groups/${groupId}/items/${itemId}/completions?start=${start}&end=${end}`,
  );
