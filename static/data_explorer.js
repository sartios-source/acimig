(() => {
    const DEFAULT_PAGE_SIZE = 25;

    function parseJsonById(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        try {
            return JSON.parse(el.textContent || 'null');
        } catch (err) {
            console.error(`Failed to parse JSON for ${id}`, err);
            return null;
        }
    }

    function getValue(row, key) {
        if (!row || !key) return null;
        if (!key.includes('.')) return row[key];
        return key.split('.').reduce((acc, part) => (acc && acc[part] !== undefined) ? acc[part] : null, row);
    }

    function normalizeValue(value) {
        if (value === null || value === undefined || value === '') {
            return 'Unknown';
        }
        if (Array.isArray(value)) {
            return value.length ? value.join(', ') : 'Unknown';
        }
        if (typeof value === 'object') {
            return JSON.stringify(value);
        }
        return String(value);
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatList(values, emptyLabel) {
        if (!Array.isArray(values) || !values.length) return emptyLabel || 'None';
        return values.map(item => escapeHtml(item)).join(', ');
    }

    function buildBindingLine(binding) {
        const parts = [];
        const bindingType = binding.binding_type || binding.type || '';
        if (bindingType) parts.push(bindingType.toUpperCase());
        if (binding.leafName || binding.leafId) parts.push(binding.leafName || `Leaf ${binding.leafId}`);
        if (binding.fexSerial || binding.fexId) parts.push(binding.fexSerial || `FEX ${binding.fexId}`);
        if (binding.rack) parts.push(`Rack ${binding.rack}`);
        if (binding.interface) parts.push(binding.interface);
        return parts.filter(Boolean).map(part => escapeHtml(part)).join(' | ');
    }

    function buildMappingSection(row) {
        if (!row) return '';
        if (Array.isArray(row.epgs) && row.epgs.length && typeof row.epgs[0] === 'object') {
            const epgBlocks = row.epgs.map(epg => {
                const title = `${epg.tenant || 'Unknown'} / ${epg.app || 'Unknown'} / ${epg.epg || 'Unknown'}`;
                const bindings = Array.isArray(epg.bindings) ? epg.bindings : [];
                const bindingLines = bindings.slice(0, 50).map(binding => `<li>${buildBindingLine(binding) || 'Binding'}</li>`).join('');
                const remainder = bindings.length > 50 ? `<div class="de-muted">+ ${bindings.length - 50} more bindings</div>` : '';
                return `
                    <div class="de-mapping-group">
                        <div class="de-mapping-title">${escapeHtml(title)}</div>
                        <ul class="de-mapping-list">${bindingLines || '<li>No bindings found</li>'}</ul>
                        ${remainder}
                    </div>
                `;
            }).join('');
            return `
                <div class="de-drawer-section">
                    <h5>EPG to Leaf/FEX mapping</h5>
                    ${epgBlocks}
                </div>
            `;
        }

        if (Array.isArray(row.epgs) && row.epgs.length) {
            return `
                <div class="de-drawer-section">
                    <h5>EPG list</h5>
                    <div class="de-muted">${formatList(row.epgs)}</div>
                    <div class="de-export-row">
                        <button type="button" class="de-export-quick" data-export="epgs">Export EPGs</button>
                    </div>
                </div>
            `;
        }

        if (Array.isArray(row.bindings) && row.bindings.length) {
            const bindingLines = row.bindings.slice(0, 50).map(binding => `<li>${buildBindingLine(binding) || 'Binding'}</li>`).join('');
            const remainder = row.bindings.length > 50 ? `<div class="de-muted">+ ${row.bindings.length - 50} more bindings</div>` : '';
            return `
                <div class="de-drawer-section">
                    <h5>Bindings</h5>
                    <ul class="de-mapping-list">${bindingLines || '<li>No bindings found</li>'}</ul>
                    ${remainder}
                </div>
            `;
        }

        const impactRows = [];
        if (row.impacted_epgs) impactRows.push(`<div><strong>EPGs</strong>: ${formatList(row.impacted_epgs)}</div>`);
        if (row.impacted_vlans) impactRows.push(`<div><strong>VLANs</strong>: ${formatList(row.impacted_vlans)}</div>`);
        if (row.impacted_bds) impactRows.push(`<div><strong>BDs</strong>: ${formatList(row.impacted_bds)}</div>`);
        if (row.impacted_vrfs) impactRows.push(`<div><strong>VRFs</strong>: ${formatList(row.impacted_vrfs)}</div>`);
        if (row.impacted_tenants) impactRows.push(`<div><strong>Tenants</strong>: ${formatList(row.impacted_tenants)}</div>`);
        if (row.top_coupled_vlans && Array.isArray(row.top_coupled_vlans)) {
            const items = row.top_coupled_vlans.map(v => `${v.vlan_id} (${v.level || 'n/a'})`).join(', ');
            impactRows.push(`<div><strong>Top Coupled VLANs</strong>: ${escapeHtml(items) || 'None'}</div>`);
        }
        if (impactRows.length) {
            return `
                <div class="de-drawer-section">
                    <h5>Impact summary</h5>
                    ${impactRows.join('')}
                    <div class="de-export-row">
                        ${row.impacted_epgs ? '<button type="button" class="de-export-quick" data-export="impacted_epgs">Export EPGs</button>' : ''}
                        ${row.impacted_vlans ? '<button type="button" class="de-export-quick" data-export="impacted_vlans">Export VLANs</button>' : ''}
                        ${row.ports ? '<button type="button" class="de-export-quick" data-export="ports">Export Ports</button>' : ''}
                    </div>
                </div>
            `;
        }

        if (Array.isArray(row.ports) && row.ports.length) {
            return `
                <div class="de-drawer-section">
                    <h5>Ports</h5>
                    <div class="de-muted">${formatList(row.ports)}</div>
                    <div class="de-export-row">
                        <button type="button" class="de-export-quick" data-export="ports">Export Ports</button>
                    </div>
                </div>
            `;
        }

        return '';
    }

    function compareValues(a, b, type, direction) {
        const dir = direction === 'desc' ? -1 : 1;
        if (a === null || a === undefined || a === '') return 1;
        if (b === null || b === undefined || b === '') return -1;
        if (type === 'number') {
            const numA = Number(a);
            const numB = Number(b);
            if (Number.isNaN(numA) || Number.isNaN(numB)) return 0;
            return (numA - numB) * dir;
        }
        return String(a).localeCompare(String(b)) * dir;
    }

    function applyFilters(data, state) {
        return data.filter(row => {
            if (state.flagOnly && state.flagField) {
                if (!row[state.flagField]) return false;
            }
            if (state.search) {
                const query = state.search.toLowerCase();
                const matches = state.columns.some(col => {
                    const val = getValue(row, col.key);
                    return normalizeValue(val).toLowerCase().includes(query);
                });
                if (!matches) return false;
            }
            for (const [key, filterValue] of Object.entries(state.filters)) {
                if (!filterValue) continue;
                const col = state.columns.find(c => c.key === key) || {};
                const raw = getValue(row, key);
                const cell = normalizeValue(raw).toLowerCase();
                const filter = filterValue.toLowerCase();
                if (col.filter === 'exact') {
                    if (cell !== filter) return false;
                } else if (col.filter === 'starts') {
                    if (!cell.startsWith(filter)) return false;
                } else {
                    if (!cell.includes(filter)) return false;
                }
            }
            if (state.customFilters) {
                for (const filter of state.customFilters) {
                    if (!filter) continue;
                    const value = filter.value;
                    if (value === null || value === '' || value === false) continue;
                    const cell = getValue(row, filter.field);
                    if (filter.operator === 'eq') {
                        if (String(cell) !== String(value)) return false;
                    } else if (filter.operator === 'gt') {
                        if (!(Number(cell) > Number(value))) return false;
                    } else if (filter.operator === 'gte') {
                        if (!(Number(cell) >= Number(value))) return false;
                    } else if (filter.operator === 'contains') {
                        if (!normalizeValue(cell).toLowerCase().includes(String(value).toLowerCase())) return false;
                    } else if (filter.operator === 'truthy') {
                        if (!cell) return false;
                    } else if (filter.operator === 'bool') {
                        const boolVal = String(cell).toLowerCase() === 'true';
                        if (boolVal !== value) return false;
                    }
                }
            }
            return true;
        });
    }

    function buildTableHeader(state, tableEl) {
        const thead = tableEl.querySelector('thead');
        thead.innerHTML = '';
        const headerRow = document.createElement('tr');
        const filterRow = document.createElement('tr');
        filterRow.classList.add('de-filter-row');

        state.columns.forEach(col => {
            if (!state.visibleColumns.has(col.key)) return;
            const th = document.createElement('th');
            th.textContent = col.label;
            th.classList.add('de-col-header');
            th.tabIndex = 0;
            th.addEventListener('click', () => toggleSort(state, col.key));
            th.addEventListener('keypress', e => {
                if (e.key === 'Enter') toggleSort(state, col.key);
            });
            headerRow.appendChild(th);

            const filterTh = document.createElement('th');
            const input = document.createElement('input');
            input.type = 'text';
            input.classList.add('de-filter');
            input.placeholder = col.filter === 'exact' ? 'Exact...' : 'Filter...';
            input.value = state.filters[col.key] || '';
            input.addEventListener('input', e => {
                state.filters[col.key] = e.target.value;
                state.page = 1;
                render(state);
            });
            filterTh.appendChild(input);
            filterRow.appendChild(filterTh);
        });

        thead.appendChild(headerRow);
        thead.appendChild(filterRow);
    }

    function toggleSort(state, key) {
        if (state.sort.key === key) {
            state.sort.direction = state.sort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            state.sort.key = key;
            state.sort.direction = 'asc';
        }
        render(state);
    }

    function renderRows(state, tableEl, rows) {
        const tbody = tableEl.querySelector('tbody');
        tbody.innerHTML = '';
        if (!rows.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = state.visibleColumns.size || 1;
            td.classList.add('de-empty');
            if (state.filterSummary && state.filterSummary.active) {
                td.textContent = `No matching rows (${state.filterSummary.label})`;
            } else {
                td.textContent = 'No data to display';
            }
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }

        rows.forEach(row => {
            const tr = document.createElement('tr');
            tr.classList.add('de-row');
            tr.addEventListener('click', () => openDrawer(state, row));

            state.columns.forEach(col => {
                if (!state.visibleColumns.has(col.key)) return;
                const td = document.createElement('td');
                td.textContent = normalizeValue(getValue(row, col.key));
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function updatePagination(state, total, container) {
        const totalPages = Math.max(1, Math.ceil(total / state.pageSize));
        if (state.page > totalPages) state.page = totalPages;

        const info = container.querySelector('.de-page-info');
        const start = (state.page - 1) * state.pageSize + 1;
        const end = Math.min(state.page * state.pageSize, total);
        info.textContent = total
            ? `Showing ${start}-${end} of ${total}`
            : 'No matching rows';

        container.querySelector('.de-prev').disabled = state.page <= 1;
        container.querySelector('.de-next').disabled = state.page >= totalPages;
    }

    function setupColumnPicker(state, container) {
        const list = container.querySelector('.de-columns-list');
        list.innerHTML = '';
        state.columns.forEach(col => {
            const label = document.createElement('label');
            label.classList.add('de-column-option');
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = state.visibleColumns.has(col.key);
            input.addEventListener('change', () => {
                if (input.checked) {
                    state.visibleColumns.add(col.key);
                } else {
                    state.visibleColumns.delete(col.key);
                }
                render(state);
            });
            const span = document.createElement('span');
            span.textContent = col.label;
            label.appendChild(input);
            label.appendChild(span);
            list.appendChild(label);
        });
    }

    function setupFiltersPanel(state, container, options) {
        if (!options.filtersPanel) return;
        const panel = container.querySelector('.de-filters-panel .de-filters-body');
        if (!panel) return;
        panel.innerHTML = '';
        state.customFilters = [];

        (options.filters || []).forEach(filter => {
            const wrapper = document.createElement('div');
            wrapper.classList.add('de-filter-control');
            const label = document.createElement('label');
            label.textContent = filter.label;
            wrapper.appendChild(label);

            if (filter.type === 'select') {
                const select = document.createElement('select');
                const optionAll = document.createElement('option');
                optionAll.value = '';
                optionAll.textContent = 'All';
                select.appendChild(optionAll);
                const values = filter.values || Array.from(new Set(state.data.map(row => getValue(row, filter.field)).filter(v => v !== null && v !== undefined && v !== '')));
                values.sort().forEach(value => {
                    const opt = document.createElement('option');
                    opt.value = value;
                    opt.textContent = value;
                    select.appendChild(opt);
                });
                select.addEventListener('change', e => {
                    filter.value = e.target.value;
                    state.page = 1;
                    render(state);
                });
                wrapper.appendChild(select);
            } else if (filter.type === 'checkbox') {
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.addEventListener('change', e => {
                    if (Object.prototype.hasOwnProperty.call(filter, 'value') && filter.value !== true && filter.value !== false) {
                        filter.value = e.target.checked ? filter.value : null;
                    } else {
                        filter.value = e.target.checked;
                    }
                    state.page = 1;
                    render(state);
                });
                wrapper.appendChild(checkbox);
            } else {
                const input = document.createElement('input');
                input.type = 'text';
                input.placeholder = 'Filter...';
                input.addEventListener('input', e => {
                    filter.value = e.target.value;
                    state.page = 1;
                    render(state);
                });
                wrapper.appendChild(input);
            }

            if (!filter.operator) {
                filter.operator = filter.type === 'checkbox' ? 'truthy' : 'eq';
            }
            state.customFilters.push(filter);
            panel.appendChild(wrapper);
        });
    }

    function openDrawer(state, row) {
        const drawer = state.drawer;
        if (!drawer) return;
        drawer.setAttribute('aria-hidden', 'false');
        drawer.classList.add('open');

        const titleEl = drawer.querySelector('.de-drawer-title');
        const subtitleEl = drawer.querySelector('.de-drawer-subtitle');
        const whyEl = drawer.querySelector('.de-drawer-why');
        const detailsEl = drawer.querySelector('.de-drawer-details');

        titleEl.textContent = getValue(row, state.titleField) || state.titleFallback || 'Details';
        subtitleEl.textContent = state.subtitleField && getValue(row, state.subtitleField)
            ? normalizeValue(getValue(row, state.subtitleField))
            : '';

        const why = row.why || row.reasons || row.reason || '';
        if (Array.isArray(why)) {
            whyEl.innerHTML = `<h5>Why</h5><ul>${why.map(item => `<li>${normalizeValue(item)}</li>`).join('')}</ul>`;
        } else if (why) {
            whyEl.innerHTML = `<h5>Why</h5><p>${normalizeValue(why)}</p>`;
        } else {
            whyEl.innerHTML = '';
        }

        const mappingSection = buildMappingSection(row);
        const detailRows = Object.keys(row).map(key => {
            return `<div class="de-detail-row"><span>${key}</span><span>${normalizeValue(row[key])}</span></div>`;
        }).join('');
        detailsEl.innerHTML = `${mappingSection}<div class="de-detail-grid">${detailRows}</div>`;

        detailsEl.querySelectorAll('.de-export-quick').forEach(button => {
            button.addEventListener('click', e => {
                e.stopPropagation();
                const exportType = button.getAttribute('data-export');
                if (!exportType) return;
                exportRowList(row, exportType);
            });
        });
    }

    function exportRowList(row, exportType) {
        let values = [];
        let name = exportType;
        if (exportType === 'epgs') {
            values = Array.isArray(row.epgs) ? row.epgs : [];
            name = 'epgs';
        } else if (exportType === 'impacted_epgs') {
            values = Array.isArray(row.impacted_epgs) ? row.impacted_epgs : [];
            name = 'impacted_epgs';
        } else if (exportType === 'impacted_vlans') {
            values = Array.isArray(row.impacted_vlans) ? row.impacted_vlans : [];
            name = 'impacted_vlans';
        } else if (exportType === 'ports') {
            values = Array.isArray(row.ports) ? row.ports : [];
            name = 'ports';
        }
        const header = 'value';
        const lines = [header, ...values.map(v => `"${String(v).replace(/"/g, '""')}"`)];
        const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${name}_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function closeDrawer(state) {
        if (!state.drawer) return;
        state.drawer.setAttribute('aria-hidden', 'true');
        state.drawer.classList.remove('open');
    }

    function buildExportQuery(state) {
        const params = new URLSearchParams();
        if (state.search) params.set('search', state.search);
        Object.entries(state.filters).forEach(([key, value]) => {
            if (!value) return;
            params.set(key, value);
        });
        if (state.customFilters) {
            state.customFilters.forEach(filter => {
                if (!filter || filter.value === null || filter.value === '' || filter.value === false) return;
                params.set(filter.field, filter.value);
            });
        }
        return params.toString();
    }

    function exportCsv(state, rows) {
        if (state.exportEndpoint) {
            const query = buildExportQuery(state);
            const url = query ? `${state.exportEndpoint}?${query}` : state.exportEndpoint;
            window.location = url;
            return;
        }
        const visibleCols = state.columns.filter(c => state.visibleColumns.has(c.key));
        const header = visibleCols.map(col => `"${col.label.replace(/"/g, '""')}"`).join(',');
        const lines = rows.map(row => visibleCols.map(col => {
            const value = normalizeValue(getValue(row, col.key));
            return `"${String(value).replace(/"/g, '""')}"`;
        }).join(','));
        const csvContent = [header, ...lines].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${state.id}_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function render(state) {
        const tableEl = state.table;
        buildTableHeader(state, tableEl);
        setupColumnPicker(state, state.columnsPanel);

        let filtered = applyFilters(state.data, state);
        if (state.sort.key) {
            const col = state.columns.find(c => c.key === state.sort.key) || {};
            filtered.sort((a, b) => compareValues(getValue(a, state.sort.key), getValue(b, state.sort.key), col.type, state.sort.direction));
        }

        state.currentRows = filtered;
        updateFilterSummary(state);

        const start = (state.page - 1) * state.pageSize;
        const pageRows = filtered.slice(start, start + state.pageSize);
        renderRows(state, tableEl, pageRows);
        updatePagination(state, filtered.length, state.pagination);
    }

    function summarizeFilters(state) {
        const details = [];
        if (state.search) {
            details.push(`Search: "${state.search}"`);
        }
        Object.entries(state.filters).forEach(([key, value]) => {
            if (!value) return;
            const col = state.columns.find(c => c.key === key);
            const label = col ? col.label : key;
            details.push(`${label}: ${value}`);
        });
        if (state.customFilters) {
            state.customFilters.forEach(filter => {
                if (!filter || filter.value === null || filter.value === '' || filter.value === false) return;
                details.push(`${filter.label}: ${filter.value}`);
            });
        }
        return details;
    }

    function updateFilterSummary(state) {
        const summaryEl = state.container.querySelector('.de-filter-summary');
        const textEl = state.container.querySelector('.de-filter-text');
        if (!summaryEl || !textEl) return;
        const details = summarizeFilters(state);
        if (!details.length) {
            summaryEl.setAttribute('hidden', '');
            state.filterSummary = { active: false, label: '' };
            return;
        }
        const total = state.data.length;
        const filtered = state.currentRows ? state.currentRows.length : 0;
        const label = `${details.join(', ')} | Filtered ${filtered} of ${total}`;
        textEl.textContent = label;
        summaryEl.removeAttribute('hidden');
        state.filterSummary = { active: true, label };
        console.debug(`[DataExplorer] ${state.id} filters`, { filters: details, filtered, total });
    }

    function initExplorer(container) {
        const id = container.id;
        const data = parseJsonById(`${id}-data`) || [];
        const columns = parseJsonById(`${id}-columns`) || [];
        const options = parseJsonById(`${id}-options`) || {};

        const state = {
            id,
            data,
            columns,
            filters: {},
            search: '',
            sort: { key: options.defaultSort || '', direction: 'desc' },
            page: 1,
            pageSize: DEFAULT_PAGE_SIZE,
            visibleColumns: new Set(columns.map(c => c.key)),
            flagField: options.flagField || '',
            titleField: options.titleField || columns[0]?.key,
            subtitleField: options.subtitleField || '',
            titleFallback: options.titleFallback || 'Details',
            exportEndpoint: options.exportEndpoint || ''
        };

        state.container = container;
        state.table = container.querySelector('.de-table');
        state.pagination = container.querySelector('.de-pagination');
        state.columnsPanel = container.querySelector('.de-columns-panel');
        state.drawer = document.getElementById(`${id}-drawer`);
        setupFiltersPanel(state, container, options);

        const searchInput = container.querySelector('.de-search');
        searchInput.addEventListener('input', e => {
            state.search = e.target.value.trim();
            state.page = 1;
            render(state);
        });

        const pageSizeSelect = container.querySelector('.de-page-size');
        pageSizeSelect.addEventListener('change', e => {
            state.pageSize = parseInt(e.target.value, 10);
            state.page = 1;
            render(state);
        });

        container.querySelector('.de-prev').addEventListener('click', () => {
            state.page = Math.max(1, state.page - 1);
            render(state);
        });

        container.querySelector('.de-next').addEventListener('click', () => {
            state.page += 1;
            render(state);
        });

        container.querySelector('.de-export').addEventListener('click', () => {
            exportCsv(state, state.currentRows || []);
        });

        const columnsToggle = container.querySelector('.de-columns-toggle');
        columnsToggle.addEventListener('click', () => {
            const isHidden = state.columnsPanel.hasAttribute('hidden');
            if (isHidden) {
                state.columnsPanel.removeAttribute('hidden');
            } else {
                state.columnsPanel.setAttribute('hidden', '');
            }
        });

        const clearButton = container.querySelector('.de-clear-filters');
        if (clearButton) {
            clearButton.addEventListener('click', () => {
                state.search = '';
                state.filters = {};
                if (state.customFilters) {
                    state.customFilters.forEach(filter => {
                        filter.value = '';
                    });
                }
                const searchInput = container.querySelector('.de-search');
                if (searchInput) searchInput.value = '';
                container.querySelectorAll('.de-filter-row input').forEach(input => {
                    input.value = '';
                });
                container.querySelectorAll('.de-filters-panel select').forEach(select => {
                    select.value = '';
                });
                container.querySelectorAll('.de-filters-panel input[type="checkbox"]').forEach(checkbox => {
                    checkbox.checked = false;
                });
                state.page = 1;
                render(state);
            });
        }

        const flagContainer = container.querySelector('.de-flags');
        const flagToggle = container.querySelector('.de-flag-only');
        if (state.flagField && data.some(row => row[state.flagField])) {
            flagContainer.removeAttribute('hidden');
            flagToggle.addEventListener('change', e => {
                state.flagOnly = e.target.checked;
                state.page = 1;
                render(state);
            });
        }

        if (state.drawer) {
            state.drawer.querySelector('.de-drawer-close').addEventListener('click', () => closeDrawer(state));
            state.drawer.querySelector('.de-drawer-overlay').addEventListener('click', () => closeDrawer(state));
        }

        render(state);
    }

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('.data-explorer').forEach(initExplorer);
    });
})();
