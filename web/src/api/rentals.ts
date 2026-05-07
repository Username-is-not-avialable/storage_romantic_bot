import { apiJson } from "@/api/http";
import type { Rental, RentalsList } from "@/api/types";

export async function listActiveRentals(userId?: number | null): Promise<Rental[]> {
  const sp = new URLSearchParams();
  if (userId != null) sp.set("user_id", String(userId));
  const qs = sp.toString();
  const path = qs ? `/api/rentals/active?${qs}` : "/api/rentals/active";
  const data = await apiJson<RentalsList>(path);
  return data.rentals;
}

export async function listDebtors(): Promise<Rental[]> {
  const data = await apiJson<RentalsList>("/api/rentals/debtors");
  return data.rentals;
}

export async function issueRental(body: {
  user_id: number;
  issue_manager_id: number;
  due_date: string;
  event: string;
  comment?: string | null;
  items: { gear_id: number; qty: number }[];
}): Promise<Rental> {
  return apiJson<Rental>("/api/rentals/issue", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function returnRental(
  rentalId: number,
  body: {
    manager_id: number;
    items: { gear_id: number; quantity: number }[];
    comment?: string | null;
    fee_status_snapshot?: string | null;
  },
): Promise<Rental> {
  return apiJson<Rental>(`/api/rentals/${rentalId}/return`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
