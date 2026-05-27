import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/http";
import { register } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const MIN_PASSWORD_LEN = 8;

export function RegisterPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [document, setDocument] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const passwordTooShort = password.length > 0 && password.length < MIN_PASSWORD_LEN;
  const passwordsDontMatch = confirmPassword.length > 0 && password !== confirmPassword;

  const isSubmitDisabled =
    busy ||
    email.trim().length === 0 ||
    fullName.trim().length === 0 ||
    phone.trim().length === 0 ||
    password.length < MIN_PASSWORD_LEN ||
    password !== confirmPassword;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (isSubmitDisabled) return;

    setError(null);
    setBusy(true);

    try {
      await register({
        email: email.trim().toLowerCase(),
        full_name: fullName.trim(),
        phone: phone.trim(),
        document: document.trim() || null,
        password,
      });
      navigate("/login", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Не удалось зарегистрироваться");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col gap-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Регистрация</CardTitle>
          <CardDescription>Создайте учетную запись для работы со складом.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void onSubmit(e)} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="reg-email">Email</Label>
              <Input id="reg-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-name">ФИО</Label>
              <Input id="reg-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-phone">Телефон</Label>
              <Input id="reg-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+79991234567" required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-document">Документ (опционально)</Label>
              <Input id="reg-document" value={document} onChange={(e) => setDocument(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-password">Пароль</Label>
              <Input
                id="reg-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={MIN_PASSWORD_LEN}
                required
              />
              {passwordTooShort ? <p className="text-xs text-muted-foreground">Минимум {MIN_PASSWORD_LEN} символов.</p> : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="reg-confirm-password">Подтверждение пароля</Label>
              <Input
                id="reg-confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
              {passwordsDontMatch ? <p className="text-xs text-destructive">Пароли не совпадают.</p> : null}
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
            <Button type="submit" className="w-full" disabled={isSubmitDisabled}>
              {busy ? "Регистрация…" : "Зарегистрироваться"}
            </Button>
          </form>
        </CardContent>
      </Card>
      <p className="text-center text-xs text-muted-foreground">
        Уже есть аккаунт?{" "}
        <Link className="underline-offset-4 hover:underline" to="/login">
          Войти
        </Link>
      </p>
    </div>
  );
}
