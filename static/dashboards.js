/**
 * ACI Analysis Tool - Interactive Dashboards
 * Chart.js and D3.js based visualizations
 */

// Global chart instances
let charts = {};

// Load data from embedded JSON
let vizData = {};
try {
    const dataElement = document.getElementById('viz-data');
    if (dataElement) {
        vizData = JSON.parse(dataElement.textContent);
    }
} catch (e) {
    console.error('Error parsing visualization data:', e);
}

// Initialize dashboards when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboards();
    setupTabNavigation();
    setDefaultTab();
});

function initializeDashboards() {
    if (!vizData || Object.keys(vizData).length === 0) {
        console.log('No visualization data available');
        return;
    }

    // Initialize only the remaining visualization dashboards
    const initializers = [
        ['topology', initializeTopologyDashboard],
        ['vlans', initializeVLANDashboard]
    ];
    initializers.forEach(([name, fn]) => {
        try {
            fn();
        } catch (err) {
            console.error(`Failed to initialize ${name} dashboard:`, err);
        }
    });
}

function showNoData(canvasId, message) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !canvas.parentElement) return;
    canvas.parentElement.innerHTML = `<div class="no-data text-sm text-gray-500 italic">${message}</div>`;
}

// ===== Tab Navigation =====
function setupTabNavigation() {
    const tabs = document.querySelectorAll('.dashboard-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function setDefaultTab() {
    const vlanTab = document.querySelector('.dashboard-tab[data-tab="vlans"]');
    if (vlanTab) {
        switchTab('vlans');
        return;
    }

    const firstTab = document.querySelector('.dashboard-tab');
    if (firstTab) {
        const tabName = firstTab.getAttribute('data-tab');
        if (tabName) {
            switchTab(tabName);
        }
    }
}

function switchTab(tabName) {
    // Update active tab button
    document.querySelectorAll('.dashboard-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`.dashboard-tab[data-tab="${tabName}"]`).classList.add('active');

    // Update active panel
    document.querySelectorAll('.dashboard-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`${tabName}-dashboard`).classList.add('active');

    if (tabName === 'topology') {
        setTimeout(() => {
            createTopologyVisualization();
        }, 50);
    }

    resizeChartsInPanel(tabName);
}

function resizeChartsInPanel(tabName) {
    const panel = document.getElementById(`${tabName}-dashboard`);
    if (!panel || !window.Chart || !Chart.getChart) return;

    panel.querySelectorAll('canvas').forEach(canvas => {
        const chart = Chart.getChart(canvas);
        if (chart && chart.resize) {
            chart.resize();
        }
    });
}

// ===== Overview Dashboard =====
function initializeOverviewDashboard() {
    createUtilizationDistributionChart();
    createHealthOverviewChart();
}

function createUtilizationDistributionChart() {
    const ctx = document.getElementById('utilizationDistributionChart');
    if (!ctx) return;

    const portUtil = vizData.port_utilization || [];
    const knownUtil = portUtil.filter(item => item.utilization_pct !== null && item.utilization_pct !== undefined);
    const unknownCount = portUtil.length - knownUtil.length;
    if (knownUtil.length === 0) {
        showNoData('utilizationDistributionChart', 'No port utilization data available');
        return;
    }

    // Group by utilization ranges
    const ranges = {
        '0-20%': 0,
        '20-40%': 0,
        '40-60%': 0,
        '60-80%': 0,
        '80-100%': 0
    };

    knownUtil.forEach(item => {
        const util = item.utilization_pct;
        if (util < 20) ranges['0-20%']++;
        else if (util < 40) ranges['20-40%']++;
        else if (util < 60) ranges['40-60%']++;
        else if (util < 80) ranges['60-80%']++;
        else ranges['80-100%']++;
    });

    if (unknownCount > 0) {
        ranges['Unknown'] = unknownCount;
    }

    charts.utilizationDistribution = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(ranges),
            datasets: [{
                data: Object.values(ranges),
                backgroundColor: [
                    '#FF6384',  // Red - very low
                    '#FF9F40',  // Orange - low
                    '#FFCD56',  // Yellow - medium
                    '#4BC0C0',  // Teal - good
                    '#36A2EB',  // Blue - excellent
                    '#94A3B8'   // Gray - unknown
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} FEX (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

function createHealthOverviewChart() {
    const ctx = document.getElementById('healthOverviewChart');
    if (!ctx) return;

    const stats = vizData.statistics || {};
    const portUtil = vizData.port_utilization || [];
    const knownUtil = portUtil.filter(p => p.utilization_pct !== null && p.utilization_pct !== undefined);
    if (knownUtil.length === 0 && !vizData.vpc_symmetry && !vizData.vlan_distribution) {
        showNoData('healthOverviewChart', 'No health metrics available');
        return;
    }

    // Calculate health metrics
    const goodUtil = knownUtil.filter(p => p.utilization_pct >= 40 && p.utilization_pct <= 80).length;
    const poorUtil = knownUtil.filter(p => p.utilization_pct < 40).length;
    const vpcSymmetric = vizData.vpc_symmetry?.statistics?.symmetry_rate || 100;
    const vlanOverlaps = vizData.vlan_distribution?.overlaps?.length || 0;
    const utilScore = knownUtil.length ? ((goodUtil / knownUtil.length) * 100) : null;

    charts.healthOverview = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Port Utilization', 'VPC Symmetry', 'VLAN Health', 'Overall Health'],
            datasets: [{
                label: 'Health Score',
                data: [
                    utilScore,
                    vpcSymmetric,
                    Math.max(0, 100 - (vlanOverlaps * 5)),
                    utilScore !== null
                        ? ((utilScore + vpcSymmetric + Math.max(0, 100 - (vlanOverlaps * 5))) / 3)
                        : null
                ],
                backgroundColor: ['#4BC0C0', '#36A2EB', '#FFCD56', '#9966FF']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// ===== Topology Dashboard =====
let topologySimulation;
let currentZoom = 1;

function initializeTopologyDashboard() {
    createTopologyVisualization();
}

function createTopologyVisualization() {
    const container = document.getElementById('topology-canvas');
    if (!container || !vizData.topology) return;

    const width = container.clientWidth || 800;
    const height = 600;

    // Clear existing
    container.innerHTML = '';

    const svg = d3.select('#topology-canvas')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g');

    // Create zoom behavior
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
            currentZoom = event.transform.k;
        });

    svg.call(zoom);

    // Store zoom for controls
    svg.zoomBehavior = zoom;

    const nodes = vizData.topology.nodes || [];
    const edges = vizData.topology.edges || [];
    if (!nodes.length) {
        container.innerHTML = '<div class="no-data text-sm text-gray-500 italic">No topology data available</div>';
        return;
    }

    window.topologyData = { nodes, edges };
    window.topologyLeafIdMap = buildTopologyLeafIdMap(nodes);
    window.overloadedLeafIds = getOverloadedLeafIds();
    populateLeafFilterOptions(nodes);

    // Create force simulation
    topologySimulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    // Create edges
    const link = g.append('g')
        .selectAll('line')
        .data(edges)
        .enter().append('line')
        .attr('class', 'topology-edge')
        .style('stroke', '#999')
        .style('stroke-width', 2);

    // Create nodes
    const node = g.append('g')
        .selectAll('g')
        .data(nodes)
        .enter().append('g')
        .attr('class', 'topology-node')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    // Add circles
    node.append('circle')
        .attr('r', d => d.type === 'leaf' ? 20 : 15)
        .style('fill', d => d.type === 'leaf' ? '#4A90E2' : '#7ED321')
        .style('stroke', '#fff')
        .style('stroke-width', 2);

    // Add labels
    const labels = node.append('text')
        .attr('class', 'topology-label')
        .attr('dy', 35)
        .attr('text-anchor', 'middle')
        .style('font-size', '10px')
        .style('fill', '#333')
        .text(d => d.name || d.id);

    // Add tooltips
    node.append('title')
        .text(d => `${d.name || d.id}\nType: ${d.type}\nModel: ${d.model || 'N/A'}`);

    topologySimulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node
            .attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Store selections for filtering/highlighting
    window.topologyNodeSelection = node;
    window.topologyLinkSelection = link;

    // Store for zoom controls
    window.topologyZoom = zoom;
    window.topologySvg = svg;
    updateTopologyStats(null);
    highlightOverloaded();

    function dragstarted(event) {
        if (!event.active) topologySimulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
    }

    function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
    }

    function dragended(event) {
        if (!event.active) topologySimulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
    }
}

// Topology controls
function zoomIn() {
    if (window.topologySvg && window.topologyZoom) {
        window.topologySvg.transition().duration(300).call(
            window.topologyZoom.scaleBy, 1.3
        );
    }
}

function zoomOut() {
    if (window.topologySvg && window.topologyZoom) {
        window.topologySvg.transition().duration(300).call(
            window.topologyZoom.scaleBy, 0.7
        );
    }
}

function resetView() {
    if (window.topologySvg && window.topologyZoom) {
        window.topologySvg.transition().duration(500).call(
            window.topologyZoom.transform,
            d3.zoomIdentity
        );
    }
}

function toggleLabels() {
    const showLabels = document.getElementById('show-labels').checked;
    document.querySelectorAll('.topology-label').forEach(label => {
        label.style.display = showLabels ? 'block' : 'none';
    });
}

function buildTopologyLeafIdMap(nodes) {
    const map = {};
    nodes.filter(node => node.type === 'leaf').forEach(node => {
        const rawId = String(node.id ?? '');
        const nameId = String(node.name ?? '');
        const match = rawId.match(/(\d+)/g) || nameId.match(/(\d+)/g);
        const leafId = match ? match[match.length - 1] : rawId || nameId;
        if (leafId) {
            map[leafId] = node.id;
        }
    });
    return map;
}

function populateLeafFilterOptions(nodes) {
    const filter = document.getElementById('leaf-filter');
    if (!filter) return;

    while (filter.options.length > 1) {
        filter.remove(1);
    }

    const leafNodes = nodes.filter(node => node.type === 'leaf');
    leafNodes.forEach(node => {
        const rawId = String(node.id ?? '');
        const nameId = String(node.name ?? '');
        const match = rawId.match(/(\d+)/g) || nameId.match(/(\d+)/g);
        const leafId = match ? match[match.length - 1] : rawId || nameId;
        const option = document.createElement('option');
        option.value = leafId || rawId;
        option.textContent = node.name || node.id || `Leaf-${leafId}`;
        filter.appendChild(option);
    });
}

function getOverloadedLeafIds() {
    const mappings = vizData.leaf_fex_mapping?.mappings || [];
    const overloadedIds = new Set();
    mappings.forEach(mapping => {
        if (mapping.overloaded) {
            overloadedIds.add(String(mapping.leaf_id));
        }
    });
    return overloadedIds;
}

function updateTopologyStats(visibleIds) {
    const statsLeafs = document.getElementById('leafs-shown');
    const statsFex = document.getElementById('fex-shown');
    const statsAvg = document.getElementById('avg-fex-leaf');
    const nodes = window.topologyData?.nodes || [];

    const visibleNodes = visibleIds
        ? nodes.filter(node => visibleIds.has(String(node.id)))
        : nodes;

    const leafCount = visibleNodes.filter(node => node.type === 'leaf').length;
    const fexCount = visibleNodes.filter(node => node.type !== 'leaf').length;
    const avgFex = leafCount ? (fexCount / leafCount).toFixed(2) : '0';

    if (statsLeafs) statsLeafs.textContent = leafCount;
    if (statsFex) statsFex.textContent = fexCount;
    if (statsAvg) statsAvg.textContent = avgFex;
}

function filterTopology() {
    const filter = document.getElementById('leaf-filter');
    if (!filter || !window.topologyData) return;

    const selected = filter.value;
    const nodeSelection = window.topologyNodeSelection;
    const linkSelection = window.topologyLinkSelection;
    const edges = window.topologyData.edges || [];

    let visibleIds = null;
    if (selected !== 'all') {
        const leafNodeId = window.topologyLeafIdMap?.[selected] || selected;
        visibleIds = new Set([String(leafNodeId)]);

        edges.forEach(edge => {
            const sourceId = String(edge.source?.id ?? edge.source);
            const targetId = String(edge.target?.id ?? edge.target);
            if (sourceId === String(leafNodeId) || targetId === String(leafNodeId)) {
                visibleIds.add(sourceId);
                visibleIds.add(targetId);
            }
        });
    }

    if (nodeSelection) {
        nodeSelection.style('display', d => {
            if (!visibleIds) return 'block';
            return visibleIds.has(String(d.id)) ? 'block' : 'none';
        });
    }

    if (linkSelection) {
        linkSelection.style('display', d => {
            if (!visibleIds) return 'block';
            const sourceId = String(d.source?.id ?? d.source);
            const targetId = String(d.target?.id ?? d.target);
            return visibleIds.has(sourceId) && visibleIds.has(targetId) ? 'block' : 'none';
        });
    }

    updateTopologyStats(visibleIds);
    highlightOverloaded();
}

function highlightOverloaded() {
    const checkbox = document.getElementById('highlight-overloaded');
    const nodeSelection = window.topologyNodeSelection;
    if (!checkbox || !nodeSelection) return;

    const overloadedIds = window.overloadedLeafIds || new Set();
    const highlight = checkbox.checked;

    nodeSelection.select('circle')
        .style('stroke', d => {
            const leafId = String(d.id ?? '');
            const match = leafId.match(/(\d+)/g);
            const shortId = match ? match[match.length - 1] : leafId;
            const isOverloaded = overloadedIds.has(leafId) || overloadedIds.has(shortId);
            if (highlight && d.type === 'leaf' && isOverloaded) {
                return '#ef4444';
            }
            return '#fff';
        })
        .style('stroke-width', d => {
            const leafId = String(d.id ?? '');
            const match = leafId.match(/(\d+)/g);
            const shortId = match ? match[match.length - 1] : leafId;
            const isOverloaded = overloadedIds.has(leafId) || overloadedIds.has(shortId);
            if (highlight && d.type === 'leaf' && isOverloaded) {
                return 3;
            }
            return 2;
        });
}

// ===== Mapping Table =====
function filterMappingTable() {
    const searchInput = document.getElementById('mapping-search');
    const showOverloaded = document.getElementById('show-overloaded-only');
    const rows = document.querySelectorAll('#mapping-table tbody tr.mapping-row');

    if (!rows.length) return;

    const query = (searchInput?.value || '').toLowerCase();
    const overloadedOnly = !!showOverloaded?.checked;

    rows.forEach(row => {
        const rowText = row.textContent.toLowerCase();
        const fexCount = parseInt(row.getAttribute('data-fex-count') || '0', 10);
        const isOverloaded = fexCount > 12;

        let visible = true;
        if (query && !rowText.includes(query)) {
            visible = false;
        }
        if (overloadedOnly && !isOverloaded) {
            visible = false;
        }

        row.style.display = visible ? 'table-row' : 'none';
    });
}

// ===== Utilization Dashboard =====
function initializeUtilizationDashboard() {
    createPortUtilizationChart();
    createConsolidationScoreChart();
    populateConsolidationTable();
}

function createPortUtilizationChart() {
    const ctx = document.getElementById('portUtilizationChart');
    if (!ctx) return;

    const allUtil = vizData.port_utilization || [];
    const knownUtil = allUtil.filter(p => p.utilization_pct !== null && p.utilization_pct !== undefined);
    const needsDataCount = allUtil.length - knownUtil.length;
    const portUtil = knownUtil.slice(0, 30);  // Top 30 known
    if (portUtil.length === 0) {
        showNoData('portUtilizationChart', 'No port utilization data available');
        return;
    }

    const needsDataEl = document.getElementById('utilization-needs-data');
    if (needsDataEl) {
        needsDataEl.textContent = needsDataCount
            ? `${needsDataCount} FEX devices need utilization data before consolidation decisions.`
            : '';
    }

    charts.portUtilization = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: portUtil.map(p => p.fex_identifier || `FEX-${p.fex_id}`),
            datasets: [{
                label: 'Utilization %',
                data: portUtil.map(p => p.utilization_pct),
                backgroundColor: portUtil.map(p => {
                    if (p.utilization_pct < 20) return '#FF6384';
                    if (p.utilization_pct < 40) return '#FF9F40';
                    if (p.utilization_pct < 60) return '#FFCD56';
                    if (p.utilization_pct < 80) return '#4BC0C0';
                    return '#36A2EB';
                })
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const item = portUtil[context.dataIndex];
                            return [
                                `Utilization: ${item.utilization_pct}%`,
                                `Connected: ${item.connected_ports}/${item.total_ports}`,
                                `Score: ${item.consolidation_score}`
                            ];
                        }
                    }
                }
            }
        }
    });
}

function createConsolidationScoreChart() {
    const ctx = document.getElementById('consolidationScoreChart');
    if (!ctx) return;

    const allUtil = vizData.port_utilization || [];
    const knownUtil = allUtil.filter(p => p.utilization_pct !== null && p.utilization_pct !== undefined);
    const portUtil = knownUtil.slice(0, 20);
    if (portUtil.length === 0) {
        showNoData('consolidationScoreChart', 'No consolidation data available');
        return;
    }

    charts.consolidationScore = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'FEX Devices',
                data: portUtil.map(p => ({
                    x: p.utilization_pct,
                    y: p.consolidation_score,
                    label: p.fex_identifier || `FEX-${p.fex_id}`
                })),
                backgroundColor: 'rgba(74, 144, 226, 0.5)',
                borderColor: '#4A90E2',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Utilization %'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Consolidation Score'
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.raw.label + `: ${context.parsed.x.toFixed(1)}% util, Score: ${context.parsed.y}`;
                        }
                    }
                }
            }
        }
    });
}

