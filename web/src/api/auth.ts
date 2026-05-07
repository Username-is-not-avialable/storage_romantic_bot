import { apiFetch, apiJson } from "@/api/http";
import type { MeUser } from "@/api/types";

export async function login(email: string, password: string): Promise<void> {
  await apiJson<{ message: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function logout(): Promise<void> {
  await apiJson<{ message: string }>("/api/auth/logout", { method: "POST" });
}

export async function fetchMe(): Promise<MeUser> {
  return apiJson<MeUser>("/api/auth/me");
}

export async function fetchMeOptional(): Promise<MeUser | null> {
  const res = await apiFetch("/api/auth/me");
  if (res.status === 401) {
    return null;
  }
  if (!res.ok) {
    return null;
  }
  return (await res.json()) as MeUser;
}
