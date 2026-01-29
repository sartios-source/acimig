(() => {
    function parseJson(id) {
        const el = document.getElementById(id);
        if (!el) return [];
        try {
            return JSON.parse(el.textContent || '[]');
        } catch (err) {
            console.error('Failed to parse FEX flow data', err);
            return [];
        }
    }

    function norm(value) {
        return String(value || '').trim();
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

            const card = document.createElement('div');
            card.className = 'fex-flow-card';
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
        const rackRows = parseJson('fex-rack-explorer-rows');
        const deviceRows = parseJson('fex-device-explorer-rows');
        renderFlow(rackRows, deviceRows);
    });
})();
