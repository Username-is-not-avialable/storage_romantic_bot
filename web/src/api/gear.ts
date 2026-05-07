import { apiJson } from "@/api/http";
import type { GearItem, GearSearchResponse } from "@/api/types";

/** Максимум `limit` по контракту GET /api/gear/ */
const GEAR_PAGE_LIMIT = 100;

export async function listGear(params: {
  query?: string;
  page?: number;
  limit?: number;
}): Promise<GearItem[]> {
  const sp = new URLSearchParams();
  if (params.query !== undefined && params.query !== "") {
    sp.set("query", params.query);
  }
  if (params.page !== undefined) sp.set("page", String(params.page));
  if (params.limit !== undefined) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  const path = qs ? `/api/gear/?${qs}` : "/api/gear/";
  const data = await apiJson<GearSearchResponse>(path);
  return data.items;
}

/** Весь каталог пачками по 100 (для подстановки имён и полных выпадающих списков). */
export async function listAllGear(): Promise<GearItem[]> {
  const all: GearItem[] = [];
  let page = 1;
  for (;;) {
    const batch = await listGear({ page, limit: GEAR_PAGE_LIMIT });
    all.push(...batch);
    if (batch.length < GEAR_PAGE_LIMIT) break;
    page += 1;
  }
  return all;
}

export async function getGear(id: number): Promise<GearItem> {
  return apiJson<GearItem>(`/api/gear/${id}`);
}
