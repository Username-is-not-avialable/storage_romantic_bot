import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listAllGear } from "@/api/gear";
import { listActiveRentals } from "@/api/rentals";
import { listMyRentalRequests } from "@/api/rentalRequests";
import { listMyReturnRequests } from "@/api/returnRequests";
import { useMe } from "@/auth/useMe";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RequireAuth } from "@/components/auth/Guards";

export function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardInner />
    </RequireAuth>
  );
}

function DashboardInner() {
  const { data: me } = useMe();

  const rentalsQ = useQuery({
    queryKey: ["active-rentals", "mine", me?.id],
    queryFn: () => listActiveRentals(me!.id),
    enabled: Boolean(me),
  });

  const reqQ = useQuery({
    queryKey: ["my-rental-requests"],
    queryFn: () => listMyRentalRequests(),
    enabled: Boolean(me),
  });

  const retQ = useQuery({
    queryKey: ["my-return-requests"],
    queryFn: () => listMyReturnRequests(),
    enabled: Boolean(me),
  });

  const { data: gearItems = [] } = useQuery({
    queryKey: ["gear-dashboard-names"],
    queryFn: () => listAllGear(),
    enabled: Boolean(me),
  });
  const gearNames = useMemo(() => new Map(gearItems.map((g) => [g.id, g.name])), [gearItems]);

  if (!me) return null;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Мой склад</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            {me.full_name} · {me.email}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link to="/requests/new">Новая заявка на выдачу</Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link to="/me/return-requests/new">Заявка на возврат</Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Мои активные аренды</CardTitle>
          <CardDescription>Текущие выдачи со списком позиций и остатком к возврату.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {rentalsQ.isLoading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
          {rentalsQ.data?.length === 0 ? (
            <p className="text-sm text-muted-foreground">Нет активных аренд.</p>
          ) : null}
          {rentalsQ.data?.map((r) => (
            <div key={r.id} className="rounded-lg border border-border p-3 text-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-medium">
                  #{r.id} · {r.event}
                </span>
                <span className="text-muted-foreground text-xs">
                  срок: {r.due_date} · статус: {r.status}
                </span>
              </div>
              <ul className="mt-2 space-y-1 text-xs">
                {r.items.map((it) => (
                  <li key={it.gear_id}>
                    {it.gear_name} — выдано {it.qty_issued}, осталось {it.qty_outstanding}
                  </li>
                ))}
              </ul>
              <Button asChild size="sm" variant="outline" className="mt-3">
                <Link to={`/me/return-requests/new?rental_id=${r.id}`}>Сдать по этой аренде</Link>
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Мои заявки на выдачу</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {reqQ.isLoading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
          {reqQ.data?.length === 0 ? <p className="text-sm text-muted-foreground">Заявок пока нет.</p> : null}
          {reqQ.data?.map((req) => (
            <div key={req.id} className="rounded-lg border border-border p-3 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">#{req.id} · {req.event}</span>
                <span className="text-muted-foreground text-xs">{req.status}</span>
              </div>
              <p className="text-muted-foreground mt-1 text-xs">Сдать до: {req.due_date}</p>
              <ul className="mt-2 space-y-1 text-xs">
                {req.items.map((it) => (
                  <li key={it.gear_id}>
                    {gearNames.get(it.gear_id) ?? `gear #${it.gear_id}`} × {it.qty_requested}
                  </li>
                ))}
              </ul>
              {req.decision_comment ? (
                <p className="text-muted-foreground mt-2 text-xs">Комментарий: {req.decision_comment}</p>
              ) : null}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Мои заявки на возврат</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {retQ.isLoading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
          {retQ.data?.length === 0 ? <p className="text-sm text-muted-foreground">Заявок пока нет.</p> : null}
          {retQ.data?.map((rr) => (
            <div key={rr.id} className="rounded-lg border border-border p-3 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <span className="font-medium">
                  #{rr.id} · аренда #{rr.rental_id}
                </span>
                <span className="text-muted-foreground text-xs">{rr.status}</span>
              </div>
              <ul className="mt-2 space-y-1 text-xs">
                {rr.items.map((it) => (
                  <li key={it.gear_id}>
                    {gearNames.get(it.gear_id) ?? `gear #${it.gear_id}`} — сдать {it.qty_return}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
