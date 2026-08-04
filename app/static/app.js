// Global Application State
let activeWorkspace = "Default";
let networkInstance = null;
let physicsEnabled = true;
let currentNodes = [];

// DOM Elements
const workspaceSelect = document.getElementById("workspaceSelect");
const newWorkspaceForm = document.getElementById("newWorkspaceForm");
const newWorkspaceInput = document.getElementById("newWorkspaceInput");
const scrapeForm = document.getElementById("scrapeForm");
const scrapeUrlInput = document.getElementById("scrapeUrlInput");
const scrapeSubmitBtn = document.getElementById("scrapeSubmitBtn");
const scraperStatus = document.getElementById("scraperStatus");
const statArticles = document.getElementById("statArticles");
const statPeople = document.getElementById("statPeople");
const statCompanies = document.getElementById("statCompanies");
const recentArticlesBody = document.getElementById("recentArticlesBody");
const connectionsTableBody = document.getElementById("connectionsTableBody");
const networkGraphContainer = document.getElementById("networkGraphContainer");
const togglePhysicsBtn = document.getElementById("togglePhysicsBtn");
const resetGraphBtn = document.getElementById("resetGraphBtn");

// Pathfinder Elements
const pathfinderForm = document.getElementById("pathfinderForm");
const pathSourceSelect = document.getElementById("pathSourceSelect");
const pathTargetSelect = document.getElementById("pathTargetSelect");
const findPathBtn = document.getElementById("findPathBtn");
const clearPathBtn = document.getElementById("clearPathBtn");

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
    // Load workspaces
    loadWorkspaces().then(() => {
        // Trigger initial data load
        updateDashboardData();
    });

    // Event Listeners
    workspaceSelect.addEventListener("change", (e) => {
        activeWorkspace = e.target.value;
        updateDashboardData();
    });

    newWorkspaceForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const newOrg = newWorkspaceInput.value.trim();
        if (!newOrg) return;

        // Check if it already exists in select
        let exists = false;
        for (let i = 0; i < workspaceSelect.options.length; i++) {
            if (workspaceSelect.options[i].value.toLowerCase() === newOrg.toLowerCase()) {
                exists = true;
                workspaceSelect.selectedIndex = i;
                activeWorkspace = workspaceSelect.options[i].value;
                break;
            }
        }

        if (!exists) {
            // Add temporary client-side option until it's saved in DB
            const option = document.createElement("option");
            option.value = newOrg;
            option.textContent = newOrg;
            workspaceSelect.appendChild(option);
            workspaceSelect.value = newOrg;
            activeWorkspace = newOrg;
        }

        newWorkspaceInput.value = "";
        updateDashboardData();
    });

    scrapeForm.addEventListener("submit", handleScrapeSubmit);
    pathfinderForm.addEventListener("submit", handlePathfinderSubmit);
    clearPathBtn.addEventListener("click", handleClearPath);
 
    togglePhysicsBtn.addEventListener("click", () => {
        physicsEnabled = !physicsEnabled;
        togglePhysicsBtn.classList.toggle("active", physicsEnabled);
        if (networkInstance) {
            networkInstance.setOptions({ physics: { enabled: physicsEnabled } });
        }
    });

    resetGraphBtn.addEventListener("click", () => {
        if (networkInstance) {
            networkInstance.fit({ animation: true });
        }
    });

    // Stats Cards & Legend Items Click Interactivity
    document.querySelectorAll(".stat-card, .legend-item[data-entity]").forEach(item => {
        item.addEventListener("click", () => {
            const entityType = item.getAttribute("data-entity");
            openEntityDetailsModal(entityType);
        });
    });

    // Close Modal Event Listeners
    const closeModalBtn = document.getElementById("closeModalBtn");
    const detailsModal = document.getElementById("detailsModal");
    if (closeModalBtn && detailsModal) {
        closeModalBtn.addEventListener("click", () => {
            detailsModal.classList.add("hidden");
        });
        detailsModal.addEventListener("click", (e) => {
            if (e.target === detailsModal) {
                detailsModal.classList.add("hidden");
            }
        });
    }
});

