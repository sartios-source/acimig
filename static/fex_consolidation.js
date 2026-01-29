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

    function renderFlow(racks, devices) {
        const grid = document.getElementById('fex-flow-grid');
        if (!grid) return;
        grid.innerHTML = '';

        const candidates = racks.filter(row => String(row.can_consolidate || '').toLowerCase() === 'yes');
        if (!candidates.length) {
            const empty = document.createElement('div');
            empty.className = 'fex-empty';
            empty.textContent = 'No consolidation candidates in the current view.';
            grid.appendChild(empty);
            return;
        }

        const devicesByRack = {};
        devices.forEach(device => {
            const rack = device.rack || 'Unknown';
            if (!devicesByRack[rack]) devicesByRack[rack] = [];
            devicesByRack[rack].push(device);
        });

        candidates.forEach(row => {
            const rack = row.rack || 'Unknown';
            const members = devicesByRack[rack] || [];
            const target = members.find(item => item.target_for_rack) || null;

            const card = document.createElement('div');
            card.className = 'fex-flow-card';
            const memberHtml = members.map(item => {
                const portsUsed = item.connected_ports === null || item.connected_ports === undefined ? 'Unknown' : item.connected_ports;
                const portsTotal = item.total_ports || 0;
                const leaf = item.leaf_name || item.leaf_id || 'Leaf Unknown';
                const role = item.target_for_rack ? 'Target' : 'Member';
                return `
                    <div class="fex-flow-member ${item.target_for_rack ? 'is-target' : ''}">
                        <div>
                            <div class="fex-flow-id">FEX ${norm(item.fex_id)} ${item.serial ? `(${norm(item.serial)})` : ''}</div>
                            <div class="fex-flow-meta">${leaf} - ${portsUsed}/${portsTotal} ports used</div>
                        </div>
                        <span class="fex-flow-role">${role}</span>
                    </div>
                `;
            }).join('');

            card.innerHTML = `
                <div class="fex-flow-title">
                    <div>
                        <h5>Rack ${norm(rack)}</h5>
                        <p>${row.fex_count || 0} FEX - ${row.connected_ports || 0}/${row.total_ports || 0} ports used</p>
                    </div>
                    <span class="fex-flow-status">${row.can_consolidate || ''}</span>
                </div>
                <div class="fex-flow-target">
                    <strong>Target:</strong> ${norm(row.target_fex || (target ? `FEX ${target.fex_id}` : ''))}
                </div>
                <div class="fex-flow-members">${memberHtml || '<div class="fex-empty">No FEX members found.</div>'}</div>
            `;
            grid.appendChild(card);
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
            renderFlow(filtered.racks, filtered.devices);
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
