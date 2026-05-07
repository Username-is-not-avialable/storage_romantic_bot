import { useMemo, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { listAllGear } from "@/api/gear";
import { issueRental, listActiveRentals, listDebtors, returnRental } from "@/api/rentals";
import { ApiError } from "@/api/http";
import { RequireAuth, RequireRole } from "@/components/auth/Guards";
import { useMe } from "@/auth/useMe";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type Tab = "active" | "debtors" | "issue" | "return";

export function ManagerRentalsPage() {
  return (
    <RequireAuth>
      <RequireRole allow={["manager", "admin"]}>
        <ManagerRentalsInner />
      </RequireRole>
    </RequireAuth>
  );
}

function ManagerRentalsInner() {
  const { data: me } = useMe();
  const [tab, setTab] = useState<Tab>("active");

  const activeQ = useQuery({
    queryKey: ["mgr-rentals-active"],
    queryFn: () => listActiveRentals(),
    enabled: tab === "active" || tab === "return",
  });
  const debtQ = useQuery({
    queryKey: ["mgr-rentals-debtors"],
    queryFn: () => listDebtors(),
    enabled: tab === "debtors",
  });

  const qc = useQueryClient();
  const invalidateRentals = () => {
    void qc.invalidateQueries({ queryKey: ["mgr-rentals-active"] });
    void qc.invalidateQueries({ queryKey: ["mgr-rentals-debtors"] });
  };

  const rentalsForReturn = activeQ.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Аренды</h1>
        <p className="text-muted-foreground mt-1 text-sm">Активные выдачи, должники, ручная выдача и приём.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["active", "Активные"],
            ["debtors", "Должники"],
            ["issue", "Выдача"],
            ["return", "Приём"],
          ] as const
        ).map(([k, label]) => (
          <Button
            key={k}
            size="sm"
            variant={tab === k ? "default" : "outline"}
            onClick={() => setTab(k)}
          >
            {label}
          </Button>
        ))}
      </div>

      {tab === "active" ? (
        <RentalsListCard
          title="Активные аренды"
          description="Все текущие выдачи (вид завснара)."
          loading={activeQ.isLoading}
          rentals={activeQ.data ?? []}
        />
      ) : null}

      {tab === "debtors" ? (
        <RentalsListCard
          title="Просрочки"
          description="Активные аренды с истекшим сроком."
          loading={debtQ.isLoading}
          rentals={debtQ.data ?? []}
        />
      ) : null}

      {tab === "issue" && me ? (
        <IssueForm managerId={me.id} onSuccess={invalidateRentals} />
      ) : null}

      {tab === "return" && me ? (
        <ReturnForm
          managerId={me.id}
          rentals={rentalsForReturn}
          loading={activeQ.isLoading}
          onSuccess={invalidateRentals}
        />
      ) : null}
    </div>
  );
}

