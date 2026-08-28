// Global Application State
let activeWorkspace = "Default";
let networkInstance = null;
let physicsEnabled = true;
let currentNodes = [];
let currentEdges = [];
let includeTimeTree = false;
let graphLimit = 30;

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
    // Initialize custom dark dropdowns (replaces native OS popups)
    initCustomSelect(workspaceSelect);
    initCustomSelect(document.getElementById("graphLimitSelect"));
    initCustomSelect(pathSourceSelect);
    initCustomSelect(pathTargetSelect);

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
        refreshCustomSelect(workspaceSelect);
        updateDashboardData();
    });

    scrapeForm.addEventListener("submit", handleScrapeSubmit);
    pathfinderForm.addEventListener("submit", handlePathfinderSubmit);
    clearPathBtn.addEventListener("click", handleClearPath);

    const googleNewsTriggerBtn = document.getElementById("googleNewsTriggerBtn");
    if (googleNewsTriggerBtn) {
        googleNewsTriggerBtn.addEventListener("click", handleGoogleNewsTrigger);
    }

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

    const toggleTimeTreeBtn = document.getElementById("toggleTimeTreeBtn");
    if (toggleTimeTreeBtn) {
        toggleTimeTreeBtn.addEventListener("click", () => {
            includeTimeTree = !includeTimeTree;
            toggleTimeTreeBtn.classList.toggle("active", includeTimeTree);
            fetchGraphData();
        });
    }

    const consolidateEntitiesBtn = document.getElementById("consolidateEntitiesBtn");
    if (consolidateEntitiesBtn) {
        consolidateEntitiesBtn.addEventListener("click", async () => {
            consolidateEntitiesBtn.disabled = true;
            consolidateEntitiesBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Merging...';
            try {
                const res = await fetch(`/api/consolidate?org=${encodeURIComponent(activeWorkspace)}`, { method: "POST" });
                const data = await res.json();
                console.log("Entity Consolidation Response:", data);
                await updateDashboardData();
            } catch (err) {
                console.error("Entity Consolidation Failed:", err);
            } finally {
                consolidateEntitiesBtn.disabled = false;
                consolidateEntitiesBtn.innerHTML = '<i class="fa-solid fa-code-merge"></i> Merge Aliases';
            }
        });
    }

    const vacuumDbBtn = document.getElementById("vacuumDbBtn");
    if (vacuumDbBtn) {
        vacuumDbBtn.addEventListener("click", async () => {
            vacuumDbBtn.disabled = true;
            vacuumDbBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Vacuuming...';
            try {
                const res = await fetch(`/api/vacuum?org=${encodeURIComponent(activeWorkspace)}`, { method: "POST" });
                const data = await res.json();
                console.log("Database Vacuum Response:", data);
                await updateDashboardData();
            } catch (err) {
                console.error("Database Vacuum Failed:", err);
            } finally {
                vacuumDbBtn.disabled = false;
                vacuumDbBtn.innerHTML = '<i class="fa-solid fa-broom"></i> Vacuum DB';
            }
        });
    }

    const graphLimitSelect = document.getElementById("graphLimitSelect");
    if (graphLimitSelect) {
        graphLimitSelect.addEventListener("change", (e) => {
            graphLimit = parseInt(e.target.value, 10) || 30;
            fetchGraphData();
        });
    }

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

    // Close button for floating graph info box
    const closeInfoBoxBtn = document.getElementById("closeInfoBoxBtn");
    if (closeInfoBoxBtn) {
        closeInfoBoxBtn.addEventListener("click", () => {
            hideGraphInfoBox();
        });
    }

    const closeStockMenuBtn = document.getElementById("closeStockMenuBtn");
    if (closeStockMenuBtn) {
        closeStockMenuBtn.addEventListener("click", () => {
            hideCompanyStockMenu();
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

        refreshCustomSelect(workspaceSelect);
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
                    <td colspan="5" class="empty-state">No articles in this workspace yet.</td>
                </tr>
            `;
            return;
        }

        articles.forEach(article => {
            const row = document.createElement("tr");

            const titleCell = document.createElement("td");
            titleCell.textContent = article.title;
            titleCell.style.fontWeight = "500";

            const categoryCell = document.createElement("td");
            const catBadge = document.createElement("span");
            catBadge.className = "badge " + getCategoryClass(article.category);
            catBadge.textContent = article.category || "General";
            categoryCell.appendChild(catBadge);

            const sentimentCell = document.createElement("td");
            const sentBadge = document.createElement("span");
            sentBadge.className = "badge " + getSentimentClass(article.sentiment);
            sentBadge.textContent = article.sentiment || "Neutral";
            sentimentCell.appendChild(sentBadge);

            const dateCell = document.createElement("td");
            dateCell.className = "time-stamp";
            if (article.created_at) {
                const date = new Date(article.created_at);
                dateCell.textContent = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + date.toLocaleDateString();
            } else {
                dateCell.textContent = "N/A";
            }

            const linkCell = document.createElement("td");
            if (article.url) {
                const link = document.createElement("a");
                link.href = article.url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.className = "article-link-btn";
                link.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square"></i> Open`;
                linkCell.appendChild(link);
            } else {
                linkCell.textContent = "N/A";
                linkCell.style.color = "var(--text-muted)";
            }

            row.appendChild(titleCell);
            row.appendChild(categoryCell);
            row.appendChild(sentimentCell);
            row.appendChild(dateCell);
            row.appendChild(linkCell);
            recentArticlesBody.appendChild(row);
        });
    } catch (error) {
        console.error("Failed to fetch recent articles:", error);
    }
}

