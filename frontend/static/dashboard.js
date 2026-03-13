(function () {
    const listEl = document.getElementById('sub-list');
    const form = document.getElementById('form-add-sub');

    function loadSubscriptions() {
        fetch('/api/subscriptions', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.subscriptions || data.subscriptions.length === 0) {
                    listEl.innerHTML = '<p class="meta">尚無追蹤網站，請在上方新增。</p>';
                    return;
                }
                listEl.innerHTML = data.subscriptions.map(function (s) {
                    var lastCheck = s.last_checked_at ? new Date(s.last_checked_at).toLocaleString('zh-TW') : '尚未檢查';
                    var lastChange = s.last_changed_at ? new Date(s.last_changed_at).toLocaleString('zh-TW') : '-';
                    return (
                        '<div class="sub-card" data-id="' + s.id + '">' +
                        '<h3>' + (s.name || '未命名') + '</h3>' +
                        '<div class="url">' + escapeHtml(s.url) + '</div>' +
                        (s.watch_description ? '<div class="meta">關注：' + escapeHtml(s.watch_description.slice(0, 80)) + (s.watch_description.length > 80 ? '…' : '') + '</div>' : '') +
                        '<div class="meta">上次檢查：' + lastCheck + '　有變更：' + lastChange + '</div>' +
                        '<div class="actions">' +
                        '<button type="button" class="btn-check primary">立即檢查</button>' +
                        '<button type="button" class="btn-diff">看差異</button>' +
                        '<button type="button" class="btn-delete danger">刪除</button>' +
                        '</div>' +
                        '<div class="diff-box diff-placeholder" style="display:none;"></div>' +
                        '</div>'
                    );
                }).join('');
                listEl.querySelectorAll('.btn-check').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.sub-card').dataset.id, 10);
                        checkOne(id, btn);
                    });
                });
                listEl.querySelectorAll('.btn-diff').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.sub-card').dataset.id, 10);
                        showDiff(id, btn.closest('.sub-card').querySelector('.diff-placeholder'));
                    });
                });
                listEl.querySelectorAll('.btn-delete').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.sub-card').dataset.id, 10);
                        if (confirm('確定要刪除此追蹤？')) deleteOne(id, btn.closest('.sub-card'));
                    });
                });
            })
            .catch(function () {
                listEl.innerHTML = '<p class="meta">無法載入訂閱列表。</p>';
            });
    }

    function escapeHtml(s) {
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function checkOne(id, btn) {
        btn.disabled = true;
        btn.textContent = '檢查中…';
        fetch('/api/subscriptions/' + id + '/check', { method: 'POST', credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function () {
                btn.disabled = false;
                btn.textContent = '立即檢查';
                loadSubscriptions();
            })
            .catch(function () {
                btn.disabled = false;
                btn.textContent = '立即檢查';
            });
    }

    function showDiff(id, boxEl) {
        if (boxEl.style.display === 'block' && boxEl.dataset.loaded === '1') {
            boxEl.style.display = 'none';
            return;
        }
        boxEl.textContent = '載入中…';
        boxEl.style.display = 'block';
        boxEl.dataset.loaded = '0';
        fetch('/api/subscriptions/' + id + '/diff', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                boxEl.textContent = data.diff_summary || '尚無差異可顯示。';
                if (data.old_at && data.new_at) {
                    boxEl.textContent += '\n\n（' + data.old_at + ' → ' + data.new_at + '）';
                }
                boxEl.dataset.loaded = '1';
            })
            .catch(function () {
                boxEl.textContent = '無法取得差異。';
                boxEl.dataset.loaded = '1';
            });
    }

    function deleteOne(id, cardEl) {
        fetch('/api/subscriptions/' + id, { method: 'DELETE', credentials: 'same-origin' })
            .then(function (r) {
                if (r.ok) cardEl.remove();
                else alert('刪除失敗');
            })
            .catch(function () { alert('刪除失敗'); });
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var url = document.getElementById('sub-url').value.trim();
        var name = document.getElementById('sub-name').value.trim() || null;
        var watch = document.getElementById('sub-watch').value.trim() || null;
        fetch('/api/subscriptions', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, name: name, watch_description: watch })
        })
            .then(function (r) {
                if (r.ok || r.status === 201) {
                    document.getElementById('sub-url').value = '';
                    document.getElementById('sub-name').value = '';
                    document.getElementById('sub-watch').value = '';
                    loadSubscriptions();
                } else {
                    return r.json().then(function (d) { alert(d.error || '新增失敗'); });
                }
            })
            .catch(function () { alert('新增失敗'); });
    });

    loadSubscriptions();
})();
