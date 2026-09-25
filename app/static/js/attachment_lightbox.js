document.addEventListener('DOMContentLoaded', function () {
    var overlay = document.createElement('div');
    overlay.className = 'attachment-lightbox-overlay';
    overlay.innerHTML = '<span class="attachment-lightbox-close">&times;</span><img class="attachment-lightbox-img" alt="">';
    document.body.appendChild(overlay);
    var img = overlay.querySelector('.attachment-lightbox-img');

    function close() {
        overlay.classList.remove('is-open');
        img.src = '';
    }

    overlay.addEventListener('click', function (e) {
        if (e.target === overlay || e.target.classList.contains('attachment-lightbox-close')) {
            close();
        }
    });

    // Делегирование на document, а не отдельный обработчик на каждую
    // картинку: вложения рендерятся сервером в нескольких местах на
    // странице тикета (описание + каждый комментарий), одного общего
    // попапа на всех достаточно.
    document.addEventListener('click', function (e) {
        var trigger = e.target.closest('.attachment-lightbox-trigger');
        if (!trigger) return;
        e.preventDefault();
        img.src = trigger.getAttribute('href');
        overlay.classList.add('is-open');
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') close();
    });
});
