import { useQuery } from "@tanstack/react-query";

import { fetchMeOptional } from "@/api/auth";

export const ME_QUERY_KEY = ["me"] as const;

export function useMe() {
  return useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: fetchMeOptional,
    staleTime: 60_000,
  });
}
