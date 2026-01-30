(() => {
    function parseJson(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        try {
            return JSON.parse(el.textContent || 'null');
        } catch (err) {
            console.error('BI explorer JSON parse failed:', id, err);
            return null;
        }
    }

    function formatNumber(value) {
        if (value === null || value === undefined || value === '') return 'N/A';
        const num = Number(value);
        if (Number.isNaN(num)) return value;
        return num.toLocaleString();
    }

    function aggregate(rows, field, agg, filter) {
        let scoped = rows;
        if (filter && filter.field) {
            scoped = rows.filter(row => {
                const val = row[filter.field];
                if (filter.equals !== undefined) return String(val) === String(filter.equals);
                return true;
            });
        }
        if (agg === 'count') return scoped.length;
        if (agg === 'unique') {
            return new Set(scoped.map(row => row[field]).filter(v => v !== null && v !== undefined && v !== '')).size;
        }
        if (agg === 'sum') {
            return scoped.reduce((acc, row) => acc + (Number(row[field]) || 0), 0);
        }
        if (agg === 'max') {
            return scoped.reduce((acc, row) => Math.max(acc, Number(row[field]) || 0), 0);
        }
        return '';
    }

    function buildKpis(rows, config, container) {
        if (!container) return;
        container.innerHTML = '';
        const kpis = config.kpis || [];
        if (!kpis.length) return;
        kpis.forEach(kpi => {
            const value = aggregate(rows, kpi.field, kpi.agg || 'count', kpi.filter);
            const card = document.createElement('div');
            card.className = 'bi-kpi';
            card.innerHTML = `
                <p>${kpi.label}</p>
                <h3>${formatNumber(value)}</h3>
            `;
            container.appendChild(card);
        });
    }

    function buildPivot(rows, rowField, colField, container) {
        if (!container || !rowField || !colField) return;
        const pivot = {};
        const rowValues = new Set();
        const colValues = new Set();

        rows.forEach(row => {
            const r = row[rowField] ?? 'Unknown';
            const c = row[colField] ?? 'Unknown';
            rowValues.add(r);
            colValues.add(c);
            pivot[r] = pivot[r] || {};
            pivot[r][c] = (pivot[r][c] || 0) + 1;
        });

        const rowList = Array.from(rowValues).sort();
        const colList = Array.from(colValues).sort();

        let html = '<table class="table table-sm table-striped">';
        html += '<thead><tr><th>' + rowField + '</th>';
        colList.forEach(c => {
            html += `<th>${c}</th>`;
        });
        html += '</tr></thead><tbody>';
        rowList.forEach(r => {
            html += `<tr><td>${r}</td>`;
            colList.forEach(c => {
                html += `<td>${pivot[r]?.[c] || 0}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    function fetchRemote(config, page, size, search, sortField, sortDir) {
        if (!config || !config.remoteUrl) {
            return Promise.resolve({ rows: [], total: 0, page: 1, size: size });
        }
        const params = new URLSearchParams();
        params.set('page', String(page));
        params.set('size', String(size));
        if (search) params.set('search', search);
        if (sortField) params.set('sort', sortField);
        if (sortDir) params.set('dir', sortDir);
        return fetch(`${config.remoteUrl}?${params.toString()}`)
            .then(res => {
                if (!res.ok) {
                    return { rows: [], total: 0, page: 1, size: size, error: `HTTP ${res.status}` };
                }
                return res.json();
            })
            .catch(err => {
                console.error('Remote BI fetch failed', err);
                if (window.reportUiError) {
                    window.reportUiError({
                        source: 'bi_explorer',
                        message: 'Remote BI fetch failed',
                        detail: String(err)
                    });
                }
                return { rows: [], total: 0, page: 1, size: size, error: 'Network error' };
            });
    }

    function applyConditionalFormatting(cell) {
        const field = cell.getField();
        const value = cell.getValue();
        if (value === null || value === undefined) return;

        if (field.includes('score') || field.includes('utilization')) {
            const num = Number(value);
            if (Number.isNaN(num)) return;
            if (num >= 60) cell.getElement().classList.add('bi-cell-high');
            else if (num >= 35) cell.getElement().classList.add('bi-cell-med');
            else cell.getElement().classList.add('bi-cell-low');
        }
        if (field.includes('status') && String(value).toLowerCase().includes('needs')) {
            cell.getElement().classList.add('bi-cell-warn');
        }
    }

    function badgeClassFor(field, value) {
        const normalized = String(value || '').toLowerCase();
        if (field === 'coupling_level' || field === 'complexity_level') {
            if (normalized.includes('critical')) return 'bi-badge--critical';
            if (normalized.includes('high')) return 'bi-badge--high';
            if (normalized.includes('medium')) return 'bi-badge--medium';
            if (normalized.includes('low')) return 'bi-badge--low';
        }
        if (field === 'difficulty_bucket') {
            if (normalized.includes('blocked')) return 'bi-badge--blocked';
            if (normalized.includes('hard')) return 'bi-badge--hard';
            if (normalized.includes('easy')) return 'bi-badge--easy';
            if (normalized.includes('moderate')) return 'bi-badge--moderate';
        }
        if (field === 'matched_label') {
            if (normalized.includes('matched')) return 'bi-badge--matched';
            if (normalized.includes('unmatched')) return 'bi-badge--unmatched';
        }
        if (field === 'MatchReason' || field === 'match_reason') {
            return 'bi-badge--soft';
        }
        if (field === 'vpc_symmetry') {
            if (normalized.includes('symmetric')) return 'bi-badge--matched';
            if (normalized.includes('asymmetric')) return 'bi-badge--unmatched';
        }
        return 'bi-badge--soft';
    }

    function badgeFormatter(field) {
        return function(cell) {
            const value = cell.getValue();
            if (value === null || value === undefined || value === '') return '';
            const badgeClass = badgeClassFor(field, value);
            const text = String(value);
            return `<span class="bi-badge ${badgeClass}">${text}</span>`;
        };
    }

    function setDebugBanner(banner, message) {
        if (!banner) return;
        if (!message) {
            banner.textContent = '';
            banner.hidden = true;
            return;
        }
        banner.textContent = message;
        banner.hidden = false;
    }

    function renderSimpleTable(tableEl, columns, rows) {
        if (!tableEl) return;
        const cols = columns || [];
        const data = rows || [];
        let html = '<table class="table table-sm table-striped mb-0"><thead><tr>';
        cols.forEach(col => {
            html += `<th>${col.label || col.title || col.field || ''}</th>`;
        });
        html += '</tr></thead><tbody>';
        data.slice(0, 200).forEach(row => {
            html += '<tr>';
            cols.forEach(col => {
                const key = col.key || col.field;
                const val = row && key ? row[key] : '';
                html += `<td>${val === null || val === undefined ? '' : String(val)}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        tableEl.innerHTML = html;
    }

    function updateDebugBanner(banner, config, table, payload) {
        if (!banner) return;
        if (payload && payload.error) {
            setDebugBanner(banner, `Data fetch failed (${payload.error}). If the API works, this is a UI binding issue.`);
            return;
        }
        if (payload && typeof payload.total === 'number' && payload.total > 0) {
            const shown = table ? table.getData().length : 0;
            if (shown === 0) {
                setDebugBanner(banner, `Data returned (${payload.total} rows) but table is empty. UI binding failed.`);
                return;
            }
        }
        setDebugBanner(banner, '');
    }

    function initExplorer(section) {
        const id = section.getAttribute('id');
        const rows = parseJson(`${id}-rows`) || [];
        const config = parseJson(`${id}-config`) || {};
        const debugBanner = section.querySelector('.bi-debug-banner');
        const isNextMode = document.body.classList.contains('ui-next');
        const badgeFields = new Set(['coupling_level', 'complexity_level', 'difficulty_bucket', 'matched_label', 'vpc_symmetry', 'MatchReason', 'match_reason']);
        const columns = (config.columns || []).map((col, index) => ({
            title: col.label || col.title || col.field,
            field: col.key || col.field,
            headerFilter: col.filter !== false,
            hozAlign: col.numeric ? 'right' : 'left',
            sorter: col.sorter || (col.numeric ? 'number' : 'string'),
            frozen: col.frozen || index === 0,
            formatter: isNextMode && badgeFields.has(col.key || col.field)
                ? badgeFormatter(col.key || col.field)
                : (col.formatter || undefined)
        }));

        const tableEl = section.querySelector(`[data-table="${id}"]`);
        if (!tableEl) return;
        const tabulatorAvailable = typeof Tabulator !== 'undefined';

        let table = null;
        if (tabulatorAvailable) {
            table = new Tabulator(tableEl, {
                data: rows,
                columns: columns,
                layout: 'fitColumns',
                height: '520px',
                pagination: 'local',
                paginationSize: 100,
                movableColumns: true,
                placeholder: 'No data available',
                rowClick: (e, row) => {
                    const drawer = document.getElementById('biDetailDrawer');
                    const body = document.getElementById('biDetailBody');
                    if (drawer && body) {
                        body.textContent = JSON.stringify(row.getData(), null, 2);
                        const offcanvas = bootstrap.Offcanvas.getOrCreateInstance(drawer);
                        offcanvas.show();
                    }
                },
                rowFormatter: row => {
                    row.getCells().forEach(applyConditionalFormatting);
                }
            });
            buildKpis(rows, config, section.querySelector(`[data-kpis="${id}"]`));
        } else {
            setDebugBanner(debugBanner, 'Tabulator not loaded. Rendering basic table fallback.');
            if (window.reportUiError) {
                window.reportUiError({
                    source: 'bi_explorer',
                    message: 'Tabulator not loaded',
                    detail: `explorer=${id}`
                });
            }
            renderSimpleTable(tableEl, config.columns || [], rows);
        }

        const searchInput = section.querySelector(`[data-search="${id}"]`);
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const value = searchInput.value.toLowerCase();
                if (config.remote) {
                    fetchRemote(config, 1, table.getPageSize(), value, table.getSorters()[0]?.field, table.getSorters()[0]?.dir)
                        .then(payload => {
                            if (table) {
                                table.setData(payload.rows);
                                buildKpis(payload.rows, config, section.querySelector(`[data-kpis="${id}"]`));
                                updateChartAndPivot(table, section, config);
                            } else {
                                renderSimpleTable(tableEl, config.columns || [], payload.rows || []);
                            }
                            updateDebugBanner(debugBanner, config, table, payload);
                        });
                } else {
                    if (!value) {
                        table && table.clearFilter();
                    } else {
                        table && table.setFilter(row => {
                            return Object.values(row).some(val => String(val ?? '').toLowerCase().includes(value));
                        });
                    }
                    if (table) updateChartAndPivot(table, section, config);
                }
            });
        }

        const pageSelect = section.querySelector(`[data-page-size="${id}"]`);
        if (pageSelect) {
            pageSelect.addEventListener('change', () => {
                const size = Number(pageSelect.value || 100);
                table && table.setPageSize(size);
                if (config.remote) {
                    fetchRemote(config, 1, size, searchInput?.value || '', table?.getSorters?.()[0]?.field, table?.getSorters?.()[0]?.dir)
                        .then(payload => {
                            if (table) {
                                table.setData(payload.rows);
                                buildKpis(payload.rows, config, section.querySelector(`[data-kpis="${id}"]`));
                                updateChartAndPivot(table, section, config);
                            } else {
                                renderSimpleTable(tableEl, config.columns || [], payload.rows || []);
                            }
                            updateDebugBanner(debugBanner, config, table, payload);
                        });
                }
            });
        }

        const exportBtn = section.querySelector('.bi-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                if (table) {
                    table.download('csv', `${id}_export.csv`);
                } else {
                    setDebugBanner(debugBanner, 'Export not available in fallback mode.');
                }
            });
        }

        const scopedFilters = Array.from(section.querySelectorAll('[data-filter-field]'));
        const externalFilters = Array.from(document.querySelectorAll(`[data-filter-field][data-filter-target="${id}"]`));
        const filterInputs = Array.from(new Set(scopedFilters.concat(externalFilters)));
        filterInputs.forEach(input => {
            input.addEventListener('change', () => {
                const field = input.getAttribute('data-filter-field');
                const value = input.getAttribute('data-filter-value');
                const active = filterInputs.filter(item => item.getAttribute('data-filter-field') === field && item.checked);
                if (!active.length || value === 'all') {
                    table.removeFilter(field, '=');
                } else {
                    const selected = active.map(item => item.getAttribute('data-filter-value'));
                    table.setFilter(row => selected.includes(String(row[field])));
                }
                updateChartAndPivot(table, section, config);
            });
        });

        const rowSelect = section.querySelector(`[data-pivot-rows="${id}"]`);
        const colSelect = section.querySelector(`[data-pivot-cols="${id}"]`);
        const pivotRun = section.querySelector(`[data-pivot-run="${id}"]`);
        if (rowSelect && colSelect) {
            columns.forEach(col => {
                const opt = document.createElement('option');
                opt.value = col.field;
                opt.textContent = col.title;
                rowSelect.appendChild(opt.cloneNode(true));
                colSelect.appendChild(opt);
            });
        }
        if (pivotRun && rowSelect && colSelect) {
            pivotRun.addEventListener('click', () => {
                const data = table.getData('active');
                const pivotContainer = section.querySelector(`[data-pivot-table="${id}"]`);
                buildPivot(data, rowSelect.value, colSelect.value, pivotContainer);
            });
        }

        if (config.remote) {
            fetchRemote(config, 1, table?.getPageSize?.() || 100, searchInput?.value || '', table?.getSorters?.()[0]?.field, table?.getSorters?.()[0]?.dir)
                .then(payload => {
                    if (table) {
                        table.setData(payload.rows);
                        buildKpis(payload.rows, config, section.querySelector(`[data-kpis="${id}"]`));
                        updateChartAndPivot(table, section, config);
                    } else {
                        renderSimpleTable(tableEl, config.columns || [], payload.rows || []);
                    }
                    updateDebugBanner(debugBanner, config, table, payload);
                });
        } else {
            if (table) updateChartAndPivot(table, section, config);
            if (rows.length === 0) {
                setDebugBanner(debugBanner, 'No local rows provided to UI. If the backend has data, check binding.');
            }
        }
    }

    function updateChartAndPivot(table, section, config) {
        const data = table.getData('active');
        const chartCanvas = section.querySelector(`[data-chart="${section.id}"]`);
        if (chartCanvas) {
            if (typeof Chart === 'undefined') {
                if (window.reportUiError) {
                    window.reportUiError({
                        source: 'bi_explorer',
                        message: 'Chart.js not loaded',
                        detail: `explorer=${section.id}`
                    });
                }
                return;
            }
            const ctx = chartCanvas.getContext('2d');
            const chartConfig = config.chart || {};
            const field = chartConfig.field || '';
            const type = chartConfig.type || 'bar';
            const label = chartConfig.label || field;
            const counts = {};
            if (field) {
                data.forEach(row => {
                    const key = row[field] ?? 'Unknown';
                    counts[key] = (counts[key] || 0) + 1;
                });
            }
            if (chartCanvas._chart) chartCanvas._chart.destroy();
            chartCanvas._chart = new Chart(ctx, {
                type: type,
                data: {
                    labels: Object.keys(counts),
                    datasets: [{
                        label: label,
                        data: Object.values(counts),
                        backgroundColor: '#0f5f9c'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
        }

        const pivotContainer = section.querySelector(`[data-pivot-table="${section.id}"]`);
        const rowSelect = section.querySelector(`[data-pivot-rows="${section.id}"]`);
        const colSelect = section.querySelector(`[data-pivot-cols="${section.id}"]`);
        if (pivotContainer && rowSelect && colSelect && rowSelect.value && colSelect.value) {
            buildPivot(data, rowSelect.value, colSelect.value, pivotContainer);
        }
    }

    document.querySelectorAll('.bi-explorer').forEach(initExplorer);
})();
