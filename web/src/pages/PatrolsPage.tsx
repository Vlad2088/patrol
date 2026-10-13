// Обходы: журнал с фильтрами (дата/объект/статус)
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { StatusBadge, Table } from "../components/ui";
import { todayIsoFacility as todayIso, fmtTime, useFacilityTz } from "../lib/date";


const STATUSES = [
  ["", "Все"],
  ["planned", "Запланирован"],
  ["in_progress", "Идёт"],
  ["completed", "Завершён"],
  ["partial", "Частично"],
  ["missed", "Пропущен"],
];

export default function PatrolsPage() {
  useFacilityTz();
  const [date, setDate] = useState(todayIso());
  const [objectId, setObjectId] = useState("");
  const [status, setStatus] = useState("");
  const { data: objects } = useQuery({ queryKey: ["objects"], queryFn: api.objects });
  const { data: patrols, isLoading } = useQuery({
    queryKey: ["patrols", date, objectId, status],
    queryFn: () =>
      api.patrols({
        date: date || undefined,
        object_id: objectId ? Number(objectId) : undefined,
        status_filter: status || undefined,
      }),
    refetchInterval: 30_000,
  });

  return (
    <div>
      <h2>Обходы</h2>
      <div className="form-row wrap">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <select value={objectId} onChange={(e) => setObjectId(e.target.value)}>
          <option value="">Все объекты</option>
          {(objects ?? []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {isLoading ? <div>Загрузка...</div> : (
        <Table head={["Объект", "Маршрут", "Окно", "Статус", "Точек", "Начат", "Завершён"]}>
          {(patrols ?? []).map((p) => (
            <tr key={p.id}>
              <td>{p.object_name}</td>
              <td>{p.route_name}</td>
              <td className="small">
                {fmtTime(p.window_start)}
                –
                {fmtTime(p.window_end)}
              </td>
              <td><StatusBadge status={p.status} /></td>
              <td>{p.checkpoints_scanned}/{p.checkpoints_total}</td>
              <td>{p.started_at ? fmtTime(p.started_at) : "—"}</td>
              <td>{p.finished_at ? fmtTime(p.finished_at) : "—"}</td>
            </tr>
          ))}
        </Table>
      )}
      {patrols?.length === 0 && <div className="muted small">Нет обходов по фильтру</div>}
    </div>
  );
}
