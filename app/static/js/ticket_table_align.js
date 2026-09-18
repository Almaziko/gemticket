function alignTicketTables() {
    var tables = document.querySelectorAll('table.ticket-table');
    if (!tables.length) return;

    // "Название" (2-я колонка, индекс 1) — сознательно не измеряется и не
    // получает фиксированную ширину: ей отдаётся весь остаток после
    // остальных колонок, иначе одно длинное название тянуло бы всю таблицу
    // в ширину (и требовало горизонтальной прокрутки вместо обрезания
    // многоточием).
    var FLEX_COLUMN_INDEX = 1;

    var columnCount = 0;
    for (var t = 0; t < tables.length; t++) {
        var headerCells = tables[t].querySelectorAll('thead th');
        if (headerCells.length > columnCount) columnCount = headerCells.length;
    }
    if (!columnCount) return;

    // Таблица растянута на 100% ширины (Bootstrap .table), а table-layout:
    // auto при растянутой ширине не сжимает колонки до их минимума — он
    // распределяет между ними ВЕСЬ остаток свободного места, из-за чего
    // измеренная ширина оказывается заметно больше, чем реально нужно
    // контенту (это и давало те самые "слишком большие" отступы). Чтобы
    // замерить настоящий минимум, на время замера убираем растяжение —
    // тогда auto-layout честно сжимает таблицу по контенту.
    var previousWidths = [];
    for (var pw = 0; pw < tables.length; pw++) {
        previousWidths.push(tables[pw].style.width);
        tables[pw].style.width = 'auto';
    }

    var maxWidths = new Array(columnCount).fill(0);

    function measure(cells) {
        for (var i = 0; i < cells.length; i++) {
            if (i === FLEX_COLUMN_INDEX) continue;
            var width = cells[i].getBoundingClientRect().width;
            if (width > maxWidths[i]) maxWidths[i] = width;
        }
    }

    for (var t2 = 0; t2 < tables.length; t2++) {
        measure(tables[t2].querySelectorAll('thead th'));
        var rows = tables[t2].querySelectorAll('tbody tr');
        for (var r = 0; r < rows.length; r++) {
            measure(rows[r].querySelectorAll('td'));
        }
    }

    for (var t3 = 0; t3 < tables.length; t3++) {
        tables[t3].style.width = previousWidths[t3];

        var cols = tables[t3].querySelectorAll('colgroup col');
        for (var c = 0; c < cols.length && c < maxWidths.length; c++) {
            if (c === FLEX_COLUMN_INDEX) continue;
            if (maxWidths[c]) cols[c].style.width = Math.ceil(maxWidths[c]) + 'px';
        }
        // table-layout: fixed только теперь, после того как ширины уже
        // измерены по естественному (сжатому) контенту — иначе браузер бы
        // измерял уже "зажатые" фиксированной раскладкой ячейки. Колонка
        // "Название" остаётся без явной ширины и забирает весь остаток.
        tables[t3].style.tableLayout = 'fixed';
    }
}

document.addEventListener('DOMContentLoaded', alignTicketTables);
