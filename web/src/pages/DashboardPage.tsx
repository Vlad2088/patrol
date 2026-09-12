// Мониторинг: сводка по объектам за дату + лента нарушений
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/ui";

const todayIso = () => new Date().toISOString().slice(0, 10);

export default function DashboardPage() {
  const [date, setDate] = useState(todayIso());
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", date],
    queryFn: () => api.dashboard(date),
    refetchInterval: 30_000,
  });
  const { data: violations } = useQuery({
    queryKey: ["notifications"],
    queryFn: api.notifications,
    refetchInterval: 60_000,
  });

  if (isLoading) return <div>Загрузка...</div>;
  if (error) return <div className="alert">Ошибка: {(error as Error).message}</div>;

  return (
    <div>
      <div className="page-head">
        <h2>Мониторинг</h2>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      </div>

      <div className="cards">
        {(data?.rows ?? []).map((r) => (
          <div key={r.object_id} className="card">
            <div className="card-title">{r.object_name}</div>
            <div className="card-grid">
              <span>Обходов: <b>{r.patrols_total}</b></span>
              <span className="planned">План: {r.planned}</span>
              <span className="inprogress">Идут: {r.in_progress}</span>
              <span className="completed">Готово: {r.completed}</span>
              <span className="partial">Частично: {r.partial}</span>
              <span className="missed">Пропущено: {r.missed}</span>
              <span className="missed">Нарушений: {r.violations}</span>
            </div>
          </div>
        ))}
      </div>

      <h3>Нарушения (последние)</h3>
      <Table head={["Когда зафиксировано", "Тип", "Обход", "Детали"]}>
        {(violations ?? []).slice(0, 20).map((v) => (
          <tr key={v.id}>
            <td>{new Date(v.detected_at).toLocaleString("ru-RU")}</td>
            <td>{v.kind === "missed_patrol" ? "Пропуск обхода" : "Непройденные точки"}</td>
            <td>#{v.patrol_id}</td>
            <td className="mono small">{JSON.stringify(v.details).slice(0, 120)}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
