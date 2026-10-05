(function () {
    function buildDefaultTrigger(select) {
        var trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = select.className + ' gt-select-trigger';
        trigger.disabled = select.disabled;
        trigger.innerHTML =
            '<span class="gt-select-trigger-label"></span>' +
            '<svg class="gt-select-trigger-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg>';
        select.insertAdjacentElement('afterend', trigger);
        return trigger;
    }

    function enhanceSelect(select) {
        if (select.dataset.gtEnhanced || select.multiple) return;
        if (select.offsetParent === null) return;
        select.dataset.gtEnhanced = '1';

        var chip = select.closest('.gt-avatar-select-chip, .gt-form-select-chip');
        var trigger = chip || buildDefaultTrigger(select);
        var labelEl = trigger.querySelector('.gt-select-trigger-label');

        select.classList.add('gt-select-native');
        if (!chip) {
            trigger.setAttribute('tabindex', select.disabled ? '-1' : '0');
        } else if (!trigger.hasAttribute('tabindex')) {
            trigger.setAttribute('tabindex', '0');
        }
        trigger.setAttribute('role', 'button');
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        var panel = null;
        var items = [];

        function syncLabel() {
            if (!labelEl) return;
            var opt = select.options[select.selectedIndex];
            labelEl.textContent = opt ? opt.textContent : '';
        }

        function setActive(el) {
            items.forEach(function (it) { it.classList.remove('is-active'); });
            if (el) {
                el.classList.add('is-active');
                el.scrollIntoView({ block: 'nearest' });
            }
        }

        function closePanel() {
            if (!panel) return;
            panel.remove();
            panel = null;
            items = [];
            trigger.setAttribute('aria-expanded', 'false');
            document.removeEventListener('mousedown', onDocMouseDown, true);
            window.removeEventListener('scroll', closePanel, true);
            window.removeEventListener('resize', closePanel);
            document.removeEventListener('keydown', onPanelKeydown, true);
        }

        function onDocMouseDown(e) {
            if (panel && !panel.contains(e.target) && !trigger.contains(e.target)) {
                closePanel();
            }
        }

        function choose(li) {
            var value = li.getAttribute('data-value');
            if (select.value !== value) {
                select.value = value;
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            syncLabel();
            closePanel();
            trigger.focus();
        }

        function onPanelKeydown(e) {
            if (!panel) return;
            var activeIdx = items.findIndex(function (it) { return it.classList.contains('is-active'); });
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setActive(items[Math.min(items.length - 1, activeIdx + 1)]);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setActive(items[Math.max(0, activeIdx - 1)]);
            } else if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                if (items[activeIdx] && !items[activeIdx].classList.contains('is-disabled')) choose(items[activeIdx]);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                closePanel();
                trigger.focus();
            } else if (e.key === 'Tab') {
                closePanel();
            }
        }

        function positionPanel() {
            var rect = trigger.getBoundingClientRect();
            var maxHeight = 280;
            var spaceBelow = window.innerHeight - rect.bottom - 12;
            var spaceAbove = rect.top - 12;
            panel.style.left = Math.round(rect.left) + 'px';
            panel.style.minWidth = Math.round(rect.width) + 'px';
            if (spaceBelow < 160 && spaceAbove > spaceBelow) {
                panel.style.bottom = Math.round(window.innerHeight - rect.top + 6) + 'px';
                panel.style.top = 'auto';
                panel.style.maxHeight = Math.min(maxHeight, spaceAbove) + 'px';
            } else {
                panel.style.top = Math.round(rect.bottom + 6) + 'px';
                panel.style.bottom = 'auto';
                panel.style.maxHeight = Math.min(maxHeight, spaceBelow) + 'px';
            }
        }

        function openPanel() {
            if (select.disabled) return;
            if (panel) { closePanel(); return; }

            panel = document.createElement('div');
            panel.className = 'gt-select-panel';
            panel.setAttribute('role', 'listbox');

            items = [];
            Array.prototype.forEach.call(select.options, function (opt) {
                var li = document.createElement('div');
                li.className = 'gt-select-option';
                li.setAttribute('role', 'option');
                li.setAttribute('data-value', opt.value);
                li.textContent = opt.textContent;
                if (opt.disabled) li.classList.add('is-disabled');
                if (opt.value === select.value) li.classList.add('is-selected');
                li.addEventListener('click', function () {
                    if (!opt.disabled) choose(li);
                });
                li.addEventListener('mouseenter', function () { setActive(li); });
                panel.appendChild(li);
                items.push(li);
            });

            document.body.appendChild(panel);
            positionPanel();
            setActive(panel.querySelector('.is-selected') || items[0]);
            trigger.setAttribute('aria-expanded', 'true');

            setTimeout(function () {
                document.addEventListener('mousedown', onDocMouseDown, true);
                window.addEventListener('scroll', closePanel, true);
                window.addEventListener('resize', closePanel);
                document.addEventListener('keydown', onPanelKeydown, true);
            }, 0);
        }

        trigger.addEventListener('click', function (e) {
            e.preventDefault();
            openPanel();
        });
        trigger.addEventListener('keydown', function (e) {
            if (!panel && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault();
                openPanel();
            }
        });

        syncLabel();
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('select').forEach(enhanceSelect);
    });
})();
