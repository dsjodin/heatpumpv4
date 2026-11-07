/**
 * Live system schema rendered as SVG from providers/<brand>/schema.yaml
 * (embedded in the page as JSON in #schema-layout).
 */
(function () {
    const NS = 'http://www.w3.org/2000/svg';
    let bindings = [];

    function el(tag, attrs, parent, text) {
        const node = document.createElementNS(NS, tag);
        for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
        if (text !== undefined) node.textContent = text;
        if (parent) parent.appendChild(node);
        return node;
    }

    // Condition: "metric" (on when > 0), {key, gt|lt|eq|ne}, {all: [...]}, {any: [...]}
    function test(cond, latest) {
        if (cond === undefined || cond === null) return false;
        if (typeof cond === 'string') return Number(latest[cond]) > 0;
        if (cond.all) return cond.all.every(c => test(c, latest));
        if (cond.any) return cond.any.some(c => test(c, latest));
        const v = latest[cond.key];
        if (v === undefined || v === null) return false;
        if ('gt' in cond) return v > cond.gt;
        if ('lt' in cond) return v < cond.lt;
        if ('eq' in cond) return v == cond.eq;
        if ('ne' in cond) return v != cond.ne;
        return Number(v) > 0;
    }

    function format(value, unit, decimals) {
        if (value === undefined || value === null || isNaN(value)) return '--';
        return Number(value).toFixed(decimals ?? 1) + (unit || '');
    }

    function bindActive(node, cond) {
        if (cond !== undefined) bindings.push(latest => node.classList.toggle('active', test(cond, latest)));
    }

    function bindText(node, c) {
        if (c.value) bindings.push(latest => { node.textContent = format(latest[c.value], c.unit, c.decimals); });
    }

    function valueBox(parent, cx, cy, w, h, c) {
        el('rect', { x: cx - w / 2, y: cy - h / 2, width: w, height: h, rx: 2, class: 'sch-valuebox' }, parent);
        const t = el('text', { x: cx, y: cy + 1, class: 'sch-value' }, parent, '--');
        bindText(t, c);
    }

    const RENDER = {
        pipe(g, c) {
            const pts = c.points.map(p => p.join(',')).join(' ');
            el('polyline', { points: pts, class: `sch-pipe medium-${c.medium || 'hot'}` }, g);
            const flow = el('polyline', { points: pts, class: 'sch-flow' }, g);
            bindActive(flow, c.flow);
        },

        cabinet(g, c) {
            el('rect', { x: c.x, y: c.y, width: c.w, height: c.h, rx: 6, class: 'sch-cabinet' }, g);
            el('rect', { x: c.x + 5, y: c.y + c.h, width: c.w - 10, height: 8, class: 'sch-cabinet-foot' }, g);
        },

        display(g, c) {
            el('rect', { x: c.x, y: c.y, width: c.w, height: c.h, rx: 3, class: 'sch-display' }, g);
            const rowH = c.h / Math.max(c.rows.length, 3);
            c.rows.forEach((row, i) => {
                const y = c.y + rowH * (i + 0.5);
                el('text', { x: c.x + 8, y, class: 'sch-display-label' }, g, row.label);
                el('rect', { x: c.x + c.w * 0.55, y: y - 11, width: c.w * 0.4, height: 22, class: 'sch-display-cell' }, g);
                const t = el('text', { x: c.x + c.w * 0.75, y: y + 1, class: 'sch-value' }, g, '--');
                bindText(t, row);
            });
        },

        pump(g, c) {
            const r = c.r || 22;
            const p = el('g', { class: 'sch-pump', transform: `translate(${c.x},${c.y})` }, g);
            el('circle', { r, class: 'sch-pump-body' }, p);
            const imp = el('g', { class: 'sch-impeller' }, p);
            for (let a = 0; a < 360; a += 120) {
                el('path', { d: `M0,0 Q${r * 0.5},${-r * 0.2} ${r * 0.75},0`, transform: `rotate(${a})` }, imp);
            }
            el('circle', { r: 3, class: 'sch-pump-hub' }, p);
            bindActive(p, c.active);
        },

        compressor(g, c) {
            const r = c.r || 26;
            const p = el('g', { class: 'sch-compressor', transform: `translate(${c.x},${c.y})` }, g);
            el('circle', { r, class: 'sch-compressor-body' }, p);
            const rotor = el('g', { class: 'sch-impeller' }, p);
            el('path', { d: `M${-r * 0.6},0 A${r * 0.6},${r * 0.6} 0 0 1 ${r * 0.6},0`, class: 'sch-rotor' }, rotor);
            el('path', { d: `M${r * 0.3},0 A${r * 0.3},${r * 0.3} 0 0 1 ${-r * 0.3},0`, class: 'sch-rotor' }, rotor);
            bindActive(p, c.active);
        },

        expansion(g, c) {
            const s = 14;
            el('path', {
                d: `M${c.x - s * 1.6},${c.y - s} L${c.x},${c.y} L${c.x - s * 1.6},${c.y + s} Z M${c.x + s * 1.6},${c.y - s} L${c.x},${c.y} L${c.x + s * 1.6},${c.y + s} Z`,
                class: 'sch-expansion'
            }, g);
        },

        heater(g, c) {
            const steps = c.steps || [{ label: '' }];
            const w = c.w / steps.length;
            steps.forEach((step, i) => {
                const s = el('g', { class: 'sch-heater' }, g);
                const x = c.x + i * w;
                el('rect', { x: x + 2, y: c.y, width: w - 4, height: c.h, class: 'sch-heater-body' }, s);
                el('text', { x: x + w / 2, y: c.y + 13, class: 'sch-heater-label' }, s, step.label);
                const mx = x + w / 2, my = c.y + c.h / 2 + 8;
                el('path', { d: `M${mx + 5},${my - 20} L${mx - 6},${my + 1} L${mx + 6},${my - 1} L${mx - 5},${my + 20}`, class: 'sch-bolt' }, s);
                bindActive(s, step.active);
            });
        },

        valve3(g, c) {
            const s = c.size || 36;
            const p = el('g', { class: 'sch-valve', transform: `translate(${c.x},${c.y})` }, g);
            el('rect', { x: -s / 2, y: -s / 2, width: s, height: s, rx: 8, class: 'sch-valve-body' }, p);
            el('path', { d: `M${-s * 0.3},0 L${s * 0.3},0 M${s * 0.12},${-s * 0.15} L${s * 0.3},0 L${s * 0.12},${s * 0.15}`, class: 'sch-arrow sch-arrow-idle' }, p);
            el('path', { d: `M0,${s * 0.3} L0,${-s * 0.3} M${-s * 0.15},${-s * 0.12} L0,${-s * 0.3} L${s * 0.15},${-s * 0.12}`, class: 'sch-arrow sch-arrow-active' }, p);
            bindActive(p, c.active);
        },

        tank(g, c) {
            const p = el('g', { class: 'sch-tank' }, g);
            el('rect', { x: c.x, y: c.y, width: c.w, height: c.h, rx: 6, class: 'sch-tank-body' }, p);
            el('text', { x: c.x + c.w / 2, y: c.y + 18, class: 'sch-label' }, p, c.label || '');
            valueBox(p, c.x + c.w / 2, c.y + 44, c.w - 20, 30, c);
            el('circle', { cx: c.x + c.w / 2, cy: c.y + c.h - 45, r: 14, class: 'sch-tank-dial' }, p);
            el('rect', { x: c.x + c.w / 2 - 15, y: c.y + c.h - 22, width: 30, height: 10, rx: 5, class: 'sch-tank-led' }, p);
            bindActive(p, c.active);
        },

        radiator(g, c) {
            const p = el('g', { class: 'sch-radiator' }, g);
            el('rect', { x: c.x, y: c.y, width: c.w, height: c.h, rx: 10, class: 'sch-radiator-body' }, p);
            const fins = Math.floor((c.w - 20) / 14);
            for (let i = 0; i < fins; i++) {
                const x = c.x + 16 + i * 14;
                el('line', { x1: x, y1: c.y + 18, x2: x, y2: c.y + c.h - 18, class: 'sch-radiator-fin' }, p);
            }
            const waves = el('g', { class: 'sch-heatwaves' }, p);
            for (let i = 0; i < 3; i++) {
                const x = c.x + c.w / 2 - 18 + i * 18;
                el('path', { d: `M${x},${c.y - 8} q-6,-7 0,-14 q6,-7 0,-14`, class: 'sch-wave' }, waves);
            }
            bindActive(p, c.active);
        },

        sensor(g, c) {
            if (c.label) el('text', { x: c.x, y: c.y - 24, class: 'sch-label' }, g, c.label);
            valueBox(g, c.x, c.y, c.w || 72, c.h || 30, c);
        },

        label(g, c) {
            el('text', { x: c.x, y: c.y, class: 'sch-label' }, g, c.text || '');
        }
    };

    function drawGrid(svg, w, h) {
        const g = el('g', { class: 'sch-grid' }, svg);
        for (let x = 0; x <= w; x += 50) {
            el('line', { x1: x, y1: 0, x2: x, y2: h }, g);
            el('text', { x: x + 2, y: 10 }, g, x);
        }
        for (let y = 0; y <= h; y += 50) {
            el('line', { x1: 0, y1: y, x2: w, y2: y }, g);
            el('text', { x: 2, y: y - 2 }, g, y);
        }
        svg.gridPos = el('text', { x: w - 6, y: h - 6, class: 'sch-grid-pos' }, g, '');
        if (!svg.gridListener) {
            svg.gridListener = e => {
                const s = toSvgPoint(svg, e);
                if (svg.gridPos) svg.gridPos.textContent = `${Math.round(s.x)}, ${Math.round(s.y)}`;
            };
            svg.addEventListener('mousemove', svg.gridListener);
        }
    }

    function toSvgPoint(svg, e) {
        const p = svg.createSVGPoint();
        p.x = e.clientX; p.y = e.clientY;
        return p.matrixTransform(svg.getScreenCTM().inverse());
    }

    // Draws layout into svg. Each pipe/component is wrapped in <g data-kind data-idx>.
    function build(svg, layout, opts = {}) {
        bindings = [];
        const local = bindings;
        while (svg.firstChild) svg.removeChild(svg.firstChild);
        const [w, h] = layout.viewbox || [800, 450];
        svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
        // Cabinets go behind the pipes, everything else on top
        const back = el('g', {}, svg);
        const pipes = el('g', {}, svg);
        const comps = el('g', {}, svg);
        (layout.pipes || []).forEach((c, i) => {
            RENDER.pipe(el('g', { 'data-kind': 'pipe', 'data-idx': i }, pipes), c);
        });
        (layout.components || []).forEach((c, i) => {
            if (!RENDER[c.type]) return console.warn('Unknown schema component type:', c.type);
            const g = el('g', { 'data-kind': 'component', 'data-idx': i }, c.type === 'cabinet' ? back : comps);
            RENDER[c.type](g, c);
        });
        if (opts.grid) drawGrid(svg, w, h);
        return {
            update(latest) {
                if (latest) local.forEach(fn => fn(latest));
            }
        };
    }

    function init() {
        const svg = document.getElementById('schema-svg');
        const src = document.getElementById('schema-layout');
        if (!svg || !src) return;
        const layout = JSON.parse(src.textContent);
        if (!layout) return;
        const r = build(svg, layout, { grid: new URLSearchParams(location.search).has('grid') });
        window.updateSchema = r.update;
    }

    window.SchemaRenderer = { build, test, el, toSvgPoint, types: Object.keys(RENDER).filter(t => t !== 'pipe') };

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
