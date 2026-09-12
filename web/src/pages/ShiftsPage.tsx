// Смены: назначение охранников на объекты
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Field, Table } from "../components/ui";

const todayIso = () => new Date().toISOString().slice(0, 10);

export default function ShiftsPage() {
  const qc = useQueryClient();
  const [date, setDate] = useState(todayIso());
  const { data: shifts } = useQuery({ queryKey: ["shifts", date], queryFn: () => api.shifts({ date }) });
  const { data: objects } = useQuery({ queryKey: ["objects"], queryFn: api.objects });
  const { data: guards } = useQuery({ queryKey: ["guards"], queryFn: api.guards });

  const [form, setForm] = useState({ object_id: "", guard_id: "", starts_at: "08:00", ends_at: "20:00" });

  const create = useMutation({
    mutationFn: () => {
      const d = date || todayIso();
      return api.createShift({
        object_id: Number(form.object_id),
        guard_id: Number(form.guard_id),
        starts_at: new Date(`${d}T${form.starts_at}:00`).toISOString(),
        ends_at: new Date(`${d}T${form.ends_at}:00`).toISOString(),
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shifts"] }),
  });
  const del = useMutation({
    mutationFn: (id: number) => api.deleteShift(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shifts"] }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (form.object_id && form.guard_id) create.mutate();
  };

  return (
    <div>
      <h2>Смены</h2>
      <div className="page-head">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>

      <form className="form-row wrap" onSubmit={submit}>
        <Field label="Объект">
          <select value={form.object_id} onChange={(e) => setForm({ ...form, object_id: e.target.value })}>
            <option value="">— выберите —</option>
            {(objects ?? []).filter((o) => o.is_active).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </Field>
        <Field label="Охранник">
          <select value={form.guard_id} onChange={(e) => setForm({ ...form, guard_id: e.target.value })}>
            <option value="">— выберите —</option>
            {(guards ?? []).filter((g) => g.is_active).map((g) => <option key={g.id} value={g.id}>{g.full_name}</option>)}
          </select>
        </Field>
        <Field label="Начало">
          <input type="time" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
        </Field>
        <Field label="Конец">
          <input type="time" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} />
        </Field>
        <button className="btn" disabled={create.isPending || !form.object_id || !form.guard_id}>Назначить</button>
      </form>
      {create.isError && <div className="alert">{(create.error as Error).message}</div>}

      <Table head={["Объект", "Охранник", "Начало", "Конец", ""]}>
        {(shifts ?? []).map((s) => (
          <tr key={s.id}>
            <td>{s.object_name}</td>
            <td>{s.guard_full_name}</td>
            <td>{new Date(s.starts_at).toLocaleString("ru-RU")}</td>
            <td>{new Date(s.ends_at).toLocaleString("ru-RU")}</td>
            <td><button className="btn-ghost" onClick={() => del.mutate(s.id)}>Удалить</button></td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