// Fetch and render workspace network graph
async function fetchGraphData() {
    try {
        const response = await fetch(`/api/graph?org=${encodeURIComponent(activeWorkspace)}&limit=${graphLimit}&include_time_tree=${includeTimeTree}`);
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
        currentEdges = edges;
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
    const styledNodes = nodesArray.map((node, index) => {
        let size = 12;
        let font = { color: "#ffffff", size: 12, face: "Outfit" };

        if (node.group === "Organization") {
            size = 22;
            font = { color: "#ffffff", size: 14, bold: true, face: "Outfit" };
        } else if (node.group === "Article") {
            size = 18;
            font = { color: "#e1e7ec", size: 12, face: "Outfit" };
        } else if (node.group === "Year") {
            size = 24;
            font = { color: "#ffffff", size: 13, bold: true, face: "Outfit" };
        } else if (node.group === "Month") {
            size = 20;
            font = { color: "#ffffff", size: 12, bold: true, face: "Outfit" };
        } else if (node.group === "Week") {
            size = 17;
            font = { color: "#ffffff", size: 11, face: "Outfit" };
        } else if (node.group === "Day") {
            size = 15;
            font = { color: "#ffffff", size: 11, face: "Outfit" };
        } else if (node.group === "TimePeriod") {
            size = 14;
            font = { color: "#ffffff", size: 10, face: "Outfit" };
        }

        const extra = {};
        if (nodesArray.length <= 10) {
            // Distribute small nodes in a stable, spaced-out circular pattern centered at (0, 0)
            const angle = (2 * Math.PI * index) / nodesArray.length;
            extra.x = 180 * Math.cos(angle);
            extra.y = 180 * Math.sin(angle);
        }

        return {
            ...node,
            size: size,
            font: font,
            ...extra
        };
    });

    // Declarative label formatters map
    const EDGE_LABEL_FORMATTERS = {
        "INDIRECTLY_INVOLVED_WITH": (w) => w > 1 ? `Indirect Association (${w}x)` : "Indirect Association",
        "CO_OCCURRED_WITH": (w) => `Co-occurred (${w} article${w > 1 ? 's' : ''})`,
        "LOCATED_IN": (w) => w > 1 ? `Located In (${w}x)` : "Located In",
        "MENTIONED_IN": () => "Mentioned In",
        "UNDER_WORKSPACE": () => "Workspace Link",
        "HAS_MONTH": () => "Month",
        "HAS_WEEK": () => "Week",
        "HAS_DAY": () => "Day",
        "HAS_PERIOD": () => "Period",
        "HAS_ARTICLE": () => "Article Link"
    };

    // Map edges to be user-friendly with explicit string IDs, dynamic weights, and visual line thickness
    const styledEdges = edgesArray.map((edge, idx) => {
        const weight = edge.weight || 1;
        const formatter = EDGE_LABEL_FORMATTERS[edge.label];
        const friendlyLabel = formatter ? formatter(weight) : edge.label;
        const width = Math.min(1.5 + (weight - 1) * 1.2, 7);
        const fromId = String(edge.from);
        const toId = String(edge.to);

        return {
            id: edge.id ? String(edge.id) : `e_${fromId}_${toId}_${idx}`,
            ...edge,
            from: fromId,
            to: toId,
            label: friendlyLabel,
            width: width
        };
    });

    // Use DataSet to allow dynamic style updates (highlights/dimming)
    const nodesDataSet = new vis.DataSet(styledNodes);
    const edgesDataSet = new vis.DataSet(styledEdges);

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
                color: "#e1e7ec",
                size: 9,
                face: "Outfit",
                background: "transparent",
                strokeWidth: 0
            },
            smooth: {
                type: "continuous",
                roundness: 0.2
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
            },
            Year: {
                color: {
                    background: "#9ca3af",
                    border: "#4b5563",
                    highlight: { background: "#d1d5db", border: "#9ca3af" }
                }
            },
            Month: {
                color: {
                    background: "#818cf8",
                    border: "#4f46e5",
                    highlight: { background: "#a5b4fc", border: "#818cf8" }
                }
            },
            Week: {
                color: {
                    background: "#38bdf8",
                    border: "#0284c7",
                    highlight: { background: "#7dd3fc", border: "#38bdf8" }
                }
            },
            Day: {
                color: {
                    background: "#34d399",
                    border: "#059669",
                    highlight: { background: "#6ee7b7", border: "#34d399" }
                }
            },
            TimePeriod: {
                color: {
                    background: "#fb923c",
                    border: "#ea580c",
                    highlight: { background: "#fdba74", border: "#fb923c" }
                }
            }
        },
        physics: {
            enabled: nodesArray.length > 10,
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
                enabled: nodesArray.length > 10,
                iterations: 150,
                updateInterval: 25,
                onlyDynamicEdges: false,
                fit: nodesArray.length > 10
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200
        }
    };

    console.log("renderNetwork called with nodes:", nodesArray, "edges:", edgesArray);

    // Recreate canvas element to clean legacy structures
    networkGraphContainer.innerHTML = "";

    try {
        networkInstance = new vis.Network(networkGraphContainer, data, options);
        console.log("vis.Network instance successfully created.");

        // Spotlight Focus Mode: Dim unrelated nodes/edges and show clear entity names at the end of all connected threads
        function applySpotlightFocus(selectedEdgeId, selectedNodeId) {
            let targetNodeIds = new Set();
            let targetEdgeIds = new Set();

            const selNodeStr = selectedNodeId !== null && selectedNodeId !== undefined ? String(selectedNodeId) : null;
            const selEdgeStr = selectedEdgeId !== null && selectedEdgeId !== undefined ? String(selectedEdgeId) : null;

            if (selEdgeStr) {
                targetEdgeIds.add(selEdgeStr);
                const matchingEdge = styledEdges.find(e => String(e.id) === selEdgeStr);
                if (matchingEdge) {
                    targetNodeIds.add(String(matchingEdge.from));
                    targetNodeIds.add(String(matchingEdge.to));
                }
            } else if (selNodeStr) {
                targetNodeIds.add(selNodeStr);
                styledEdges.forEach(edge => {
                    const fromStr = String(edge.from);
                    const toStr = String(edge.to);
                    if (fromStr === selNodeStr || toStr === selNodeStr) {
                        targetEdgeIds.add(String(edge.id));
                        targetNodeIds.add(fromStr);
                        targetNodeIds.add(toStr);
                    }
                });
            }

            if (targetNodeIds.size === 0 && targetEdgeIds.size === 0) {
                resetSpotlightFocus();
                return;
            }

            const updatedNodes = styledNodes.map(node => {
                const nodeIdStr = String(node.id);
                const isFocused = targetNodeIds.has(nodeIdStr);
                const isSelectedSelf = selNodeStr && nodeIdStr === selNodeStr;

                return {
                    id: node.id,
                    opacity: isFocused ? 1.0 : 0.12,
                    font: {
                        color: isFocused ? (isSelectedSelf ? "#00e5ff" : "#ffffff") : "rgba(255, 255, 255, 0.1)",
                        size: isFocused ? 13 : 9,
                        face: "Outfit",
                        bold: true,
                        strokeWidth: isFocused ? 4 : 0,
                        strokeColor: "#0a0b10"
                    }
                };
            });

            const updatedEdges = styledEdges.map(edge => {
                const edgeIdStr = String(edge.id);
                const isFocused = targetEdgeIds.has(edgeIdStr);
                return {
                    id: edge.id,
                    color: isFocused ? { color: "#00e5ff", highlight: "#00e5ff" } : { color: "rgba(255, 255, 255, 0.03)" },
                    width: isFocused ? 4 : 1,
                    font: {
                        color: isFocused ? "#80f2ff" : "transparent",
                        size: isFocused ? 12 : 0,
                        face: "Outfit",
                        background: isFocused ? "#101324" : "transparent"
                    }
                };
            });

            nodesDataSet.update(updatedNodes);
            edgesDataSet.update(updatedEdges);
        }

        function resetSpotlightFocus() {
            nodesDataSet.update(styledNodes);
            edgesDataSet.update(styledEdges);
        }

        // Setup Hover and Select Events
        networkInstance.on("hoverEdge", (params) => {
            const edgeId = params.edge;
            const edgeData = edgesDataSet.get(edgeId);
            if (edgeData && edgeData.context) {
                showGraphInfoBox(edgeData);
            }
        });

        networkInstance.on("blurEdge", () => {
            hideGraphInfoBox();
        });

        networkInstance.on("selectEdge", (params) => {
            const edgeId = params.edges[0];
            if (edgeId) {
                applySpotlightFocus(edgeId, null);
                const edgeData = edgesDataSet.get(edgeId);
                if (edgeData && edgeData.context) {
                    showGraphInfoBox(edgeData);
                }
            }
        });

        networkInstance.on("hoverNode", (params) => {
            const nodeId = params.node;
            const nodeData = nodesDataSet.get(nodeId);
            if (nodeData && (nodeData.group === "Company" || nodeData.group === "Organization")) {
                showCompanyStockMenu(nodeData.label);
            }
        });

        networkInstance.on("selectNode", (params) => {
            const nodeId = params.nodes[0];
            if (nodeId) {
                applySpotlightFocus(null, nodeId);
                const nodeData = nodesDataSet.get(nodeId);
                if (nodeData && (nodeData.group === "Company" || nodeData.group === "Organization")) {
                    showCompanyStockMenu(nodeData.label);
                }
            }
        });

        networkInstance.on("click", (params) => {
            if (params.nodes.length === 0 && params.edges.length === 0) {
                resetSpotlightFocus();
                hideGraphInfoBox();
                hideCompanyStockMenu();
            }
        });
    } catch (err) {
        console.error("Error creating vis.Network instance:", err);
        networkGraphContainer.innerHTML = `
            <div class="graph-placeholder" style="color: var(--error);">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <p>Error rendering network graph: ${err.message}</p>
            </div>
        `;
        return;
    }

    if (nodesArray.length > 10) {
        const disablePhysicsCallback = function () {
            console.log("Graph stabilization finished. Node count:", nodesArray.length);
            if (networkInstance) {
                networkInstance.setOptions({ physics: { enabled: false } });
            }
            physicsEnabled = false;
            if (togglePhysicsBtn) {
                togglePhysicsBtn.classList.remove("active");
            }
            console.log("Physics disabled to prevent performance lag on large graph.");
        };

        networkInstance.on("stabilized", disablePhysicsCallback);
        networkInstance.on("stabilizationIterationsDone", disablePhysicsCallback);
    } else {
        physicsEnabled = false;
        if (togglePhysicsBtn) {
            togglePhysicsBtn.classList.remove("active");
        }
        console.log("Physics disabled by default for small static graph.");
    }

    // Center camera at (0,0) at scale 1.0 for small node counts to guarantee they are visible and centered
    if (nodesArray.length > 0 && nodesArray.length <= 10) {
        setTimeout(() => {
            if (networkInstance) {
                console.log("Applying manual moveTo fallback for small graph...");
                networkInstance.moveTo({
                    position: { x: 0, y: 0 },
                    scale: 1.0,
                    animation: {
                        duration: 500,
                        easingFunction: "easeInOutQuad"
                    }
                });
            }
        }, 200);
    }

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
        }, 4000);

        setTimeout(() => {
            updateDashboardData();
        }, 8000);

        setTimeout(() => {
            updateDashboardData();
        }, 13000);

        setTimeout(() => {
            updateDashboardData();
            // Reset loader status
            textEl.textContent = "Scraping web article content...";
            scraperStatus.classList.add("hidden");
            scraperStatus.style.borderColor = "var(--border-color)";
            scrapeSubmitBtn.disabled = false;
        }, 18000);

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
        const response = await fetch(`/api/path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&org=${encodeURIComponent(activeWorkspace)}`);
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

        // Generate and display the human-readable narrative trail explanation
        showPathNarrative(pathData.nodes, pathData.edges, source, target);

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
    const explanationDiv = document.getElementById("pathfinderExplanation");
    if (explanationDiv) explanationDiv.classList.add("hidden");
    updateDashboardData();
}