function populateConsolidationTable() {
    const tbody = document.getElementById('consolidation-table');
    if (!tbody) return;

    const portUtil = (vizData.port_utilization || [])
        .filter(p => p.utilization_pct !== null && p.utilization_pct !== undefined)
        .filter(p => (p.consolidation_score || 0) >= 60)
        .slice(0, 10);

    if (portUtil.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-4 text-sm text-gray-500 italic text-center">No consolidation candidates available.</td></tr>';
        return;
    }

    tbody.innerHTML = portUtil.map(p => `
        <tr>
            <td>${p.fex_identifier || `FEX-${p.fex_id}`}</td>
            <td>${p.utilization_pct}%</td>
            <td><span class="score-badge score-${p.consolidation_score >= 80 ? 'high' : 'medium'}">${p.consolidation_score}</span></td>
            <td class="recommendation-cell">${p.recommendation}</td>
        </tr>
    `).join('');
}

// ===== VLAN Dashboard =====
function initializeVLANDashboard() {
    createVLANCouplingChart();
}

function createVLANCouplingChart() {
    const ctx = document.getElementById('vlanCouplingChart');
    if (!ctx) return;

    const vlanRows = vizData.vlan_coupling?.vlans || [];
    if (!vlanRows.length) {
        showNoData('vlanCouplingChart', 'No VLAN coupling data available');
        return;
    }

    const counts = { low: 0, medium: 0, high: 0, critical: 0 };
    vlanRows.forEach(vlan => {
        const level = (vlan.coupling_level || 'low').toLowerCase();
        if (counts[level] !== undefined) {
            counts[level] += 1;
        } else {
            counts.low += 1;
        }
    });

    charts.vlanCoupling = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Low', 'Medium', 'High', 'Critical'],
            datasets: [{
                label: 'VLANs',
                data: [counts.low, counts.medium, counts.high, counts.critical],
                backgroundColor: ['#7ED321', '#FFCD56', '#FF9F40', '#FF6384']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { beginAtZero: true }
            }
        }
    });
}

