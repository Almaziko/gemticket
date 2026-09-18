document.addEventListener('DOMContentLoaded', function () {
    var inputs = document.querySelectorAll('input[type="date"][data-empty-text]');
    for (var i = 0; i < inputs.length; i++) {
        (function (input) {
            var wrap = document.createElement('div');
            wrap.className = 'date-field-wrap';
            input.parentNode.insertBefore(wrap, input);
            wrap.appendChild(input);

            var overlay = document.createElement('span');
            overlay.className = 'date-field-placeholder';
            overlay.textContent = input.getAttribute('data-empty-text');
            overlay.setAttribute('aria-hidden', 'true');
            wrap.appendChild(overlay);

            function updateOverlay() {
                var empty = !input.value;
                overlay.hidden = !empty;
                // Пустой <input type="date"> в Chrome сам рисует сегменты
                // "дд.мм.гггг" — без этого они накладывались бы на наш
                // оверлей нечитаемой кашей. Прячем их (только текст, не
                // саму иконку календаря) пока поле пустое и не в фокусе.
                input.classList.toggle('date-empty', empty);
            }

            input.addEventListener('focus', function () {
                overlay.hidden = true;
                input.classList.remove('date-empty');
            });
            input.addEventListener('blur', updateOverlay);
            input.addEventListener('input', updateOverlay);
            input.addEventListener('change', updateOverlay);
            updateOverlay();
        })(inputs[i]);
    }
});
