document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-group-toggle]');
    if (!btn) return;
    var expanded = btn.getAttribute('aria-expanded') !== 'false';
    btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
});
