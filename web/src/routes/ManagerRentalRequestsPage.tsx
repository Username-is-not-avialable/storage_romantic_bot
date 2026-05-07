import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listAllGear } from "@/api/gear";
import { decideRentalRequest, listManagerRentalRequests } from "@/api/rentalRequests";
import type { RentalRequest } from "@/api/types";
import { ApiError } from "@/api/http";
import { RequireAuth, RequireRole } from "@/components/auth/Guards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

export function ManagerRentalRequestsPage() {
  return (
    <RequireAuth>
      <RequireRole allow={["manager", "admin"]}>
        <ManagerRentalRequestsInner />
      </RequireRole>
    </RequireAuth>
  );
}

function ManagerRentalRequestsInner() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"pending" | "all">("pending");

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ["mgr-rental-requests", filter],
    queryFn: () => listManagerRentalRequests(filter === "pending" ? "pending" : undefined),
  });

  const { data: gear = [] } = useQuery({
    queryKey: ["gear-mgr"],
    queryFn: () => listAllGear(),
  });
  const gearNames = useMemo(() => new Map(gear.map((g) => [g.id, g.name])), [gear]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Заявки на выдачу</h1>
          <p className="text-muted-foreground mt-1 text-sm">Очередь на решение завснара.</p>
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
          <DecisionCard
            key={req.id}
            req={req}
            gearNames={gearNames}
            onDecided={() => {
              void qc.invalidateQueries({ queryKey: ["mgr-rental-requests"] });
            }}
          />
        ))}
      </div>
      {!isLoading && requests.length === 0 ? (
        <p className="text-sm text-muted-foreground">Нет заявок в этом фильтре.</p>
      ) : null}
    </div>
  );
}

function DecisionCard({
  req,
  gearNames,
  onDecided,
}: {
  req: RentalRequest;
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
      await decideRentalRequest(req.id, d, comment.trim() || null);
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
        <CardTitle className="text-base">
          #{req.id} · {req.event}
        </CardTitle>
        <CardDescription>
          {req.user_full_name} · срок {req.due_date} · статус {req.status}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="space-y-1 text-sm">
          {req.items.map((it) => (
            <li key={it.gear_id}>
              {gearNames.get(it.gear_id) ?? `gear #${it.gear_id}`} × {it.qty_requested}
            </li>
          ))}
        </ul>
        {req.comment ? <p className="text-muted-foreground text-xs">Комментарий: {req.comment}</p> : null}
        {req.deposit_document ? (
          <p className="text-muted-foreground text-xs">Залог: {req.deposit_document}</p>
        ) : null}
        {pending ? (
          <div className="space-y-2 border-t border-border pt-3">
            <div className="space-y-2">
              <Label htmlFor={`c-${req.id}`}>Комментарий к решению</Label>
              <Textarea
                id={`c-${req.id}`}
                rows={2}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={busy} onClick={() => void decide("approve")}>
                Принять
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
