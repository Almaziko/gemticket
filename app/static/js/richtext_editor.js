function setupRichTextEditor(editorSelector, hiddenSelector, toolbarSelector) {
    var editor = document.querySelector(editorSelector);
    var hidden = document.querySelector(hiddenSelector);
    if (!editor || !hidden) return;

    function sync() {
        hidden.value = editor.innerHTML;
    }

    editor.addEventListener('input', sync);
    sync();

    var toolbar = toolbarSelector ? document.querySelector(toolbarSelector) : null;
    if (toolbar) {
        var buttons = toolbar.querySelectorAll('[data-cmd]');
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].addEventListener('click', function (e) {
                e.preventDefault();
                var cmd = this.getAttribute('data-cmd');
                editor.focus();
                if (cmd === 'createLink') {
                    var url = window.prompt('Введите ссылку (с http:// или https://):');
                    if (!url) return;
                    document.execCommand('createLink', false, url);
                } else {
                    document.execCommand(cmd, false, null);
                }
                sync();
            });
        }
    }

    var form = editor.closest('form');
    if (form) {
        form.addEventListener('submit', sync);
    }
}
