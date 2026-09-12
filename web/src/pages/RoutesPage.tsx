// Маршруты: список по объекту, точки, добавление, QR-PDF, расписания
import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, authStore } from "../api/client";
import { Field, Table } from "../components/ui";

const WEEKDAYS = ["", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

export default function RoutesPage() {
  const qc = useQueryClient();
  const { data: objects } = useQuery({ queryKey: ["objects"], queryFn: api.objects });
  const [objectId, setObjectId] = useState<number | null>(null);
  const { data: routes } = useQuery({
    queryKey: ["routes", objectId],
    queryFn: () => api.routes(objectId ?? undefined),
    enabled: true,
  });

  const [routeName, setRouteName] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const { data: checkpoints } = useQuery({
    queryKey: ["checkpoints", selected],
    queryFn: () => api.checkpoints(selected!),
    enabled: selected != null,
  });
  const { data: schedules } = useQuery({
    queryKey: ["schedules", selected],
    queryFn: () => api.schedules(selected!),
    enabled: selected != null,
  });

  const [cpNames, setCpNames] = useState("");
  const [sched, setSched] = useState({ kind: "daily", once_date: "", weekdays: [] as number[], shift_kind: "", window_start: "22:00", window_end: "23:00" });

  const createRoute = useMutation({
    mutationFn: () => api.createRoute({ object_id: objectId!, name: routeName }),
    onSuccess: () => {
      setRouteName("");
      qc.invalidateQueries({ queryKey: ["routes"] });
    },
  });
  const addCp = useMutation({
    mutationFn: () =>
      api.addCheckpoints(selected!, cpNames.split("\n").map((s) => ({ name: s.trim() || null }))),
    onSuccess: () => {
      setCpNames("");
      qc.invalidateQueries({ queryKey: ["checkpoints"] });
      qc.invalidateQueries({ queryKey: ["routes"] });
    },
  });
  const delCp = useMutation({
    mutationFn: (id: number) => api.deleteCheckpoint(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["checkpoints"] });
      qc.invalidateQueries({ queryKey: ["routes"] });
    },
  });
  const createSched = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        route_id: selected,
        kind: sched.kind,
        window_start: `${sched.window_start}:00`,
        window_end: `${sched.window_end}:00`,
      };
      if (sched.kind === "once") body.once_date = sched.once_date;
      if (sched.kind === "weekly") body.weekdays = sched.weekdays;
      if (sched.kind === "shift") body.shift_kind = sched.shift_kind || "day";
      return api.createSchedule(body);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
  const delSched = useMutation({
    mutationFn: (id: number) => api.deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });

  const submitRoute = (e: FormEvent) => {
    e.preventDefault();
    if (objectId && routeName.trim().length >= 2) createRoute.mutate();
  };
  const submitCp = (e: FormEvent) => {
    e.preventDefault();
    if (selected && cpNames.trim()) addCp.mutate();
  };
  const submitSched = (e: FormEvent) => {
    e.preventDefault();
    if (selected) createSched.mutate();
  };

  const downloadQr = () => {
    fetch(api.qrPdfUrl(selected!), {
      headers: { Authorization: `Bearer ${authStore.access}` },
    })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((b) => {
        const url = URL.createObjectURL(b);
        const a = document.createElement("a");
        a.href = url;
        a.download = `route_${selected}_qr.pdf`;
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e: Error) => alert(e.message));
  };

  const route = (routes ?? []).find((r) => r.id === selected);

  return (
    <div>
      <h2>Маршруты и точки</h2>

      <div className="form-row">
        <Field label="Объект">
          <select value={objectId ?? ""} onChange={(e) => { setObjectId(Number(e.target.value)); setSelected(null); }}>
            <option value="">— выберите —</option>
            {(objects ?? []).filter((o) => o.is_active).map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </Field>
      </div>

      {objectId != null && (
        <>
          <form className="form-row" onSubmit={submitRoute}>
            <Field label="Новый маршрут">
              <input value={routeName} onChange={(e) => setRouteName(e.target.value)} placeholder="Периметр" />
            </Field>
            <button className="btn" disabled={createRoute.isPending || routeName.trim().length < 2}>Создать</button>
          </form>

          <Table head={["ID", "Название", "Точек", ""]}>
            {(routes ?? []).map((r) => (
              <tr key={r.id} className={r.id === selected ? "selected" : ""}>
                <td>{r.id}</td>
                <td>{r.name}</td>
                <td>{r.checkpoints_count}</td>
                <td>
                  <button className="btn-ghost" onClick={() => setSelected(r.id)}>
                    {r.id === selected ? "Скрыть" : "Открыть"}
                  </button>
                </td>
              </tr>
            ))}
          </Table>

          {selected != null && (
            <div className="panel">
              <h3>{route?.name}: точки</h3>

              {checkpoints && checkpoints.length > 0 && (
                <>
                  <Table head={["№", "Код QR", "Название", ""]}>
                    {checkpoints.map((c) => (
                      <tr key={c.id}>
                        <td>{c.order_num}</td>
                        <td className="mono">{c.code}</td>
                        <td>{c.name ?? "—"}</td>
                        <td>
                          {c.order_num === Math.max(...checkpoints.map((x) => x.order_num)) && (
                            <button className="btn-ghost" onClick={() => delCp.mutate(c.id)}>Удалить</button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </Table>
                  <button className="btn-outline" onClick={downloadQr}>Скачать QR-наклейки (PDF)</button>
                </>
              )}

              <form className="form-row" onSubmit={submitCp}>
                <Field label="Добавить точки (по одной в строке)">
                  <textarea rows={4} value={cpNames} onChange={(e) => setCpNames(e.target.value)} placeholder={"Вход\nУгол А\nСклад"} />
                </Field>
                <button className="btn" disabled={addCp.isPending || !cpNames.trim()}>Добавить</button>
              </form>
              {addCp.isError && <div className="alert">{(addCp.error as Error).message}</div>}

              <h3>Расписания</h3>
              <Table head={["Тип", "Когда", "Окно", ""]}>
                {(schedules ?? []).filter((s) => s.is_active).map((s) => (
                  <tr key={s.id}>
                    <td>{s.kind}</td>
                    <td>
                      {s.kind === "once" && `разово ${s.once_date}`}
                      {s.kind === "daily" && "ежедневно"}
                      {s.kind === "weekly" && (s.weekdays ?? []).map((d) => WEEKDAYS[d]).join(", ")}
                      {s.kind === "shift" && `смена: ${s.shift_kind === "day" ? "день" : "ночь"}`}
                    </td>
                    <td>{s.window_start.slice(0, 5)}–{s.window_end.slice(0, 5)}</td>
                    <td><button className="btn-ghost" onClick={() => delSched.mutate(s.id)}>Удалить</button></td>
                  </tr>
                ))}
              </Table>

              <form className="form-row wrap" onSubmit={submitSched}>
                <Field label="Тип">
                  <select value={sched.kind} onChange={(e) => setSched({ ...sched, kind: e.target.value })}>
                    <option value="daily">Ежедневно</option>
                    <option value="weekly">По дням недели</option>
                    <option value="once">Разово</option>
                    <option value="shift">По сменам</option>
                  </select>
                </Field>
                {sched.kind === "once" && (
                  <Field label="Дата">
                    <input type="date" value={sched.once_date} onChange={(e) => setSched({ ...sched, once_date: e.target.value })} />
                  </Field>
                )}
                {sched.kind === "weekly" && (
                  <Field label="Дни недели">
                    <div className="weekday-picker">
                      {WEEKDAYS.slice(1).map((lbl, i) => (
                        <button
                          type="button"
                          key={lbl}
                          className={`wd ${sched.weekdays.includes(i + 1) ? "on" : ""}`}
                          onClick={() =>
                            setSched({
                              ...sched,
                              weekdays: sched.weekdays.includes(i + 1)
                                ? sched.weekdays.filter((d) => d !== i + 1)
                                : [...sched.weekdays, i + 1],
                            })
                          }
                        >
                          {lbl}
                        </button>
                      ))}
                    </div>
                  </Field>
                )}
                {sched.kind === "shift" && (
                  <Field label="Смена">
                    <select value={sched.shift_kind} onChange={(e) => setSched({ ...sched, shift_kind: e.target.value })}>
                      <option value="day">День</option>
                      <option value="night">Ночь</option>
                    </select>
                  </Field>
                )}
                <Field label="Окно начала">
                  <input type="time" value={sched.window_start} onChange={(e) => setSched({ ...sched, window_start: e.target.value })} />
                </Field>
                <Field label="Окно конца">
                  <input type="time" value={sched.window_end} onChange={(e) => setSched({ ...sched, window_end: e.target.value })} />
                </Field>
                <button className="btn" disabled={createSched.isPending}>Добавить расписание</button>
              </form>
              {createSched.isError && <div className="alert">{(createSched.error as Error).message}</div>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
