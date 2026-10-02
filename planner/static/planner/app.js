(function () {
  'use strict';

  var months = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  var monthsGen = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
  var statusLabels = { waiting: 'Ожидание', received: 'Ответ', accepted: 'Принято', rejected: 'Отклонено' };
  var statusClass = { waiting: 'tag-waiting', received: 'tag-received', accepted: 'tag-accepted', rejected: 'tag-rejected' };

  // Состояние (загружается с сервера)
  var TODAY = null;
  var cal = {};
  var tasks = { major: [], projects: [], short: [], chores: [] };
  var shop = { big: [], small: [] };
  var waiting = [];

  var view = null;
  var currentKey = null;
  var editable = false;

  /* ---------- сеть ---------- */

  function getCookie(name) {
    var m = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[1]) : '';
  }

  function api(method, url, body) {
    var opts = {
      method: method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') }
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    return fetch(url, opts).then(function (r) {
      if (r.redirected) { location.reload(); return new Promise(function () {}); } // сессия истекла
      if (!r.ok) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          var err = new Error(j.error || ('HTTP ' + r.status));
          err.status = r.status;
          throw err;
        });
      }
      return r.status === 204 ? null : r.json();
    });
  }

  var toastTimer = null;
  function toast(msg) {
    var el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('show'); }, 3500);
  }
  function onErr(err) {
    toast(err && err.status === 403 && err.message
      ? err.message
      : 'Не удалось сохранить. Проверьте соединение и обновите страницу.');
  }

  // Правка текста: отправляем с небольшой задержкой, чтобы не слать запрос на каждую букву
  var timers = {};
  function patchLater(kind, id, data) {
    var k = kind + ':' + id;
    clearTimeout(timers[k]);
    timers[k] = setTimeout(function () {
      api('PATCH', '/api/' + kind + '/' + id + '/', data).catch(onErr);
    }, 400);
  }

  /* ---------- навигация ---------- */

  var navBtns = document.querySelectorAll('.nav button[data-page]');
  function showPage(id) {
    document.querySelectorAll('.page').forEach(function (p) { p.classList.remove('active'); });
    document.getElementById('page-' + id).classList.add('active');
  }
  navBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      navBtns.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      showPage(btn.dataset.page);
    });
  });

  /* ---------- календарь ---------- */

  function dateKey(y, m, d) {
    return y + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
  }
  function monthStart(key) {
    var p = key.split('-');
    return new Date(+p[0], +p[1] - 1, 1);
  }
  function progress(key) {
    var e = cal[key];
    if (!e || !e.items) return { done: 0, total: 0 };
    return {
      total: e.items.length,
      done: e.items.filter(function (i) { return i.done; }).length
    };
  }
  function ensure(key) {
    if (!cal[key]) cal[key] = { items: [] };
    return cal[key];
  }

  function renderCal() {
    var y = view.getFullYear();
    var m = view.getMonth();
    document.getElementById('monthLabel').textContent = months[m] + ' ' + y;
    var grid = document.getElementById('calendarGrid');
    grid.innerHTML = '';

    var offset = (new Date(y, m, 1).getDay() + 6) % 7;
    var days = new Date(y, m + 1, 0).getDate();

    for (var i = 0; i < offset; i++) {
      var empty = document.createElement('div');
      empty.className = 'day empty';
      grid.appendChild(empty);
    }

    for (var d = 1; d <= days; d++) {
      var key = dateKey(y, m, d);
      var cell = document.createElement('div');
      cell.className = 'day';
      if (key === TODAY) cell.classList.add('today');
      if (key > TODAY) cell.classList.add('future');

      var fill = document.createElement('div');
      fill.className = 'fill';
      var p = progress(key);
      var pct = p.total ? Math.round(p.done / p.total * 100) : 0;
      fill.style.height = pct + '%';
      if (pct >= 55) cell.classList.add('high');
      cell.appendChild(fill);

      var num = document.createElement('div');
      num.className = 'num';
      num.textContent = d;
      cell.appendChild(num);

      if (key <= TODAY) {
        (function (k, day, month, year) {
          cell.addEventListener('click', function () { openDay(k, day, month, year); });
        })(key, d, m, y);
      }
      grid.appendChild(cell);
    }
  }

  document.getElementById('prevMonth').addEventListener('click', function () {
    view.setMonth(view.getMonth() - 1);
    renderCal();
  });
  document.getElementById('nextMonth').addEventListener('click', function () {
    view.setMonth(view.getMonth() + 1);
    renderCal();
  });
  document.getElementById('todayBtn').addEventListener('click', function () {
    view = monthStart(TODAY);
    renderCal();
  });

  function openDay(key, d, m, y) {
    currentKey = key;
    editable = key === TODAY;
    document.getElementById('dayTitle').textContent = d + ' ' + monthsGen[m] + ' ' + y;
    document.getElementById('daySub').textContent = editable ? 'Отмечайте — квадрат заполняется' : 'Только просмотр';
    document.getElementById('dayLocked').style.display = editable ? 'none' : 'block';
    document.getElementById('dayForm').style.display = editable ? '' : 'none';
    if (editable) ensure(key);
    renderDay();
    showPage('day');
  }

  function renderDay() {
    var list = document.getElementById('dayList');
    list.innerHTML = '';
    var entry = cal[currentKey];
    var items = entry && entry.items ? entry.items : [];

    if (!items.length) {
      var e = document.createElement('li');
      e.className = 'empty';
      e.textContent = editable ? 'Пусто. Добавьте задачу.' : 'Ничего не было.';
      list.appendChild(e);
      return;
    }

    items.forEach(function (item) {
      var li = document.createElement('li');
      li.className = 'item' + (item.done ? ' done' : '');

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = item.done;
      cb.disabled = !editable;
      cb.addEventListener('change', function (ev) {
        item.done = ev.target.checked;
        api('PATCH', '/api/day/' + item.id + '/', { done: item.done }).catch(onErr);
        renderDay();
        renderCal();
      });

      var inp = document.createElement('input');
      inp.type = 'text';
      inp.value = item.text;
      inp.disabled = !editable;
      inp.addEventListener('input', function () {
        item.text = inp.value;
        if (inp.value.trim()) patchLater('day', item.id, { text: inp.value });
      });

      li.appendChild(cb);
      li.appendChild(inp);

      if (editable) {
        var del = document.createElement('button');
        del.type = 'button';
        del.className = 'x';
        del.textContent = '×';
        del.addEventListener('click', function () {
          api('DELETE', '/api/day/' + item.id + '/').then(function () {
            var entry = ensure(currentKey);
            entry.items = entry.items.filter(function (x) { return x.id !== item.id; });
            renderDay();
            renderCal();
          }).catch(onErr);
        });
        li.appendChild(del);
      }
      list.appendChild(li);
    });
  }

  document.getElementById('dayForm').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!editable) return;
    var input = document.getElementById('dayInput');
    var text = input.value.trim();
    if (!text) return;
    api('POST', '/api/day/', { date: currentKey, text: text }).then(function (item) {
      ensure(currentKey).items.push(item);
      input.value = '';
      renderDay();
      renderCal();
    }).catch(onErr);
  });

  document.getElementById('dayBack').addEventListener('click', function () {
    navBtns.forEach(function (b) { b.classList.remove('active'); });
    document.querySelector('.nav button[data-page="calendar"]').classList.add('active');
    showPage('calendar');
  });

  /* ---------- задачи и покупки (одинаковая логика) ---------- */

  function renderSimple(store, kind, cat) {
    var list = document.getElementById('list-' + cat);
    list.innerHTML = '';
    var items = store[cat];
    if (!items.length) {
      var e = document.createElement('li');
      e.className = 'empty';
      e.textContent = 'Пусто';
      list.appendChild(e);
      return;
    }
    items.forEach(function (t) {
      var li = document.createElement('li');
      li.className = 'item' + (t.done ? ' done' : '');

      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = t.done;

      var span = document.createElement('input');
      span.type = 'text';
      span.value = t.text;
      span.addEventListener('input', function () {
        t.text = span.value;
        if (span.value.trim()) patchLater(kind, t.id, { text: span.value });
      });

      var del = document.createElement('button');
      del.type = 'button';
      del.className = 'x';
      del.textContent = '×';

      li.appendChild(cb);
      li.appendChild(span);
      li.appendChild(del);

      cb.addEventListener('change', function (ev) {
        t.done = ev.target.checked;
        api('PATCH', '/api/' + kind + '/' + t.id + '/', { done: t.done }).catch(onErr);
        renderSimple(store, kind, cat);
      });
      del.addEventListener('click', function () {
        api('DELETE', '/api/' + kind + '/' + t.id + '/').then(function () {
          store[cat] = store[cat].filter(function (x) { return x.id !== t.id; });
          renderSimple(store, kind, cat);
        }).catch(onErr);
      });
      list.appendChild(li);
    });
  }

  function bindSimpleForms(selector, attr, store, kind) {
    document.querySelectorAll(selector).forEach(function (form) {
      var cat = form.dataset[attr];
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = form.querySelector('input');
        var text = input.value.trim();
        if (!text) return;
        api('POST', '/api/' + kind + '/', { category: cat, text: text }).then(function (item) {
          store[cat].push(item);
          input.value = '';
          renderSimple(store, kind, cat);
        }).catch(onErr);
      });
    });
  }

  bindSimpleForms('.add[data-cat]', 'cat', tasks, 'task');
  bindSimpleForms('.add[data-shop]', 'shop', shop, 'shop');

  /* ---------- ожидание ---------- */

  function fmtDate(iso) {
    if (!iso) return '';
    var p = iso.split('-');
    return p[2] + '.' + p[1] + '.' + p[0];
  }

  function renderWait() {
    var list = document.getElementById('waitList');
    list.innerHTML = '';
    if (!waiting.length) {
      var e = document.createElement('div');
      e.className = 'empty';
      e.textContent = 'Список пуст';
      list.appendChild(e);
      return;
    }
    waiting.forEach(function (w) {
      var card = document.createElement('div');
      card.className = 'w-card';

      var main = document.createElement('div');
      main.className = 'main';
      var title = document.createElement('div');
      title.className = 'title';
      title.textContent = w.title;
      var meta = document.createElement('div');
      meta.className = 'meta';
      meta.textContent = (w.date ? 'Подано: ' + fmtDate(w.date) : '') + (w.notes ? (w.date ? ' · ' : '') + w.notes : '');
      main.appendChild(title);
      main.appendChild(meta);

      var tag = document.createElement('span');
      tag.className = 'tag ' + statusClass[w.status];
      tag.textContent = statusLabels[w.status];

      var sel = document.createElement('select');
      Object.keys(statusLabels).forEach(function (val) {
        var opt = document.createElement('option');
        opt.value = val;
        opt.textContent = statusLabels[val];
        if (val === w.status) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener('change', function (ev) {
        w.status = ev.target.value;
        api('PATCH', '/api/wait/' + w.id + '/', { status: w.status }).catch(onErr);
        renderWait();
      });

      var del = document.createElement('button');
      del.type = 'button';
      del.className = 'x';
      del.textContent = '×';
      del.addEventListener('click', function () {
        api('DELETE', '/api/wait/' + w.id + '/').then(function () {
          waiting = waiting.filter(function (x) { return x.id !== w.id; });
          renderWait();
        }).catch(onErr);
      });

      card.appendChild(main);
      card.appendChild(tag);
      card.appendChild(sel);
      card.appendChild(del);
      list.appendChild(card);
    });
  }

  document.getElementById('waitForm').addEventListener('submit', function (e) {
    e.preventDefault();
    var title = document.getElementById('wTitle').value.trim();
    if (!title) return;
    api('POST', '/api/wait/', {
      title: title,
      date: document.getElementById('wDate').value,
      status: document.getElementById('wStatus').value,
      notes: document.getElementById('wNotes').value.trim()
    }).then(function (item) {
      waiting.push(item);
      document.getElementById('wTitle').value = '';
      document.getElementById('wDate').value = '';
      document.getElementById('wStatus').value = 'waiting';
      document.getElementById('wNotes').value = '';
      renderWait();
    }).catch(onErr);
  });

  /* ---------- загрузка ---------- */

  function renderAll() {
    renderCal();
    ['major', 'projects', 'short', 'chores'].forEach(function (c) { renderSimple(tasks, 'task', c); });
    ['big', 'small'].forEach(function (c) { renderSimple(shop, 'shop', c); });
    renderWait();
  }

  function applyState(s) {
    TODAY = s.today;
    cal = s.calendar || {};
    ['major', 'projects', 'short', 'chores'].forEach(function (c) { tasks[c] = (s.tasks && s.tasks[c]) || []; });
    ['big', 'small'].forEach(function (c) { shop[c] = (s.shopping && s.shopping[c]) || []; });
    waiting = s.waiting || [];
    if (!view) view = monthStart(TODAY);
  }

  function isEmpty(s) {
    return !Object.keys(s.calendar || {}).length &&
      !Object.keys(s.tasks || {}).some(function (c) { return s.tasks[c].length; }) &&
      !Object.keys(s.shopping || {}).some(function (c) { return s.shopping[c].length; }) &&
      !(s.waiting || []).length;
  }

  // Разовый перенос данных из старой версии (localStorage в этом браузере)
  function readLegacy() {
    function get(k, fb) {
      try { var raw = localStorage.getItem(k); return raw ? JSON.parse(raw) : fb; } catch (e) { return fb; }
    }
    return {
      calendar: get('ezh.calendar', {}),
      tasks: get('ezh.tasks', {}),
      shopping: get('ezh.shopping', {}),
      waiting: get('ezh.waiting', [])
    };
  }

  function maybeMigrate(state) {
    var done = false;
    try { done = localStorage.getItem('ezh.migrated') === '1'; } catch (e) {}
    if (done || !isEmpty(state)) return Promise.resolve(state);
    var legacy = readLegacy();
    if (isEmpty(legacy)) return Promise.resolve(state);
    return api('POST', '/api/import/', legacy).then(function (res) {
      try { localStorage.setItem('ezh.migrated', '1'); } catch (e) {}
      if (res && res.imported) {
        toast('Данные из браузера перенесены в базу: ' + res.count);
        return api('GET', '/api/state/');
      }
      return state;
    }).catch(function () { return state; });
  }

  api('GET', '/api/state/')
    .then(maybeMigrate)
    .then(function (state) {
      applyState(state);
      renderAll();
    })
    .catch(function () {
      toast('Не удалось загрузить данные. Обновите страницу.');
    });
})();
