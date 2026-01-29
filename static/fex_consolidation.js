(() => {
    function parseJson(id) {
        const el = document.getElementById(id);
        if (!el) return [];
        try {
            return JSON.parse(el.textContent || '[]');
        } catch (err) {
            console.error('Failed to parse FEX consolidation data', err);
            return [];
        }
    }

    function norm(value) {
        return String(value || '').trim();
    }

    function normLower(value) {
        return norm(value).toLowerCase();
    }

    function statusKey(row) {
        const val = normLower(row.can_consolidate || '');
        if (val === 'yes') return 'candidate';
        if (val === 'needs data') return 'needs_data';
        if (val === 'no') return 'not_eligible';
        return 'unknown';
    }

    function applyFilters(racks, devices, filters) {
        const status = filters.status;
        const search = normLower(filters.search);

        const filteredRacks = racks.filter(row => {
            if (status !== 'all' && statusKey(row) !== status) return false;
            if (search) {
                const hay = [row.rack].map(normLower).join(' ');
                if (!hay.includes(search)) return false;
            }
            return true;
        });

        const filteredDevices = devices.filter(row => {
            if (search) {
                const hay = [row.fex_id, row.serial, row.model, row.leaf_id, row.rack].map(normLower).join(' ');
                if (!hay.includes(search)) return false;
            }
            return true;
        });

        return { racks: filteredRacks, devices: filteredDevices };
    }

    function renderRacks(rows, tbody) {
        tbody.innerHTML = '';
        if (!rows.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 7;
            td.className = 'fex-empty';
            td.textContent = 'No matching racks';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }
        rows.forEach(row => {
            const tr = document.createElement('tr');
            const cells = [
                row.rack || '',
                row.fex_count || 0,
                row.connected_ports === null || row.connected_ports === undefined ? 'Unknown' : row.connected_ports,
                row.total_ports || 0,
                row.can_consolidate || '',
                row.target_fex || '',
                row.recommendation || ''
            ];
            cells.forEach(value => {
                const td = document.createElement('td');
                td.textContent = norm(value);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    function renderDevices(rows, tbody) {
        tbody.innerHTML = '';
        if (!rows.length) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 10;
            td.className = 'fex-empty';
            td.textContent = 'No matching FEX devices';
            tr.appendChild(td);
            tbody.appendChild(tr);
            return;
        }
        rows.forEach(row => {
            const tr = document.createElement('tr');
            const role = row.target_for_rack ? 'Target' : 'Member';
            const cells = [
                row.fex_id || '',
                row.serial || '',
                row.model || '',
                row.leaf_name || row.leaf_id || '',
                row.rack || '',
                row.connected_ports === null || row.connected_ports === undefined ? 'Unknown' : row.connected_ports,
                row.total_ports || 0,
                row.utilization_pct === null || row.utilization_pct === undefined ? 'Unknown' : row.utilization_pct,
                row.utilization_source || 'Unknown',
                row.rack ? role : ''
            ];
            cells.forEach(value => {
                const td = document.createElement('td');
                td.textContent = norm(value);
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const rackRows = parseJson('fex-rack-data');
        const deviceRows = parseJson('fex-device-data');
        const rackBody = document.getElementById('fex-rack-body');
        const deviceBody = document.getElementById('fex-device-body');
        const summary = document.getElementById('fex-summary');
        if (!rackBody || !deviceBody) return;

        function getFilters() {
            return {
                status: document.querySelector('input[name="fex-status"]:checked')?.value || 'all',
                search: document.getElementById('fex-search')?.value || ''
            };
        }

        function update() {
            const filtered = applyFilters(rackRows, deviceRows, getFilters());
            renderRacks(filtered.racks, rackBody);
            renderDevices(filtered.devices, deviceBody);
            if (summary) summary.textContent = `Showing ${filtered.racks.length} racks`;
        }

        document.querySelectorAll('input[name="fex-status"]').forEach(input => {
            input.addEventListener('change', update);
        });
        const search = document.getElementById('fex-search');
        if (search) search.addEventListener('input', update);
        const reset = document.getElementById('fex-reset');
        if (reset) {
            reset.addEventListener('click', () => {
                document.querySelectorAll('input[name="fex-status"]').forEach(input => {
                    input.checked = input.value === 'all';
                });
                if (search) search.value = '';
                update();
            });
        }

        update();
    });
})();
