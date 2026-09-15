function setupAttachmentsPicker(fileInputSelector, listSelector) {
    var input = document.querySelector(fileInputSelector);
    var list = document.querySelector(listSelector);
    if (!input || !list) return;

    var files = [];

    function render() {
        list.innerHTML = '';
        files.forEach(function (file, index) {
            var item = document.createElement('div');
            item.className = 'd-flex align-items-center justify-content-between border rounded px-2 py-1 mb-1 small bg-white';

            var label = document.createElement('span');
            label.textContent = file.name + ' (' + Math.max(1, Math.round(file.size / 1024)) + ' КБ)';

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-outline-danger py-0 px-2';
            btn.textContent = '×';
            btn.title = 'Убрать файл';
            btn.addEventListener('click', function () {
                files.splice(index, 1);
                sync();
            });

            item.appendChild(label);
            item.appendChild(btn);
            list.appendChild(item);
        });
    }

    function sync() {
        var dt = new DataTransfer();
        files.forEach(function (f) { dt.items.add(f); });
        input.files = dt.files;
        render();
    }

    input.addEventListener('change', function () {
        files = Array.prototype.slice.call(input.files);
        render();
    });
}
