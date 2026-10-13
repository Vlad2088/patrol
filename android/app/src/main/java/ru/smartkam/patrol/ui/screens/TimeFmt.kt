// Форматирование ISO-времени из API (UTC) в часовой пояс устройства.
package ru.smartkam.patrol.ui.screens

import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

private val isoFmt = DateTimeFormatter.ISO_DATE_TIME

// «HH:mm» — окно обхода в списке обходов
fun String.fmtShort(): String = try {
    LocalDateTime.parse(this, isoFmt)
        .atOffset(ZoneOffset.UTC)
        .atZoneSameInstant(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("HH:mm"))
} catch (_: Exception) {
    this
}

// «dd.MM HH:mm» — окно обхода в истории
fun String.fmtWindow(): String = try {
    LocalDateTime.parse(this, isoFmt)
        .atOffset(ZoneOffset.UTC)
        .atZoneSameInstant(ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM HH:mm"))
} catch (_: Exception) {
    this
}
