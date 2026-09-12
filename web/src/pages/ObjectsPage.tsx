// Объекты: список + создание
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { Field, Table } from "../components/ui";

export default function ObjectsPage() {
  const qc = useQueryClient();
  const { data: objects, isLoading } = useQuery({ queryKey: ["objects"], queryFn: api.objects });
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");

  const create = useMutation({
    mutationFn: () => api.createObject({ name, address: address || undefined }),
    onSuccess: () => {
      setName("");
      setAddress("");
      qc.invalidateQueries({ queryKey: ["objects"] });
    },
  });
  const toggle = useMutation({
    mutationFn: (o: { id: number; is_active: boolean }) => api.updateObject(o.id, { is_active: !o.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["objects"] }),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (name.trim().length >= 2) create.mutate();
  };

  return (
    <div>
      <h2>Объекты</h2>
      <form className="form-row" onSubmit={submit}>
        <Field label="Название">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Склад на Ленина" />
        </Field>
        <Field label="Адрес">
          <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="ул. Ленина, 1" />
        </Field>
        <button className="btn" disabled={create.isPending || name.trim().length < 2}>Добавить</button>
      </form>
      {create.isError && <div className="alert">{(create.error as Error).message}</div>}

      {isLoading ? <div>Загрузка...</div> : (
        <Table head={["ID", "Название", "Адрес", "Активен", ""]}>
          {(objects ?? []).map((o) => (
            <tr key={o.id} className={o.is_active ? "" : "muted"}>
              <td>{o.id}</td>
              <td>{o.name}</td>
              <td>{o.address ?? "—"}</td>
              <td>{o.is_active ? "да" : "нет"}</td>
              <td>
                <button className="btn-ghost" onClick={() => toggle.mutate(o)}>
                  {o.is_active ? "Отключить" : "Включить"}
                </button>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
