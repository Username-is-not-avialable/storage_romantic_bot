import { apiJson } from "@/api/http";

export interface ManagerPublicRef {
  id: number;
  full_name: string;
}

export async function listManagers(): Promise<ManagerPublicRef[]> {
  const data = await apiJson<{ managers: ManagerPublicRef[] }>("/api/users/managers");
  return data.managers;
}
