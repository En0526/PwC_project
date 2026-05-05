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

    function fmtTaiwanTime(value) {
        if (!value) return '';
        var date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString('zh-TW', {
            timeZone: 'Asia/Taipei',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        });
    }

    function init() {
        const listEl = qs('sub-list');
        const form = qs('form-add-sub');
        const presetEl = qs('preset-list');
        const intervalSelect = qs('sub-interval');
        const intervalCustomInput = qs('sub-interval-custom');
        const notifEl = qs('notif-list');
        const expandLink = qs('expand-notifications');
        var notificationsExpanded = false;

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
                    var lastCheck = s.last_checked_at ? fmtTaiwanTime(s.last_checked_at) : '尚未檢查';
                    var lastChange = s.last_changed_at ? fmtTaiwanTime(s.last_changed_at) : '-';
                    var sourceLabel = s.last_check_source ? ('　來源：' + escapeHtml(s.last_check_source)) : '';
                    return (
                        '<div class="sub-card" data-id="' + s.id + '">' +
                        '<h3>' + (s.name || '未命名') + '</h3>' +
                        '<div class="url">' + escapeHtml(s.url) + '</div>' +
                        (s.watch_description ? '<div class="meta">關注：' + escapeHtml(s.watch_description.slice(0, 80)) + (s.watch_description.length > 80 ? '…' : '') + '</div>' : '') +
                        '<div class="meta">頻率：' + escapeHtml(s.check_interval_label || fmtInterval(s.check_interval_minutes || 30)) + '　上次檢查：' + lastCheck + '　有變更：' + lastChange + sourceLabel + '</div>' +
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
                return;
            }
        });

        function loadPresets() {
        if (!presetEl) return;
        fetch('/api/presets', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var presets = (data && data.presets) ? data.presets : [];
                presets.push({
                    id: '__stdtime_test__',
                    name: '中原標準時間 WebClock 測試',
                    url: 'https://www.stdtime.gov.tw/home/WebClock',
                    watch_description: '本機時間（client time）與 server time 測試',
                    check_interval_minutes: 1,
                    check_interval_label: '每30秒',
                    frequency: '測試清單'
                });
                syncIntervalOptionsFromPresets(presets);

                // group by frequency
                var groups = {};
                presets.forEach(function (p) {
                    var k = p.frequency || '其他';
                    if (!groups[k]) groups[k] = [];
                    groups[k].push(p);
                });
                var order = ['業師提供', '每日更新', '動態網站', '不定時更新', '每月更新', '每季更新', '測試清單', '其他'];
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
                                '<div class="meta">建議頻率：' + escapeHtml(p.check_interval_label || fmtInterval(p.check_interval_minutes)) + '</div>' +
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
                presetEl.innerHTML = '<p class="meta">無法載入推薦清單。</p>';
            });
    }

    function addFromPreset(preset, btn) {
        btn.disabled = true;
        btn.textContent = '加入中…';
        submitSubscription({
            url: preset.url,
            name: preset.name,
            watch_description: preset.watch_description || null,
            check_interval_minutes: preset.check_interval_minutes
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

    function submitSubscription(payload) {
        return fetch('/api/subscriptions', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (r) {
            return r.json().then(function (d) {
                if (r.ok || r.status === 201) return d;
                if (r.status === 409 && d && d.requires_confirmation) {
                    var ok = confirm((d.error || '已存在相同追蹤。') + '\n\n按「確定」仍要加入，按「取消」放棄。');
                    if (!ok) throw new Error('已取消新增');
                    var forced = Object.assign({}, payload, { force_create: true });
                    return fetch('/api/subscriptions', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(forced)
                    }).then(function (r2) {
                        return r2.json().then(function (d2) {
                            if (!r2.ok) throw new Error(d2.error || '新增失敗');
                            return d2;
                        });
                    });
                }
                throw new Error(d.error || '新增失敗');
            });
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

    function cleanNotificationSummary(text) {
        var lines = (text || '').split('\n');
        var cleaned = [];
        var skipRemovalBlock = false;
        lines.forEach(function (line) {
            var trimmed = line.trim();
            var isSeparator = /^-{3,}$/.test(trimmed);
            var isRemovalHeader = (
                trimmed.indexOf('移除內容') === 0 ||
                trimmed.indexOf('移除資訊') === 0 ||
                trimmed.indexOf('移除新聞') === 0 ||
                trimmed.indexOf('移除項目') === 0 ||
                trimmed.indexOf('本期移除項目') === 0 ||
                trimmed.indexOf('關注重點移除') === 0
            );
            if (trimmed.indexOf('關注條件') === 0 || trimmed.indexOf('本次移除') === 0) {
                return;
            }
            if (isRemovalHeader) {
                skipRemovalBlock = true;
                if (cleaned.length && /^-{3,}$/.test(cleaned[cleaned.length - 1].trim())) {
                    cleaned.pop();
                }
                return;
            }
            if (skipRemovalBlock) {
                if (isSeparator) {
                    skipRemovalBlock = false;
                }
                return;
            }
            cleaned.push(line);
        });
        while (cleaned.length && /^-{3,}$/.test(cleaned[cleaned.length - 1].trim())) {
            cleaned.pop();
        }
        return cleaned.join('\n');
    }

    function renderNotificationCard(n) {
        var created = fmtTaiwanTime(n.created_at);
        var className = n.is_read ? 'notif-card read' : 'notif-card unread';
        var messageText = n.message || '';
        if (n.diff_summary && messageText.indexOf('有更新：') !== -1) {
            messageText = messageText.split('有更新：')[0] + '有更新';
        }
        var diffHtml = '';
        if (n.diff_summary) {
            diffHtml =
                '<div class="notif-diff">' +
                '<div class="notif-diff-title">差異摘要</div>' +
                '<pre class="notif-diff-content">' + escapeHtml(cleanNotificationSummary(n.diff_summary)) + '</pre>' +
                '</div>';
        }
        return (
            '<div class="' + className + '" data-id="' + n.id + '">' +
            '<div class="message">' + escapeHtml(messageText) + '</div>' +
            diffHtml +
            '<div class="meta">時間：' + created + '</div>' +
            '<div class="actions">' +
            (!n.is_read ? '<button type="button" class="btn-mark-read">標記已讀</button>' : '') +
            '<button type="button" class="btn-delete-notif danger">刪除</button>' +
            '</div>' +
            '</div>'
        );
    }

    function loadNotifications() {
        if (!notifEl) return;
        if (notificationsExpanded) {
            loadAllNotifications();
            return;
        }
        fetch('/api/subscriptions/notifications', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var notifications = (data && data.notifications) ? data.notifications : [];
                var hasMore = data && data.has_more;
                var mailStatusEl = qs('mail-status');

                if (mailStatusEl) {
                    if (!data || !data.last_email_sent_at) {
                        mailStatusEl.textContent = '最近寄信：尚無紀錄';
                    } else {
                        var t = fmtTaiwanTime(data.last_email_sent_at);
                        if (data.last_email_success === true) {
                            mailStatusEl.textContent = '最近寄信：' + t + '（成功）';
                        } else if (data.last_email_success === false) {
                            var reason = data.last_email_error ? ('，原因：' + data.last_email_error) : '';
                            mailStatusEl.textContent = '最近寄信：' + t + '（失敗' + reason + '）';
                        } else {
                            mailStatusEl.textContent = '最近寄信：' + t;
                        }
                    }
                }

                var unreadBadge = qs('unread-count');
                if (unreadBadge) {
                    if (data && typeof data.unread_count === 'number' && data.unread_count > 0) {
                        unreadBadge.textContent = '(' + data.unread_count + ' 未讀)';
                        unreadBadge.style.display = 'inline';
                    } else {
                        unreadBadge.style.display = 'none';
                    }
                }

                if (!notifications.length) {
                    notifEl.innerHTML = '<p class="meta">目前沒有通知。</p>';
                    if (expandLink) expandLink.style.display = 'none';
                    return;
                }

                notifEl.innerHTML = notifications.map(renderNotificationCard).join('');

                if (expandLink) {
                    expandLink.style.display = hasMore ? 'block' : 'none';
                    expandLink.textContent = '展開全部';
                }

                notifEl.querySelectorAll('.btn-mark-read').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.notif-card').dataset.id, 10);
                        markNotificationRead(id, btn.closest('.notif-card'));
                    });
                });

                notifEl.querySelectorAll('.btn-delete-notif').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.notif-card').dataset.id, 10);
                        deleteNotification(id, btn.closest('.notif-card'));
                    });
                });
            })
            .catch(function () {
                notifEl.innerHTML = '<p class="error">載入通知失敗。</p>';
            });
    }

    function loadAllNotifications() {
        if (!notifEl) return;
        notificationsExpanded = true;
        fetch('/api/subscriptions/notifications/all', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var notifications = (data && data.notifications) ? data.notifications : [];

                if (!notifications.length) {
                    notifEl.innerHTML = '<p class="meta">目前沒有通知。</p>';
                    return;
                }

                notifEl.innerHTML = notifications.map(renderNotificationCard).join('');

                if (expandLink) {
                    expandLink.style.display = 'block';
                    expandLink.textContent = '收起';
                }

                notifEl.querySelectorAll('.btn-mark-read').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.notif-card').dataset.id, 10);
                        markNotificationRead(id, btn.closest('.notif-card'));
                    });
                });

                notifEl.querySelectorAll('.btn-delete-notif').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var id = parseInt(btn.closest('.notif-card').dataset.id, 10);
                        deleteNotification(id, btn.closest('.notif-card'));
                    });
                });
            })
            .catch(function () {
                notifEl.innerHTML = '<p class="error">載入所有通知失敗。</p>';
            });
    }

    function markNotificationRead(id, cardEl) {
        fetch('/api/subscriptions/notifications/' + id + '/read', {
            method: 'POST',
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json(); })
            .then(function () {
                cardEl.classList.remove('unread');
                cardEl.classList.add('read');
                var btn = cardEl.querySelector('.btn-mark-read');
                if (btn) btn.remove();
            })
            .catch(function () {
                alert('標記已讀失敗。');
            });
    }

    function deleteNotification(id, cardEl) {
        if (!confirm('確定要刪除此通知？')) return;

        fetch('/api/subscriptions/notifications/' + id, {
            method: 'DELETE',
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json(); })
            .then(function () {
                cardEl.remove();
                if (notifEl.children.length === 0) {
                    loadNotifications();
                }
            })
            .catch(function () {
                alert('刪除通知失敗。');
            });
    }

    function deleteAllNotifications() {
        if (!confirm('確定要刪除所有通知嗎？此動作無法復原。')) return;

        fetch('/api/subscriptions/notifications/all', {
            method: 'DELETE',
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data && data.ok) {
                    alert('已刪除所有通知（共 ' + (data.deleted_count || 0) + ' 則）。');
                    loadNotifications();
                } else {
                    alert('刪除所有通知失敗。');
                }
            })
            .catch(function () {
                alert('刪除所有通知失敗，請確認後端有在跑。');
            });
    }

    function checkOne(id, btn) {
        if (btn) {
            btn.disabled = true;
            btn.textContent = '檢查中…';
        }
        var cardEl = btn && btn.closest ? btn.closest('.sub-card') : null;
        var controller = new AbortController();
        var timeoutId = setTimeout(function () { controller.abort(); }, 45000);
        fetch('/api/subscriptions/' + id + '/check', { method: 'POST', credentials: 'same-origin', signal: controller.signal })
            .then(function (r) {
                if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || ('HTTP ' + r.status)); });
                return r.json();
            })
            .then(function (data) {
                clearTimeout(timeoutId);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '立即檢查';
                }
                if (data && data.ok === false && data.error) {
                    var status = data.result_status || 'failed';
                    var hint = data.hint || '';
                    var retryable = (data.retryable !== false);
                    
                    // 根據失敗類型提供清晰的分類提示
                    var categoryHint = '';
                    if (status.indexOf('rss') >= 0 && status.indexOf('blocked') >= 0) {
                        categoryHint = '【反爬阻擋】RSS 源被網站拒絕';
                    } else if (status.indexOf('rss_not_found') >= 0) {
                        categoryHint = '【無 RSS Feed】此 URL 不提供 RSS';
                    } else if (status.indexOf('rss') >= 0) {
                        categoryHint = '【RSS 錯誤】無法取得或解析 RSS';
                    } else if (status.indexOf('http_403') >= 0 || status.indexOf('http_429') >= 0) {
                        categoryHint = '【反爬阻擋】網站拒絕自動訪問（' + status + '）';
                    } else if (status.indexOf('dynamic') >= 0) {
                        categoryHint = '【動態頁面】需要 JavaScript 渲染';
                    } else if (status.indexOf('timeout') >= 0) {
                        categoryHint = '【超時】無法在時限內連線';
                    }
                    
                    var lines = [];
                    if (categoryHint) lines.push(categoryHint);
                    lines.push('本次無法完成擷取（不會判定為「無更新」）。');
                    if (hint) lines.push('詳情：' + hint);
                    if (!retryable) lines.push('提醒：此狀況通常重試也無效，建議改 RSS 或瀏覽器模式。');
                    alert(lines.join('\n'));
                } else if (data && data.ok === true) {
                    if (data.changed) {
                        var diffBox = cardEl ? cardEl.querySelector('.diff-placeholder') : null;
                        if (diffBox) showDiff(id, diffBox);
                        alert('檢查完成：發現更新，已建立最新通知。');
                    }
                    else {
                        var src = data.source ? ('（來源：' + data.source + '）') : '';
                        var maybeHint = data.hint ? ('\n備註：' + data.hint) : '';
                        alert('檢查完成：無變更' + src + maybeHint);
                    }
                }
                loadSubscriptions();
                loadNotifications();
            })
            .catch(function (err) {
                clearTimeout(timeoutId);
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '立即檢查';
                }
                if (err && err.name === 'AbortError') {
                    alert('立即檢查逾時（45 秒）。\n可能網站太慢或被擋，請稍後重試。');
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
                var sourcePrefix = data && data.source ? ('來源：' + data.source + '\n\n') : '';
                boxEl.textContent = sourcePrefix + (data.diff_summary || '尚無差異可顯示。');
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

    function checkAll() {
        var btn = qs('btn-check-all');
        if (btn) {
            btn.disabled = true;
            btn.textContent = '檢查中…';
        }
        fetch('/api/subscriptions/check-all', { method: 'POST', credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '全部檢查';
                }
                if (data && data.ok) {
                    var results = Array.isArray(data.results) ? data.results : [];
                    var failed = results.filter(function (r) { return !r.ok; });
                    var byStatus = {};
                    var categories = {};
                    
                    failed.forEach(function (r) {
                        var s = r.result_status || 'failed';
                        byStatus[s] = (byStatus[s] || 0) + 1;
                        
                        // 分類
                        var cat = 'other';
                        if (s.indexOf('rss') >= 0 && s.indexOf('blocked') >= 0) {
                            cat = '反爬（RSS）';
                        } else if (s.indexOf('rss_not_found') >= 0) {
                            cat = '無RSS';
                        } else if (s.indexOf('rss') >= 0) {
                            cat = 'RSS錯誤';
                        } else if (s.indexOf('http_403') >= 0 || s.indexOf('http_429') >= 0) {
                            cat = '反爬（HTTP）';
                        } else if (s.indexOf('dynamic') >= 0) {
                            cat = '動態頁面';
                        } else if (s.indexOf('timeout') >= 0) {
                            cat = '超時';
                        }
                        categories[cat] = (categories[cat] || 0) + 1;
                    });
                    
                    var statusSummary = Object.keys(byStatus).map(function (k) {
                        return k + ' x' + byStatus[k];
                    }).join('、');
                    
                    var categorySummary = Object.keys(categories).map(function (k) {
                        return k + ' x' + categories[k];
                    }).join('、');

                    var lines = [
                        '已完成全部手動檢查：' + data.checked_count + ' 個追蹤，發現 ' + data.changed_count + ' 個更新。'
                    ];
                    if (failed.length) {
                        lines.push('其中 ' + failed.length + ' 個無法判讀/擷取，不會算成「無更新」。');
                        if (categorySummary) {
                            lines.push('失敗分類：' + categorySummary);
                        }
                        var hint = failed.find(function (r) { return r.hint; });
                        if (hint) {
                            var fullHint = hint.result_status ? ('【' + hint.result_status + '】') : '';
                            lines.push('建議：' + fullHint + hint.hint);
                        }
                    }
                    alert(lines.join('\n'));
                    loadSubscriptions();
                    loadNotifications();
                } else {
                    alert('全部檢查發生錯誤。');
                }
            })
            .catch(function () {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = '全部檢查';
                }
                alert('全部檢查失敗，請確認後端有在跑。');
            });
    }

    function deleteAll() {
        if (!confirm('確定要刪除所有追蹤項目與通知嗎？此動作無法復原。')) return;
        fetch('/api/subscriptions/all', { method: 'DELETE', credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data && data.ok) {
                    alert('已刪除全部追蹤項目。');
                    loadSubscriptions();
                    loadNotifications();
                } else {
                    alert('刪除全部失敗。');
                }
            })
            .catch(function () {
                alert('刪除全部失敗，請確認後端有在跑。');
            });
    }

        var subUrlField = qs('sub-url');
        var urlHintEl = qs('sub-url-hint');
        var urlClassifyTimer = null;
        var classifySeq = 0;

        function setUrlKindHint(text, toneClass) {
            if (!urlHintEl) return;
            urlHintEl.textContent = text || '';
            urlHintEl.className = 'sub-url-hint' + (toneClass ? ' ' + toneClass : '');
        }

        function scheduleUrlKindClassify() {
            if (!subUrlField) return;
            clearTimeout(urlClassifyTimer);
            var u = (subUrlField.value || '').trim();
            if (!u || u.length < 8 || !/^https?:\/\//i.test(u)) {
                setUrlKindHint('', '');
                return;
            }
            var mySeq = ++classifySeq;
            urlClassifyTimer = setTimeout(function () {
                fetch('/api/subscriptions/url/classify', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: u })
                })
                    .then(function (r) {
                        return r.json();
                    })
                    .then(function (data) {
                        if (mySeq !== classifySeq) return;
                        if (data.error) {
                            setUrlKindHint('', '');
                            return;
                        }
                        if (!data.ok) {
                            var w = data.hint ? '無法預覽此網址：' + data.hint + ' 仍可嘗試新增。' : '';
                            setUrlKindHint(w, 'url-hint-warn');
                            return;
                        }
                        var prefix = data.mode === 'rss' ? '【RSS】' : data.mode === 'rss_broken' ? '【RSS 異常】' : '【網頁】';
                        var extra = data.feed_title ? data.feed_title + ' — ' : '';
                        var tone =
                            data.mode === 'rss'
                                ? 'url-hint-rss'
                                : data.mode === 'rss_broken'
                                  ? 'url-hint-warn'
                                  : 'url-hint-web';
                        setUrlKindHint(prefix + extra + (data.hint || ''), tone);
                    })
                    .catch(function () {
                        if (mySeq !== classifySeq) return;
                        setUrlKindHint('', '');
                    });
            }, 550);
        }

        if (subUrlField) {
            subUrlField.addEventListener('input', scheduleUrlKindClassify);
            subUrlField.addEventListener('change', scheduleUrlKindClassify);
        }

        var btnPreview = qs('btn-preview-scrape');
        var previewEl = qs('add-preview-result');
        function runPreviewScrape() {
            if (!btnPreview || !previewEl) return;
            var url0 = (qs('sub-url').value || '').trim();
            var watch0 = (qs('sub-watch').value || '').trim() || null;
            if (!url0) {
                alert('請先填寫網址。');
                return;
            }
            btnPreview.disabled = true;
            previewEl.style.display = 'block';
            previewEl.className = 'add-preview-result meta-only';
            previewEl.textContent = '擷取中…（動態網頁可能需數十秒，會自動使用瀏覽器渲染）';
            fetch('/api/subscriptions/preview', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url0, watch_description: watch0 })
            })
                .then(function (r) {
                    return r.json();
                })
                .then(function (data) {
                    btnPreview.disabled = false;
                    if (!data.ok) {
                        previewEl.className = 'add-preview-result meta-only';
                        var lines = ['【試擷取未成功】'];
                        if (data.code) lines.push('狀態代碼：' + data.code);
                        if (data.error) lines.push(String(data.error));
                        if (data.hint) lines.push('建議：' + data.hint);
                        if (data.gemini_enabled === false) {
                            lines.push('未偵測到 GEMINI_API_KEY：新網站若無專用規則，多半只能比對整頁文字。');
                        }
                        previewEl.textContent = lines.join('\n');
                        return;
                    }
                    var diag = data.diagnostic || {};
                    var head =
                        '【試擷取成功】\n' +
                        '內容長度：' +
                        (data.content_length || 0) +
                        ' 字元\n雜湊前綴：' +
                        String(data.content_hash || '').slice(0, 16) +
                        '…\n擷取來源：' +
                        (diag.source || '?') +
                        (diag.section ? ' / 區塊：' + diag.section : '') +
                        (diag.site ? ' / 站點：' + diag.site : '') +
                        '\n信心度：' +
                        (diag.confidence != null ? diag.confidence : '—') +
                        '\n' +
                        (data.gemini_enabled ? '（目前可使用 Gemini 協助區塊擷取）\n' : '（未設定 API Key：依專用規則或整頁擷取）\n') +
                        '---\n\n';
                    previewEl.className = 'add-preview-result';
                    previewEl.textContent = head + (data.preview || '');
                })
                .catch(function () {
                    btnPreview.disabled = false;
                    previewEl.style.display = 'block';
                    previewEl.className = 'add-preview-result meta-only';
                    previewEl.textContent = '請求失敗，請確認已登入且後端（python app.py）正在執行。';
                });
        }
        if (btnPreview) {
            btnPreview.addEventListener('click', runPreviewScrape);
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
        submitSubscription({ url: url, name: name, watch_description: watch, check_interval_minutes: interval })
            .then(function (data) {
                alert('新增訂閱成功！');
                document.getElementById('sub-url').value = '';
                document.getElementById('sub-name').value = '';
                document.getElementById('sub-watch').value = '';
                document.getElementById('sub-interval').value = '1440';
                if (intervalCustomInput) intervalCustomInput.value = '';
                toggleCustomIntervalInput();
                setUrlKindHint('', '');
                var pv = qs('add-preview-result');
                if (pv) {
                    pv.style.display = 'none';
                    pv.textContent = '';
                }
                loadSubscriptions();
                if (data && data.id && confirm('要現在執行第一次檢查（建立本訂閱的基準快照）嗎？\n按取消則仍依排程稍後檢查。')) {
                    checkOne(data.id, null);
                }
            })
            .catch(function (err) {
                if (err && err.message === '已取消新增') return;
                alert('新增失敗：' + (err && err.message ? err.message : '網路或系統錯誤'));
            });
    });

    loadSubscriptions();
    loadPresets();
    loadNotifications();
    var checkAllBtn = qs('btn-check-all');
    if (checkAllBtn) {
        checkAllBtn.addEventListener('click', checkAll);
    }
    var deleteAllBtn = qs('btn-delete-all');
    if (deleteAllBtn) {
        deleteAllBtn.addEventListener('click', deleteAll);
    }
    var deleteAllNotifBtn = qs('btn-delete-all-notifications');
    if (deleteAllNotifBtn) {
        deleteAllNotifBtn.addEventListener('click', deleteAllNotifications);
    }
    if (expandLink) {
        expandLink.addEventListener('click', function () {
            if (!notificationsExpanded) {
                loadAllNotifications();
            } else {
                notificationsExpanded = false;
                loadNotifications();
                expandLink.textContent = '展開全部';
            }
        });
    }
    if (intervalSelect) {
        intervalSelect.addEventListener('change', toggleCustomIntervalInput);
    }

    // ============ RSS 功能事件監聽 ============
    var btnDetectRss = qs('btn-detect-rss');
    var btnValidateRss = qs('btn-validate-rss');
    var rssResultDiv = qs('rss-result');
    var rssResultContent = qs('rss-result-content');

    if (btnDetectRss) {
        btnDetectRss.addEventListener('click', function () {
            var url = (qs('rss-detect-url').value || '').trim();
            if (!url) {
                alert('請輸入網址');
                return;
            }
            btnDetectRss.disabled = true;
            btnDetectRss.textContent = '檢測中…';
            fetch('/api/subscriptions/rss/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ url: url })
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                btnDetectRss.disabled = false;
                btnDetectRss.textContent = '🔍 偵測 RSS';
                var html = '<strong>' + data.message + '</strong>';
                if (data.feeds && data.feeds.length > 0) {
                    html += '<ul style="margin-top: 12px; list-style: none; padding: 0;">';
                    data.feeds.forEach(function (feed) {
                        var isGuess = feed.is_guess ? ' <span style="color: #999; font-size: 0.9em;">(推測)</span>' : '';
                        html += '<li style="padding: 8px; background: #fff; border: 1px solid #ddd; margin-bottom: 6px; border-radius: 3px;">';
                        html += '<strong>' + feed.title + '</strong><br>';
                        html += '<code style="color: #0066cc; font-size: 0.85em; word-break: break-all;">' + feed.url + '</code>' + isGuess;
                        html += '<br><button type="button" class="btn-use-feed" data-url="' + feed.url + '" style="margin-top: 6px; font-size: 0.9em; padding: 4px 8px; background: #0066cc; color: #fff; border: none; border-radius: 3px; cursor: pointer;">使用此 RSS</button>';
                        html += '</li>';
                    });
                    html += '</ul>';
                }
                rssResultContent.innerHTML = html;
                rssResultDiv.style.display = 'block';

                // 綁定「使用此 RSS」按鈕
                document.querySelectorAll('.btn-use-feed').forEach(function (btn) {
                    btn.addEventListener('click', function () {
                        var feedUrl = btn.getAttribute('data-url');
                        qs('sub-url').value = feedUrl;
                        qs('sub-watch').value = '';  // RSS 通常監測整個 feed
                        alert('已自動填入 RSS 網址，可立即新增。');
                    });
                });
            })
            .catch(function (err) {
                btnDetectRss.disabled = false;
                btnDetectRss.textContent = '🔍 偵測 RSS';
                rssResultContent.innerHTML = '<strong style="color: red;">檢測失敗：' + (err && err.message ? err.message : '網路或系統錯誤') + '</strong>';
                rssResultDiv.style.display = 'block';
            });
        });
    }

    if (btnValidateRss) {
        btnValidateRss.addEventListener('click', function () {
            var url = (qs('rss-validate-url').value || '').trim();
            if (!url) {
                alert('請輸入 RSS 網址');
                return;
            }
            btnValidateRss.disabled = true;
            btnValidateRss.textContent = '驗證中…';
            fetch('/api/subscriptions/rss/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ url: url })
            })
            .then(function (r) {
                var status = r.status;
                return r.json().then(function (data) {
                    return { status: status, data: data };
                });
            })
            .then(function (result) {
                btnValidateRss.disabled = false;
                btnValidateRss.textContent = '✓ 驗證';
                var data = result.data;
                var status = result.status;
                var html = '';
                
                // 處理 RSS 被阻擋的情況（202 建議改用 HTML）
                if (status === 202 && data.suggestion && data.suggestion.type === 'use_html_instead') {
                    html = '<strong style="color: orange;">⚠️ RSS 被反爬阻擋</strong><br>';
                    html += '<p style="font-size: 0.9em; color: #555;">' + data.message + '</p>';
                    html += '<p style="font-size: 0.9em; color: #555;"><strong>建議方案：</strong>監測主頁面 HTML，系統將自動偵測內容變化。</p>';
                    html += '<button type="button" class="btn-use-homepage" data-url="' + data.suggestion.homepage_url + '" style="margin-top: 8px; font-size: 0.9em; padding: 8px 14px; background: #ff9800; color: #fff; border: none; border-radius: 3px; cursor: pointer;">📄 使用主頁面 HTML 監測</button>';
                    html += ' <button type="button" class="btn-use-custom-rss" data-url="' + url + '" style="margin-left: 6px; font-size: 0.9em; padding: 8px 14px; background: #2196F3; color: #fff; border: none; border-radius: 3px; cursor: pointer;">或輸入其他 RSS</button>';
                } else if (data.valid) {
                    html = '<strong style="color: green;">✓ ' + data.message + '</strong>';
                    if (data.title) {
                        html += '<br>標題：<strong>' + data.title + '</strong>';
                    }
                    if (data.type) {
                        html += '<br>類型：<strong>' + data.type.toUpperCase() + '</strong>';
                    }
                    if (data.items_count) {
                        html += '<br>項目數：<strong>' + data.items_count + '</strong>';
                    }
                    html += '<br><button type="button" class="btn-use-validated-feed" data-url="' + url + '" style="margin-top: 12px; font-size: 0.9em; padding: 6px 12px; background: #28a745; color: #fff; border: none; border-radius: 3px; cursor: pointer;">使用此 RSS 網址</button>';
                } else {
                    html = '<strong style="color: red;">✗ ' + data.message + '</strong>';
                }
                
                rssResultContent.innerHTML = html;
                rssResultDiv.style.display = 'block';

                // 綁定「使用此 RSS 網址」按鈕
                var useBtn = document.querySelector('.btn-use-validated-feed');
                if (useBtn) {
                    useBtn.addEventListener('click', function () {
                        var feedUrl = useBtn.getAttribute('data-url');
                        qs('sub-url').value = feedUrl;
                        qs('sub-watch').value = '';
                        alert('已自動填入 RSS 網址，可立即新增。');
                    });
                }
                
                // 綁定「使用主頁面 HTML」按鈕
                var homeBtn = document.querySelector('.btn-use-homepage');
                if (homeBtn) {
                    homeBtn.addEventListener('click', function () {
                        var homepageUrl = homeBtn.getAttribute('data-url');
                        qs('sub-url').value = homepageUrl;
                        qs('sub-watch').value = '更新內容';  // 自動填入監測描述
                        alert('已自動填入主頁面 URL 和監測內容「更新內容」，系統將監測此頁面的 HTML 變化。');
                    });
                }
                
                // 綁定「輸入其他 RSS」按鈕
                var customBtn = document.querySelector('.btn-use-custom-rss');
                if (customBtn) {
                    customBtn.addEventListener('click', function () {
                        alert('您可以嘗試找到其他 RSS 源，或改用主頁面 HTML 監測。');
                    });
                }
            })
            .catch(function (err) {
                btnValidateRss.disabled = false;
                btnValidateRss.textContent = '✓ 驗證';
                rssResultContent.innerHTML = '<strong style="color: red;">驗證失敗：' + (err && err.message ? err.message : '網路或系統錯誤') + '</strong>';
                rssResultDiv.style.display = 'block';
            });
        });
    }

    toggleCustomIntervalInput();
    setInterval(loadSubscriptions, 10000);
    setInterval(loadNotifications, 30000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