// Load Workspaces list from API
async function loadWorkspaces() {
    try {
        const response = await fetch("/api/organizations");
        const data = await response.json();
        const orgs = data.organizations || [];

        // Save current selection if possible
        const prevSelection = activeWorkspace;

        // Clear existing, keep default
        workspaceSelect.innerHTML = "";
        
        // Ensure "Default" is present
        if (!orgs.includes("Default")) {
            orgs.unshift("Default");
        }

        orgs.forEach(org => {
            const option = document.createElement("option");
            option.value = org;
            option.textContent = org;
            workspaceSelect.appendChild(option);
        });

        // Restore selection or select first
        if (orgs.includes(prevSelection)) {
            workspaceSelect.value = prevSelection;
            activeWorkspace = prevSelection;
        } else {
            workspaceSelect.value = orgs[0];
            activeWorkspace = orgs[0];
        }
    } catch (error) {
        console.error("Failed to load workspace list:", error);
    }
}

// Fetch stats, recent articles, and graph for active workspace
function updateDashboardData() {
    fetchStats();
    fetchRecentArticles();
    fetchGraphData();
}

// Fetch stats
async function fetchStats() {
    try {
        const response = await fetch(`/api/stats?org=${encodeURIComponent(activeWorkspace)}`);
        const stats = await response.json();
        
        statArticles.textContent = stats.articles || 0;
        statPeople.textContent = stats.people || 0;
        statCompanies.textContent = stats.companies || 0;
    } catch (error) {
        console.error("Failed to fetch stats:", error);
    }
}

// Fetch recent articles list
async function fetchRecentArticles() {
    try {
        const response = await fetch(`/api/recent?org=${encodeURIComponent(activeWorkspace)}`);
        const data = await response.json();
        const articles = data.articles || [];

        recentArticlesBody.innerHTML = "";

        if (articles.length === 0) {
            recentArticlesBody.innerHTML = `
                <tr>
                    <td colspan="2" class="empty-state">No articles in this workspace yet.</td>
                </tr>
            `;
            return;
        }

        articles.forEach(article => {
            const row = document.createElement("tr");
            
            const titleCell = document.createElement("td");
            titleCell.textContent = article.title;
            titleCell.style.fontWeight = "500";
            
            const dateCell = document.createElement("td");
            dateCell.className = "time-stamp";
            if (article.created_at) {
                const date = new Date(article.created_at);
                dateCell.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + date.toLocaleDateString();
            } else {
                dateCell.textContent = "N/A";
            }

            row.appendChild(titleCell);
            row.appendChild(dateCell);
            recentArticlesBody.appendChild(row);
        });
    } catch (error) {
        console.error("Failed to fetch recent articles:", error);
    }
}

// Fetch and render workspace network graph
async function fetchGraphData() {
    try {
        const response = await fetch(`/api/graph?org=${encodeURIComponent(activeWorkspace)}`);
        const graph = await response.json();
        
        const nodes = graph.nodes || [];
        const edges = graph.edges || [];

        if (nodes.length === 0) {
            networkGraphContainer.innerHTML = `
                <div class="graph-placeholder">
                    <i class="fa-solid fa-circle-nodes"></i>
                    <p>No entity nodes in this workspace yet. Paste a URL below to extract intelligence!</p>
                </div>
            `;
            networkInstance = null;
            currentNodes = [];
            if (connectionsTableBody) {
                connectionsTableBody.innerHTML = `
                    <tr>
                        <td colspan="3" class="empty-state">No connections in this workspace yet.</td>
                    </tr>
                `;
            }
            populatePathfinderSelects([]);
            return;
        }

        currentNodes = nodes;
        renderNetwork(nodes, edges);
        renderConnectionsTable(nodes, edges);
        populatePathfinderSelects(nodes);
    } catch (error) {
        console.error("Failed to load graph data:", error);
        networkGraphContainer.innerHTML = `
            <div class="graph-placeholder" style="color: var(--error);">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p>Failed to load network graph visualization.</p>
            </div>
        `;
    }
}

