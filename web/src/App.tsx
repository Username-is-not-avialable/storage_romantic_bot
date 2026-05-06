import { Button } from "@/components/ui/button";

function App() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 px-6">
      <div className="text-center space-y-2 max-w-lg">
        <h1 className="text-2xl font-semibold tracking-tight">Склад снаряжения</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          Веб-интерфейс и API доступны под одним адресом: статика здесь, запросы к бэкенду — на префикс{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">/api</code>.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button>Войти (скоро)</Button>
        <Button variant="secondary">Каталог (скоро)</Button>
        <Button variant="outline">Контур shadcn</Button>
      </div>
    </main>
  );
}

export default App;
