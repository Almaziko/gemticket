function alignTicketTables() {
    var tables = document.querySelectorAll('table.ticket-table');
    if (tables.length < 2) return;

    var columnCount = 0;
    for (var t = 0; t < tables.length; t++) {
        var headerCells = tables[t].querySelectorAll('thead th');
        if (headerCells.length > columnCount) columnCount = headerCells.length;
    }
    if (!columnCount) return;

    var maxWidths = new Array(columnCount).fill(0);

    function measure(cells) {
        for (var i = 0; i < cells.length; i++) {
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
        var cols = tables[t3].querySelectorAll('colgroup col');
        for (var c = 0; c < cols.length && c < maxWidths.length; c++) {
            if (maxWidths[c]) cols[c].style.width = Math.ceil(maxWidths[c]) + 'px';
        }
        // table-layout: fixed только теперь, после того как ширины уже
        // измерены по естественному (auto) контенту — иначе браузер бы
        // измерял уже "зажатые" фиксированной раскладкой ячейки.
        tables[t3].style.tableLayout = 'fixed';
    }
}

document.addEventListener('DOMContentLoaded', alignTicketTables);
