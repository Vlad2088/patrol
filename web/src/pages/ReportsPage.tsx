// Отчёты: выгрузка CSV/XLSX (обходы/нарушения) с периодом
import { useState } from "react";
import { api, authStore } from "../api/client";
import { Field } from "../components/ui";

const iso = (d: Date) => d.toISOString().slice(0, 10);

function download(kind: "patrols" | "violations", fmt: "csv" | "xlsx", from: string, to: string) {
  const q = new URLSearchParams();
  if (from) q.set("from_", from);
  if (to) q.set("to", to);
  const url = `${api.reportUrl(kind, fmt)}?${q}`;
  fetch(url, { headers: { Authorization: `Bearer ${authStore.access}` } })
    .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .then((b) => {
      const href = URL.createObjectURL(b);
      const a = document.createElement("a");
      a.href = href;
      a.download = `${kind}_${from || "all"}.${fmt}`;
      a.click();
      URL.revokeObjectURL(href);
    })
    .catch((e: Error) => alert(e.message));
}

export default function ReportsPage() {
  const monthAgo = new Date(Date.now() - 30 * 86400_000);
  const [from, setFrom] = useState(iso(monthAgo));
  const [to, setTo] = useState(iso(new Date()));

  return (
    <div>
      <h2>Отчёты</h2>
      <div className="form-row wrap">
        <Field label="С">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
        <Field label="По">
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </Field>
      </div>

      <h3>Обходы</h3>
      <div className="form-row">
        <button className="btn" onClick={() => download("patrols", "csv", from, to)}>CSV</button>
        <button className="btn" onClick={() => download("patrols", "xlsx", from, to)}>Excel</button>
      </div>

      <h3>Нарушения</h3>
      <div className="form-row">
        <button className="btn" onClick={() => download("violations", "csv", from, to)}>CSV</button>
        <button className="btn" onClick={() => download("violations", "xlsx", from, to)}>Excel</button>
      </div>
    </div>
  );
}
