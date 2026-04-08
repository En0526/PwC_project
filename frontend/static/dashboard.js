(function () {
    function qs(id) { return document.getElementById(id); }
    function fmtInterval(mins) {
        var n = Number(mins || 0);
        if (!Number.isFinite(n) || n <= 0) return '-';
        if (n < 60) return n + ' 分';
        if (n < 60 * 24) {
            var h = n / 60;
            return (Number.isInteger(h) ? h : h.toFixed(1)) + ' 小時';
        }
        if (n < 60 * 24 * 30) {
            var d = n / (60 * 24);
            return (Number.isInteger(d) ? d : d.toFixed(1)) + ' 天';
        }
        var m = n / (60 * 24 * 30);
        return (Number.isInteger(m) ? m : m.toFixed(1)) + ' 月';
    }

    function init() {
        const listEl = qs('sub-list');
        const form = qs('form-add-sub');
        const presetEl = qs('preset-list');
        const blockedEl = qs('blocked-list');
        const intervalSelect = qs('sub-interval');
        const intervalCustomInput = qs('sub-interval-custom');

        if (!listEl || !form) {
            alert('前端初始化失敗：找不到必要的 DOM（請重新整理頁面）。');
            return;
        }

        function loadSubscriptions() {
        // 若「看差異」目前有展開，避免自動刷新把內容收起
        if (listEl.querySelector('.diff-placeholder[data-open="1"]')) {
            return;
        }
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
                        '<div class="meta">頻率：' + escapeHtml(s.check_interval_label || fmtInterval(s.check_interval_minutes || 30)) + '　上次檢查：' + lastCheck + '　有變更：' + lastChange + '</div>' +
                        '<div class="actions">' +
                        '<button type="button" class="btn-check primary">立即檢查</button>' +
                        '<button type="button" class="btn-diff">看差異</button>' +
                        '<button type="button" class="btn-delete danger">刪除</button>' +
                        '</div>' +
                        '<div class="diff-box diff-placeholder" style="display:none;"></div>' +
                        '</div>'
                    );
                }).join('');
            })
            .catch(function () {
                listEl.innerHTML = '<p class="meta">無法載入訂閱列表。</p>';
            });
    }

        // 用事件委派，避免按鈕綁定失效
        listEl.addEventListener('click', function (e) {
            var checkBtn = e.target && e.target.closest ? e.target.closest('.btn-check') : null;
            if (checkBtn) {
                var card0 = checkBtn.closest('.sub-card');
                if (!card0) return;
                var id1 = parseInt(card0.dataset.id, 10);
                checkOne(id1, checkBtn);
                return;
            }

            var diffBtn = e.target && e.target.closest ? e.target.closest('.btn-diff') : null;
            if (diffBtn) {
                var card1 = diffBtn.closest('.sub-card');
                if (!card1) return;
                var id2 = parseInt(card1.dataset.id, 10);
                showDiff(id2, card1.querySelector('.diff-placeholder'));
                return;
            }

            var deleteBtn = e.target && e.target.closest ? e.target.closest('.btn-delete') : null;
            if (deleteBtn) {
                var card2 = deleteBtn.closest('.sub-card');
                if (!card2) return;
                var id3 = parseInt(card2.dataset.id, 10);
                if (confirm('確定要刪除此追蹤？')) deleteOne(id3, card2);
            }
        });

        function loadPresets() {
        if (!presetEl) return;
        fetch('/api/presets', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var presets = (data && data.presets) ? data.presets : [];
                if (!presets.length) {
                    presetEl.innerHTML = '<p class="meta">尚無預設清單。</p>';
                    return;
                }
                syncIntervalOptionsFromPresets(presets);

                // group by frequency
                var groups = {};
                presets.forEach(function (p) {
                    var k = p.frequency || '其他';
                    if (!groups[k]) groups[k] = [];
                    groups[k].push(p);
                });
                var order = ['每日更新', '動態網站', '不定時更新', '每月更新', '每季更新', '其他'];
                var categories = order.filter(function (k) { return groups[k] && groups[k].length; });
                var activeCategory = categories[0] || null;

                function renderCategoryCards() {
                    return (
                        '<div class="preset-category-grid">' +
                        categories.map(function (k) {
                            var active = (k === activeCategory) ? ' active' : '';
                            return (
                                '<button type="button" class="preset-category-card' + active + '" data-category="' + escapeHtml(k) + '">' +
                                '<div class="preset-category-title">' + escapeHtml(k) + '</div>' +
                                '<div class="meta">' + groups[k].length + ' 個網站</div>' +
                                '</button>'
                            );
                        }).join('') +
                        '</div>'
                    );
                }

                function renderCategorySites() {
                    if (!activeCategory) return '<p class="meta">尚無分類資料。</p>';
                    var list = groups[activeCategory] || [];
                    return (
                        '<div class="preset-category-sites">' +
                        '<div class="meta"><strong>' + escapeHtml(activeCategory) + '</strong></div>' +
                        list.map(function (p) {
                            var desc = p.watch_description ? ('<div class="meta">' + escapeHtml(p.watch_description) + '</div>') : '';
                            return (
                                '<div class="sub-card preset-card" data-pid="' + escapeHtml(p.id) + '">' +
                                '<h3>' + escapeHtml(p.name) + '</h3>' +
                                '<div class="url">' + escapeHtml(p.url) + '</div>' +
                                '<div class="meta">建議頻率：' + fmtInterval(p.check_interval_minutes) + '</div>' +
                                desc +
                                '<div class="actions">' +
                                '<button type="button" class="btn-add primary">一鍵加入</button>' +
                                '</div>' +
                                '</div>'
                            );
                        }).join('') +
                        '</div>'
                    );
                }

                function renderPresetPanel() {
                    presetEl.innerHTML = renderCategoryCards() + renderCategorySites();
                }

                renderPresetPanel();

                presetEl.addEventListener('click', function (e) {
                    var btn = e.target.closest('.preset-category-card');
                    if (btn) {
                        activeCategory = btn.dataset.category;
                        renderPresetPanel();
                        return;
                    }

                    var addBtn = e.target.closest('.btn-add');
                    if (addBtn) {
                        var card = addBtn.closest('.preset-card');
                        if (!card) return;
                        var pid = card.dataset.pid;
                        var preset = presets.find(function (p) { return p.id === pid; });
                        if (!preset) return;
                        addFromPreset(preset, addBtn);
                    }
                });
            })
            .catch(function () {
                presetEl.innerHTML = '<p class="meta">無法載入常用追蹤清單。</p>';
            });
    }

    function loadBlockedSites() {
        if (!blockedEl) return;
        fetch('/api/blocked-sites', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var sites = (data && data.sites) ? data.sites : [];
                if (!sites.length) {
                    blockedEl.innerHTML = '<span class="meta">尚無紀錄。</span>';
                    return;
                }
                blockedEl.innerHTML = sites.map(function (s) {
                    var at = s.last_seen_at ? new Date(s.last_seen_at).toLocaleString('zh-TW') : '-';
                    return (
                        '<div class="sub-card preset-card">' +
                        '<div class="url">' + escapeHtml(s.url) + '</div>' +
                        '<div class="meta">疑似被擋次數：' + (s.count || 0) + '　最近：' + at + '</div>' +
                        '<div class="meta">最後錯誤：' + escapeHtml(s.last_error || '-') + '</div>' +
                        '</div>'
                    );
                }).join('');
            })
            .catch(function () {
                blockedEl.innerHTML = '<span class="meta">無法載入反爬紀錄。</span>';
            });
    }

    function addFromPreset(preset, btn) {
        btn.disabled = true;
        btn.textContent = '加入中…';
        fetch('/api/subscriptions', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: preset.url,
                name: preset.name,
                watch_description: preset.watch_description || null,
                check_interval_minutes: preset.check_interval_minutes
            })
        })
            .then(function (r) {
                if (r.ok || r.status === 201) return r.json();
                return r.json().then(function (d) { throw new Error(d.error || '新增失敗'); });
            })
            .then(function () {
                btn.disabled = false;
                btn.textContent = '一鍵加入';
                loadSubscriptions();
                alert('已加入追蹤！');
            })
            .catch(function (err) {
                btn.disabled = false;
                btn.textContent = '一鍵加入';
                alert('加入失敗：' + (err && err.message ? err.message : '未知錯誤'));
            });
    }

    function syncIntervalOptionsFromPresets(presets) {
        if (!intervalSelect) return;
        var existing = {};
        Array.prototype.forEach.call(intervalSelect.options, function (opt) {
            existing[String(opt.value)] = true;
        });
        presets.forEach(function (p) {
            var mins = parseInt(p.check_interval_minutes, 10);
            if (!Number.isFinite(mins) || mins <= 0) return;
            var key = String(mins);
            if (existing[key]) return;
            var opt = document.createElement('option');
            opt.value = key;
            opt.textContent = fmtInterval(mins);
            intervalSelect.appendChild(opt);
            existing[key] = true;
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
        var controller = new AbortController();
        var timeoutId = setTimeout(function () { controller.abort(); }, 25000);
        fetch('/api/subscriptions/' + id + '/check', { method: 'POST', credentials: 'same-origin', signal: controller.signal })
            .then(function (r) {
                if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || ('HTTP ' + r.status)); });
                return r.json();
            })
            .then(function (data) {
                clearTimeout(timeoutId);
                btn.disabled = false;
                btn.textContent = '立即檢查';
                if (data && data.ok === false && data.error) {
                    alert('本次無法完成擷取（仍會更新「上次檢查」時間）：\n' + data.error);
                } else if (data && data.ok === true) {
                    if (data.changed) {
                        if (data.mail_sent === true) {
                            alert('檢查完成：有變更，且通知信已寄出');
                        } else if (data.mail_sent === false) {
                            alert('檢查完成：有變更，但通知信未寄出\n原因：' + (data.mail_error || '未知'));
                        } else {
                            alert('檢查完成：有變更');
                        }
                    }
                    else alert('檢查完成：無變更');
                }
                loadSubscriptions();
                loadBlockedSites();
            })
            .catch(function (err) {
                clearTimeout(timeoutId);
                btn.disabled = false;
                btn.textContent = '立即檢查';
                if (err && err.name === 'AbortError') {
                    alert('立即檢查逾時（25 秒）。\n可能網站太慢或被擋，請稍後重試。');
                    return;
                }
                var msg = (err && err.message) ? err.message : '未知錯誤';
                alert('立即檢查失敗：' + msg + '\n\n請確認後端有在跑（python app.py）。');
            });
    }

    function showDiff(id, boxEl) {
        if (boxEl.style.display === 'block' && boxEl.dataset.loaded === '1') {
            boxEl.style.display = 'none';
            boxEl.dataset.open = '0';
            return;
        }
        boxEl.textContent = '載入中…';
        boxEl.style.display = 'block';
        boxEl.dataset.open = '1';
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

    function toggleCustomIntervalInput() {
        if (!intervalSelect || !intervalCustomInput) return;
        var isCustom = intervalSelect.value === 'custom';
        intervalCustomInput.style.display = isCustom ? 'block' : 'none';
        if (!isCustom) intervalCustomInput.value = '';
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
        var intervalVal = document.getElementById('sub-interval').value;
        var interval = 1440;
        if (intervalVal === 'custom') {
            var customVal = intervalCustomInput ? intervalCustomInput.value.trim() : '';
            interval = customVal ? parseInt(customVal, 10) : NaN;
            if (!Number.isFinite(interval) || interval <= 0) {
                alert('請輸入有效的自訂分鐘數（需大於 0）。');
                return;
            }
        } else {
            interval = intervalVal ? parseInt(intervalVal, 10) : 1440;
        }
        fetch('/api/subscriptions', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, name: name, watch_description: watch, check_interval_minutes: interval })
        })
            .then(function (r) {
                if (r.ok || r.status === 201) {
                    console.log('新增訂閱成功', r.status);
                    alert('新增訂閱成功！');
                    document.getElementById('sub-url').value = '';
                    document.getElementById('sub-name').value = '';
                    document.getElementById('sub-watch').value = '';
                    document.getElementById('sub-interval').value = '1440';
                    if (intervalCustomInput) intervalCustomInput.value = '';
                    toggleCustomIntervalInput();
                    loadSubscriptions();
                } else {
                    return r.json().then(function (d) {
                        console.error('新增訂閱錯誤', d);
                        alert('新增失敗: ' + (d.error || '伺服器回應非預期'));
                    });
                }
            })
            .catch(function (err) {
                console.error('新增訂閱時網路或 JS 錯誤', err);
                alert('新增失敗：網路或系統錯誤，請開 F12 看 Console');
            });
    });

    loadSubscriptions();
    loadPresets();
    loadBlockedSites();
    if (intervalSelect) {
        intervalSelect.addEventListener('change', toggleCustomIntervalInput);
    }
    toggleCustomIntervalInput();
    setInterval(loadSubscriptions, 10000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
