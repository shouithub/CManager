/* Office 在线预览共享脚本：驱动 _office_preview_modal.html 组件。 */
(function () {
    'use strict';

    var modal = document.getElementById('officePreviewModal');
    var frame = document.getElementById('officePreviewFrame');
    var title = document.getElementById('officePreviewTitle');
    var closeBtn = document.getElementById('officePreviewClose');
    if (!modal || !frame || !title || !closeBtn) return;

    function open(url, name) {
        if (!url) return;
        title.textContent = name || '在线预览';
        frame.src = url;
        modal.classList.add('active');
        modal.setAttribute('aria-hidden', 'false');
        closeBtn.focus();
    }

    function close() {
        modal.classList.remove('active');
        modal.setAttribute('aria-hidden', 'true');
        frame.src = 'about:blank';
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('.js-office-preview');
        if (button) {
            open(button.dataset.officePreviewUrl, button.dataset.officeFileName);
            return;
        }
        if (event.target.closest('#officePreviewClose') || event.target === modal) {
            close();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') close();
    });
})();