// Render dynamic graph using Vis.js Network
function renderNetwork(nodesArray, edgesArray) {
    // Styling attributes based on groups
    const styledNodes = nodesArray.map(node => {
        let size = 12;
        let font = { color: "#ffffff", size: 12, face: "Outfit" };
        
        if (node.group === "Organization") {
            size = 22;
            font = { color: "#ffffff", size: 14, bold: true, face: "Outfit" };
        } else if (node.group === "Article") {
            size = 18;
            font = { color: "#e1e7ec", size: 12, face: "Outfit" };
        }

        return {
            ...node,
            size: size,
            font: font
        };
    });

    // Use DataSet to allow dynamic style updates (highlights/dimming)
    const nodesDataSet = new vis.DataSet(styledNodes);
    const edgesDataSet = new vis.DataSet(edgesArray);

    const data = {
        nodes: nodesDataSet,
        edges: edgesDataSet
    };

    const options = {
        nodes: {
            shape: "dot",
            borderWidth: 2,
            shadow: {
                enabled: true,
                color: "rgba(0, 0, 0, 0.4)",
                size: 6,
                x: 2,
                y: 2
            }
        },
        edges: {
            width: 1.5,
            color: {
                color: "rgba(255, 255, 255, 0.15)",
                highlight: "#6366f1",
                hover: "rgba(255, 255, 255, 0.3)"
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.8 }
            },
            font: {
                color: "#9ca3af",
                size: 9,
                face: "Outfit",
                background: "#0b0c13"
            },
            smooth: {
                type: "dynamic"
            }
        },
        groups: {
            Organization: {
                color: {
                    background: "#ffd043",
                    border: "#d9ae26",
                    highlight: { background: "#ffe082", border: "#ffd043" }
                }
            },
            Article: {
                color: {
                    background: "#00e5ff",
                    border: "#00b2c7",
                    highlight: { background: "#80f2ff", border: "#00e5ff" }
                }
            },
            Person: {
                color: {
                    background: "#00ff87",
                    border: "#00cc6c",
                    highlight: { background: "#80ffc3", border: "#00ff87" }
                }
            },
            Company: {
                color: {
                    background: "#ff5f7e",
                    border: "#d94c67",
                    highlight: { background: "#ffb0c0", border: "#ff5f7e" }
                }
            },
            Location: {
                color: {
                    background: "#a855f7",
                    border: "#8b5cf6",
                    highlight: { background: "#c084fc", border: "#a855f7" }
                }
            }
        },
        physics: {
            enabled: true, // Always start with physics enabled for initial layout arrangement
            solver: "barnesHut",
            barnesHut: {
                gravitationalConstant: -1800,
                centralGravity: 0.25,
                springLength: 95,
                springConstant: 0.05,
                damping: 0.09,
                avoidOverlap: 1
            },
            stabilization: {
                enabled: true,
                iterations: 150,
                updateInterval: 25,
                fit: true
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200
        }
    };

    // Recreate canvas element to clean legacy structures
    networkGraphContainer.innerHTML = "";
    
    networkInstance = new vis.Network(networkGraphContainer, data, options);

    // Freeze physics once stabilization completes to prevent continuous lag
    networkInstance.on("stabilizationFinished", function () {
        networkInstance.setOptions({ physics: { enabled: false } });
        physicsEnabled = false;
        if (togglePhysicsBtn) {
            togglePhysicsBtn.classList.remove("active");
        }
    });

    // Track state to reset highlights
    let isNodeSelected = false;

    // Interactive Single-Click Neighborhood Highlighting
    networkInstance.on("click", function (params) {
        if (params.nodes.length > 0) {
            const selectedNodeId = params.nodes[0];
            highlightNeighbors(selectedNodeId, nodesDataSet, edgesDataSet);
            isNodeSelected = true;
        } else {
            if (isNodeSelected) {
                resetHighlights(nodesDataSet, edgesDataSet);
                isNodeSelected = false;
            }
        }
    });

    // Double-Click to fill Pathfinder Shortcut
    networkInstance.on("doubleClick", function (params) {
        if (params.nodes.length > 0) {
            const clickedNodeId = params.nodes[0];
            const clickedNode = nodesDataSet.get(clickedNodeId);
            if (clickedNode && clickedNode.label) {
                if (pathSourceSelect && pathTargetSelect) {
                    if (!pathSourceSelect.value) {
                        pathSourceSelect.value = clickedNode.label;
                    } else if (!pathTargetSelect.value) {
                        pathTargetSelect.value = clickedNode.label;
                    } else {
                        pathSourceSelect.value = clickedNode.label;
                        pathTargetSelect.value = "";
                    }
                }
            }
        }
    });
}

