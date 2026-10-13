// Все времена кабинет рендерит в поясе объекта (facility_tz с бэкенда),
// а не в поясе браузера: диспетчер из любого региона видит «настенное»
// время объекта. Ввод (смены) — тоже в поясе объекта.
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export const FACILITY_TZ_FALLBACK = "Asia/Kamchatka";

// Текущий пояс; обновляется хуком useFacilityTz при загрузке конфига.
const holder = { tz: FACILITY_TZ_FALLBACK };

export function useFacilityTz(): string {
  const { data } = useQuery({
    queryKey: ["config"],
    queryFn: api.config,
    staleTime: Infinity,
  });
  if (data?.facility_tz && data.facility_tz !== holder.tz) holder.tz = data.facility_tz;
  return holder.tz;
}

export const fmtTime = (iso: string): string =>
  new Intl.DateTimeFormat("ru-RU", {
    timeZone: holder.tz, hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));

export const fmtDateTime = (iso: string): string =>
  new Intl.DateTimeFormat("ru-RU", {
    timeZone: holder.tz, day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));

// Локальная дата в ISO (yyyy-mm-dd) ПО ПОЯСУ ОБЪЕКТА — для выборок «за день».
export const todayIsoFacility = (): string =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: holder.tz, year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());

// Дата в ISO (yyyy-mm-dd) по поясу объекта, смещённая на N дней от сейчас.
export const isoFacilityShifted = (days: number): string =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: holder.tz, year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date(Date.now() + days * 86400_000));

// «Настенное» время объекта (дата + HH:MM) — в абсолютный момент UTC.
// Перебираем смещения и сверяем, как дата выглядит в поясе объекта.
export const facilityWallToUtcIso = (dateIso: string, time: string): string => {
  const [h, m] = time.split(":").map(Number);
  for (let offsetH = -14; offsetH <= 14; offsetH++) {
    const cand = new Date(`${dateIso}T${time}:00.000Z`);
    cand.setTime(cand.getTime() - offsetH * 3600_000);
    const probe = new Intl.DateTimeFormat("en-CA", {
      timeZone: holder.tz, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    }).formatToParts(cand).reduce<Record<string, string>>((acc, p) => {
      if (p.type !== "literal") acc[p.type] = p.value;
      return acc;
    }, {});
    if (Number(probe.hour) === h && Number(probe.minute) === m) {
      return cand.toISOString();
    }
  }
  return new Date(`${dateIso}T${time}:00.000Z`).toISOString();
};

