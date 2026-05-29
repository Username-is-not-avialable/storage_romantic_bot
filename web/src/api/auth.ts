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

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  phone: string;
  document: string | null;
}

export async function register(payload: RegisterPayload): Promise<void> {
  await apiJson("/api/users/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function requestRegistrationCode(email: string): Promise<void> {
  await apiJson<{ message: string }>("/api/auth/request-code", {
    method: "POST",
    body: JSON.stringify({ email, purpose: "email_verify" }),
  });
}

export async function verifyRegistrationCode(email: string, code: string): Promise<void> {
  await apiJson<{ message: string }>("/api/auth/verify-code", {
    method: "POST",
    body: JSON.stringify({ email, purpose: "email_verify", code }),
  });
}

export interface VkLinkCodeResponse {
  code: string;
  expires_at: string;
}

export async function requestVkLinkCode(): Promise<VkLinkCodeResponse> {
  return apiJson<VkLinkCodeResponse>("/api/auth/vk-link/request_code", { method: "POST" });
}
