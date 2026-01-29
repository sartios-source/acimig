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

    function initExplorer(section) {
        const id = section.getAttribute('id');
        const rows = parseJson(`${id}-rows`) || [];
        const config = parseJson(`${id}-config`) || {};
        const columns = (config.columns || []).map((col, index) => ({
            title: col.label || col.title || col.field,
            field: col.key || col.field,
            headerFilter: col.filter !== false,
            hozAlign: col.numeric ? 'right' : 'left',
            sorter: col.sorter || (col.numeric ? 'number' : 'string'),
            frozen: col.frozen || index === 0
        }));

        const tableEl = section.querySelector(`[data-table="${id}"]`);
        if (!tableEl) return;

        const table = new Tabulator(tableEl, {
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

        const searchInput = section.querySelector(`[data-search="${id}"]`);
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                const value = searchInput.value.toLowerCase();
                if (!value) {
                    table.clearFilter();
                } else {
                    table.setFilter(row => {
                        return Object.values(row).some(val => String(val ?? '').toLowerCase().includes(value));
                    });
                }
                updateChartAndPivot(table, section, config);
            });
        }

        const pageSelect = section.querySelector(`[data-page-size="${id}"]`);
        if (pageSelect) {
            pageSelect.addEventListener('change', () => {
                table.setPageSize(Number(pageSelect.value || 100));
            });
        }

        const exportBtn = section.querySelector('.bi-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                table.download('csv', `${id}_export.csv`);
            });
        }

        section.querySelectorAll('[data-filter-field]').forEach(input => {
            input.addEventListener('change', () => {
                const field = input.getAttribute('data-filter-field');
                const value = input.getAttribute('data-filter-value');
                const active = section.querySelectorAll(`[data-filter-field="${field}"]:checked`);
                if (!active.length || value === 'all') {
                    table.removeFilter(field, '=');
                } else {
                    const selected = Array.from(active).map(item => item.getAttribute('data-filter-value'));
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

        updateChartAndPivot(table, section, config);
    }

    function updateChartAndPivot(table, section, config) {
        const data = table.getData('active');
        const chartCanvas = section.querySelector(`[data-chart="${section.id}"]`);
        if (chartCanvas) {
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
