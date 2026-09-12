// Охранники: список + создание + отключение
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Field, Table } from "../components/ui";

export default function GuardsPage() {
  const qc = useQueryClient();
  const { data: guards, isLoading } = useQuery({ queryKey: ["guards"], queryFn: api.guards });
  const [form, setForm] = useState({ login: "", password: "", full_name: "" });

  const create = useMutation({
    mutationFn: () => api.createGuard(form),
    onSuccess: () => {
      setForm({ login: "", password: "", full_name: "" });
      qc.invalidateQueries({ queryKey: ["guards"] });
    },
  });
  const toggle = useMutation({
    mutationFn: (g: { id: number; is_active: boolean }) => api.updateGuard(g.id, { is_active: !g.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["guards"] }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (form.login.length >= 3 && form.password.length >= 6 && form.full_name.length >= 3) create.mutate();
  };

  return (
    <div>
      <h2>Охранники</h2>

      <form className="form-row wrap" onSubmit={submit}>
        <Field label="Логин">
          <input value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} placeholder="ivanov" />
        </Field>
        <Field label="Пароль (мин. 6)">
          <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </Field>
        <Field label="ФИО">
          <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Иванов Иван Иванович" />
        </Field>
        <button className="btn" disabled={create.isPending}>Создать</button>
      </form>
      {create.isError && <div className="alert">{(create.error as Error).message}</div>}

      {isLoading ? <div>Загрузка...</div> : (
        <Table head={["ID", "Логин", "ФИО", "Активен", ""]}>
          {(guards ?? []).map((g) => (
            <tr key={g.id} className={g.is_active ? "" : "muted"}>
              <td>{g.id}</td>
              <td className="mono">{g.login}</td>
              <td>{g.full_name}</td>
              <td>{g.is_active ? "да" : "нет"}</td>
              <td>
                <button className="btn-ghost" onClick={() => toggle.mutate(g)}>
                  {g.is_active ? "Отключить" : "Включить"}
                </button>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
