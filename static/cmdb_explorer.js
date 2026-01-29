(() => {
    function parseJson(id) {
        const el = document.getElementById(id);
        if (!el) return [];
        try {
            return JSON.parse(el.textContent || '[]');
        } catch (err) {
            console.error('Failed to parse CMDB data', err);
            return [];
        }
    }

    function norm(value) {
        return String(value || '').trim();
    }

    function normLower(value) {
        return norm(value).toLowerCase();
    }

    function uniq(values) {
        return Array.from(new Set(values.filter(v => v !== null && v !== undefined && v !== '')));
    }

    function buildOptions(select, values) {
        select.innerHTML = '';
        const optionAll = document.createElement('option');
        optionAll.value = 'all';
        optionAll.textContent = 'All';
        select.appendChild(optionAll);
        values.sort().forEach(value => {
            const opt = document.createElement('option');
            opt.value = value;
            opt.textContent = value;
            select.appendChild(opt);
        });
    }

    function getMatchedLabel(row) {
        if (row.matched_label) return row.matched_label;
        if (row.Matched === true || row.matched === true) return 'Matched';
        if (row.Matched === false || row.matched === false) return 'Unmatched';
        return '';
    }

    function applyFilters(rows, filters) {
        const matched = filters.matched;
        const site = normLower(filters.site);
        const hall = normLower(filters.hall);
        const rack = normLower(filters.rack);
        const deviceType = normLower(filters.deviceType);
        const search = normLower(filters.search);

        return rows.filter(row => {
            if (matched !== 'all') {
                const label = normLower(getMatchedLabel(row));
                if (matched === 'matched' && label !== 'matched') return false;
                if (matched === 'unmatched' && label !== 'unmatched') return false;
            }
            if (site !== 'all' && normLower(row.Site || row.site) !== site) return false;
            if (hall !== 'all' && normLower(row.Hall || row.hall) !== hall) return false;
            if (rack !== 'all' && normLower(row.Rack || row.rack) !== rack) return false;
            if (deviceType !== 'all' && normLower(row.DeviceType || row.device_type) !== deviceType) return false;
            if (search) {
                const hay = [
                    row.SerialNumber || row.serial_number,
                    row.Name || row.name,
                    row.ModelName || row.model_name,
                    row.Site || row.site,
                    row.Hall || row.hall,
                    row.Rack || row.rack,
                    row.DeviceType || row.device_type
                ].map(normLower).join(' ');
                if (!hay.includes(search)) return false;
            }
            return true;
        });
    }

    function renderRows(rows, tbody, summaryEl) {
        tbody.innerHTML = '';
        if (!rows.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 11;
            td.className = 'cmdb-empty';
            td.textContent = 'No matching rows';
            tr.appendChild(td);
            tbody.appendChild(tr);
        } else {
            rows.forEach(row => {
                const tr = document.createElement('tr');
                const cells = [
                    row.SerialNumber || row.serial_number || '',
                    row.Name || row.name || '',
                    row.ModelName || row.model_name || '',
                    getMatchedLabel(row),
                    row.DeviceType || row.device_type || '',
                    row.DeviceID || row.device_id || '',
                    row.Site || row.site || '',
                    row.Building || row.building || '',
                    row.Hall || row.hall || '',
                    row.Rack || row.rack || '',
                    row.UnitLocation || row.unit_location || ''
                ];
                cells.forEach(value => {
                    const td = document.createElement('td');
                    td.textContent = norm(value);
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }
        if (summaryEl) {
            summaryEl.textContent = `Showing ${rows.length} rows`;
        }
    }

    function exportCsv(rows) {
        const header = [
            'SerialNumber', 'Name', 'ModelName', 'Matched', 'DeviceType', 'DeviceID',
            'Site', 'Building', 'Hall', 'Rack', 'UnitLocation'
        ];
        const lines = [header.join(',')];
        rows.forEach(row => {
            const values = [
                row.SerialNumber || row.serial_number || '',
                row.Name || row.name || '',
                row.ModelName || row.model_name || '',
                getMatchedLabel(row),
                row.DeviceType || row.device_type || '',
                row.DeviceID || row.device_id || '',
                row.Site || row.site || '',
                row.Building || row.building || '',
                row.Hall || row.hall || '',
                row.Rack || row.rack || '',
                row.UnitLocation || row.unit_location || ''
            ];
            lines.push(values.map(v => {
                const s = String(v || '');
                return s.includes(',') || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
            }).join(','));
        });
        const blob = new Blob([lines.join('
')], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `cmdb_export_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    document.addEventListener('DOMContentLoaded', () => {
        const data = parseJson('cmdb-rows-data');
        const tbody = document.getElementById('cmdb-table-body');
        if (!tbody) return;

        const siteSelect = document.getElementById('cmdb-site');
        const hallSelect = document.getElementById('cmdb-hall');
        const rackSelect = document.getElementById('cmdb-rack');
        const deviceSelect = document.getElementById('cmdb-device-type');
        const searchInput = document.getElementById('cmdb-search');
        const resetBtn = document.getElementById('cmdb-reset');
        const exportBtn = document.getElementById('cmdb-export');
        const summaryEl = document.getElementById('cmdb-summary');

        const sites = uniq(data.map(row => norm(row.Site || row.site)));
        const halls = uniq(data.map(row => norm(row.Hall || row.hall)));
        const racks = uniq(data.map(row => norm(row.Rack || row.rack)));
        const deviceTypes = uniq(data.map(row => norm(row.DeviceType || row.device_type)));

        buildOptions(siteSelect, sites);
        buildOptions(hallSelect, halls);
        buildOptions(rackSelect, racks);
        buildOptions(deviceSelect, deviceTypes);

        function currentFilters() {
            const matched = document.querySelector('input[name="cmdb-matched"]:checked')?.value || 'all';
            return {
                matched: matched,
                site: siteSelect?.value || 'all',
                hall: hallSelect?.value || 'all',
                rack: rackSelect?.value || 'all',
                deviceType: deviceSelect?.value || 'all',
                search: searchInput?.value || ''
            };
        }

        function update() {
            const filtered = applyFilters(data, currentFilters());
            renderRows(filtered, tbody, summaryEl);
            if (exportBtn) {
                exportBtn.onclick = () => exportCsv(filtered);
            }
        }

        document.querySelectorAll('input[name="cmdb-matched"]').forEach(input => {
            input.addEventListener('change', update);
        });
        [siteSelect, hallSelect, rackSelect, deviceSelect].forEach(select => {
            if (select) select.addEventListener('change', update);
        });
        if (searchInput) {
            searchInput.addEventListener('input', update);
        }
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                document.querySelectorAll('input[name="cmdb-matched"]').forEach(input => {
                    input.checked = input.value === 'all';
                });
                if (siteSelect) siteSelect.value = 'all';
                if (hallSelect) hallSelect.value = 'all';
                if (rackSelect) rackSelect.value = 'all';
                if (deviceSelect) deviceSelect.value = 'all';
                if (searchInput) searchInput.value = '';
                update();
            });
        }

        update();
    });
})();
