// Global Application State
let activeWorkspace = "Default";
let networkInstance = null;
let physicsEnabled = true;

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
const networkGraphContainer = document.getElementById("networkGraphContainer");
const togglePhysicsBtn = document.getElementById("togglePhysicsBtn");
const resetGraphBtn = document.getElementById("resetGraphBtn");

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
            return;
        }

        renderNetwork(nodes, edges);
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

    const data = {
        nodes: new vis.DataSet(styledNodes),
        edges: new vis.DataSet(edgesArray)
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
            }
        },
        physics: {
            enabled: physicsEnabled,
            solver: "forceAtlas2Based",
            forceAtlas2Based: {
                gravitationalConstant: -35,
                centralGravity: 0.015,
                springLength: 80,
                springConstant: 0.08
            },
            stabilization: {
                iterations: 120,
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