// Reconstruct path sequence and build human-readable narrative trail
function showPathNarrative(nodes, edges, sourceName, targetName) {
    const explanationDiv = document.getElementById("pathfinderExplanation");
    const stepsContainer = document.getElementById("pathfinderExplanationSteps");
    if (!explanationDiv || !stepsContainer) return;

    stepsContainer.innerHTML = "";
    const steps = reconstructPathSteps(nodes, edges, sourceName, targetName);

    if (steps.length === 0) {
        explanationDiv.classList.add("hidden");
        return;
    }

    steps.forEach(step => {
        const stepEl = document.createElement("div");
        stepEl.className = "explanation-step-container";

        const textEl = document.createElement("div");
        textEl.className = "explanation-step";
        textEl.innerHTML = getFriendlyRelationText(step);
        stepEl.appendChild(textEl);

        if (step.affected_companies && step.affected_companies.length > 0) {
            const compEl = document.createElement("div");
            compEl.className = "explanation-affected-companies";
            compEl.innerHTML = `<i class="fa-solid fa-building-circle-exclamation"></i> <strong>Affected Companies:</strong> ` +
                step.affected_companies.map(c => `<span class="company-tag">${c}</span>`).join(" ");
            stepEl.appendChild(compEl);
        }

        if (step.full_context) {
            const contextEl = document.createElement("div");
            contextEl.className = "explanation-context";
            contextEl.innerHTML = `<i class="fa-solid fa-quote-left"></i> "${step.full_context}"`;
            stepEl.appendChild(contextEl);
        }

        stepsContainer.appendChild(stepEl);
    });

    explanationDiv.classList.remove("hidden");
}

