/**
 * Visual editor for providers/<brand>/schema.yaml.
 * Uses SchemaRenderer from schema.js, so the canvas looks exactly like the live view.
 */
(function () {
    const R = window.SchemaRenderer;
    const $ = id => document.getElementById(id);
    const svg = $('sed-svg');

    const FIELDS = {
        pipe: ['name', 'medium', 'width', 'flow', 'points'],
        cabinet: ['name', 'x', 'y', 'w', 'h'],
        display: ['name', 'x', 'y', 'w', 'h', 'rows'],
        heater: ['name', 'x', 'y', 'w', 'h', 'steps'],
        tank: ['name', 'x', 'y', 'w', 'h', 'label', 'value', 'unit', 'decimals', 'active'],
        radiator: ['name', 'x', 'y', 'w', 'h', 'active'],
        pump: ['name', 'x', 'y', 'r', 'active'],
        compressor: ['name', 'x', 'y', 'r', 'active'],
        valve3: ['name', 'x', 'y', 'size', 'active'],
        expansion: ['name', 'x', 'y', 'size'],
        sensor: ['name', 'x', 'y', 'w', 'h', 'label', 'value', 'unit', 'decimals'],
        label: ['name', 'x', 'y', 'text', 'size']
    };
    const NUMBER = new Set(['x', 'y', 'w', 'h', 'r', 'size', 'width', 'decimals']);
    const CONDITION = new Set(['active', 'flow']);
    const MEDIA = ['brine_in', 'brine_out', 'cold', 'hot', 'return'];
    const LABELS = {
        name: 'Namn (valfritt, bara för dig)',
        x: 'X', y: 'Y', w: 'Bredd', h: 'Höjd', r: 'Radie', size: 'Storlek', width: 'Rörbredd', decimals: 'Decimaler',
        label: 'Etikett', value: 'Register', unit: 'Enhet', text: 'Text', medium: 'Medium',
        active: 'Aktiv när', flow: 'Flöde när', points: 'Punkter', rows: 'Rader', steps: 'Steg'
    };
    const DEFAULTS = {
        cabinet: { w: 200, h: 400 },
        display: { w: 160, h: 120, rows: [{ label: 'Utetemp', value: 'outdoor_temp', unit: '°C' }] },
        heater: { w: 80, h: 75, steps: [{ label: '3kW' }] },
        tank: { w: 100, h: 135, label: 'Varmvatten', unit: '°C' },
        radiator: { w: 135, h: 130 },
        sensor: { label: 'Givare', unit: '°C' },
        label: { text: 'Text' }
    };
    // Resize: boxes change w/h, the rest one size key. [key, default, size per px of handle movement]
    const BOX = { cabinet: 'corner', display: 'corner', heater: 'corner', tank: 'corner', radiator: 'corner', sensor: 'center' };
    const SIZE = {
        pump: ['r', 22, 1], compressor: ['r', 26, 1], valve3: ['size', 36, 2],
        expansion: ['size', 14, 1 / 1.6], label: ['size', 14, 0.5]
    };

    let brand = $('sed-brand').value;
    let layout = null;
    let sel = null;          // { kind: 'pipe'|'component', idx }
    let latest = {};
    let registers = [];
    let undoStack = [];
    let dirty = false;
    let drag = null;

    // ---------- helpers ----------

    function status(msg, ok = true) {
        const s = $('sed-status');
        s.textContent = msg;
        s.className = 'sed-status ' + (ok ? 'ok' : 'err');
    }

    function snapshot() {
        undoStack.push(JSON.stringify(layout));
        if (undoStack.length > 100) undoStack.shift();
        dirty = true;
    }

    function selected() {
        if (!sel) return null;
        return sel.kind === 'pipe' ? layout.pipes[sel.idx] : layout.components[sel.idx];
    }

    function snap(v, free) {
        return free ? Math.round(v) : Math.round(v / 5) * 5;
    }

    function textToCond(t) {
        t = t.trim();
        if (!t) return undefined;
        if (t.startsWith('{')) return JSON.parse(t);
        return t;
    }

    async function api(url, opts) {
        const res = await fetch(url, opts);
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || data.error || res.statusText);
        return data;
    }

    // ---------- rendering ----------

    function render() {
        const r = R.build(svg, layout, { grid: true });
        r.update(latest);
        if ($('sed-show-active').checked) {
            svg.querySelectorAll('.sch-flow, .sch-pump, .sch-compressor, .sch-heater, .sch-valve, .sch-tank, .sch-radiator')
                .forEach(n => n.classList.add('active'));
        }
        drawSelection();
        $('sed-pipe-width').value = layout.pipe_width ?? '';
        $('sed-vb-w').value = layout.viewbox[0];
        $('sed-vb-h').value = layout.viewbox[1];
    }

    function drawSelection() {
        const item = selected();
        if (!item) return;
        const g = svg.querySelector(`[data-kind="${sel.kind}"][data-idx="${sel.idx}"]`);
        if (!g) return;
        const b = g.getBBox();
        const overlay = R.el('g', { class: 'sed-overlay' }, svg);
        R.el('rect', { x: b.x - 4, y: b.y - 4, width: b.width + 8, height: b.height + 8, class: 'sed-sel' }, overlay);
        if (sel.kind === 'pipe') {
            item.points.forEach((p, i) => {
                R.el('circle', { cx: p[0], cy: p[1], r: 6, class: 'sed-handle', 'data-pt': i }, overlay);
            });
            return;
        }
        const pos = resizeHandlePos(item, b);
        if (pos) R.el('rect', { x: pos[0] - 5, y: pos[1] - 5, width: 10, height: 10, class: 'sed-resize' }, overlay);
    }

    function resizeHandlePos(c, bbox) {
        if (BOX[c.type] === 'corner') return [c.x + c.w, c.y + c.h];
        if (BOX[c.type] === 'center') return [c.x + (c.w || 72) / 2, c.y + (c.h || 30) / 2];
        const s = SIZE[c.type];
        if (!s) return null;
        if (c.type === 'label') return [bbox.x + bbox.width, bbox.y + bbox.height / 2];
        return [c.x + (c[s[0]] ?? s[1]) / s[2], c.y];
    }

    function resize(c, orig, dx, dy, keepRatio) {
        if (BOX[c.type]) {
            const k = BOX[c.type] === 'center' ? 2 : 1;
            let w = Math.max(5, orig.w + dx * k);
            let h = Math.max(5, orig.h + dy * k);
            if (keepRatio) h = Math.max(5, Math.round(w * orig.h / orig.w));
            c.w = Math.round(w);
            c.h = Math.round(h);
        } else {
            const [key, , k] = SIZE[c.type];
            c[key] = Math.max(5, Math.round(orig.size + dx * k));
        }
    }

    // ---------- property panel ----------

    function field(label, input, extra) {
        const wrap = document.createElement('label');
        wrap.className = 'sed-field';
        wrap.append(label, input);
        if (extra) wrap.append(extra);
        return wrap;
    }

    function input(type, value, onChange, opts = {}) {
        const i = document.createElement(opts.select ? 'select' : 'input');
        i.className = opts.select ? 'form-select form-select-sm' : 'form-control form-control-sm';
        if (opts.select) {
            opts.select.forEach(v => i.add(new Option(v, v)));
        } else {
            i.type = type;
        }
        if (opts.list) attachRegisterPicker(i);
        i.value = value ?? '';
        i.addEventListener('change', () => onChange(i.value, i));
        return i;
    }

    // ---------- register picker: all registers with description and live value ----------

    const picker = document.createElement('div');
    picker.className = 'sed-picker';
    picker.hidden = true;
    document.body.append(picker);
    let pickerInput = null;
    let pickerRows = [];
    let pickerActive = -1;

    function formatLive(r) {
        const v = latest[r.name];
        if (v === undefined || v === null) return '--';
        return (typeof v === 'number' ? +v.toFixed(2) : v) + (r.unit ? ' ' + r.unit : '');
    }

    function choose(name) {
        const i = pickerInput;
        closePicker();
        i.value = name;
        i.dispatchEvent(new Event('change'));
    }

    function highlight(k) {
        pickerRows.forEach((row, n) => row.classList.toggle('active', n === k));
        pickerActive = k;
        if (pickerRows[k]) pickerRows[k].scrollIntoView({ block: 'nearest' });
    }

    function openPicker(i) {
        pickerInput = i;
        const q = i.value.trim().toLowerCase();
        // JSON conditions are typed by hand
        if (q.startsWith('{')) return closePicker();
        // Registers that report a live value first, then alphabetical
        const hits = registers
            .filter(r => !q || r.name.toLowerCase().includes(q) || r.description.toLowerCase().includes(q))
            .sort((a, b) => (b.name in latest) - (a.name in latest) || a.name.localeCompare(b.name));
        picker.innerHTML = '';
        pickerRows = hits.map(r => {
            const row = document.createElement('div');
            row.className = 'sed-pick-row' + (r.name in latest ? '' : ' nodata');
            const name = document.createElement('code');
            name.textContent = r.name;
            const desc = document.createElement('span');
            desc.className = 'sed-pick-desc';
            desc.textContent = r.description;
            const val = document.createElement('span');
            val.className = 'sed-pick-val';
            val.textContent = formatLive(r);
            row.append(name, val, desc);
            row.addEventListener('mousedown', e => { e.preventDefault(); choose(r.name); });
            picker.append(row);
            return row;
        });
        if (!hits.length) picker.textContent = 'Inga register matchar';
        const b = i.getBoundingClientRect();
        const width = Math.min(Math.max(b.width, 460), window.innerWidth - 16);
        picker.style.width = width + 'px';
        picker.style.left = Math.max(8, Math.min(b.left, window.innerWidth - width - 8)) + 'px';
        picker.hidden = false;
        const below = window.innerHeight - b.bottom;
        picker.style.maxHeight = Math.max(below, b.top) - 16 + 'px';
        picker.style.top = (below >= 200 || below >= b.top ? b.bottom + 2 : Math.max(8, b.top - picker.offsetHeight - 2)) + 'px';
        highlight(-1);
    }

    function closePicker() {
        picker.hidden = true;
        pickerInput = null;
    }

    function attachRegisterPicker(i) {
        i.autocomplete = 'off';
        i.addEventListener('focus', () => openPicker(i));
        i.addEventListener('input', () => openPicker(i));
        i.addEventListener('blur', () => { if (pickerInput === i) closePicker(); });
        i.addEventListener('keydown', e => {
            if (picker.hidden || pickerInput !== i) return;
            if (e.key === 'ArrowDown') { e.preventDefault(); highlight(Math.min(pickerActive + 1, pickerRows.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(Math.max(pickerActive - 1, 0)); }
            else if (e.key === 'Enter' && pickerActive >= 0) { e.preventDefault(); pickerRows[pickerActive].dispatchEvent(new MouseEvent('mousedown')); }
            else if (e.key === 'Escape') { e.preventDefault(); closePicker(); }
        });
    }

    function setKey(obj, key, value) {
        snapshot();
        if (value === undefined || value === '' || (typeof value === 'number' && isNaN(value))) delete obj[key];
        else obj[key] = value;
        render();
        renderPanel();
    }

    function liveHint(text) {
        const s = document.createElement('small');
        s.className = 'sed-live';
        s.textContent = text;
        return s;
    }

    function valueHint(name) {
        if (!name) return null;
        return liveHint(name in latest ? `nu: ${latest[name]}` : 'inget livevärde');
    }

    // What "active"/"flow" does for each type, shown above the condition builder
    const ACTIVE_HELP = {
        pipe: 'Animerad flödeslinje när villkoret stämmer',
        pump: 'Hjulet snurrar och pumpen blir grön',
        compressor: 'Rotorn snurrar och kompressorn blir grön',
        valve3: 'Pilen pekar uppåt (varmvatten) när villkoret stämmer, annars åt höger (radiator)',
        tank: 'Röd ram och lampa tänds',
        radiator: 'Värmevågor och rosa fyllning',
        heater: 'Steget lyser och blixten pulserar'
    };
    const OPS = [['on', 'är på (> 0)'], ['gt', 'större än'], ['lt', 'mindre än'], ['eq', 'lika med'], ['ne', 'inte lika med']];

    // Condition <-> rows. Returns null for conditions the builder can't show (nested all/any).
    function parseCond(c) {
        const row = x => {
            if (typeof x === 'string') return { key: x, op: 'on', value: 0 };
            if (!x || typeof x !== 'object' || !x.key) return null;
            const op = ['gt', 'lt', 'eq', 'ne'].find(o => o in x);
            return op ? { key: x.key, op, value: x[op] } : { key: x.key, op: 'on', value: 0 };
        };
        if (c === undefined) return { mode: 'all', rows: [] };
        const list = c && (c.all || c.any);
        if (list) {
            const rows = list.map(row);
            return rows.every(Boolean) ? { mode: c.all ? 'all' : 'any', rows } : null;
        }
        const r = row(c);
        return r ? { mode: 'all', rows: [r] } : null;
    }

    function serializeRow(r) {
        return r.op === 'on' ? r.key : { key: r.key, [r.op]: Number(r.value) || 0 };
    }

    function serializeCond(state) {
        const rows = state.rows.filter(r => r.key);
        if (!rows.length) return undefined;
        if (rows.length === 1) return serializeRow(rows[0]);
        return { [state.mode]: rows.map(serializeRow) };
    }

    function describeRegister(name) {
        const r = registers.find(x => x.name === name);
        return r ? r.description : (name ? 'okänt register för detta märke' : '');
    }

    function condBuilder(obj, key, type) {
        const box = document.createElement('div');
        box.className = 'sed-cond';
        let state = parseCond(obj[key]);
        let rawMode = state === null;
        if (!state) state = { mode: 'all', rows: [] };

        function commit() {
            snapshot();
            const v = serializeCond(state);
            if (v === undefined) delete obj[key];
            else obj[key] = v;
            render();
            draw();
        }

        function draw() {
            box.innerHTML = '';
            const head = document.createElement('div');
            head.className = 'sed-cond-head';
            const title = document.createElement('span');
            title.className = 'sed-list-title';
            title.textContent = LABELS[key];
            const total = liveHint(obj[key] === undefined ? 'inget villkor' : (R.test(obj[key], latest) ? 'nu: PÅ' : 'nu: AV'));
            head.append(title, total);
            box.append(head);
            const h = document.createElement('div');
            h.className = 'sed-cond-help';
            h.textContent = (ACTIVE_HELP[type] ? ACTIVE_HELP[type] + '. ' : '') +
                'Villkoren läser register (mätvärden) från värmepumpen, inte andra objekt i schemat.';
            box.append(h);

            if (rawMode) {
                const t = input('text', obj[key] === undefined ? '' : JSON.stringify(obj[key]), (v, el) => {
                    try {
                        const parsed = textToCond(v);
                        snapshot();
                        if (parsed === undefined) delete obj[key]; else obj[key] = parsed;
                        render();
                        const st = parseCond(obj[key]);
                        if (st) { state = st; rawMode = false; }
                        draw();
                    } catch (e) {
                        el.classList.add('is-invalid');
                        status(`Ogiltigt villkor: ${e.message}`, false);
                    }
                });
                t.placeholder = '{"any":[{"key":"...","gt":0}, ...]}';
                box.append(t);
            } else {
                if (state.rows.length > 1) {
                    const mode = input('', state.mode, v => { state.mode = v; commit(); }, { select: [] });
                    mode.add(new Option('Alla måste stämma (och)', 'all'));
                    mode.add(new Option('Något räcker (eller)', 'any'));
                    mode.value = state.mode;
                    box.append(mode);
                }
                state.rows.forEach((r, i) => {
                    const row = document.createElement('div');
                    row.className = 'sed-cond-row';
                    const reg = input('text', r.key, v => { r.key = v.trim(); commit(); }, { list: true });
                    reg.placeholder = 'register';
                    const op = input('', r.op, v => { r.op = v; commit(); }, { select: [] });
                    OPS.forEach(([v, l]) => op.add(new Option(l, v)));
                    op.value = r.op;
                    const val = input('number', r.value, v => { r.value = Number(v); commit(); });
                    val.hidden = r.op === 'on';
                    const del = document.createElement('button');
                    del.className = 'btn btn-sm btn-outline-danger';
                    del.textContent = 'x';
                    del.addEventListener('click', () => { state.rows.splice(i, 1); commit(); });
                    row.append(reg, op, val, del);
                    box.append(row);

                    const meta = document.createElement('div');
                    meta.className = 'sed-cond-meta';
                    if (r.key) {
                        const now = latest[r.key];
                        const ok = R.test(serializeRow(r), latest);
                        meta.textContent = `${describeRegister(r.key)}. Nu: ${now ?? '--'} -> ${ok ? 'stämmer' : 'stämmer inte'}`;
                    }
                    box.append(meta);
                });
            }

            const tools = document.createElement('div');
            tools.className = 'sed-cond-tools';
            if (!rawMode) {
                const add = document.createElement('button');
                add.className = 'btn btn-sm btn-outline-secondary';
                add.textContent = '+ Villkor';
                add.addEventListener('click', () => {
                    state.rows.push({ key: '', op: 'on', value: 0 });
                    draw();
                    box.querySelectorAll('.sed-cond-row input[type=text]')[state.rows.length - 1].focus();
                });
                tools.append(add);
            }
            const json = document.createElement('button');
            json.className = 'btn btn-sm btn-link';
            json.textContent = rawMode ? 'Byggare' : 'JSON';
            json.addEventListener('click', () => {
                const st = parseCond(obj[key]);
                if (rawMode && !st) return status('Villkoret är för komplext för byggaren, redigera som JSON', false);
                if (st) state = st;
                rawMode = !rawMode;
                draw();
            });
            tools.append(json);
            box.append(tools);
        }

        draw();
        return box;
    }

    function listEditor(obj, key, subFields) {
        const box = document.createElement('div');
        box.className = 'sed-list';
        const title = document.createElement('div');
        title.className = 'sed-list-title';
        title.textContent = LABELS[key];
        box.append(title);
        (obj[key] || []).forEach((row, i) => {
            const r = document.createElement('div');
            r.className = 'sed-list-row';
            const below = [];
            subFields.forEach(f => {
                let el;
                if (CONDITION.has(f)) {
                    below.push(condBuilder(row, f, obj.type));
                    return;
                } else if (NUMBER.has(f)) {
                    el = input('number', row[f], v => setKey(row, f, v === '' ? undefined : Number(v)));
                } else {
                    el = input('text', row[f], v => setKey(row, f, v), f === 'value' ? { list: 'sed-registers' } : {});
                }
                el.placeholder = LABELS[f];
                el.title = LABELS[f];
                r.append(el);
            });
            const del = document.createElement('button');
            del.className = 'btn btn-sm btn-outline-danger';
            del.textContent = 'x';
            del.addEventListener('click', () => { snapshot(); obj[key].splice(i, 1); render(); renderPanel(); });
            r.append(del);
            box.append(r, ...below);
        });
        const add = document.createElement('button');
        add.className = 'btn btn-sm btn-outline-secondary';
        add.textContent = '+ Rad';
        add.addEventListener('click', () => {
            snapshot();
            obj[key] = obj[key] || [];
            obj[key].push({ label: 'Ny' });
            render();
            renderPanel();
        });
        box.append(add);
        return box;
    }

    function pointsEditor(obj) {
        const box = document.createElement('div');
        box.className = 'sed-list';
        const title = document.createElement('div');
        title.className = 'sed-list-title';
        title.textContent = LABELS.points;
        box.append(title);
        obj.points.forEach((p, i) => {
            const r = document.createElement('div');
            r.className = 'sed-list-row';
            [0, 1].forEach(k => {
                r.append(input('number', p[k], v => { snapshot(); p[k] = Number(v); render(); }));
            });
            const del = document.createElement('button');
            del.className = 'btn btn-sm btn-outline-danger';
            del.textContent = 'x';
            del.disabled = obj.points.length <= 2;
            del.addEventListener('click', () => { snapshot(); obj.points.splice(i, 1); render(); renderPanel(); });
            r.append(del);
            box.append(r);
        });
        const add = document.createElement('button');
        add.className = 'btn btn-sm btn-outline-secondary';
        add.textContent = '+ Punkt';
        add.addEventListener('click', () => {
            snapshot();
            const last = obj.points[obj.points.length - 1];
            obj.points.push([last[0] + 40, last[1]]);
            render();
            renderPanel();
        });
        box.append(add);
        return box;
    }

    const TYPE_NAMES = {
        pipe: 'Rör', cabinet: 'Skåp', display: 'Display', heater: 'Elpatron', tank: 'Varmvattenberedare',
        radiator: 'Radiator', pump: 'Pump', compressor: 'Kompressor', valve3: 'Växelventil',
        expansion: 'Expansionsventil', sensor: 'Givare', label: 'Text'
    };

    function itemTitle(item, kind, idx) {
        const type = kind === 'pipe' ? 'pipe' : item.type;
        const name = item.name || item.label || item.text || (item.value ? item.value : '');
        const typeName = TYPE_NAMES[type] || type;
        return `${typeName}${name && name !== typeName ? ': ' + name : ''} (#${idx})`;
    }

    function renderPanel() {
        const props = $('sed-props');
        props.innerHTML = '';
        const item = selected();
        if (!item) {
            $('sed-panel-title').textContent = 'Inget valt';
            return;
        }
        const type = sel.kind === 'pipe' ? 'pipe' : item.type;
        $('sed-panel-title').textContent = itemTitle(item, sel.kind, sel.idx);

        (FIELDS[type] || []).forEach(key => {
            if (key === 'points') return props.append(pointsEditor(item));
            if (key === 'rows') return props.append(listEditor(item, key, ['label', 'value', 'unit', 'decimals']));
            if (key === 'steps') return props.append(listEditor(item, key, ['label', 'active']));
            if (CONDITION.has(key)) return props.append(condBuilder(item, key, type));
            if (key === 'medium') {
                return props.append(field(LABELS[key], input('', item.medium || 'hot', v => setKey(item, key, v), { select: MEDIA })));
            }
            if (NUMBER.has(key)) {
                return props.append(field(LABELS[key], input('number', item[key], v => setKey(item, key, v === '' ? undefined : Number(v)))));
            }
            if (key === 'value') {
                return props.append(field(LABELS[key], input('text', item[key], v => setKey(item, key, v), { list: 'sed-registers' }), valueHint(item[key])));
            }
            props.append(field(LABELS[key], input('text', item[key], v => setKey(item, key, v))));
        });
    }

    // ---------- canvas interaction ----------

    function select(kind, idx) {
        sel = kind === null ? null : { kind, idx };
        render();
        renderPanel();
    }

    svg.addEventListener('pointerdown', e => {
        const pt = R.toSvgPoint(svg, e);
        const handle = e.target.closest('.sed-handle');
        if (e.target.closest('.sed-resize')) {
            const c = selected();
            const s = SIZE[c.type];
            drag = {
                type: 'resize', start: pt, moved: false,
                orig: BOX[c.type]
                    ? { w: c.w || 72, h: c.h || 30 }
                    : { size: c[s[0]] ?? s[1] }
            };
        } else if (handle && sel && sel.kind === 'pipe') {
            const i = Number(handle.dataset.pt);
            drag = { type: 'point', i, start: pt, orig: [...layout.pipes[sel.idx].points[i]], moved: false };
        } else {
            const g = e.target.closest('[data-kind]');
            if (!g) return select(null);
            const kind = g.dataset.kind;
            const idx = Number(g.dataset.idx);
            if (!sel || sel.kind !== kind || sel.idx !== idx) select(kind, idx);
            const item = selected();
            drag = {
                type: 'item', start: pt, moved: false,
                orig: kind === 'pipe' ? item.points.map(p => [...p]) : [item.x, item.y]
            };
        }
        svg.setPointerCapture(e.pointerId);
    });

    svg.addEventListener('pointermove', e => {
        if (!drag) return;
        const pt = R.toSvgPoint(svg, e);
        const dx = pt.x - drag.start.x;
        const dy = pt.y - drag.start.y;
        if (!drag.moved) {
            if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return;
            snapshot();
            drag.moved = true;
        }
        // Snap the movement, not the position, so existing alignments are kept
        const item = selected();
        const ddx = snap(dx, e.shiftKey), ddy = snap(dy, e.shiftKey);
        if (drag.type === 'resize') {
            // Shift keeps proportions (and skips snapping)
            resize(item, drag.orig, ddx, ddy, e.shiftKey);
        } else if (drag.type === 'point') {
            item.points[drag.i] = [drag.orig[0] + ddx, drag.orig[1] + ddy];
        } else if (sel.kind === 'pipe') {
            item.points = drag.orig.map(p => [p[0] + ddx, p[1] + ddy]);
        } else {
            item.x = drag.orig[0] + ddx;
            item.y = drag.orig[1] + ddy;
        }
        render();
    });

    svg.addEventListener('pointerup', () => {
        if (drag && drag.moved) renderPanel();
        drag = null;
    });

    function nudge(dx, dy) {
        const item = selected();
        if (!item) return;
        snapshot();
        if (sel.kind === 'pipe') item.points = item.points.map(p => [p[0] + dx, p[1] + dy]);
        else { item.x += dx; item.y += dy; }
        render();
        renderPanel();
    }

    function removeSelected() {
        if (!sel) return;
        snapshot();
        (sel.kind === 'pipe' ? layout.pipes : layout.components).splice(sel.idx, 1);
        select(null);
    }

    function duplicateSelected() {
        const item = selected();
        if (!item) return;
        snapshot();
        const copy = JSON.parse(JSON.stringify(item));
        if (sel.kind === 'pipe') {
            copy.points = copy.points.map(p => [p[0] + 20, p[1] + 20]);
            layout.pipes.push(copy);
            select('pipe', layout.pipes.length - 1);
        } else {
            copy.x += 20; copy.y += 20;
            layout.components.push(copy);
            select('component', layout.components.length - 1);
        }
    }

    function undo() {
        if (!undoStack.length) return;
        layout = JSON.parse(undoStack.pop());
        if (sel && !selected()) sel = null;
        render();
        renderPanel();
    }

    document.addEventListener('keydown', e => {
        if (e.target.matches('input, select, textarea')) return;
        const step = e.shiftKey ? 10 : 1;
        const keys = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
        if (keys[e.key] && sel) { e.preventDefault(); nudge(...keys[e.key]); }
        else if ((e.key === 'Delete' || e.key === 'Backspace') && sel) { e.preventDefault(); removeSelected(); }
        else if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
        else if ((e.ctrlKey || e.metaKey) && e.key === 'd') { e.preventDefault(); duplicateSelected(); }
        else if (e.key === 'Escape') select(null);
    });

    // ---------- toolbar ----------

    R.types.forEach(t => $('sed-add-type').add(new Option(t, t)));

    $('sed-add').addEventListener('click', () => {
        const type = $('sed-add-type').value;
        snapshot();
        const [w, h] = layout.viewbox;
        const c = Object.assign({ type, x: Math.round(w / 2 / 5) * 5, y: Math.round(h / 2 / 5) * 5 }, JSON.parse(JSON.stringify(DEFAULTS[type] || {})));
        layout.components.push(c);
        select('component', layout.components.length - 1);
    });

    $('sed-add-pipe').addEventListener('click', () => {
        snapshot();
        const [w, h] = layout.viewbox;
        layout.pipes.push({ medium: 'hot', points: [[w / 2 - 50, h / 2], [w / 2 + 50, h / 2]] });
        select('pipe', layout.pipes.length - 1);
    });

    $('sed-duplicate').addEventListener('click', duplicateSelected);
    $('sed-delete').addEventListener('click', removeSelected);
    $('sed-undo').addEventListener('click', undo);
    $('sed-show-active').addEventListener('change', render);

    $('sed-pipe-width').addEventListener('change', e => {
        const v = Number(e.target.value);
        snapshot();
        if (e.target.value !== '' && v > 0) layout.pipe_width = v;
        else delete layout.pipe_width;
        render();
    });

    ['sed-vb-w', 'sed-vb-h'].forEach((id, k) => {
        $(id).addEventListener('change', e => {
            const v = Number(e.target.value);
            if (v > 0) { snapshot(); layout.viewbox[k] = v; render(); }
        });
    });

    $('sed-brand').addEventListener('change', e => {
        if (dirty && !confirm('Osparade ändringar försvinner. Fortsätt?')) {
            e.target.value = brand;
            return;
        }
        brand = e.target.value;
        load();
    });

    $('sed-copy').addEventListener('click', async () => {
        const from = $('sed-copy-from').value;
        if (!confirm(`Ersätt nuvarande layout med ${from}? (kan ångras)`)) return;
        try {
            const l = await api(`/api/schema/${from}`);
            snapshot();
            layout = normalize(l);
            select(null);
            status(`Kopierade layout från ${from}. Kontrollera registernamnen innan du sparar.`);
        } catch (e) {
            status(e.message, false);
        }
    });

    async function generate(save) {
        const data = await api(`/api/schema/${brand}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ layout, save })
        });
        $('sed-yaml').value = data.yaml;
        return data.yaml;
    }

    $('sed-save').addEventListener('click', async () => {
        try {
            await generate(true);
            dirty = false;
            status(`Sparat till providers/${brand}/schema.yaml`);
        } catch (e) {
            status(e.message, false);
        }
    });

    $('sed-download').addEventListener('click', async () => {
        try {
            const text = await generate(false);
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([text], { type: 'text/yaml' }));
            a.download = 'schema.yaml';
            a.click();
            URL.revokeObjectURL(a.href);
        } catch (e) {
            status(e.message, false);
        }
    });

    $('sed-copy-yaml').addEventListener('click', async () => {
        try {
            const text = await generate(false);
            $('sed-yaml-box').open = true;
            try {
                await navigator.clipboard.writeText(text);
            } catch {
                // clipboard API needs https; fall back to selecting the textarea
                $('sed-yaml').select();
                document.execCommand('copy');
            }
            status('YAML kopierad');
        } catch (e) {
            status(e.message, false);
        }
    });

    window.addEventListener('beforeunload', e => {
        if (dirty) e.preventDefault();
    });

    // ---------- data ----------

    function normalize(l) {
        const out = {
            viewbox: l.viewbox || [800, 450],
            pipes: l.pipes || [],
            components: l.components || []
        };
        if (l.pipe_width) out.pipe_width = l.pipe_width;
        return out;
    }

    async function loadRegisters() {
        registers = [];
        try {
            registers = await api(`/api/registers/${brand}`);
        } catch (e) {
            status(e.message, false);
        }
    }

    async function loadLatest() {
        try {
            const data = await api('/api/debug/all-metrics');
            latest = {};
            (data.metrics || []).forEach(m => { latest[m.name] = m.value; });
            if (layout && !drag) render();
        } catch {
            // no InfluxDB: editor still works without live values
        }
    }

    async function load() {
        try {
            layout = normalize(await api(`/api/schema/${brand}`));
            undoStack = [];
            dirty = false;
            sel = null;
            await loadRegisters();
            render();
            renderPanel();
            status(`Laddade ${brand}`);
        } catch (e) {
            status(e.message, false);
        }
    }

    load();
    loadLatest();
    setInterval(loadLatest, 30000);
})();
