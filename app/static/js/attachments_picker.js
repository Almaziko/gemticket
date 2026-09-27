function setupAttachmentsPicker(fileInputSelector, listSelector, dropZoneSelector) {
    var input = document.querySelector(fileInputSelector);
    var list = document.querySelector(listSelector);
    if (!input || !list) return;

    var files = [];

    function formatSize(bytes) {
        var kb = bytes / 1024;
        return kb > 1024 ? (kb / 1024).toFixed(1) + ' МБ' : Math.max(1, Math.round(kb)) + ' КБ';
    }

    function render() {
        list.innerHTML = '';
        if (files.length) list.classList.add('gt-files');
        files.forEach(function (file, index) {
            var isImage = /^image\//.test(file.type);
            var ext = (file.name.split('.').pop() || '').toUpperCase();

            var chip = document.createElement('div');
            chip.className = 'gt-file-chip';

            var body = document.createElement('span');
            body.className = 'gt-file-link';
            body.style.cursor = 'default';

            var thumb = document.createElement('span');
            if (isImage) {
                thumb.className = 'gt-file-thumb';
                thumb.style.backgroundImage = 'url(' + URL.createObjectURL(file) + ')';
            } else {
                thumb.className = 'gt-file-thumb gt-file-thumb-doc';
                thumb.textContent = ext;
            }

            var meta = document.createElement('span');
            meta.className = 'gt-file-meta';
            var name = document.createElement('span');
            name.className = 'gt-file-name';
            name.textContent = file.name;
            var size = document.createElement('span');
            size.className = 'gt-file-size';
            size.textContent = formatSize(file.size);
            meta.appendChild(name);
            meta.appendChild(size);

            body.appendChild(thumb);
            body.appendChild(meta);

            var removeForm = document.createElement('span');
            removeForm.className = 'gt-file-remove-form';
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'gt-file-remove';
            btn.title = 'Убрать файл';
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"></path></svg>';
            btn.addEventListener('click', function () {
                files.splice(index, 1);
                sync();
            });
            removeForm.appendChild(btn);

            chip.appendChild(body);
            chip.appendChild(removeForm);
            list.appendChild(chip);
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

    var dropZone = dropZoneSelector ? document.querySelector(dropZoneSelector) : null;
    if (dropZone) {
        dropZone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropZone.classList.add('is-dragover');
        });
        dropZone.addEventListener('dragleave', function () {
            dropZone.classList.remove('is-dragover');
        });
        dropZone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropZone.classList.remove('is-dragover');
            var dropped = (e.dataTransfer && e.dataTransfer.files) || [];
            Array.prototype.forEach.call(dropped, function (f) { files.push(f); });
            sync();
        });
    }
}
