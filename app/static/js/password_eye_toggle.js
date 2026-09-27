function setupPasswordEyeToggle(inputId, btnId) {
    var input = document.getElementById(inputId);
    var btn = document.getElementById(btnId);
    if (!input || !btn) return;
    var showing = false;

    function apply() {
        input.type = showing ? 'text' : 'password';
        btn.querySelector('.gt-eye-off').style.display = showing ? 'none' : '';
        btn.querySelector('.gt-eye-on').style.display = showing ? '' : 'none';
        btn.title = showing ? 'Скрыть пароль' : 'Показать пароль';
    }

    btn.addEventListener('click', function () {
        showing = !showing;
        apply();
    });

    // Поле пароля в формах редактирования специально остаётся пустым
    // ("оставьте пустым, чтобы не менять") — показывать в таком случае
    // нечего, кнопка глаза выключена, пока пользователь не начнёт печатать.
    function syncDisabled() {
        btn.disabled = !input.value;
        if (!input.value && showing) {
            showing = false;
            apply();
        }
    }
    input.addEventListener('input', syncDisabled);
    syncDisabled();
}
