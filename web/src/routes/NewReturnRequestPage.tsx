import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { listActiveRentals } from "@/api/rentals";
import { createReturnRequest } from "@/api/returnRequests";
import { listManagers } from "@/api/users";
import { ApiError } from "@/api/http";
import { useMe } from "@/auth/useMe";
import { RequireAuth } from "@/components/auth/Guards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function NewReturnRequestPage() {
  return (
    <RequireAuth>
      <NewReturnRequestInner />
    </RequireAuth>
  );
}

function NewReturnRequestInner() {
  const [searchParams] = useSearchParams();
  const presetRentalId = Number(searchParams.get("rental_id") || "0") || null;

  const { data: me, isPending: mePending } = useMe();
  const qc = useQueryClient();
  const { data: rentals = [], isFetching: rentalsFetching } = useQuery({
    queryKey: ["active-rentals-return-form", "mine", me?.id],
    queryFn: () => listActiveRentals(me!.id),
    enabled: Boolean(me),
  });

  const { data: managers = [], isLoading: managersLoading } = useQuery({
    queryKey: ["web-managers"],
    queryFn: () => listManagers(),
  });

  const [rentalId, setRentalId] = useState<number | null>(presetRentalId);
  const [qtyByGear, setQtyByGear] = useState<Record<number, number>>({});
  const [targetManagerId, setTargetManagerId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (presetRentalId) setRentalId(presetRentalId);
  }, [presetRentalId]);

  const rental = useMemo(() => rentals.find((r) => r.id === rentalId) ?? null, [rentals, rentalId]);

  useEffect(() => {
    if (!rental) return;
    const next: Record<number, number> = {};
    for (const it of rental.items) {
      if (it.qty_outstanding > 0) {
        next[it.gear_id] = it.qty_outstanding;
      }
    }
    setQtyByGear(next);
  }, [rental]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(null);
    if (!rentalId || !rental) {
      setError("Выберите активную аренду");
      return;
    }
    const items = Object.entries(qtyByGear)
      .map(([gid, q]) => ({ gear_id: Number(gid), qty_return: q }))
      .filter((x) => x.qty_return > 0);
    if (items.length === 0) {
      setError("Укажите количество хотя бы по одной позиции");
      return;
    }
    for (const it of rental.items) {
      const q = qtyByGear[it.gear_id] ?? 0;
      if (q > it.qty_outstanding) {
        setError(`По «${it.gear_name}» нельзя сдать больше ${it.qty_outstanding}`);
        return;
      }
    }

    let tm: number | null = null;
    if (targetManagerId !== "") {
      const parsed = Number.parseInt(targetManagerId, 10);
      if (!Number.isInteger(parsed) || parsed < 1) {
        setError("Выберите завснара из списка");
        return;
      }
      tm = parsed;
    }

    setBusy(true);
    try {
      const res = await createReturnRequest({
        rental_id: rentalId,
        target_manager_id: tm,
        items,
      });
      setDone(`Заявка #${res.id} отправлена (${res.status}).`);
      await qc.invalidateQueries({ queryKey: ["my-return-requests"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось создать заявку");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Заявка на возврат</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Для активной аренды укажите, что сдаёте.{" "}
          <Link className="underline-offset-4 hover:underline" to="/me">
            Мои аренды
          </Link>
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Параметры</CardTitle>
          <CardDescription>Количества не могут превышать остаток по аренде.</CardDescription>
        </CardHeader>
        <CardContent>
          {mePending || rentalsFetching ? <p className="text-sm text-muted-foreground">Загрузка аренд…</p> : null}
          <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
            <div className="space-y-2">
              <Label htmlFor="rental">Аренда</Label>
              <select
                id="rental"
                className={cn(
                  "flex h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm shadow-sm",
                )}
                value={rentalId ?? ""}
                onChange={(e) => setRentalId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">— выберите —</option>
                {rentals.map((r) => (
                  <option key={r.id} value={r.id}>
                    #{r.id} · {r.event} (до {r.due_date})
                  </option>
                ))}
              </select>
            </div>

            {rental ? (
              <div className="space-y-3 rounded-lg border border-border p-3">
                <p className="text-sm font-medium">Позиции к сдаче</p>
                <ul className="space-y-3">
                  {rental.items
                    .filter((it) => it.qty_outstanding > 0)
                    .map((it) => (
                      <li key={it.gear_id} className="flex flex-wrap items-center gap-2 text-sm">
                        <span className="min-w-0 flex-1">
                          {it.gear_name}{" "}
                          <span className="text-muted-foreground text-xs">
                            (осталось {it.qty_outstanding})
                          </span>
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
              <Label htmlFor="tm">Завснар (опционально)</Label>
              <select
                id="tm"
                className={cn(
                  "flex h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm shadow-sm",
                )}
                value={targetManagerId}
                onChange={(e) => setTargetManagerId(e.target.value)}
              >
                <option value="">Все завснары</option>
                {managers.map((m) => (
                  <option key={m.id} value={String(m.id)}>
                    {m.full_name}
                  </option>
                ))}
              </select>
              {managersLoading ? (
                <p className="text-muted-foreground text-xs">Загрузка списка завснаров…</p>
              ) : managers.length === 0 ? (
                <p className="text-muted-foreground text-xs">
                  В системе нет активных завснаров — заявку обработает тот, кто первый возьмёт в работу, либо
                  обратитесь к администратору.
                </p>
              ) : null}
            </div>

            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            {done ? <p className="text-sm text-green-700 dark:text-green-400">{done}</p> : null}
            <Button type="submit" disabled={busy || !rental}>
              {busy ? "Отправка…" : "Отправить заявку"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
