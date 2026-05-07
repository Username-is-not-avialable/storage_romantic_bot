import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { listAllGear } from "@/api/gear";
import { createRentalRequest } from "@/api/rentalRequests";
import { listManagers } from "@/api/users";
import { ApiError } from "@/api/http";
import { RequireAuth } from "@/components/auth/Guards";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type Line = { gear_id: number; qty_requested: number };

export function NewRentalRequestPage() {
  return (
    <RequireAuth>
      <NewRentalRequestInner />
    </RequireAuth>
  );
}

function NewRentalRequestInner() {
  const [searchParams] = useSearchParams();
  const presetGearId = Number(searchParams.get("gear_id") || "0") || null;

  const qc = useQueryClient();
  const { data: gearItems = [] } = useQuery({
    queryKey: ["gear-all-request"],
    queryFn: () => listAllGear(),
  });

  const { data: managers = [], isLoading: managersLoading } = useQuery({
    queryKey: ["web-managers"],
    queryFn: () => listManagers(),
  });

  const gearMap = useMemo(() => new Map(gearItems.map((g) => [g.id, g])), [gearItems]);

  const [lines, setLines] = useState<Line[]>([]);

  useEffect(() => {
    if (!presetGearId || !gearMap.has(presetGearId)) return;
    setLines((ls) => {
      if (ls.length > 0) return ls;
      return [{ gear_id: presetGearId, qty_requested: 1 }];
    });
  }, [presetGearId, gearMap]);
  const [due, setDue] = useState("");
  const [event, setEvent] = useState("");
  const [comment, setComment] = useState("");
  const [deposit, setDeposit] = useState("");
  const [targetManagerId, setTargetManagerId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [addGearId, setAddGearId] = useState<string>("");

  function addLine() {
    const gid = Number(addGearId);
    if (!gid || lines.some((l) => l.gear_id === gid)) return;
    setLines((ls) => [...ls, { gear_id: gid, qty_requested: 1 }]);
    setAddGearId("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(null);
    if (lines.length === 0) {
      setError("Добавьте хотя бы одну позицию");
      return;
    }
    if (!due || !event.trim()) {
      setError("Укажите срок возврата и мероприятие");
      return;
    }
    if (!deposit.trim()) {
      setError("Укажите залоговый документ (описание или имя файла)");
      return;
    }
    if (!targetManagerId) {
      setError("Выберите завснара — ему будет адресована заявка");
      return;
    }
    setBusy(true);
    try {
      const res = await createRentalRequest({
        due_date: due,
        event: event.trim(),
        comment: comment.trim() || null,
        deposit_document: deposit.trim(),
        target_manager_id: Number(targetManagerId),
        items: lines.map((l) => ({ gear_id: l.gear_id, qty_requested: l.qty_requested })),
      });
      setDone(`Заявка #${res.id} создана (статус ${res.status}).`);
      await qc.invalidateQueries({ queryKey: ["my-rental-requests"] });
      setLines([]);
      setEvent("");
      setComment("");
      setDeposit("");
      setTargetManagerId("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить заявку");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Заявка на выдачу</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          Каталог:{" "}
          <Link className="underline-offset-4 hover:underline" to="/catalog">
            выбрать снаряжение
          </Link>
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Параметры</CardTitle>
          <CardDescription>Дата может быть в формате ГГГГ-ММ-ДД.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="due">Срок возврата</Label>
                <Input id="due" type="date" value={due} onChange={(e) => setDue(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="event">Мероприятие</Label>
                <Input id="event" value={event} onChange={(e) => setEvent(e.target.value)} required />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="comment">Комментарий</Label>
              <Textarea id="comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={3} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="dep">Залоговый документ (описание / имя файла)</Label>
              <Input
                id="dep"
                value={deposit}
                onChange={(e) => setDeposit(e.target.value)}
                required
                minLength={1}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="target-mgr">Завснар (адресат заявки)</Label>
              <select
                id="target-mgr"
                required
                className={cn(
                  "flex h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm shadow-sm",
                )}
                value={targetManagerId}
                onChange={(e) => setTargetManagerId(e.target.value)}
              >
                <option value="">— выберите завснара —</option>
                {managers.map((m) => (
                  <option key={m.id} value={String(m.id)}>
                    {m.full_name}
                  </option>
                ))}
              </select>
              {managersLoading ? (
                <p className="text-muted-foreground text-xs">Загрузка списка…</p>
              ) : managers.length === 0 ? (
                <p className="text-muted-foreground text-xs">
                  Нет активных завснаров в системе — обратитесь к администратору.
                </p>
              ) : null}
            </div>

            <div className="space-y-3 rounded-lg border border-border p-3">
              <p className="text-sm font-medium">Позиции</p>
              {lines.length === 0 ? (
                <p className="text-muted-foreground text-xs">Добавьте позиции из каталога.</p>
              ) : null}
              <ul className="space-y-2">
                {lines.map((l, idx) => {
                  const g = gearMap.get(l.gear_id);
                  return (
                    <li key={l.gear_id} className="flex flex-wrap items-center gap-2 text-sm">
                      <span className="min-w-0 flex-1 truncate">{g?.name ?? `gear #${l.gear_id}`}</span>
                      <Input
                        className="w-20"
                        type="number"
                        min={1}
                        value={l.qty_requested}
                        onChange={(e) =>
                          setLines((ls) =>
                            ls.map((x, i) =>
                              i === idx ? { ...x, qty_requested: Number(e.target.value) || 1 } : x,
                            ),
                          )
                        }
                      />
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setLines((ls) => ls.filter((_, i) => i !== idx))}
                      >
                        Убрать
                      </Button>
                    </li>
                  );
                })}
              </ul>
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1">
                  <Label className="text-xs">Добавить</Label>
                  <select
                    className={cn(
                      "flex h-9 min-w-[200px] rounded-md border border-input bg-transparent px-2 text-sm shadow-sm",
                    )}
                    value={addGearId}
                    onChange={(e) => setAddGearId(e.target.value)}
                  >
                    <option value="">— выберите —</option>
                    {gearItems
                      .filter((g) => g.available_count > 0)
                      .map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.name} ({g.available_count} своб.)
                        </option>
                      ))}
                  </select>
                </div>
                <Button type="button" variant="secondary" onClick={addLine} disabled={!addGearId}>
                  Добавить
                </Button>
              </div>
            </div>

            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            {done ? <p className="text-sm text-green-700 dark:text-green-400">{done}</p> : null}
            <Button type="submit" disabled={busy || managers.length === 0}>
              {busy ? "Отправка…" : "Отправить заявку"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
