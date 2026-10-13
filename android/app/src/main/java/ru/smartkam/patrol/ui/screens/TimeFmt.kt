// Форматирование ISO-времени из API (UTC) в часовой пояс ОБЪЕКТА.
// Пояс устройства охранника ненадёжен (авто-определение по сети врёт),
// поэтому берём facility_tz из sync-пакета, а не ZoneId.systemDefault().
package ru.smartkam.patrol.ui.screens

import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

private val isoFmt = DateTimeFormatter.ISO_DATE_TIME

// Устанавливается после синхронизации (facility_tz с сервера).
object FacilityTz {
    var zone: ZoneId = ZoneId.of("Asia/Kamchatka")
}

// «HH:mm» — окно обхода в списке обходов
fun String.fmtShort(): String = try {
    LocalDateTime.parse(this, isoFmt)
        .atOffset(ZoneOffset.UTC)
        .atZoneSameInstant(FacilityTz.zone)
        .format(DateTimeFormatter.ofPattern("HH:mm"))
} catch (_: Exception) {
    this
}

// «dd.MM HH:mm» — окно обхода в истории
fun String.fmtWindow(): String = try {
    LocalDateTime.parse(this, isoFmt)
        .atOffset(ZoneOffset.UTC)
        .atZoneSameInstant(FacilityTz.zone)
        .format(DateTimeFormatter.ofPattern("dd.MM HH:mm"))
} catch (_: Exception) {
    this
}