function createVLANDistributionChart() {
    const ctx = document.getElementById('vlanDistributionChart');
    if (!ctx) return;

    const vlanData = vizData.vlan_distribution || {};
    const vlanUsage = vlanData.vlan_usage || {};
    if (!Object.keys(vlanUsage).length) {
        showNoData('vlanDistributionChart', 'No VLAN data available');
        return;
    }

    // Get top 20 VLANs by usage
    const vlanEntries = Object.entries(vlanUsage)
        .map(([vlan, usages]) => ({ vlan: parseInt(vlan), count: usages.length }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 20);

    charts.vlanDistribution = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: vlanEntries.map(v => `VLAN ${v.vlan}`),
            datasets: [{
                label: 'EPG Count',
                data: vlanEntries.map(v => v.count),
                backgroundColor: '#9966FF'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

function populateVLANOverlaps() {
    const container = document.getElementById('vlan-overlaps');
    if (!container) return;

    const overlaps = vizData.vlan_distribution?.overlaps || [];

    if (overlaps.length === 0) {
        container.innerHTML = '<div class="no-data">✓ No VLAN overlaps detected</div>';
        return;
    }

    container.innerHTML = overlaps.map(overlap => `
        <div class="overlap-card severity-${overlap.severity}">
            <div class="overlap-header">
                <span class="overlap-vlan">VLAN ${overlap.vlan}</span>
                <span class="overlap-badge">${overlap.epg_count} EPGs</span>
            </div>
            <div class="overlap-severity">${overlap.severity.toUpperCase()}</div>
            <div class="overlap-details">${overlap.total_bindings} total bindings</div>
        </div>
    `).join('');
}

function createVLANHeatmap() {
    const container = document.getElementById('vlan-heatmap');
    if (!container) return;

    const vlanData = vizData.vlan_distribution || {};
    const stats = vlanData.statistics || {};
    const vlanRange = stats.vlan_range || 'N/A';

    if (vlanRange === 'N/A') {
        container.innerHTML = '<div class="no-data">No VLAN data available</div>';
        return;
    }

    const [minVlan, maxVlan] = vlanRange.split('-').map(Number);
    const vlanUsage = vlanData.vlan_usage || {};

    // Create simple heatmap visualization
    let html = '<div class="vlan-heatmap-grid">';
    for (let vlan = minVlan; vlan <= Math.min(maxVlan, minVlan + 100); vlan++) {
        const usage = vlanUsage[vlan]?.length || 0;
        const intensity = Math.min(usage / 5, 1);  // Max 5 EPGs for color scaling
        html += `<div class="vlan-cell" style="background-color: rgba(74, 144, 226, ${intensity})"
                     title="VLAN ${vlan}: ${usage} EPG(s)"></div>`;
    }
    html += '</div>';
    html += `<div class="heatmap-legend">Showing VLANs ${minVlan}-${Math.min(maxVlan, minVlan + 100)}</div>`;

    container.innerHTML = html;
}

// ===== Complexity Dashboard =====
function initializeComplexityDashboard() {
    createComplexityDistributionChart();
    createComplexityFactorsChart();
    createTopComplexEPGsChart();
}

function createComplexityDistributionChart() {
    const ctx = document.getElementById('complexityDistributionChart');
    if (!ctx) return;

    const epgComplexity = vizData.epg_complexity || [];
    if (epgComplexity.length === 0) {
        showNoData('complexityDistributionChart', 'No EPG complexity data available');
        return;
    }

    const levels = { low: 0, medium: 0, high: 0 };
    epgComplexity.forEach(epg => {
        levels[epg.complexity_level]++;
    });

    charts.complexityDistribution = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Low', 'Medium', 'High'],
            datasets: [{
                data: [levels.low, levels.medium, levels.high],
                backgroundColor: ['#7ED321', '#FFCD56', '#FF6384']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function createComplexityFactorsChart() {
    const ctx = document.getElementById('complexityFactorsChart');
    if (!ctx) return;

    const epgComplexity = vizData.epg_complexity || [];
    if (epgComplexity.length === 0) {
        showNoData('complexityFactorsChart', 'No EPG complexity data available');
        return;
    }

    // Calculate averages
    const avgPaths = epgComplexity.reduce((sum, e) => sum + e.path_count, 0) / epgComplexity.length || 0;
    const avgVlans = epgComplexity.reduce((sum, e) => sum + e.vlan_count, 0) / epgComplexity.length || 0;
    const avgNodes = epgComplexity.reduce((sum, e) => sum + e.node_count, 0) / epgComplexity.length || 0;

    charts.complexityFactors = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Path Attachments', 'VLAN Diversity', 'Node Spread'],
            datasets: [{
                label: 'Average Complexity Factors',
                data: [avgPaths, avgVlans, avgNodes],
                backgroundColor: 'rgba(153, 102, 255, 0.2)',
                borderColor: '#9966FF',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true
                }
            }
        }
    });
}

function createTopComplexEPGsChart() {
    const ctx = document.getElementById('topComplexEpgsChart');
    if (!ctx) return;

    const epgComplexity = (vizData.epg_complexity || []).slice(0, 20);
    if (epgComplexity.length === 0) {
        showNoData('topComplexEpgsChart', 'No EPG complexity data available');
        return;
    }

    charts.topComplexEpgs = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: epgComplexity.map(e => e.epg_name),
            datasets: [{
                label: 'Complexity Score',
                data: epgComplexity.map(e => e.complexity_score),
                backgroundColor: epgComplexity.map(e => {
                    if (e.complexity_level === 'high') return '#FF6384';
                    if (e.complexity_level === 'medium') return '#FFCD56';
                    return '#7ED321';
                })
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// ===== Migration Dashboard =====
function initializeMigrationDashboard() {
    populateMigrationSummary();
    createMigrationFlagsChart();
    createVPCSymmetryChart();
    populateMigrationFlagsList();
}

function populateMigrationSummary() {
    const flags = vizData.migration_flags || [];
    const readyEl = document.getElementById('ready-count');
    const warningEl = document.getElementById('warning-count');
    const issueEl = document.getElementById('issue-count');
    if (!readyEl || !warningEl || !issueEl) return;

    const ready = flags.filter(f => f.severity === 'low').length;
    const warnings = flags.filter(f => f.severity === 'medium').length;
    const issues = flags.filter(f => f.severity === 'high').length;

    readyEl.textContent = ready;
    warningEl.textContent = warnings;
    issueEl.textContent = issues;
}

function createMigrationFlagsChart() {
    const ctx = document.getElementById('migrationFlagsChart');
    if (!ctx) return;

    const flags = vizData.migration_flags || [];
    if (!flags.length) {
        showNoData('migrationFlagsChart', 'No migration flag data available');
        return;
    }
    const categoryCounts = {};

    flags.forEach(flag => {
        categoryCounts[flag.category] = (categoryCounts[flag.category] || 0) + flag.count;
    });

    charts.migrationFlags = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(categoryCounts),
            datasets: [{
                data: Object.values(categoryCounts),
                backgroundColor: [
                    '#FF6384', '#36A2EB', '#FFCD56', '#4BC0C0', '#9966FF'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function createVPCSymmetryChart() {
    const ctx = document.getElementById('vpcSymmetryChart');
    if (!ctx) return;

    const vpcStats = vizData.vpc_symmetry?.statistics || {};
    const symmetryRate = vpcStats.symmetry_rate || 0;
    if (!Object.keys(vpcStats).length) {
        showNoData('vpcSymmetryChart', 'No VPC symmetry data available');
        return;
    }

    charts.vpcSymmetry = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Symmetric', 'Asymmetric'],
            datasets: [{
                data: [symmetryRate, 100 - symmetryRate],
                backgroundColor: ['#7ED321', '#FF6384']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed.toFixed(1) + '%';
                        }
                    }
                }
            }
        }
    });
}

function populateMigrationFlagsList() {
    const container = document.getElementById('migration-flags-list');
    if (!container) return;

    const flags = vizData.migration_flags || [];

    if (flags.length === 0) {
        container.innerHTML = '<div class="no-data">✓ No migration issues detected</div>';
        return;
    }

    container.innerHTML = flags.map(flag => `
        <div class="flag-card severity-${flag.severity}">
            <div class="flag-header">
                <span class="flag-badge">${flag.severity.toUpperCase()}</span>
                <span class="flag-count">${flag.count} items</span>
            </div>
            <div class="flag-message">${flag.message}</div>
            <div class="flag-recommendation">💡 ${flag.recommendation}</div>
        </div>
    `).join('');
}

// ===== Hierarchy Dashboard =====
function initializeHierarchyDashboard() {
    if (!vizData.device_mapping || !vizData.device_mapping.hierarchy) {
        console.log('No device mapping data available');
        return;
    }

    // Populate tenant filter dropdown
    const tenantFilter = document.getElementById('hierarchy-tenant-filter');
    if (tenantFilter) {
        const tenants = new Set();
        Object.values(vizData.device_mapping.device_map || {}).forEach(device => {
            (device.tenants || []).forEach(tenant => tenants.add(tenant));
        });

        Array.from(tenants).sort().forEach(tenant => {
            const option = document.createElement('option');
            option.value = tenant;
            option.textContent = tenant;
            tenantFilter.appendChild(option);
        });
    }

    console.log('Hierarchy dashboard initialized');
}

function toggleNode(headerElement) {
    const contentElement = headerElement.nextElementSibling;
    const toggleIcon = headerElement.querySelector('.toggle-icon');

    if (contentElement.style.display === 'none') {
        contentElement.style.display = 'block';
        toggleIcon.textContent = '▼';
        headerElement.classList.add('expanded');
    } else {
        contentElement.style.display = 'none';
        toggleIcon.textContent = '▶';
        headerElement.classList.remove('expanded');
    }
}

function toggleExpandAll() {
    const expandAll = document.getElementById('expand-all');
    const allNodes = document.querySelectorAll('.hierarchy-node .node-header');

    allNodes.forEach(header => {
        const contentElement = header.nextElementSibling;
        const toggleIcon = header.querySelector('.toggle-icon');

        if (expandAll.checked) {
            contentElement.style.display = 'block';
            toggleIcon.textContent = '▼';
            header.classList.add('expanded');
        } else {
            contentElement.style.display = 'none';
            toggleIcon.textContent = '▶';
            header.classList.remove('expanded');
        }
    });
}

function filterHierarchy() {
    const leafFilter = document.getElementById('hierarchy-leaf-filter').value;
    const tenantFilter = document.getElementById('hierarchy-tenant-filter').value;
    const vlanFilter = document.getElementById('hierarchy-vlan-filter').value.trim();
    const searchText = document.getElementById('hierarchy-search').value.toLowerCase();
    const showEmpty = document.getElementById('show-empty-devices').checked;

    // Parse VLAN filter (supports "100" or "100-200")
    let vlanMin = null, vlanMax = null;
    if (vlanFilter) {
        if (vlanFilter.includes('-')) {
            const parts = vlanFilter.split('-');
            vlanMin = parseInt(parts[0]);
            vlanMax = parseInt(parts[1]);
        } else {
            vlanMin = vlanMax = parseInt(vlanFilter);
        }
    }

    // Filter leaf nodes
    const leafNodes = document.querySelectorAll('.leaf-node');
    let visibleCount = 0;

    leafNodes.forEach(leafNode => {
        const leafId = leafNode.getAttribute('data-leaf-id');
        const leafTitleElement = leafNode.querySelector('.node-title');
        const leafTitle = leafTitleElement ? leafTitleElement.textContent.toLowerCase() : '';

        // Check leaf filter
        if (leafFilter !== 'all' && leafId !== leafFilter) {
            leafNode.style.display = 'none';
            return;
        }

        // Check search text
        if (searchText && !leafTitle.includes(searchText)) {
            let matchFound = false;

            // Check FEX and EPG names
            const fexNodes = leafNode.querySelectorAll('.fex-node');
            fexNodes.forEach(fexNode => {
                const fexTitleElement = fexNode.querySelector('.node-title');
                const fexTitle = fexTitleElement ? fexTitleElement.textContent.toLowerCase() : '';
                if (fexTitle.includes(searchText)) {
                    matchFound = true;
                }
            });

            const epgItems = leafNode.querySelectorAll('.epg-item');
            epgItems.forEach(epgItem => {
                const epgNameElement = epgItem.querySelector('.epg-name');
                const epgName = epgNameElement ? epgNameElement.textContent.toLowerCase() : '';
                if (epgName.includes(searchText)) {
                    matchFound = true;
                }
            });

            if (!matchFound) {
                leafNode.style.display = 'none';
                return;
            }
        }

        // Filter FEX nodes and EPG items within this leaf
        let hasVisibleContent = false;

        // Filter FEX nodes
        const fexNodes = leafNode.querySelectorAll('.fex-node');
        fexNodes.forEach(fexNode => {
            const epgItems = fexNode.querySelectorAll('.epg-item');
            let fexHasVisibleEpgs = false;

            epgItems.forEach(epgItem => {
                const tenant = epgItem.getAttribute('data-tenant');
                const vlan = epgItem.getAttribute('data-vlan');
                const epgNameElement = epgItem.querySelector('.epg-name');
                const epgName = epgNameElement ? epgNameElement.textContent.toLowerCase() : '';

                let visible = true;

                // Apply tenant filter
                if (tenantFilter !== 'all' && tenant !== tenantFilter) {
                    visible = false;
                }

                // Apply VLAN filter
                if (vlanMin !== null && vlan && vlan !== 'None') {
                    const vlanNum = parseInt(vlan);
                    if (vlanNum < vlanMin || vlanNum > vlanMax) {
                        visible = false;
                    }
                }

                // Apply search filter
                if (searchText && !epgName.includes(searchText)) {
                    visible = false;
                }

                epgItem.style.display = visible ? 'flex' : 'none';
                if (visible) {
                    fexHasVisibleEpgs = true;
                    hasVisibleContent = true;
                }
            });

            // Show/hide FEX based on whether it has visible EPGs
            if (!showEmpty && !fexHasVisibleEpgs) {
                fexNode.style.display = 'none';
            } else {
                fexNode.style.display = 'block';
                hasVisibleContent = true;
            }
        });

        // Filter direct EPG items on leaf
        const directEpgs = leafNode.querySelectorAll('.epg-section .epg-item');
        directEpgs.forEach(epgItem => {
            const tenant = epgItem.getAttribute('data-tenant');
            const vlan = epgItem.getAttribute('data-vlan');
            const epgNameElement = epgItem.querySelector('.epg-name');
            const epgName = epgNameElement ? epgNameElement.textContent.toLowerCase() : '';

            let visible = true;

            if (tenantFilter !== 'all' && tenant !== tenantFilter) {
                visible = false;
            }

            if (vlanMin !== null && vlan && vlan !== 'None') {
                const vlanNum = parseInt(vlan);
                if (vlanNum < vlanMin || vlanNum > vlanMax) {
                    visible = false;
                }
            }

            if (searchText && !epgName.includes(searchText)) {
                visible = false;
            }

            epgItem.style.display = visible ? 'flex' : 'none';
            if (visible) {
                hasVisibleContent = true;
            }
        });

        // Show/hide leaf based on content
        if (!showEmpty && !hasVisibleContent) {
            leafNode.style.display = 'none';
        } else {
            leafNode.style.display = 'block';
            visibleCount++;
        }
    });

    // Filter the stats table
    const tableRows = document.querySelectorAll('.stats-table tbody tr');
    tableRows.forEach(row => {
        const deviceCell = row.querySelector('td:first-child');
        const searchable = (deviceCell ? deviceCell.textContent : row.textContent).toLowerCase();

        let visible = true;

        if (searchText && !searchable.includes(searchText)) {
            visible = false;
        }

        row.style.display = visible ? 'table-row' : 'none';
    });

    console.log(`Filtered hierarchy: ${visibleCount} leafs visible`);
}

function scrollToDevice(deviceId) {
    switchTab('hierarchy');

    // Find the device in the hierarchy
    const deviceNode = document.querySelector(`[data-leaf-id="${deviceId}"], [data-fex-id="${deviceId}"]`);

    if (deviceNode) {
        // Expand parent nodes
        let parent = deviceNode.parentElement;
        while (parent) {
            if (parent.classList && parent.classList.contains('node-content')) {
                parent.style.display = 'block';
                const header = parent.previousElementSibling;
                if (header) {
                    const toggleIcon = header.querySelector('.toggle-icon');
                    if (toggleIcon) {
                        toggleIcon.textContent = '▼';
                    }
                    header.classList.add('expanded');
                }
            }
            parent = parent.parentElement;
        }

        // Scroll to device
        deviceNode.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Highlight briefly
        deviceNode.classList.add('highlight');
        setTimeout(() => {
            deviceNode.classList.remove('highlight');
        }, 2000);
    }
}

function exportHierarchyData() {
    if (!vizData.device_mapping) {
        alert('No device mapping data available to export');
        return;
    }

    // Build CSV data
    const rows = [
        ['Device Type', 'Device ID', 'EPG Name', 'Tenant', 'VLAN', 'EPG DN']
    ];

    vizData.device_mapping.hierarchy.forEach(leaf => {
        // Direct EPGs on leaf
        if (leaf.direct_epgs) {
            leaf.direct_epgs.forEach(epg => {
                rows.push([
                    'Leaf',
                    `leaf-${leaf.leaf_id}`,
                    epg.epg,
                    epg.tenant,
                    epg.vlan || 'N/A',
                    epg.epg_dn || 'N/A'
                ]);
            });
        }

        // EPGs on FEX
        if (leaf.fex_devices) {
            leaf.fex_devices.forEach(fex => {
                if (fex.epgs) {
                    fex.epgs.forEach(epg => {
                        rows.push([
                            'FEX',
                            `fex-${fex.fex_id}`,
                            epg.epg,
                            epg.tenant,
                            epg.vlan || 'N/A',
                            epg.epg_dn || 'N/A'
                        ]);
                    });
                }
            });
        }
    });

    // Convert to CSV string
    const csvContent = rows.map(row =>
        row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');

    // Download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `device_hierarchy_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    console.log(`Exported ${rows.length - 1} records to CSV`);
}

function exportLeafFexEpgMapping() {
    if (!vizData.device_mapping || !vizData.device_mapping.hierarchy) {
        alert('No device mapping data available to export');
        return;
    }

    const rows = [
        ['Leaf ID', 'Leaf Name', 'FEX ID', 'EPG Name', 'Tenant', 'VLAN', 'EPG DN']
    ];

    vizData.device_mapping.hierarchy.forEach(leaf => {
        const leafId = leaf.leaf_id ? `leaf-${leaf.leaf_id}` : '';
        const leafName = leaf.leaf_name || '';
        (leaf.fex_devices || []).forEach(fex => {
            const fexId = fex.fex_id ? `fex-${fex.fex_id}` : '';
            if (fex.epgs && fex.epgs.length) {
                fex.epgs.forEach(epg => {
                    rows.push([
                        leafId,
                        leafName,
                        fexId,
                        epg.epg || '',
                        epg.tenant || '',
                        epg.vlan || 'N/A',
                        epg.epg_dn || 'N/A'
                    ]);
                });
            } else {
                rows.push([leafId, leafName, fexId, '', '', '', '']);
            }
        });
    });

    const csvContent = rows.map(row =>
        row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `leaf_fex_epg_mapping_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    Object.values(charts).forEach(chart => {
        if (chart && chart.destroy) {
            chart.destroy();
        }
    });
});
