import { apiJson } from "@/api/http";
import type { AdminUser } from "@/api/types";

export async function listAdminUsers(name?: string): Promise<AdminUser[]> {
  const sp = new URLSearchParams();
  if (name?.trim()) sp.set("name", name.trim());
  const qs = sp.toString();
  const path = qs ? `/api/admin/users?${qs}` : "/api/admin/users";
  const data = await apiJson<{ users: AdminUser[] }>(path);
  return data.users;
}
