import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listGear } from "@/api/gear";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export function CatalogPage() {
  const [q, setQ] = useState("");

  const effectiveQuery = useMemo(() => {
    const t = q.trim();
    if (t.length === 0) return undefined;
    return t;
  }, [q]);

  const hint =
    effectiveQuery !== undefined && effectiveQuery.length > 0 && effectiveQuery.length < 3
      ? "Введите не меньше 3 символов для поиска или очистите поле, чтобы показать весь каталог."
      : null;

  const { data: items = [], isFetching } = useQuery({
    queryKey: ["gear", effectiveQuery],
    queryFn: () =>
      listGear({
        query: effectiveQuery,
        page: 1,
        limit: 80,
      }),
    enabled: hint === null,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Каталог снаряжения</h1>
        <p className="text-muted-foreground mt-1 text-sm">Поиск по названию и описанию (от 3 символов).</p>
      </div>
      <div className="space-y-2 max-w-md">
        <Label htmlFor="search">Поиск</Label>
        <Input
          id="search"
          placeholder="Например: палатка"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {hint ? <p className="text-amber-700 dark:text-amber-400 text-xs">{hint}</p> : null}
      </div>
      {isFetching ? <p className="text-sm text-muted-foreground">Загрузка…</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((g) => (
          <Card key={g.id} className={cn(g.available_count === 0 && "opacity-70")}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base leading-snug">{g.name}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-muted-foreground text-xs">
                Доступно:{" "}
                <span className="text-foreground font-medium">
                  {g.available_count} / {g.total_quantity}
                </span>
              </p>
              {g.description ? <p className="text-xs leading-relaxed line-clamp-3">{g.description}</p> : null}
              <Button asChild size="sm" variant="outline" disabled={g.available_count === 0}>
                <Link to={`/requests/new?gear_id=${g.id}`}>Арендовать эту позицию</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      {!isFetching && items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Ничего не найдено.</p>
      ) : null}
    </div>
  );
}
