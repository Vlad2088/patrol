// Общие UI-компоненты: таблица, поле, кнопка
import type { ReactNode } from "react";

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <table className="tbl">
      <thead>
        <tr>{head.map((h) => <th key={h}>{h}</th>)}</tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    planned: "planned",
    in_progress: "inprogress",
    completed: "completed",
    missed: "missed",
    partial: "partial",
  };
  const labels: Record<string, string> = {
    planned: "Запланирован",
    in_progress: "Идёт",
    completed: "Завершён",
    missed: "Пропущен",
    partial: "Частично",
  };
  return <span className={`st ${map[status] ?? ""}`}>{labels[status] ?? status}</span>;
}