// Highlights directly connected neighbor nodes & edges
function highlightNeighbors(selectedNodeId, nodesDataset, edgesDataset) {
    const connectedEdges = networkInstance.getConnectedEdges(selectedNodeId);
    const connectedNodes = networkInstance.getConnectedNodes(selectedNodeId);
    
    const allNodes = nodesDataset.get();
    const allEdges = edgesDataset.get();
    
    const updatedNodes = allNodes.map(node => {
        const isNeighbor = connectedNodes.includes(node.id) || node.id === selectedNodeId;
        let fontColor = "#ffffff";
        if (node.group === "Article") fontColor = "#e1e7ec";
        
        return {
            id: node.id,
            color: {
                background: isNeighbor ? undefined : "rgba(30, 41, 59, 0.2)",
                border: isNeighbor ? undefined : "rgba(30, 41, 59, 0.1)"
            },
            font: {
                color: isNeighbor ? fontColor : "rgba(148, 163, 184, 0.25)"
            }
        };
    });
    
    const updatedEdges = allEdges.map(edge => {
        const isConnected = connectedEdges.includes(edge.id);
        return {
            id: edge.id,
            color: {
                color: isConnected ? "#6366f1" : "rgba(255, 255, 255, 0.02)"
            }
        };
    });
    
    nodesDataset.update(updatedNodes);
    edgesDataset.update(updatedEdges);
}

// Resets opacity highlights for all nodes & edges
function resetHighlights(nodesDataset, edgesDataset) {
    const allNodes = nodesDataset.get();
    const allEdges = edgesDataset.get();
    
    const updatedNodes = allNodes.map(node => {
        let fontColor = "#ffffff";
        if (node.group === "Article") fontColor = "#e1e7ec";
        return {
            id: node.id,
            color: {
                background: undefined,
                border: undefined
            },
            font: {
                color: fontColor
            }
        };
    });
    
    const updatedEdges = allEdges.map(edge => {
        return {
            id: edge.id,
            color: {
                color: "rgba(255, 255, 255, 0.15)"
            }
        };
    });
    
    nodesDataset.update(updatedNodes);
    edgesDataset.update(updatedEdges);
}

// Handle Form Submission for Scraping
async function handleScrapeSubmit(e) {
    e.preventDefault();
    const url = scrapeUrlInput.value.trim();
    if (!url) return;

    // Show loaders & disable buttons
    scrapeSubmitBtn.disabled = true;
    scraperStatus.classList.remove("hidden");

    try {
        const response = await fetch("/api/scrape", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                url: url,
                org: activeWorkspace
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Server error processing scrapers.");
        }

        const data = await response.json();
        
        // Flash success status
        const textEl = scraperStatus.querySelector(".status-text");
        textEl.textContent = `Queued: "${data.title.substring(0, 40)}..."`;
        scraperStatus.style.borderColor = "var(--success)";
        
        scrapeUrlInput.value = "";

        // Reload lists/graphs in cycles so background threads show updates
        setTimeout(() => {
            updateDashboardData();
            loadWorkspaces(); // Refresh selection dropdown
        }, 1000);

        setTimeout(() => {
            updateDashboardData();
        }, 3000);

        setTimeout(() => {
            updateDashboardData();
            // Reset loader status
            textEl.textContent = "Scraping web article content...";
            scraperStatus.classList.add("hidden");
            scraperStatus.style.borderColor = "var(--border-color)";
            scrapeSubmitBtn.disabled = false;
        }, 5000);

    } catch (error) {
        console.error("Scraping operation failed:", error);
        alert(`Failed to ingest article: ${error.message}`);
        
        // Reset loader status
        scraperStatus.classList.add("hidden");
        scrapeSubmitBtn.disabled = false;
    }
}