function RentalsListCard({
  title,
  description,
  loading,
  rentals,
}: {
  title: string;
  description: string;
  loading: boolean;
  rentals: Awaited<ReturnType<typeof listActiveRentals>>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
        {!loading && rentals.length === 0 ? (
          <p className="text-sm text-muted-foreground">Пусто.</p>
        ) : null}
        {rentals.map((r) => (
          <div key={r.id} className="rounded-lg border border-border p-3 text-sm">
            <div className="flex flex-wrap justify-between gap-2">
              <span className="font-medium">
                #{r.id} · {r.event}
              </span>
              <span className="text-muted-foreground text-xs">
                {r.user_full_name} · до {r.due_date}
              </span>
            </div>
            <ul className="mt-2 space-y-1 text-xs">
              {r.items.map((it) => (
                <li key={it.gear_id}>
                  {it.gear_name}: выдано {it.qty_issued}, осталось {it.qty_outstanding}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function IssueForm({ managerId, onSuccess }: { managerId: number; onSuccess: () => void }) {
  const { data: gearItems = [] } = useQuery({
    queryKey: ["gear-issue"],
    queryFn: () => listAllGear(),
  });
  const gearMap = useMemo(() => new Map(gearItems.map((g) => [g.id, g])), [gearItems]);

  const [userId, setUserId] = useState("");
  const [due, setDue] = useState("");
  const [event, setEvent] = useState("");
  const [comment, setComment] = useState("");
  const [lines, setLines] = useState<{ gear_id: number; qty: number }[]>([]);
  const [pick, setPick] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function addLine() {
    const gid = Number(pick);
    if (!gid || lines.some((l) => l.gear_id === gid)) return;
    setLines((ls) => [...ls, { gear_id: gid, qty: 1 }]);
    setPick("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const uid = Number(userId);
    if (!uid || !due || !event.trim() || lines.length === 0) {
      setError("Заполните участника, срок, мероприятие и позиции");
      return;
    }
    setBusy(true);
    try {
      await issueRental({
        user_id: uid,
        issue_manager_id: managerId,
        due_date: due,
        event: event.trim(),
        comment: comment.trim() || null,
        items: lines,
      });
      onSuccess();
      setUserId("");
      setDue("");
      setEvent("");
      setComment("");
      setLines([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка выдачи");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Ручная выдача</CardTitle>
        <CardDescription>Создаёт аренду, минуя этап создания заявки.</CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="uid">Участник (users.id)</Label>
              <Input id="uid" value={userId} onChange={(e) => setUserId(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="due2">Срок возврата</Label>
              <Input id="due2" type="date" value={due} onChange={(e) => setDue(e.target.value)} required />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="ev2">Мероприятие</Label>
            <Input id="ev2" value={event} onChange={(e) => setEvent(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="cm2">Комментарий</Label>
            <Textarea id="cm2" rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
          <div className="space-y-2 rounded-lg border border-border p-3">
            <p className="text-sm font-medium">Позиции</p>
            <ul className="space-y-2 text-sm">
              {lines.map((l, idx) => (
                <li key={l.gear_id} className="flex flex-wrap items-center gap-2">
                  <span className="flex-1 truncate">{gearMap.get(l.gear_id)?.name ?? `#${l.gear_id}`}</span>
                  <Input
                    className="w-20"
                    type="number"
                    min={1}
                    value={l.qty}
                    onChange={(e) =>
                      setLines((ls) =>
                        ls.map((x, i) => (i === idx ? { ...x, qty: Number(e.target.value) || 1 } : x)),
                      )
                    }
                  />
                  <Button type="button" size="sm" variant="ghost" onClick={() => setLines((ls) => ls.filter((_, i) => i !== idx))}>
                    Убрать
                  </Button>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-end gap-2">
              <select
                className={cn(
                  "flex h-9 min-w-[200px] rounded-md border border-input bg-transparent px-2 text-sm shadow-sm",
                )}
                value={pick}
                onChange={(e) => setPick(e.target.value)}
              >
                <option value="">— снаряжение —</option>
                {gearItems
                  .filter((g) => g.available_count > 0)
                  .map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name} ({g.available_count})
                    </option>
                  ))}
              </select>
              <Button type="button" variant="secondary" onClick={addLine} disabled={!pick}>
                Добавить
              </Button>
            </div>
          </div>
          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          <Button type="submit" disabled={busy}>
            {busy ? "Выдача…" : "Оформить выдачу"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function ReturnForm({
  managerId,
  rentals,
  loading,
  onSuccess,
}: {
  managerId: number;
  rentals: Awaited<ReturnType<typeof listActiveRentals>>;
  loading: boolean;
  onSuccess: () => void;
}) {
  const [rentalId, setRentalId] = useState<number | "">("");
  const [qtyByGear, setQtyByGear] = useState<Record<number, number>>({});
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const rental = useMemo(
    () => (rentalId === "" ? null : rentals.find((r) => r.id === rentalId) ?? null),
    [rentals, rentalId],
  );

  function onPickRental(id: number) {
    setRentalId(id);
    const r = rentals.find((x) => x.id === id);
    const next: Record<number, number> = {};
    if (r) {
      for (const it of r.items) {
        if (it.qty_outstanding > 0) next[it.gear_id] = it.qty_outstanding;
      }
    }
    setQtyByGear(next);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (rentalId === "" || !rental) {
      setError("Выберите аренду");
      return;
    }
    const items = Object.entries(qtyByGear)
      .map(([gid, q]) => ({ gear_id: Number(gid), quantity: q }))
      .filter((x) => x.quantity > 0);
    if (items.length === 0) {
      setError("Укажите количества возврата");
      return;
    }
    for (const it of rental.items) {
      const q = qtyByGear[it.gear_id] ?? 0;
      if (q > it.qty_outstanding) {
        setError(`Слишком много по ${it.gear_name}`);
        return;
      }
    }
    setBusy(true);
    try {
      await returnRental(rentalId, {
        manager_id: managerId,
        items,
        comment: comment.trim() || null,
        fee_status_snapshot: null,
      });
      onSuccess();
      setRentalId("");
      setQtyByGear({});
      setComment("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ошибка приёма");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Приём / частичный возврат</CardTitle>
        <CardDescription>Фиксируется через события возврата на стороне API.</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? <p className="text-sm text-muted-foreground">Загрузка аренд…</p> : null}
        <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
          <div className="space-y-2">
            <Label htmlFor="rid">Аренда</Label>
            <select
              id="rid"
              className={cn(
                "flex h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm shadow-sm",
              )}
              value={rentalId === "" ? "" : String(rentalId)}
              onChange={(e) => {
                const v = e.target.value;
                if (!v) {
                  setRentalId("");
                  setQtyByGear({});
                  return;
                }
                onPickRental(Number(v));
              }}
            >
              <option value="">— выберите —</option>
              {rentals.map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} · {r.user_full_name} · {r.event}
                </option>
              ))}
            </select>
          </div>
          {rental ? (
            <div className="space-y-2 rounded-lg border border-border p-3">
              <p className="text-sm font-medium">Возврат по позициям</p>
              <ul className="space-y-2 text-sm">
                {rental.items
                  .filter((it) => it.qty_outstanding > 0)
                  .map((it) => (
                    <li key={it.gear_id} className="flex flex-wrap items-center gap-2">
                      <span className="min-w-0 flex-1">
                        {it.gear_name}{" "}
                        <span className="text-muted-foreground text-xs">(макс {it.qty_outstanding})</span>
                      </span>
                      <Input
                        className="w-24"
                        type="number"
                        min={0}
                        max={it.qty_outstanding}
                        value={qtyByGear[it.gear_id] ?? 0}
                        onChange={(e) =>
                          setQtyByGear((m) => ({
                            ...m,
                            [it.gear_id]: Number(e.target.value),
                          }))
                        }
                      />
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="cm3">Комментарий</Label>
            <Textarea id="cm3" rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
          {error ? <p className="text-destructive text-sm">{error}</p> : null}
          <Button type="submit" disabled={busy || !rental}>
            {busy ? "Сохранение…" : "Записать возврат"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
