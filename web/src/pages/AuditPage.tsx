// Аудит: журнал действий диспетчеров (только чтение)
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Table } from "../components/ui";

const ACTION_LABEL: Record<string, string> = {
  create: "Создание",
  update: "Изменение",
  delete: "Удаление",
};
const ENTITY_LABEL: Record<string, string> = {
  object: "Объект",
  route: "Маршрут",
  checkpoint: "Точка",
  checkpoints: "Точки (пакет)",
  schedule: "Расписание",
  shift: "Смена",
  guard: "Охранник",
};

export default function AuditPage() {
  const { data: audit, isLoading } = useQuery({ queryKey: ["audit"], queryFn: api.audit });

  return (
    <div>
      <h2>Аудит действий</h2>
      {isLoading ? <div>Загрузка...</div> : (
        <Table head={["Когда", "Пользователь", "Действие", "Сущность", "ID", "Детали"]}>
          {(audit ?? []).map((a) => (
            <tr key={a.id}>
              <td className="small">{new Date(a.created_at).toLocaleString("ru-RU")}</td>
              <td>#{a.user_id}</td>
              <td>{ACTION_LABEL[a.action] ?? a.action}</td>
              <td>{ENTITY_LABEL[a.entity] ?? a.entity}</td>
              <td>{a.entity_id ?? "—"}</td>
              <td className="mono small">{JSON.stringify(a.payload).slice(0, 100)}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
