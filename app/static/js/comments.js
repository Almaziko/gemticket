document.addEventListener('click', function (e) {
    var toggleBtn = e.target.closest('[data-comment-edit-toggle]');
    if (toggleBtn) {
        var wrap = document.getElementById(toggleBtn.getAttribute('data-comment-edit-toggle'));
        if (!wrap) return;
        var display = wrap.querySelector('[data-comment-display]');
        var form = wrap.querySelector('[data-comment-edit-form]');
        if (display) display.hidden = true;
        if (form) form.hidden = false;
        return;
    }

    var cancelBtn = e.target.closest('[data-comment-edit-cancel]');
    if (cancelBtn) {
        var wrap2 = document.getElementById(cancelBtn.getAttribute('data-comment-edit-cancel'));
        if (!wrap2) return;
        var display2 = wrap2.querySelector('[data-comment-display]');
        var form2 = wrap2.querySelector('[data-comment-edit-form]');
        if (display2) display2.hidden = false;
        if (form2) form2.hidden = true;
    }
});

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-edit-deadline]').forEach(function (btn) {
        var deadline = new Date(btn.getAttribute('data-edit-deadline')).getTime();
        var remaining = deadline - Date.now();
        if (remaining <= 0) {
            btn.remove();
            return;
        }
        setTimeout(function () { btn.remove(); }, Math.min(remaining, 2147483647));
    });

    if (location.hash.indexOf('#comment-') === 0) {
        var target = document.querySelector(location.hash);
        if (target) {
            target.classList.add('is-highlighted');
            setTimeout(function () { target.classList.remove('is-highlighted'); }, 2200);
        }
    }
});
