(() => {
    function initVlanExplorer() {
        const rowsDataEl = document.getElementById('vlan-rows-data');
        if (!rowsDataEl) return;

        let vlanRows = [];
        try {
            vlanRows = JSON.parse(rowsDataEl.textContent || '[]');
        } catch (err) {
            console.error('Failed to parse VLAN rows data', err);
            vlanRows = [];
        }
        const serverCountEl = document.getElementById('vlan-data-count');
        const serverCount = serverCountEl ? Number(serverCountEl.getAttribute('data-count') || 0) : 0;
        if (!vlanRows.length && serverCount > 0) {
            console.warn('VLAN explorer: JS rows empty but server has data; keeping fallback rows.');
            return;
        }

    const state = {
        rows: vlanRows,
        filtered: [],
        sort: { key: 'coupling_score', direction: 'desc' },
        visibleColumns: new Set(),
        filters: {
            level: 'all',
            flagged: false,
            scoreMin: null,
            scoreMax: null,
            search: '',
            chips: new Set()
        }
    };

    const TABLE_COLUMNS = [
        { key: 'vlan_id', label: 'VLAN', sortable: true },
        { key: 'coupling_level', label: 'Level', sortable: true },
        { key: 'coupling_score', label: 'Score', sortable: true, numeric: true },
        { key: 'epg_count', label: 'EPGs', sortable: true, numeric: true },
        { key: 'tenant_count', label: 'Tenants', sortable: true, numeric: true },
        { key: 'bd_count', label: 'BDs', sortable: true, numeric: true },
        { key: 'vrf_count', label: 'VRFs', sortable: true, numeric: true },
        { key: 'binding_count', label: 'Bindings', sortable: true, numeric: true },
        { key: 'leaf_count', label: 'Leaves', sortable: true, numeric: true },
        { key: 'fex_count', label: 'FEX', sortable: true, numeric: true }
    ];

    const CHIPS = {
        overlap: row => row.overlap,
        multi_tenant: row => (row.tenant_count || 0) > 1,
        multi_bd: row => (row.bd_count || 0) > 1,
        cross_tenant_bd: row => (row.tenant_count || 0) > 1 && (row.bd_count || 0) > 1,
        high_bindings: row => (row.binding_count || 0) > 50,
        many_leaves: row => (row.leaf_count || 0) > 4,
        leaf_only: row => row.has_leaf_bindings && !row.has_fex_bindings,
        fex_only: row => row.has_fex_bindings && !row.has_leaf_bindings,
        mixed_leaf_fex: row => row.mixed_bindings,
        multi_leaf: row => (row.leaf_count || 0) > 1,
        multi_rack: row => (row.rack_count || 0) > 1
    };

    function initColumns() {
        const stored = window.localStorage.getItem('vlan_column_visibility');
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                if (Array.isArray(parsed)) {
                    state.visibleColumns = new Set(parsed);
                    return;
                }
            } catch (err) {
                console.warn('Failed to parse stored VLAN column visibility', err);
            }
        }
        state.visibleColumns = new Set(TABLE_COLUMNS.map(col => col.key));
    }

    function persistColumns() {
        window.localStorage.setItem('vlan_column_visibility', JSON.stringify(Array.from(state.visibleColumns)));
    }

    function normalize(value) {
        if (value === null || value === undefined) return '';
        return String(value);
    }

    function getLevel(row) {
        if (row.coupling_severity === 'critical') return 'critical';
        return row.coupling_level || 'low';
    }

    function applyFilters() {
        const { level, flagged, scoreMin, scoreMax, search, chips } = state.filters;
        const query = search.trim().toLowerCase();

        state.filtered = state.rows.filter(row => {
            if (level && level !== 'all') {
                if (getLevel(row) !== level) return false;
            }
            if (flagged && !row.flagged) return false;
            if (scoreMin !== null && Number(row.coupling_score || 0) < scoreMin) return false;
            if (scoreMax !== null && Number(row.coupling_score || 0) > scoreMax) return false;
            if (query) {
                const blob = row.search_blob || '';
                if (!blob.includes(query)) return false;
            }
            for (const chip of chips) {
                const fn = CHIPS[chip];
                if (fn && !fn(row)) return false;
            }
            return true;
        });
    }

    function compare(a, b, key, direction) {
        const dir = direction === 'desc' ? -1 : 1;
        const av = a[key];
        const bv = b[key];
        if (typeof av === 'number' && typeof bv === 'number') {
            return (av - bv) * dir;
        }
        return normalize(av).localeCompare(normalize(bv)) * dir;
    }

    function sortRows() {
        const { key, direction } = state.sort;
        if (!key) return;
        state.filtered.sort((a, b) => compare(a, b, key, direction));
    }

    function renderTable() {
        const tbody = document.getElementById('vlan-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        document.querySelectorAll('#vlan-table thead th[data-col]').forEach(th => {
            const key = th.getAttribute('data-col');
            th.style.display = state.visibleColumns.has(key) ? '' : 'none';
        });

        const colSpan = state.visibleColumns.size + 1;

        const summary = document.getElementById('vlan-table-summary');
        if (summary) {
            summary.textContent = `Showing ${state.filtered.length} of ${state.rows.length} VLANs`;
        }

        if (!state.filtered.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = colSpan;
            td.classList.add('vlan-empty');
            td.textContent = buildEmptyMessage();
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        const worst = document.getElementById('worst-vlan-card')?.getAttribute('data-worst-vlan');

        state.filtered.forEach(row => {
            const tr = document.createElement('tr');
            tr.classList.add('vlan-row');
            tr.setAttribute('data-vlan-id', row.vlan_id);
            if (worst && String(row.vlan_id) === String(worst)) {
                tr.classList.add('vlan-row-highlight');
            }
            tr.addEventListener('click', () => {
                const panel = document.getElementById('vlan-mapping-panel');
                if (panel) {
                    renderMappingPanel(row, panel);
                }
            });

            const expander = document.createElement('td');
            expander.classList.add('vlan-expander');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.classList.add('vlan-expander-btn');
            btn.textContent = '+';
            btn.addEventListener('click', e => {
                e.stopPropagation();
                toggleDetails(row.vlan_id, tr, btn);
            });
            expander.appendChild(btn);
            tr.appendChild(expander);

            TABLE_COLUMNS.forEach(col => {
                if (!state.visibleColumns.has(col.key)) return;
                const td = document.createElement('td');
                td.classList.toggle('vlan-num', !!col.numeric);

                if (col.key === 'coupling_level') {
                    const level = getLevel(row);
                    const badge = document.createElement('span');
                    badge.className = `vlan-badge vlan-badge-${level}`;
                    badge.textContent = level;
                    td.appendChild(badge);
                } else {
                    td.textContent = normalize(row[col.key] ?? 'N/A');
                }
                tr.appendChild(td);
            });

            tbody.appendChild(tr);

            const detailRow = document.createElement('tr');
            detailRow.classList.add('vlan-detail-row');
            detailRow.setAttribute('data-vlan-detail', row.vlan_id);
            const detailCell = document.createElement('td');
            detailCell.colSpan = colSpan;
            detailCell.innerHTML = '';
            detailRow.appendChild(detailCell);
            tbody.appendChild(detailRow);
        });
    }

    function buildEmptyMessage() {
        const filters = getActiveFilters().map(f => f.label);
        if (!filters.length) return 'No data to display';
        return `No matching rows (filters: ${filters.join(', ')})`;
    }

    function toggleDetails(vlanId, rowEl, btn) {
        const detailRow = rowEl.nextElementSibling;
        if (!detailRow || !detailRow.classList.contains('vlan-detail-row')) return;
        const isOpen = detailRow.classList.toggle('open');
        btn.textContent = isOpen ? '-' : '+';
        if (isOpen && !detailRow.dataset.rendered) {
            const row = state.filtered.find(r => String(r.vlan_id) === String(vlanId));
            renderDetails(row, detailRow);
            detailRow.dataset.rendered = 'true';
        }
    }

    function renderDetails(row, detailRow) {
        if (!row) return;
        const detailCell = detailRow.querySelector('td');
        const readiness = row.coupling_score >= 35 ? 'Hard' : row.coupling_score >= 15 ? 'Medium' : 'Easy';
        const reasons = row.reasons && row.reasons.length ? row.reasons : (row.why ? [row.why] : []);
        const hasRack = (row.rack_count || 0) > 0;

        detailCell.innerHTML = `
            <div class="vlan-detail-grid">
                <div class="vlan-detail-summary">
                    <div class="vlan-detail-metric">EPGs <strong>${row.epg_count || 0}</strong></div>
                    <div class="vlan-detail-metric">Bindings <strong>${row.binding_count || 0}</strong></div>
                    <div class="vlan-detail-metric">Leaves <strong>${row.leaf_count || 0}</strong></div>
                    <div class="vlan-detail-metric">FEX <strong>${row.fex_count || 0}</strong></div>
                    <div class="vlan-detail-metric">Racks <strong>${row.rack_count || 0}</strong></div>
                    <div class="vlan-detail-metric">Readiness <strong>${readiness}</strong></div>
                </div>
                <div class="vlan-detail-reasons">
                    <h4>Top drivers</h4>
                    <ul>${reasons.slice(0, 3).map(r => `<li>${r}</li>`).join('') || '<li>No drivers available</li>'}</ul>
                </div>
                <div class="vlan-detail-controls">
                    <span>Group by</span>
                    <button type="button" class="vlan-toggle-btn active" data-group="leaf">Leaf</button>
                    <button type="button" class="vlan-toggle-btn" data-group="rack" ${hasRack ? '' : 'disabled'}>Rack</button>
                </div>
            </div>
            <div class="vlan-epg-list" data-vlan="${row.vlan_id}"></div>
        `;

        const container = detailCell.querySelector('.vlan-epg-list');
        renderEpgList(row, container, 'leaf');

        detailCell.querySelectorAll('.vlan-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                detailCell.querySelectorAll('.vlan-toggle-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                renderEpgList(row, container, btn.dataset.group);
            });
        });
    }

    function renderMappingPanel(row, panel) {
        if (!row || !panel) return;
        const epgs = row.epgs || [];
        const bindings = epgs.flatMap(epg => epg.bindings || []);
        const leafs = new Set(bindings.map(b => b.leafId).filter(Boolean));
        const fex = new Set(bindings.map(b => b.fexSerial || b.fexId).filter(Boolean));
        const racks = new Set(bindings.map(b => b.rack).filter(Boolean));
        const reasons = row.reasons && row.reasons.length ? row.reasons : (row.why ? [row.why] : []);

        panel.innerHTML = `
            <div class="vlan-detail-grid">
                <div class="vlan-detail-summary">
                    <div class="vlan-detail-metric">VLAN <strong>${row.vlan_id}</strong></div>
                    <div class="vlan-detail-metric">EPGs <strong>${row.epg_count || epgs.length}</strong></div>
                    <div class="vlan-detail-metric">Bindings <strong>${row.binding_count || bindings.length}</strong></div>
                    <div class="vlan-detail-metric">Leaves <strong>${leafs.size}</strong></div>
                    <div class="vlan-detail-metric">FEX <strong>${fex.size}</strong></div>
                    <div class="vlan-detail-metric">Racks <strong>${racks.size}</strong></div>
                </div>
                <div class="vlan-detail-reasons">
                    <h4>Top drivers</h4>
                    <ul>${reasons.slice(0, 3).map(r => `<li>${r}</li>`).join('') || '<li>No drivers available</li>'}</ul>
                </div>
            </div>
            <div class="vlan-epg-list"></div>
        `;
        renderEpgList(row, panel.querySelector('.vlan-epg-list'), 'leaf');
    }

    function renderEpgList(row, container, groupBy) {
        const epgs = row.epgs || [];
        if (!container) return;
        if (!epgs.length) {
            container.innerHTML = '<div class="vlan-empty">No EPG bindings available for this VLAN.</div>';
            return;
        }

        const html = epgs.map(epg => {
            const title = `${epg.tenant || 'Unknown'} / ${epg.app || 'Unknown'} / ${epg.epg || 'Unknown'}`;
            const bindings = Array.isArray(epg.bindings) ? epg.bindings : [];
            const grouped = groupBindings(bindings, groupBy);
            const groupsHtml = Object.entries(grouped).map(([label, items]) => {
                const list = items.map(item => renderBinding(item)).join('');
                return `<div class="vlan-binding-group"><h5>${label}</h5><div class="vlan-binding-list">${list}</div></div>`;
            }).join('');
            return `
                <details class="vlan-epg-item">
                    <summary>
                        <span class="vlan-epg-title">${title}</span>
                        <span class="vlan-epg-meta">BD ${epg.bd || 'N/A'} - VRF ${epg.vrf || 'N/A'} - ${bindings.length} bindings</span>
                    </summary>
                    <div class="vlan-epg-body">${groupsHtml}</div>
                </details>
            `;
        }).join('');

        container.innerHTML = html;
        container.querySelectorAll('.vlan-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const value = btn.getAttribute('data-copy');
                if (!value) return;
                navigator.clipboard?.writeText(value).then(() => {
                    btn.textContent = 'Copied';
                    setTimeout(() => (btn.textContent = 'Copy path'), 1500);
                });
            });
        });
    }

    function groupBindings(bindings, groupBy) {
        const grouped = {};
        bindings.forEach(binding => {
            let key = 'Unknown';
            if (groupBy === 'rack') {
                key = binding.rack || 'Unknown Rack';
            } else {
                key = binding.leafName || (binding.leafId ? `Leaf ${binding.leafId}` : 'Leaf Unknown');
            }
            if (!grouped[key]) grouped[key] = [];
            grouped[key].push(binding);
        });
        return grouped;
    }

    function renderBinding(binding) {
        const leafLabel = binding.leafName || (binding.leafId ? `Leaf ${binding.leafId}` : 'Leaf Unknown');
        const fexLabel = binding.fexSerial ? `FEX ${binding.fexSerial}` : (binding.fexId ? `FEX ${binding.fexId}` : '');
        const rackLabel = binding.rack ? `Rack ${binding.rack}` : '';
        const path = binding.path || '';
        const interfaceLabel = binding.interface || 'N/A';
        return `
            <div class="vlan-binding">
                <span class="vlan-pill">${binding.binding_type === 'fex' ? 'FEX' : 'Leaf'}</span>
                <span class="vlan-pill">${leafLabel}</span>
                ${fexLabel ? `<span class="vlan-pill">${fexLabel}</span>` : ''}
                ${rackLabel ? `<span class="vlan-pill">${rackLabel}</span>` : ''}
                <span class="vlan-binding-path">${interfaceLabel}</span>
                ${path ? `<button type="button" class="vlan-copy" data-copy="${path}">Copy path</button>` : ''}
            </div>
        `;
    }

    function renderColumnMenu() {
        const list = document.getElementById('vlan-column-list');
        if (!list) return;
        list.innerHTML = '';
        TABLE_COLUMNS.forEach(col => {
            const label = document.createElement('label');
            label.classList.add('vlan-column-option');
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = state.visibleColumns.has(col.key);
            input.addEventListener('change', () => {
                if (input.checked) {
                    state.visibleColumns.add(col.key);
                } else {
                    state.visibleColumns.delete(col.key);
                }
                persistColumns();
                renderTable();
            });
            label.appendChild(input);
            label.appendChild(document.createTextNode(col.label));
            list.appendChild(label);
        });
    }

    function setupDropdowns() {
        document.querySelectorAll('.vlan-dropdown').forEach(dropdown => {
            const button = dropdown.querySelector('.vlan-action-btn');
            const menu = dropdown.querySelector('.vlan-dropdown-menu');
            button.addEventListener('click', e => {
                e.stopPropagation();
                const open = !menu.hasAttribute('hidden');
                document.querySelectorAll('.vlan-dropdown-menu').forEach(m => m.setAttribute('hidden', ''));
                if (!open) menu.removeAttribute('hidden');
            });
        });
        document.addEventListener('click', () => {
            document.querySelectorAll('.vlan-dropdown-menu').forEach(menu => menu.setAttribute('hidden', ''));
        });
    }

    function setupSorting() {
        document.querySelectorAll('#vlan-table thead th[data-col]').forEach(th => {
            const key = th.getAttribute('data-col');
            th.addEventListener('click', () => {
                if (state.sort.key === key) {
                    state.sort.direction = state.sort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    state.sort.key = key;
                    state.sort.direction = 'desc';
                }
                update();
            });
        });
    }

    function setupFilters() {
        document.querySelectorAll('input[name="coupling-level"]').forEach(input => {
            input.addEventListener('change', () => {
                state.filters.level = input.value;
                update();
            });
        });
        const flagged = document.getElementById('vlan-flagged-toggle');
        flagged.addEventListener('change', e => {
            state.filters.flagged = e.target.checked;
            update();
        });
        const scoreMin = document.getElementById('vlan-score-min');
        const scoreMax = document.getElementById('vlan-score-max');
        scoreMin.addEventListener('input', e => {
            const val = e.target.value === '' ? null : Number(e.target.value);
            state.filters.scoreMin = Number.isNaN(val) ? null : val;
            update();
        });
        scoreMax.addEventListener('input', e => {
            const val = e.target.value === '' ? null : Number(e.target.value);
            state.filters.scoreMax = Number.isNaN(val) ? null : val;
            update();
        });
        const search = document.getElementById('vlan-search');
        search.addEventListener('input', e => {
            state.filters.search = e.target.value || '';
            update();
        });
        document.querySelectorAll('#vlan-quick-filters .vlan-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const key = chip.dataset.chip;
                if (state.filters.chips.has(key)) {
                    state.filters.chips.delete(key);
                    chip.classList.remove('active');
                } else {
                    state.filters.chips.add(key);
                    chip.classList.add('active');
                }
                update();
            });
        });
        const reset = document.getElementById('vlan-reset');
        reset.addEventListener('click', () => resetFilters());
    }

    function resetFilters() {
        state.filters.level = 'all';
        state.filters.flagged = false;
        state.filters.scoreMin = null;
        state.filters.scoreMax = null;
        state.filters.search = '';
        state.filters.chips.clear();

        document.querySelectorAll('input[name="coupling-level"]').forEach(input => {
            input.checked = input.value === 'all';
        });
        const flagged = document.getElementById('vlan-flagged-toggle');
        if (flagged) flagged.checked = false;
        const scoreMin = document.getElementById('vlan-score-min');
        const scoreMax = document.getElementById('vlan-score-max');
        if (scoreMin) scoreMin.value = '';
        if (scoreMax) scoreMax.value = '';
        const search = document.getElementById('vlan-search');
        if (search) search.value = '';
        document.querySelectorAll('#vlan-quick-filters .vlan-chip').forEach(chip => chip.classList.remove('active'));
        update();
    }

    function updateActiveChips() {
        const container = document.getElementById('vlan-active-chips');
        if (!container) return;
        container.innerHTML = '';
        getActiveFilters().forEach(filter => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.classList.add('vlan-chip', 'active');
            chip.textContent = filter.label;
            chip.addEventListener('click', () => removeFilter(filter));
            container.appendChild(chip);
        });
    }

    function getActiveFilters() {
        const filters = [];
        if (state.filters.level && state.filters.level !== 'all') {
            filters.push({ type: 'level', value: state.filters.level, label: state.filters.level });
        }
        if (state.filters.flagged) {
            filters.push({ type: 'flagged', value: true, label: 'Flagged' });
        }
        if (state.filters.scoreMin !== null || state.filters.scoreMax !== null) {
            filters.push({
                type: 'score',
                value: [state.filters.scoreMin, state.filters.scoreMax],
                label: `Score ${state.filters.scoreMin ?? 0}-${state.filters.scoreMax ?? 100}`
            });
        }
        if (state.filters.search) {
            filters.push({ type: 'search', value: state.filters.search, label: `Search "${state.filters.search}"` });
        }
        state.filters.chips.forEach(chip => {
            filters.push({ type: 'chip', value: chip, label: chip.replace(/_/g, ' ') });
        });
        return filters;
    }

    function removeFilter(filter) {
        if (filter.type === 'level') {
            state.filters.level = 'all';
            document.querySelectorAll('input[name="coupling-level"]').forEach(input => {
                input.checked = input.value === 'all';
            });
        } else if (filter.type === 'flagged') {
            state.filters.flagged = false;
            const flagged = document.getElementById('vlan-flagged-toggle');
            if (flagged) flagged.checked = false;
        } else if (filter.type === 'score') {
            state.filters.scoreMin = null;
            state.filters.scoreMax = null;
            const scoreMin = document.getElementById('vlan-score-min');
            const scoreMax = document.getElementById('vlan-score-max');
            if (scoreMin) scoreMin.value = '';
            if (scoreMax) scoreMax.value = '';
        } else if (filter.type === 'search') {
            state.filters.search = '';
            const search = document.getElementById('vlan-search');
            if (search) search.value = '';
        } else if (filter.type === 'chip') {
            state.filters.chips.delete(filter.value);
            document.querySelectorAll(`#vlan-quick-filters .vlan-chip[data-chip="${filter.value}"]`).forEach(chip => {
                chip.classList.remove('active');
            });
        }
        update();
    }

    function setupExport() {
        const menu = document.getElementById('vlan-export-dropdown');
        if (!menu) return;
        menu.querySelectorAll('[data-export]').forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.export;
                if (mode === 'summary') {
                    exportSummary();
                } else {
                    exportDetailed();
                }
            });
        });
    }

    function exportSummary() {
        const headers = [
            'vlan_id', 'coupling_level', 'score', 'flagged', 'overlap',
            'epg_count', 'tenant_count', 'bd_count', 'vrf_count',
            'binding_count', 'leaf_count', 'fex_count',
            'tenants', 'bds', 'vrfs', 'reasons'
        ];
        const lines = [headers.join(',')];
        state.filtered.forEach(row => {
            const values = [
                row.vlan_id,
                getLevel(row),
                row.coupling_score,
                row.flagged,
                row.overlap,
                row.epg_count,
                row.tenant_count,
                row.bd_count,
                row.vrf_count,
                row.binding_count,
                row.leaf_count,
                row.fex_count,
                (row.tenants || []).join(';'),
                (row.bds || []).join(';'),
                (row.vrfs || []).join(';'),
                (row.reasons || []).join('; ')
            ];
            lines.push(values.map(escapeCsv).join(','));
        });
        downloadCsv(lines.join('\n'), 'vlan_summary');
    }

    function exportDetailed() {
        const headers = [
            'vlan_id', 'coupling_level', 'score',
            'tenant', 'app', 'epg', 'bd', 'vrf',
            'binding_type', 'leafId', 'leafName', 'fexId', 'fexSerial',
            'rack', 'site', 'building', 'hall', 'interface', 'path', 'encap'
        ];
        const lines = [headers.join(',')];
        state.filtered.forEach(row => {
            const level = getLevel(row);
            (row.epgs || []).forEach(epg => {
                (epg.bindings || []).forEach(binding => {
                    const values = [
                        row.vlan_id,
                        level,
                        row.coupling_score,
                        epg.tenant,
                        epg.app,
                        epg.epg,
                        epg.bd,
                        epg.vrf,
                        binding.binding_type,
                        binding.leafId,
                        binding.leafName,
                        binding.fexId,
                        binding.fexSerial,
                        binding.rack,
                        binding.site,
                        binding.building,
                        binding.hall,
                        binding.interface,
                        binding.path,
                        binding.encap
                    ];
                    lines.push(values.map(escapeCsv).join(','));
                });
            });
        });
        downloadCsv(lines.join('\n'), 'vlan_detailed');
    }

    function escapeCsv(value) {
        const str = value === null || value === undefined ? '' : String(value);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
    }

    function downloadCsv(content, name) {
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${name}_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function setupWorstVlanLink() {
        const card = document.getElementById('worst-vlan-card');
        const button = card?.querySelector('.vlan-kpi-link');
        const target = card?.getAttribute('data-worst-vlan');
        if (!button || !target) return;
        button.addEventListener('click', () => {
            const row = document.querySelector(`tr.vlan-row[data-vlan-id="${target}"]`);
            if (!row) return;
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            row.classList.add('vlan-row-highlight');
            setTimeout(() => row.classList.remove('vlan-row-highlight'), 2000);
        });
    }

    function update() {
        applyFilters();
        sortRows();
        updateActiveChips();
        renderTable();
    }

        function init() {
            initColumns();
            renderColumnMenu();
            setupDropdowns();
            setupSorting();
            setupFilters();
            setupExport();
            setupWorstVlanLink();
            const reset = document.getElementById('vlan-mapping-reset');
            if (reset) {
                reset.addEventListener('click', () => {
                    const panel = document.getElementById('vlan-mapping-panel');
                    if (panel) {
                        panel.innerHTML = '<div class="text-sm text-gray-500">No VLAN selected yet.</div>';
                    }
                });
            }
            update();
        }

        init();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVlanExplorer);
    } else {
        initVlanExplorer();
    }
})();
