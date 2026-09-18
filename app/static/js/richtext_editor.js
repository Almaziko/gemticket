function setupRichTextEditor(editorSelector, hiddenSelector, toolbarSelector, submitSelector) {
    var editor = document.querySelector(editorSelector);
    var hidden = document.querySelector(hiddenSelector);
    if (!editor || !hidden) return;

    function isEmpty() {
        var nbsp = String.fromCharCode(160);
        var text = editor.textContent.split(nbsp).join(' ').trim();
        return text.length === 0 && !editor.querySelector('img');
    }

    function sync() {
        hidden.value = editor.innerHTML;
        // Ищем кнопку каждый раз, а не один раз при инициализации: инлайновый
        // скрипт выполняется сразу после разметки редактора, а сама кнопка
        // "Отправить" стоит в форме ниже и на этот момент ещё не существует
        // в DOM — querySelector() при setup вернул бы null навсегда.
        var submitBtn = submitSelector ? document.querySelector(submitSelector) : null;
        if (submitBtn) submitBtn.disabled = isEmpty();
    }

    editor.addEventListener('input', sync);
    sync();

    var toolbar = toolbarSelector ? document.querySelector(toolbarSelector) : null;
    var toolbarButtons = [];
    if (toolbar) {
        toolbarButtons = toolbar.querySelectorAll('[data-cmd]');
        for (var i = 0; i < toolbarButtons.length; i++) {
            toolbarButtons[i].addEventListener('click', function (e) {
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
                updateActiveStates();
            });
        }
    }

    function updateActiveStates() {
        for (var i = 0; i < toolbarButtons.length; i++) {
            var cmd = toolbarButtons[i].getAttribute('data-cmd');
            if (cmd === 'createLink') continue;
            var active = false;
            try { active = document.queryCommandState(cmd); } catch (err) { /* браузер не поддерживает */ }
            toolbarButtons[i].classList.toggle('active', active);
        }
    }

    editor.addEventListener('keyup', updateActiveStates);
    editor.addEventListener('mouseup', updateActiveStates);
    editor.addEventListener('focus', updateActiveStates);

    var form = editor.closest('form');
    if (form) {
        form.addEventListener('submit', sync);
    }
}
