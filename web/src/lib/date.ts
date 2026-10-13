// Локальная дата в ISO (yyyy-mm-dd) по часовому поясу браузера,
// а не UTC: до полудня Камчатки toISOString() давал вчерашний день.
export const todayIso = (): string => {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60_000).toISOString().slice(0, 10);
};
