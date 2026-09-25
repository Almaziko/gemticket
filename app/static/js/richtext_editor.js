function setupRichTextEditor(editorSelector, hiddenSelector, toolbarSelector, submitSelector) {
    var editor = document.querySelector(editorSelector);
    var hidden = document.querySelector(hiddenSelector);
    if (!editor || !hidden) return;

    // Без этого Chrome по Enter заворачивает новый абзац в <div> (а Firefox
    // вообще ограничивается голым <br>), и у <div> нет отступа снизу — два
    // абзаца, набранные через Enter+Enter, визуально слипались в один без
    // видимого пропуска строки. Приводим оба браузера к <p> — под него уже
    // есть margin-bottom в .richtext-content (см. style.css).
    try { document.execCommand('defaultParagraphSeparator', false, 'p'); } catch (err) { /* не критично */ }

    // Если редактор стартует пустым, первый набранный текст ложится прямо в
    // contenteditable-контейнер без обёртки в <p> — и самый первый Enter в
    // такой ситуации браузер трактует не как разрыв абзаца, а как обычный
    // перенос строки (<br>), в отличие от всех следующих Enter, которые уже
    // корректно создают новый <p>. Подкладываем пустой абзац заранее, чтобы
    // курсор с самого начала оказывался внутри <p>, и первый Enter вёл себя
    // так же, как и остальные.
    if (editor.innerHTML.trim() === '') {
        editor.innerHTML = '<p><br></p>';
    }

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

    // По умолчанию браузер при вставке обычного текста (Ctrl+V, скопированного
    // не из HTML-источника) вставляет его буквально как текстовый узел с
    // символами перевода строки внутри — а HTML такие переносы не показывает
    // (схлопывает как обычный пробел), поэтому вставленные "два абзаца" на
    // экране сливались в один. Разбираем текст сами: пустая строка — новый
    // абзац, одиночный перенос внутри абзаца — <br>.
    editor.addEventListener('paste', function (e) {
        if (!e.clipboardData) return;
        var text = e.clipboardData.getData('text/plain');
        if (!text) return;
        e.preventDefault();
        document.execCommand('insertHTML', false, pastedTextToHtml(text));
        sync();
    });

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function pastedTextToHtml(text) {
        var normalized = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
        var paragraphs = normalized.split(/\n{2,}/);
        return paragraphs.map(function (p) {
            var withBr = escapeHtml(p).replace(/\n/g, '<br>');
            return '<p>' + (withBr || '<br>') + '</p>';
        }).join('');
    }

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