function reconstructPathSteps(nodesArray, edgesArray, sourceName, targetName) {
    const nodeMap = new Map();
    nodesArray.forEach(n => {
        nodeMap.set(n.id, n);
    });

    let sourceNode = nodesArray.find(n => n.label === sourceName);
    let targetNode = nodesArray.find(n => n.label === targetName);

    if (!sourceNode || !targetNode) {
        sourceNode = nodesArray.find(n => n.label.toLowerCase() === sourceName.toLowerCase());
        targetNode = nodesArray.find(n => n.label.toLowerCase() === targetName.toLowerCase());
    }

    if (!sourceNode || !targetNode) return [];

    const steps = [];
    let currentNode = sourceNode;
    const visitedNodeIds = new Set([currentNode.id]);

    while (currentNode.id !== targetNode.id) {
        let nextEdge = null;
        let nextNode = null;
        let direction = "";

        for (const edge of edgesArray) {
            if (edge.from === currentNode.id && nodeMap.has(edge.to) && !visitedNodeIds.has(edge.to)) {
                nextEdge = edge;
                nextNode = nodeMap.get(edge.to);
                direction = "forward";
                break;
            } else if (edge.to === currentNode.id && nodeMap.has(edge.from) && !visitedNodeIds.has(edge.from)) {
                nextEdge = edge;
                nextNode = nodeMap.get(edge.from);
                direction = "backward";
                break;
            }
        }

        if (!nextEdge || !nextNode) {
            break;
        }

        const comps = nextEdge.affected_companies || nextNode.affected_companies || currentNode.affected_companies || [];

        steps.push({
            from: currentNode,
            to: nextNode,
            relation: nextEdge.label,
            direction: direction,
            context: nextEdge.context || "",
            full_context: nextEdge.full_context || "",
            affected_companies: comps
        });

        visitedNodeIds.add(nextNode.id);
        currentNode = nextNode;
    }

    return steps;
}

