import { apiJson } from "@/api/http";
import type { RentalReturnRequest, RentalReturnRequestsList } from "@/api/types";

export async function createReturnRequest(body: {
  rental_id: number;
  target_manager_id?: number | null;
  items: { gear_id: number; qty_return: number }[];
}): Promise<RentalReturnRequest> {
  return apiJson<RentalReturnRequest>("/api/rental-return-requests/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listMyReturnRequests(status?: string): Promise<RentalReturnRequest[]> {
  const sp = new URLSearchParams();
  if (status) sp.set("status", status);
  const qs = sp.toString();
  const path = qs ? `/api/rental-return-requests/?${qs}` : "/api/rental-return-requests/";
  const data = await apiJson<RentalReturnRequestsList>(path);
  return data.requests;
}

export async function listManagerReturnRequests(status?: string): Promise<RentalReturnRequest[]> {
  const sp = new URLSearchParams();
  if (status) sp.set("status", status);
  const qs = sp.toString();
  const path = qs ? `/api/manager/rental-return-requests/?${qs}` : "/api/manager/rental-return-requests/";
  const data = await apiJson<RentalReturnRequestsList>(path);
  return data.requests;
}

export async function decideReturnRequest(
  id: number,
  decision: "approve" | "reject",
  comment: string | null,
): Promise<RentalReturnRequest> {
  return apiJson<RentalReturnRequest>(`/api/manager/rental-return-requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ decision, comment }),
  });
}
