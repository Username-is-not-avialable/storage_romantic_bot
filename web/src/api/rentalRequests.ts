import { apiJson } from "@/api/http";
import type { RentalRequest, RentalRequestsList } from "@/api/types";

export async function createRentalRequest(body: {
  due_date: string;
  event: string;
  comment?: string | null;
  deposit_document?: string | null;
  target_manager_id: number;
  items: { gear_id: number; qty_requested: number }[];
}): Promise<RentalRequest> {
  return apiJson<RentalRequest>("/api/rental-requests/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listMyRentalRequests(status?: string): Promise<RentalRequest[]> {
  const sp = new URLSearchParams();
  if (status) sp.set("status", status);
  const qs = sp.toString();
  const path = qs ? `/api/rental-requests/?${qs}` : "/api/rental-requests/";
  const data = await apiJson<RentalRequestsList>(path);
  return data.requests;
}

export async function listManagerRentalRequests(status?: string): Promise<RentalRequest[]> {
  const sp = new URLSearchParams();
  if (status) sp.set("status", status);
  const qs = sp.toString();
  const path = qs ? `/api/manager/rental-requests/?${qs}` : "/api/manager/rental-requests/";
  const data = await apiJson<RentalRequestsList>(path);
  return data.requests;
}

export async function decideRentalRequest(
  id: number,
  decision: "approve" | "reject",
  comment: string | null,
): Promise<RentalRequest> {
  return apiJson<RentalRequest>(`/api/manager/rental-requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ decision, comment }),
  });
}