function getFriendlyRelationText(step) {
    const fromLabel = `<span class="badge badge-${step.from.group.toLowerCase()}">${step.from.label}</span>`;
    const toLabel = `<span class="badge badge-${step.to.group.toLowerCase()}">${step.to.label}</span>`;

    const rel = step.relation;
    const isForward = step.direction === "forward";

    if (rel === "MENTIONED_IN") {
        return isForward
            ? `${fromLabel} is mentioned in the article ${toLabel}`
            : `the article ${fromLabel} mentions ${toLabel}`;
    }
    if (rel === "INDIRECTLY_INVOLVED_WITH") {
        return isForward
            ? `${fromLabel} is indirectly involved with ${toLabel}`
            : `${fromLabel} is indirectly associated with ${toLabel}`;
    }
    if (rel === "LOCATED_IN") {
        return isForward
            ? `${fromLabel} is located in ${toLabel}`
            : `${fromLabel} houses ${toLabel}`;
    }
    if (rel === "UNDER_WORKSPACE") {
        return isForward
            ? `the article ${fromLabel} is filed under workspace ${toLabel}`
            : `the workspace ${fromLabel} contains article ${toLabel}`;
    }

    return isForward
        ? `${fromLabel} is linked to ${toLabel} via <span class="relation-code">${rel}</span>`
        : `${fromLabel} is linked from ${toLabel} via <span class="relation-code">${rel}</span>`;
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

    const maxRows = 100;
    const displayEdges = edges.slice(0, maxRows);

    // Create a lookup map for node data
    const nodeMap = new Map();
    nodes.forEach(node => {
        nodeMap.set(node.id, node);
    });

    displayEdges.forEach(edge => {
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

    if (edges.length > maxRows) {
        const row = document.createElement("tr");
        row.innerHTML = `<td colspan="3" class="empty-state" style="font-size: 0.85rem; color: var(--text-muted);">... and ${edges.length - maxRows} more connections</td>`;
        connectionsTableBody.appendChild(row);
    }
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

    refreshCustomSelect(pathSourceSelect);
    refreshCustomSelect(pathTargetSelect);
}

// Show details inside the floating graph overlay box on hover/select
function showGraphInfoBox(edgeData) {
    const infoBox = document.getElementById("graphInfoBox");
    const infoBoxBody = document.getElementById("graphInfoBoxBody");
    if (!infoBox || !infoBoxBody) return;

    const fromNode = currentNodes.find(n => n.id === edgeData.from);
    const toNode = currentNodes.find(n => n.id === edgeData.to);
    if (!fromNode || !toNode) return;

    // Map edge label to friendly name
    let friendlyLabel = edgeData.label;
    if (friendlyLabel === "INDIRECTLY_INVOLVED_WITH") {
        friendlyLabel = "Indirect Association";
    } else if (friendlyLabel === "MENTIONED_IN") {
        friendlyLabel = "Mentioned In";
    } else if (friendlyLabel === "LOCATED_IN") {
        friendlyLabel = "Located In";
    } else if (friendlyLabel === "UNDER_WORKSPACE") {
        friendlyLabel = "Workspace Link";
    }

    const step = {
        from: fromNode,
        to: toNode,
        relation: friendlyLabel,
        direction: "forward"
    };

    const friendlyHtml = getFriendlyRelationText(step);

    let htmlContent = `
        <div class="info-box-step">${friendlyHtml}</div>
    `;

    if (edgeData.context) {
        htmlContent += `
            <div class="info-box-quote"><i class="fa-solid fa-quote-left"></i> "${edgeData.context}"</div>
        `;
    }

    infoBoxBody.innerHTML = htmlContent;
    infoBox.classList.add("visible");
}

function hideGraphInfoBox() {
    const infoBox = document.getElementById("graphInfoBox");
    if (infoBox) {
        infoBox.classList.remove("visible");
    }
}

let activeCompanyFinancialsCache = {};

async function showCompanyStockMenu(companyName) {
    const stockMenu = document.getElementById("companyStockMenu");
    if (!stockMenu || !companyName) return;

    const companyNameEl = document.getElementById("stockMenuCompanyName");
    const tickerEl = document.getElementById("stockMenuTicker");
    const priceEl = document.getElementById("stockMenuPrice");
    const changeEl = document.getElementById("stockMenuChange");
    const subtextEl = document.getElementById("stockMenuSubtext");

    const posPctEl = document.getElementById("stockMenuPosPct");
    const neuPctEl = document.getElementById("stockMenuNeuPct");
    const negPctEl = document.getElementById("stockMenuNegPct");

    const barPos = document.getElementById("sentBarPos");
    const barNeu = document.getElementById("sentBarNeu");
    const barNeg = document.getElementById("sentBarNeg");

    const articlesListEl = document.getElementById("stockMenuArticlesList");

    companyNameEl.textContent = companyName;
    tickerEl.textContent = "...";
    priceEl.textContent = "Loading...";
    changeEl.textContent = "--";
    changeEl.className = "stock-change-pill";
    subtextEl.textContent = "Fetching Market Quote & News Sentiment...";

    articlesListEl.innerHTML = `<div class="empty-news-text"><i class="fa-solid fa-spinner fa-spin"></i> Fetching news sentiment...</div>`;
    stockMenu.classList.remove("hidden");

    try {
        const cacheKey = `${companyName}_${activeWorkspace}`;
        let data = activeCompanyFinancialsCache[cacheKey];
        if (!data) {
            const res = await fetch(`/api/company-financials?company=${encodeURIComponent(companyName)}&org=${encodeURIComponent(activeWorkspace)}`);
            data = await res.json();
            activeCompanyFinancialsCache[cacheKey] = data;
        }

        const quote = data.stock_quote || {};
        const sent = data.sentiment_summary || {};
        const articles = data.articles || [];

        if (quote.is_public && quote.current_price !== undefined) {
            tickerEl.textContent = quote.ticker || "US";
            priceEl.textContent = quote.formatted_price || `$${quote.current_price}`;
            changeEl.textContent = quote.formatted_change || "--";
            changeEl.className = `stock-change-pill ${quote.is_up ? 'up' : 'down'}`;
            subtextEl.textContent = "USD • Real-Time Market Quote";
        } else if (quote.ticker) {
            tickerEl.textContent = quote.ticker;
            priceEl.textContent = "USD Quote N/A";
            changeEl.textContent = quote.message || "Unlisted";
            changeEl.className = "stock-change-pill unlisted";
            subtextEl.textContent = "USD • Financial Quote Unavailable";
        } else {
            tickerEl.textContent = "PRIVATE";
            priceEl.textContent = "Private Entity";
            changeEl.textContent = "Unlisted";
            changeEl.className = "stock-change-pill unlisted";
            subtextEl.textContent = "Entity not publicly traded on stock exchanges";
        }

        // Render Sentiment Bar
        const posP = sent.positive_pct || 0;
        const neuP = sent.neutral_pct || (sent.total_articles ? 0 : 100);
        const negP = sent.negative_pct || 0;

        barPos.style.width = `${posP}%`;
        barNeu.style.width = `${neuP}%`;
        barNeg.style.width = `${negP}%`;

        posPctEl.textContent = `${posP}%`;
        neuPctEl.textContent = `${neuP}%`;
        negPctEl.textContent = `${negP}%`;

        // Render Related News Links
        if (articles.length === 0) {
            articlesListEl.innerHTML = `<div class="empty-news-text">No related news articles found in workspace.</div>`;
        } else {
            let html = "";
            articles.forEach(art => {
                const targetUrl = art.url || "#";
                const sentimentIcon = art.sentiment === "Positive" ? '<i class="fa-solid fa-face-smile" style="color:#22c55e;"></i>' : (art.sentiment === "Negative" ? '<i class="fa-solid fa-face-frown" style="color:#ef4444;"></i>' : '<i class="fa-solid fa-face-meh" style="color:#64748b;"></i>');
                html += `
                    <div class="stock-article-item">
                        <a href="${targetUrl}" target="_blank" rel="noopener noreferrer" class="stock-article-title" title="${art.title}">
                            ${sentimentIcon} ${art.title}
                        </a>
                        ${art.url ? `<a href="${art.url}" target="_blank" rel="noopener noreferrer" class="stock-article-link-icon"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ''}
                    </div>
                `;
            });
            articlesListEl.innerHTML = html;
        }

    } catch (err) {
        console.error("Failed to load company financials:", err);
        priceEl.textContent = "Error";
        subtextEl.textContent = "Failed to load financial & news sentiment metrics.";
    }
}

function hideCompanyStockMenu() {
    const stockMenu = document.getElementById("companyStockMenu");
    if (stockMenu) {
        stockMenu.classList.add("hidden");
    }
}

async function handleGoogleNewsTrigger() {
    const triggerBtn = document.getElementById("googleNewsTriggerBtn");
    const statusDiv = document.getElementById("googleNewsStatus");
    if (!triggerBtn || !statusDiv) return;

    triggerBtn.disabled = true;
    statusDiv.classList.remove("hidden");

    try {
        const response = await fetch("/api/cron/google-news", {
            method: "POST"
        });

        if (!response.ok) {
            throw new Error("Failed to trigger Google News ingestion.");
        }

        const data = await response.json();
        const textEl = statusDiv.querySelector(".status-text");
        textEl.textContent = "Sync started in background! Preparing workspaces...";
        statusDiv.style.borderColor = "var(--success)";

        // Refresh list of workspaces and select Google News if present
        setTimeout(() => {
            loadWorkspaces().then(() => {
                let exists = false;
                for (let i = 0; i < workspaceSelect.options.length; i++) {
                    if (workspaceSelect.options[i].value === "Google News") {
                        exists = true;
                        workspaceSelect.selectedIndex = i;
                        activeWorkspace = "Google News";
                        break;
                    }
                }
                updateDashboardData();
            });
        }, 3000);

        // Keep updating data as ingestion runs in background
        setTimeout(() => {
            updateDashboardData();
        }, 8000);

        setTimeout(() => {
            updateDashboardData();
        }, 15000);

        setTimeout(() => {
            updateDashboardData();
        }, 22000);

        setTimeout(() => {
            updateDashboardData();
        }, 3000);

        setTimeout(() => {
            updateDashboardData();
            statusDiv.classList.add("hidden");
            statusDiv.style.borderColor = "var(--border-color)";
            textEl.textContent = "Scraping & processing Google News...";
            triggerBtn.disabled = false;
        }, 35000);

    } catch (error) {
        console.error("Google News Sync failed:", error);
        alert(`Failed to sync Google News: ${error.message}`);
        statusDiv.classList.add("hidden");
        triggerBtn.disabled = false;
    }
}

function getCategoryClass(category) {
    if (!category) return "badge-general";
    const cat = category.toLowerCase();
    if (cat === "technology" || cat === "tech") return "badge-tech";
    if (cat === "finance") return "badge-finance";
    if (cat === "geopolitics") return "badge-geopolitics";
    if (cat === "defense") return "badge-defense";
    if (cat === "healthcare") return "badge-healthcare";
    return "badge-general";
}

function getSentimentClass(sentiment) {
    if (!sentiment) return "badge-neutral";
    const sent = sentiment.toLowerCase();
    if (sent === "positive") return "badge-positive";
    if (sent === "negative") return "badge-negative";
    return "badge-neutral";
}

// Universal Custom Select Component Builder with Search Support (Bypasses Windows Native White Popups)
function initCustomSelect(selectEl) {
    if (!selectEl) return;
    
    if (selectEl.dataset.customInitialized) {
        refreshCustomSelect(selectEl);
        return;
    }
    selectEl.dataset.customInitialized = "true";

    const parent = selectEl.parentElement;
    if (parent) {
        parent.classList.add("custom-active-wrapper");
    }

    selectEl.style.setProperty("display", "none", "important");
    selectEl.style.setProperty("pointer-events", "none", "important");
    selectEl.tabIndex = -1;

    const isLimit = selectEl.id === "graphLimitSelect";
    const isPathfinder = selectEl.classList.contains("pathfinder-select");

    const container = document.createElement("div");
    container.className = `custom-select-container ${isLimit ? "limit-dropdown" : ""} ${isPathfinder ? "pathfinder-dropdown" : ""}`;
    container.id = `${selectEl.id}_customContainer`;

    const trigger = document.createElement("div");
    trigger.className = "custom-select-trigger";
    
    const iconI = parent ? parent.querySelector("i") : null;
    let iconHtml = "";
    if (iconI && iconI.parentElement === parent) {
        iconHtml = iconI.outerHTML;
        iconI.style.display = "none";
    }

    trigger.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem; overflow: hidden; width: 100%;">
            ${iconHtml}
            <span class="trigger-text" style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"></span>
        </div>
        <i class="fa-solid fa-chevron-down chevron"></i>
    `;

    const optionsMenu = document.createElement("div");
    optionsMenu.className = "custom-select-options";

    // Sticky search box for Pathfinder selects
    let searchInput = null;
    if (isPathfinder) {
        const searchBox = document.createElement("div");
        searchBox.className = "custom-select-search";
        searchBox.innerHTML = `
            <i class="fa-solid fa-magnifying-glass"></i>
            <input type="text" class="custom-search-input" placeholder="Search entity..." autocomplete="off">
        `;
        searchInput = searchBox.querySelector("input");
        searchBox.addEventListener("click", (e) => e.stopPropagation());
        
        searchInput.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            const optionItems = optionsListContainer.querySelectorAll(".custom-option");
            let hasVisible = false;

            optionItems.forEach(item => {
                const text = item.textContent.toLowerCase();
                if (!query || text.includes(query)) {
                    item.style.display = "flex";
                    hasVisible = true;
                } else {
                    item.style.display = "none";
                }
            });

            let noRes = optionsListContainer.querySelector(".custom-no-results");
            if (!hasVisible) {
                if (!noRes) {
                    noRes = document.createElement("div");
                    noRes.className = "custom-no-results";
                    noRes.textContent = "No entities found";
                    optionsListContainer.appendChild(noRes);
                }
                noRes.style.display = "block";
            } else if (noRes) {
                noRes.style.display = "none";
            }
        });

        optionsMenu.appendChild(searchBox);
    }

    const optionsListContainer = document.createElement("div");
    optionsListContainer.className = "custom-options-list";
    optionsMenu.appendChild(optionsListContainer);

    container.appendChild(trigger);
    container.appendChild(optionsMenu);

    if (parent) {
        parent.appendChild(container);
    }

    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const isOpen = container.classList.contains("open");
        document.querySelectorAll(".custom-select-container.open").forEach(c => {
            c.classList.remove("open");
            if (c.parentElement) c.parentElement.style.zIndex = "";
        });

        if (!isOpen) {
            container.classList.add("open");
            if (parent) parent.style.zIndex = "100000";
        } else {
            if (parent) parent.style.zIndex = "";
        }

        if (!isOpen && searchInput) {
            setTimeout(() => {
                searchInput.value = "";
                searchInput.dispatchEvent(new Event("input"));
                searchInput.focus();
            }, 50);
        }
    });

    document.addEventListener("click", (e) => {
        if (!container.contains(e.target)) {
            container.classList.remove("open");
            if (parent) parent.style.zIndex = "";
        }
    });

    function syncOptions() {
        optionsListContainer.innerHTML = "";
        const triggerText = trigger.querySelector(".trigger-text");
        
        const selectedOpt = selectEl.options[selectEl.selectedIndex] || selectEl.options[0];
        if (triggerText && selectedOpt) {
            triggerText.textContent = selectedOpt.textContent;
        }

        Array.from(selectEl.options).forEach((opt, idx) => {
            if (opt.disabled && !opt.value) return;

            const item = document.createElement("div");
            item.className = `custom-option ${opt.selected ? "selected" : ""}`;
            item.textContent = opt.textContent;

            item.addEventListener("click", (e) => {
                e.stopPropagation();
                selectEl.selectedIndex = idx;
                selectEl.value = opt.value;
                if (triggerText) triggerText.textContent = opt.textContent;
                
                optionsListContainer.querySelectorAll(".custom-option").forEach(o => o.classList.remove("selected"));
                item.classList.add("selected");
                
                container.classList.remove("open");
                selectEl.dispatchEvent(new Event("change"));
            });

            optionsListContainer.appendChild(item);
        });
    }

    syncOptions();
    selectEl._syncCustomOptions = syncOptions;
}

function refreshCustomSelect(selectEl) {
    if (selectEl && typeof selectEl._syncCustomOptions === "function") {
        selectEl._syncCustomOptions();
    }
}

