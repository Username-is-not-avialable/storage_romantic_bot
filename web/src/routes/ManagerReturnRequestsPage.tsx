import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listAllGear } from "@/api/gear";
import { decideReturnRequest, listManagerReturnRequests } from "@/api/returnRequests";
import type { RentalReturnRequest } from "@/api/types";
import { ApiError } from "@/api/http";
import { RequireAuth, RequireRole } from "@/components/auth/Guards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function ManagerReturnRequestsPage() {
  return (
    <RequireAuth>
      <RequireRole allow={["manager", "admin"]}>
        <ManagerReturnRequestsInner />
      </RequireRole>
    </RequireAuth>
  );
}

function ManagerReturnRequestsInner() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"pending" | "all">("pending");

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ["mgr-return-requests", filter],
    queryFn: () => listManagerReturnRequests(filter === "pending" ? "pending" : undefined),
  });

  const { data: gear = [] } = useQuery({
    queryKey: ["gear-mgr-ret"],
    queryFn: () => listAllGear(),
  });
  const gearNames = useMemo(() => new Map(gear.map((g) => [g.id, g.name])), [gear]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Заявки на возврат</h1>
          <p className="text-muted-foreground mt-1 text-sm">Участник инициировал сдачу по аренде.</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant={filter === "pending" ? "default" : "outline"} onClick={() => setFilter("pending")}>
            Ожидают
          </Button>
          <Button size="sm" variant={filter === "all" ? "default" : "outline"} onClick={() => setFilter("all")}>
            Все
          </Button>
        </div>
      </div>
      {isLoading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
      <div className="space-y-4">
        {requests.map((req) => (
          <ReturnDecisionCard
            key={req.id}
            req={req}
            gearNames={gearNames}
            onDecided={() => void qc.invalidateQueries({ queryKey: ["mgr-return-requests"] })}
          />
        ))}
      </div>
      {!isLoading && requests.length === 0 ? (
        <p className="text-sm text-muted-foreground">Нет заявок в этом фильтре.</p>
      ) : null}
    </div>
  );
}

function ReturnDecisionCard({
  req,
  gearNames,
  onDecided,
}: {
  req: RentalReturnRequest;
  gearNames: Map<number, string>;
  onDecided: () => void;
}) {
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function decide(d: "approve" | "reject") {
    setError(null);
    setBusy(true);
    try {
      await decideReturnRequest(req.id, d, comment.trim() || null);
      onDecided();
      setComment("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  const pending = req.status === "pending";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">#{req.id} · аренда #{req.rental_id}</CardTitle>
        <CardDescription>
          {req.user_full_name}
          {req.target_manager_id ? ` · адресовано менеджеру #${req.target_manager_id}` : ""} · {req.status}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="space-y-1 text-sm">
          {req.items.map((it) => (
            <li key={it.gear_id}>
              {gearNames.get(it.gear_id) ?? `gear #${it.gear_id}`} — сдать {it.qty_return}
            </li>
          ))}
        </ul>
        {pending ? (
          <div className="space-y-2 border-t border-border pt-3">
            <div className="space-y-2">
              <Label htmlFor={`rc-${req.id}`}>Комментарий</Label>
              <Textarea
                id={`rc-${req.id}`}
                rows={2}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={busy} onClick={() => void decide("approve")}>
                Принять и принять физически
              </Button>
              <Button type="button" variant="destructive" disabled={busy} onClick={() => void decide("reject")}>
                Отклонить
              </Button>
            </div>
          </div>
        ) : req.decision_comment ? (
          <p className="text-muted-foreground text-xs">Решение: {req.decision_comment}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
