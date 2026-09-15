function setupPasteUpload(pasteTargetSelector, fileInputSelector) {
    var pasteTarget = document.querySelector(pasteTargetSelector);
    var fileInput = document.querySelector(fileInputSelector);
    if (!pasteTarget || !fileInput) return;

    pasteTarget.addEventListener('paste', function (event) {
        var clipboardData = event.clipboardData || window.clipboardData;
        if (!clipboardData || !clipboardData.items) return;

        var dt = new DataTransfer();
        for (var i = 0; i < fileInput.files.length; i++) {
            dt.items.add(fileInput.files[i]);
        }

        var added = false;
        for (var j = 0; j < clipboardData.items.length; j++) {
            var item = clipboardData.items[j];
            if (item.kind === 'file' && item.type.indexOf('image/') === 0) {
                var blob = item.getAsFile();
                if (blob) {
                    var ext = (item.type.split('/')[1] || 'png').split('+')[0];
                    var namedFile = new File([blob], 'pasted-' + Date.now() + '.' + ext, { type: item.type });
                    dt.items.add(namedFile);
                    added = true;
                }
            }
        }

        if (added) {
            fileInput.files = dt.files;
            event.preventDefault();
        }
    });
}