// Pathfinder Submit Handler
async function handlePathfinderSubmit(e) {
    e.preventDefault();
    if (!pathSourceSelect || !pathTargetSelect) return;
    const source = pathSourceSelect.value;
    const target = pathTargetSelect.value;
    if (!source || !target) return;

    findPathBtn.disabled = true;

    try {
        const response = await fetch(`/api/path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to find shortest path.");
        }
        
        const pathData = await response.json();
        
        if (!pathData.nodes || pathData.nodes.length === 0) {
            alert(`No connection found between "${source}" and "${target}".`);
            findPathBtn.disabled = false;
            return;
        }

        // Render ONLY the isolated path nodes and edges in the network canvas
        renderNetwork(pathData.nodes, pathData.edges);
        
        // Also update the connections list table below to display only the path connections
        renderConnectionsTable(pathData.nodes, pathData.edges);

    } catch (error) {
        console.error("Pathfinding failed:", error);
        alert(`Pathfinding error: ${error.message}`);
    } finally {
        findPathBtn.disabled = false;
    }
}

// Clear Pathfinder selection and reload full graph
function handleClearPath() {
    if (pathSourceSelect) pathSourceSelect.value = "";
    if (pathTargetSelect) pathTargetSelect.value = "";
    updateDashboardData();
}

// Render dynamic relationships table
function renderConnectionsTable(nodes, edges) {
    if (!connectionsTableBody) return;
    
    connectionsTableBody.innerHTML = "";
    
    if (edges.length === 0) {
        connectionsTableBody.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">No connections in this workspace yet.</td>
            </tr>
        `;
        return;
    }
    
    // Create a lookup map for node data
    const nodeMap = new Map();
    nodes.forEach(node => {
        nodeMap.set(node.id, node);
    });
    
    edges.forEach(edge => {
        const sourceNode = nodeMap.get(edge.from);
        const targetNode = nodeMap.get(edge.to);
        
        if (!sourceNode || !targetNode) return;
        
        const row = document.createElement("tr");
        
        // Source Cell
        const sourceCell = document.createElement("td");
        const sourceGroup = sourceNode.group || "Unknown";
        sourceCell.innerHTML = `<span class="badge badge-${sourceGroup.toLowerCase()}">${sourceNode.label}</span>`;
        
        // Relation/Edge Label Cell
        const relationCell = document.createElement("td");
        relationCell.innerHTML = `<span class="relation-code">${edge.label}</span>`;
        
        // Target Cell
        const targetCell = document.createElement("td");
        const targetGroup = targetNode.group || "Unknown";
        targetCell.innerHTML = `<span class="badge badge-${targetGroup.toLowerCase()}">${targetNode.label}</span>`;
        
        row.appendChild(sourceCell);
        row.appendChild(relationCell);
        row.appendChild(targetCell);
        
        connectionsTableBody.appendChild(row);
    });
}

// Open modal containing table lists of entities
function openEntityDetailsModal(entityType) {
    const modal = document.getElementById("detailsModal");
    const modalTitle = document.getElementById("modalTitle");
    const modalTableHead = document.getElementById("modalTableHead");
    const modalTableBody = document.getElementById("modalTableBody");
    
    if (!modal || !modalTitle || !modalTableHead || !modalTableBody) return;
    
    let groupFilter = "";
    let columns = [];
    if (entityType === "articles") {
        groupFilter = "Article";
        modalTitle.textContent = "Workspace Articles";
        columns = ["Title", "Type"];
    } else if (entityType === "people") {
        groupFilter = "Person";
        modalTitle.textContent = "Extracted People";
        columns = ["Name", "Type"];
    } else if (entityType === "companies") {
        groupFilter = "Company";
        modalTitle.textContent = "Extracted Companies";
        columns = ["Name", "Type"];
    } else if (entityType === "organizations") {
        groupFilter = "Organization";
        modalTitle.textContent = "Workspace Organizations";
        columns = ["Name", "Type"];
    } else if (entityType === "locations") {
        groupFilter = "Location";
        modalTitle.textContent = "Extracted Locations";
        columns = ["Location", "Type"];
    } else {
        return;
    }
    
    // Set Header
    modalTableHead.innerHTML = `
        <tr>
            ${columns.map(col => `<th>${col}</th>`).join("")}
        </tr>
    `;
    
    // Filter Nodes
    const filteredNodes = currentNodes.filter(node => node.group === groupFilter);
    
    // Populate Body
    modalTableBody.innerHTML = "";
    if (filteredNodes.length === 0) {
        modalTableBody.innerHTML = `
            <tr>
                <td colspan="2" class="empty-state">No ${entityType} found in this workspace.</td>
            </tr>
        `;
    } else {
        filteredNodes.forEach(node => {
            const row = document.createElement("tr");
            
            const nameCell = document.createElement("td");
            nameCell.style.fontWeight = "500";
            nameCell.textContent = node.label;
            
            const groupCell = document.createElement("td");
            const nodeGroup = node.group || "Unknown";
            groupCell.innerHTML = `<span class="badge badge-${nodeGroup.toLowerCase()}">${nodeGroup}</span>`;
            
            row.appendChild(nameCell);
            row.appendChild(groupCell);
            modalTableBody.appendChild(row);
        });
    }
    
    // Show Modal
    modal.classList.remove("hidden");
}

// Populate the Pathfinder Source/Target Dropdown select menus
function populatePathfinderSelects(nodes) {
    if (!pathSourceSelect || !pathTargetSelect) return;
    
    // Save current values to restore if they still exist
    const prevSource = pathSourceSelect.value;
    const prevTarget = pathTargetSelect.value;
    
    pathSourceSelect.innerHTML = '<option value="" disabled selected>Select source...</option>';
    pathTargetSelect.innerHTML = '<option value="" disabled selected>Select target...</option>';
    
    if (nodes.length === 0) return;
    
    // Categorize nodes by group/type
    const groups = {
        Person: [],
        Company: [],
        Location: [],
        Article: [],
        Organization: []
    };
    
    nodes.forEach(node => {
        const grp = node.group || "Unknown";
        if (groups[grp]) {
            groups[grp].push(node);
        } else {
            groups[grp] = [node];
        }
    });
    
    // Sort nodes inside each group alphabetically by label
    for (const grp in groups) {
        groups[grp].sort((a, b) => a.label.localeCompare(b.label));
    }
    
    // Generate option elements grouped in optgroups
    const groupLabels = {
        Person: "People",
        Company: "Companies",
        Location: "Locations",
        Article: "Articles",
        Organization: "Workspaces"
    };
    
    const docFragmentSource = document.createDocumentFragment();
    const docFragmentTarget = document.createDocumentFragment();
    
    for (const grp of ["Person", "Company", "Location", "Article", "Organization"]) {
        const list = groups[grp] || [];
        if (list.length === 0) continue;
        
        const optgroupSource = document.createElement("optgroup");
        optgroupSource.label = groupLabels[grp];
        
        const optgroupTarget = document.createElement("optgroup");
        optgroupTarget.label = groupLabels[grp];
        
        list.forEach(node => {
            const optionSource = document.createElement("option");
            optionSource.value = node.label;
            optionSource.textContent = node.label;
            optgroupSource.appendChild(optionSource);
            
            const optionTarget = document.createElement("option");
            optionTarget.value = node.label;
            optionTarget.textContent = node.label;
            optgroupTarget.appendChild(optionTarget);
        });
        
        docFragmentSource.appendChild(optgroupSource);
        docFragmentTarget.appendChild(optgroupTarget);
    }
    
    pathSourceSelect.appendChild(docFragmentSource);
    pathTargetSelect.appendChild(docFragmentTarget);
    
    // Restore selection if nodes are still present in active graph
    const sourceExists = nodes.some(n => n.label === prevSource);
    if (sourceExists) pathSourceSelect.value = prevSource;
    
    const targetExists = nodes.some(n => n.label === prevTarget);
    if (targetExists) pathTargetSelect.value = prevTarget;
}
