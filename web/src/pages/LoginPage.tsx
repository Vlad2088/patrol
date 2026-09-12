// Страница входа
import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, authStore } from "../api/client";

export default function LoginPage() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const t = await api.login(login, password);
      if (t.role !== "dispatcher") {
        setError("Веб-кабинет только для диспетчеров");
        authStore.clear();
      } else {
        nav("/");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>Patrol — кабинет диспетчера</h1>
        {error && <div className="alert">{error}</div>}
        <input placeholder="Логин" value={login} onChange={(e) => setLogin(e.target.value)} autoFocus />
        <input type="password" placeholder="Пароль" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button className="btn" disabled={busy || !login || !password}>
          {busy ? "Вход..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
