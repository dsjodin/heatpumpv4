/**
 * Visual editor for providers/<brand>/schema.yaml.
 * Uses SchemaRenderer from schema.js, so the canvas looks exactly like the live view.
 */
(function () {
    const R = window.SchemaRenderer;
    const $ = id => document.getElementById(id);
    const svg = $('sed-svg');

    const FIELDS = {
        pipe: ['medium', 'flow', 'points'],
        cabinet: ['x', 'y', 'w', 'h'],
        display: ['x', 'y', 'w', 'h', 'rows'],
        heater: ['x', 'y', 'w', 'h', 'steps'],
        tank: ['x', 'y', 'w', 'h', 'label', 'value', 'unit', 'decimals', 'active'],
        radiator: ['x', 'y', 'w', 'h', 'active'],
        pump: ['x', 'y', 'r', 'active'],
        compressor: ['x', 'y', 'r', 'active'],
        valve3: ['x', 'y', 'size', 'active'],
        expansion: ['x', 'y'],
        sensor: ['x', 'y', 'w', 'h', 'label', 'value', 'unit', 'decimals'],
        label: ['x', 'y', 'text']
    };
    const NUMBER = new Set(['x', 'y', 'w', 'h', 'r', 'size', 'decimals']);
    const CONDITION = new Set(['active', 'flow']);
    const MEDIA = ['brine_in', 'brine_out', 'cold', 'hot', 'return'];
    const LABELS = {
        x: 'X', y: 'Y', w: 'Bredd', h: 'Höjd', r: 'Radie', size: 'Storlek', decimals: 'Decimaler',
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

    let brand = $('sed-brand').value;
    let layout = null;
    let sel = null;          // { kind: 'pipe'|'component', idx }
    let latest = {};
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

    function condToText(c) {
        if (c === undefined) return '';
        return typeof c === 'string' ? c : JSON.stringify(c);
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
        if (opts.list) i.setAttribute('list', opts.list);
        i.value = value ?? '';
        i.addEventListener('change', () => onChange(i.value, i));
        return i;
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

    function condField(obj, key) {
        const hint = liveHint('');
        const showHint = () => {
            if (obj[key] === undefined) hint.textContent = '';
            else hint.textContent = R.test(obj[key], latest) ? 'nu: PÅ' : 'nu: AV';
        };
        const i = input('text', condToText(obj[key]), (v, el) => {
            try {
                setKey(obj, key, textToCond(v));
            } catch (e) {
                el.classList.add('is-invalid');
                status(`Ogiltigt villkor: ${e.message}`, false);
            }
        }, { list: 'sed-registers' });
        i.placeholder = 'register eller {"key":"...","gt":0}';
        showHint();
        return field(LABELS[key], i, hint);
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
            subFields.forEach(f => {
                let el;
                if (CONDITION.has(f)) {
                    el = input('text', condToText(row[f]), v => {
                        try { setKey(row, f, textToCond(v)); } catch (e) { status(`Ogiltigt villkor: ${e.message}`, false); }
                    }, { list: 'sed-registers' });
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
            box.append(r);
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

    function renderPanel() {
        const props = $('sed-props');
        props.innerHTML = '';
        const item = selected();
        if (!item) {
            $('sed-panel-title').textContent = 'Inget valt';
            return;
        }
        const type = sel.kind === 'pipe' ? 'pipe' : item.type;
        $('sed-panel-title').textContent = sel.kind === 'pipe' ? `Rör #${sel.idx}` : `${type} #${sel.idx}`;

        (FIELDS[type] || []).forEach(key => {
            if (key === 'points') return props.append(pointsEditor(item));
            if (key === 'rows') return props.append(listEditor(item, key, ['label', 'value', 'unit', 'decimals']));
            if (key === 'steps') return props.append(listEditor(item, key, ['label', 'active']));
            if (CONDITION.has(key)) return props.append(condField(item, key));
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
        if (handle && sel && sel.kind === 'pipe') {
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
        if (drag.type === 'point') {
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
        return {
            viewbox: l.viewbox || [800, 450],
            pipes: l.pipes || [],
            components: l.components || []
        };
    }

    async function loadRegisters() {
        const list = $('sed-registers');
        list.innerHTML = '';
        try {
            const regs = await api(`/api/registers/${brand}`);
            regs.forEach(r => list.append(new Option(`${r.description} ${r.unit ? '(' + r.unit + ')' : ''}`, r.name)));
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
