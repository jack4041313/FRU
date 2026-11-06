// Selected gNB is managed here (not in an inline HTML script).
let selectedGNBIP = null;
let configuredGNBIPs = [];


// Throughput and RU Log share the same Select RU selection.
let selectedRU = 1;
let currentRuConfig = {ru_count: 1, cc_per_ru: 3};
let ruSelectionVersion = 0;
function clearThroughputCharts() {
    [cell0DlChart, cell0UlChart, cell1DlChart, cell2DlChart].forEach(chart => {
        chart.data.labels = [];
        chart.data.datasets[0].data = [];
        chart.update();
    });
}
function renderRUButtons() {
    const group = document.getElementById("ruButtonGroup");
    if (!group) return;
    group.replaceChildren();
    for (let ru = 1; ru <= currentRuConfig.ru_count; ru++) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `btn btn-sm ${ru === selectedRU ? "btn-primary active" : "btn-outline-primary"}`;
        button.textContent = `RU-${ru}`;
        button.addEventListener("click", () => {
            selectedRU = ru;
            ruSelectionVersion++;
            renderRUButtons();
            clearThroughputCharts();
            updateThroughput();
            updateRuLog();
        });
        group.appendChild(button);
    }
    document.getElementById("cc1Card").hidden = currentRuConfig.cc_per_ru < 2;
    document.getElementById("cc2Card").hidden = currentRuConfig.cc_per_ru < 3;
    // Only global Cell 0 supports the existing UL chart.
    const ulCell = (selectedRU - 1) * currentRuConfig.cc_per_ru;
    document.getElementById("cell0UlChart").closest(".card").hidden = ulCell > 2;
    for (const cc of [0, 1, 2]) {
        const cellId = (selectedRU - 1) * currentRuConfig.cc_per_ru + cc;
        for (const mode of ["DL", "UL"]) {
            const title = document.getElementById(`cell${cc}${mode}Title`);
            if (title) title.textContent = `RU-${selectedRU} / Cell-${cellId} ${mode} Throughput`;
        }
    }
}
async function loadRUConfig() {
    if (!selectedGNBIP) return;
    const ip = selectedGNBIP;
    const response = await fetch(`/api/ru-config?ip=${encodeURIComponent(ip)}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const config = await response.json();
    if (ip !== selectedGNBIP) return;
    currentRuConfig = config;
    selectedRU = 1;
    ruSelectionVersion++;
    document.getElementById("ruCount").value = String(config.ru_count);
    document.getElementById("ccPerRu").value = String(config.cc_per_ru);
    renderRUButtons();
    clearThroughputCharts();
    updateThroughput();
    updateRuLog();
}
document.getElementById("saveRuConfig").addEventListener("click", async () => {
    if (!selectedGNBIP) return;
    const ip = selectedGNBIP;
    const button = document.getElementById("saveRuConfig");
    const message = document.getElementById("ruConfigMessage");
    button.disabled = true;
    message.textContent = "";
    try {
        const response = await fetch(`/api/ru-config?ip=${encodeURIComponent(ip)}`, {
            method: "PUT", headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                ru_count: Number(document.getElementById("ruCount").value),
                cc_per_ru: Number(document.getElementById("ccPerRu").value)
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        if (ip === selectedGNBIP) {
            currentRuConfig = data;
            selectedRU = 1;
            ruSelectionVersion++;
            renderRUButtons();
                    clearThroughputCharts();
            updateThroughput();
            updateRuLog();
        }
    } catch (error) { message.textContent = `Save failed: ${error.message}`; }
    finally { button.disabled = false; }
});

function renderGNBButtons() {
    const group = document.getElementById("gnbButtonGroup");
    group.replaceChildren();
    configuredGNBIPs.forEach(ip => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.gnbIp = ip;
        button.textContent = ip;
        const active = ip === selectedGNBIP;
        button.className = `btn ${active ? "btn-primary active" : "btn-outline-primary"}`;
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.addEventListener("click", () => selectGNB(ip));
        group.appendChild(button);
        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "btn btn-outline-danger";
        removeButton.textContent = "×";
        removeButton.title = `Stop monitoring and remove ${ip}`;
        removeButton.setAttribute("aria-label", `Remove ${ip}`);
        removeButton.addEventListener("click", () => removeGNB(ip));
        group.appendChild(removeButton);
    });
}

async function loadGNBs() {
    try {
        const response = await fetch("/api/gnbs");
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        configuredGNBIPs = data.gnbs || [];
        if (!configuredGNBIPs.includes(selectedGNBIP)) {
            selectedGNBIP = configuredGNBIPs[0] || null;
        }
        renderGNBButtons();
        if (selectedGNBIP) selectGNB(selectedGNBIP);
    } catch (error) {
        document.getElementById("gnbAddMessage").textContent = `Unable to load gNB list: ${error.message}`;
        console.error("[gNB] Load failed:", error);
    }
}

async function removeGNB(ip) {
    if (!window.confirm(`Stop all monitors and disconnect SSH for ${ip}?`)) return;
    const message = document.getElementById("gnbAddMessage");
    message.textContent = `Stopping ${ip}...`;
    try {
        const response = await fetch(`/api/gnbs/${encodeURIComponent(ip)}`, {method: "DELETE"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        configuredGNBIPs = configuredGNBIPs.filter(item => item !== ip);
        if (selectedGNBIP === ip) {
            selectedGNBIP = null;
            if (configuredGNBIPs.length) {
                selectGNB(configuredGNBIPs[0]);
            } else {
                document.getElementById("dashboardTitle").textContent = "gNB Dashboard";
                document.title = "gNB Dashboard";
                document.getElementById("status").textContent = "No gNB selected";
                document.getElementById("status").className = "badge bg-secondary";
                document.getElementById("reconnectGnbButton").disabled = true;
                document.getElementById("netconfConsole").textContent = "No gNB selected";
                document.getElementById("rumanagerConsole").textContent = "No gNB selected";
                document.getElementById("l1Uptime").textContent = "Unknown";
                const ruLog = document.getElementById("ruLogConsole");
                if (ruLog) ruLog.textContent = "No gNB selected";
            }
        }
        renderGNBButtons();
        message.textContent = `${ip}: monitoring stopped and removed.`;
    } catch (error) {
        message.textContent = `Remove failed: ${error.message}`;
    }
}

async function addGNB(event) {
    event.preventDefault();
    const input = document.getElementById("gnbIpInput");
    const message = document.getElementById("gnbAddMessage");
    const button = document.getElementById("addGnbButton");
    const ip = input.value.trim();
    button.disabled = true;
    message.textContent = `Adding ${ip}...`;
    try {
        const response = await fetch("/api/gnbs", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ip})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        if (!configuredGNBIPs.includes(data.ip)) configuredGNBIPs.push(data.ip);
        renderGNBButtons();
        selectGNB(data.ip);
        message.textContent = data.added
            ? `${data.ip} added. Connecting over SSH...`
            : `${data.ip} already exists (connection retry requested if needed).`;
        input.value = "";
    } catch (error) {
        message.textContent = `Add gNB failed: ${error.message}`;
    } finally {
        button.disabled = false;
    }
}

document.getElementById("addGnbForm").addEventListener("submit", addGNB);

// Default time range
let range = "10m";

//=============================
// Chart Creator
//=============================

function createChart(
    element,
    label,
    color,
    bgColor
) {

    return new Chart(
        document.getElementById(element),
        {

            type: "line",

            data: {

                labels: [],

                datasets: [

                    {
                        label: label,

                        data: [],

                        borderColor: color,

                        backgroundColor: bgColor,

                        tension: 0.3,

                        fill: true
                    }

                ]

            },

            options: {

                responsive: true,

                maintainAspectRatio: false

            }

        }
    );

}


//=============================
// Charts
//=============================


//=====================================
// Cell-0 DL
//=====================================

const cell0DlChart =
    createChart(
        "cell0DlChart",
        "Cell-0 DL Throughput (Mbps)",
        "#38bdf8",
        "rgba(56,189,248,0.15)"
    );


//=====================================
// Cell-0 UL
//=====================================

const cell0UlChart =
    createChart(
        "cell0UlChart",
        "Cell-0 UL Throughput (Mbps)",
        "#22c55e",
        "rgba(34,197,94,0.15)"
    );


//=====================================
// Cell-1 DL
//=====================================

const cell1DlChart =
    createChart(
        "cell1DlChart",
        "Cell-1 DL Throughput (Mbps)",
        "#f59e0b",
        "rgba(245,158,11,0.15)"
    );


//=====================================
// Cell-2 DL
//=====================================

const cell2DlChart =
    createChart(
        "cell2DlChart",
        "Cell-2 DL Throughput (Mbps)",
        "#a855f7",
        "rgba(168,85,247,0.15)"
    );


//=====================================
// Update Chart Function
//=====================================

function updateChart(
    chart,
    data
) {

    if (!data)
        return;


    chart.data.labels =
        data.map(
            x => x.time
        );


    chart.data.datasets[0].data =
        data.map(
            x => x.value
        );


    chart.update();

}


//=====================================
// Update Throughput
//=====================================

async function updateThroughput() {
    if (!selectedGNBIP) return;
    const ip = selectedGNBIP;
    const ru = selectedRU;
    const version = ruSelectionVersion;
    try {
        const response = await fetch(`/api/throughput?ip=${encodeURIComponent(ip)}&ru=${ru}&range=${encodeURIComponent(range)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (ip !== selectedGNBIP || ru !== selectedRU || version !== ruSelectionVersion) return;
        const charts = [cell0DlChart, cell1DlChart, cell2DlChart];
        for (let cc = 0; cc < 3; cc++) {
            const cell = data.cells.find(item => item.cc === cc);
            updateChart(charts[cc], cell ? cell.dl : []);
            if (cc === 0) updateChart(cell0UlChart, cell ? cell.ul : []);
        }
    } catch (error) { if (ip === selectedGNBIP) console.error("Failed to get throughput:", error); }
}

//=====================================
// Time Range
//=====================================

document
    .getElementById("timeRange")
    .addEventListener(
        "change",
        function () {

            range = this.value;

            updateThroughput();

        }
    );


//=====================================
// Initial Throughput Load
//=====================================

updateThroughput();


//=====================================
// Throughput Refresh
//=====================================

setInterval(
    updateThroughput,
    5000
);


//=====================================
// Update Logs
//=====================================

function updateLogs() {
    if (!selectedGNBIP) return;

     fetch(`/api/logs?ip=${encodeURIComponent(selectedGNBIP)}`)

        .then(
            response => {

                if (!response.ok) {

                    throw new Error(
                        `HTTP error: ${response.status}`
                    );

                }

                return response.json();

            }
        )

        .then(
            data => {

                console.log(
                    "LOG DATA:",
                    data
                );


                //=====================================
                // Netconf Server
                //=====================================

                const netconfConsole =
                    document.getElementById(
                        "netconfConsole"
                    );


                if (netconfConsole) {

                    //=================================
                    // Check whether user is already
                    // near the bottom
                    //=================================

                    const netconfAtBottom =
                        netconfConsole.scrollHeight -
                        netconfConsole.scrollTop -
                        netconfConsole.clientHeight <
                        50;


                    //=================================
                    // Update Netconf log
                    //=================================

                    if (
                        data.netconf !== undefined &&
                        data.netconf !== null
                    ) {

                        netconfConsole.textContent =
                            data.netconf;

                    }

                    else {

                        netconfConsole.textContent =
                            "No netconf log data";

                    }


                    //=================================
                    // Auto scroll Netconf
                    //
                    // Only scroll if user was already
                    // near the bottom
                    //=================================

                    if (netconfAtBottom) {

                        netconfConsole.scrollTop =
                            netconfConsole.scrollHeight;

                    }

                }

                else {

                    console.error(
                        "netconfConsole element not found"
                    );

                }


                //=====================================
                // RU Manager
                //=====================================

                const rumanagerConsole =
                    document.getElementById(
                        "rumanagerConsole"
                    );


                if (rumanagerConsole) {

                    //=================================
                    // Check whether user is already
                    // near the bottom
                    //=================================

                    const rumanagerAtBottom =
                        rumanagerConsole.scrollHeight -
                        rumanagerConsole.scrollTop -
                        rumanagerConsole.clientHeight <
                        50;


                    //=================================
                    // Update RU Manager log
                    //=================================

                    if (
                        data.rumanager !== undefined &&
                        data.rumanager !== null
                    ) {

                        rumanagerConsole.textContent =
                            data.rumanager;

                    }

                    else {

                        rumanagerConsole.textContent =
                            "No RU Manager log data";

                    }


                    //=================================
                    // Auto scroll RU Manager
                    //
                    // Only scroll if user was already
                    // near the bottom
                    //=================================

                    if (rumanagerAtBottom) {

                        rumanagerConsole.scrollTop =
                            rumanagerConsole.scrollHeight;

                    }

                }

                else {

                    console.error(
                        "rumanagerConsole element not found"
                    );

                }

            }
        )

        .catch(
            error => {

                console.error(
                    "Failed to get logs:",
                    error
                );

            }
        );

}

//=====================================
// selectGNB
//=====================================
function selectGNB(ip) {

    selectedGNBIP = ip;

    document.getElementById("dashboardTitle").textContent =
        ip + " Dashboard";

    document.title = ip + " Dashboard";

    document.querySelectorAll("[data-gnb-ip]").forEach(button => {

        const selected = button.dataset.gnbIp === ip;

        button.classList.toggle("btn-primary", selected);
        button.classList.toggle("active", selected);
        button.classList.toggle("btn-outline-primary", !selected);

        button.setAttribute(
            "aria-pressed",
            selected ? "true" : "false"
        );
    });

    ruSelectionVersion++;
    document.getElementById("ruButtonGroup").replaceChildren();
    document.getElementById("l1Uptime").textContent = "Waiting for L1 log...";
    loadRUConfig().catch(error => {
        document.getElementById("ruConfigMessage").textContent = `Load failed: ${error.message}`;
    });
    // Refresh throughput and logs for the selected gNB
    updateThroughput();
    updateLogs();
    window.dispatchEvent(new Event("gnbChanged"));
}

// Manual reconnect applies only to the currently selected gNB.
let reconnectRequestIP = null;
const reconnectButton = document.getElementById("reconnectGnbButton");
reconnectButton.addEventListener("click", async () => {
    const ip = selectedGNBIP;
    if (!ip || reconnectRequestIP) return;
    reconnectRequestIP = ip;
    reconnectButton.disabled = true;
    reconnectButton.textContent = "Reconnecting...";
    try {
        const response = await fetch(`/api/gnbs/${encodeURIComponent(ip)}/reconnect`, {
            method: "POST"
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        if (selectedGNBIP === ip) {
            document.getElementById("status").textContent = "Reconnecting";
            document.getElementById("status").className = "badge bg-warning text-dark";
        }
    } catch (error) {
        if (selectedGNBIP === ip) window.alert(`Reconnect ${ip} failed: ${error.message}`);
    } finally {
        reconnectRequestIP = null;
        updateGNBStatus();
    }
});

// =====================================
// Update gNB SSH Status
// =====================================

async function updateGNBStatus() {
    const reconnectButton = document.getElementById("reconnectGnbButton");
    if (!selectedGNBIP) {
        reconnectButton.disabled = true;
        return;
    }

    const ip = selectedGNBIP;

    const statusElement = document.getElementById("status");

    if (!statusElement) {
        console.error("[Status] Element not found");
        return;
    }

    console.log("[Status] Checking:", ip);

    try {

        const response = await fetch(
            `/api/status?ip=${encodeURIComponent(ip)}`
        );

        console.log("[Status] HTTP:", response.status);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        console.log("[Status] API response:", data);

        if (ip !== selectedGNBIP) {
            return;
        }

        const uptimeElement = document.getElementById("l1Uptime");
        if (uptimeElement) uptimeElement.textContent = data.connected === true
            ? (data.l1_uptime || "Waiting for L1 log...") : "Unknown";
        reconnectButton.textContent = data.reconnecting ? "Reconnecting..." : "Reconnect";
        reconnectButton.disabled = data.connected === true || data.reconnecting === true || reconnectRequestIP !== null;

        if (data.connected === true) {

            statusElement.textContent = "Connected";
            statusElement.className = "badge bg-success";

        } else if (data.reconnecting === true) {
            statusElement.textContent = "Reconnecting";
            statusElement.className = "badge bg-warning text-dark";
        } else {

            statusElement.textContent = "Disconnect";
            statusElement.className = "badge bg-danger";

        }

    } catch (error) {

        console.error("[Status] Failed:", error);

        if (ip !== selectedGNBIP) {
            return;
        }

        statusElement.textContent = "Unknown";
        statusElement.className = "badge bg-secondary";
        document.getElementById("l1Uptime").textContent = "Unknown";
        reconnectButton.disabled = true;

    }
}

// =====================================
// Initial Status Check
// =====================================

updateGNBStatus();


// =====================================
// Refresh Every 5 Seconds
// =====================================

setInterval(
    updateGNBStatus,
    5000
);


// =====================================
// Refresh When gNB Changes
// =====================================

window.addEventListener(
    "gnbChanged",
    function () {

        const statusElement =
            document.getElementById("status");

        reconnectButton.disabled = true;
        statusElement.textContent = "Checking...";

        statusElement.className =
            "badge bg-secondary";

        updateGNBStatus();

    }
);

//=====================================
// Initial Log Load
//=====================================

updateLogs();


//=====================================
// Log Refresh
//=====================================

setInterval(
    updateLogs,
    1000
);



// RU log panel (independent from existing Netconf / ORU Boot monitors)
let ruLogSelectedType = "rumanager";
let ruLogRequestCounter = 0;

async function updateRuLog() {
    const consoleEl = document.getElementById("ruLogConsole");
    if (!consoleEl) return;
    const ip = typeof selectedGNBIP !== "undefined" ? selectedGNBIP : "";
    if (!ip) { consoleEl.textContent = "Select a gNB first"; return; }
    const ru = selectedRU;
    const logType = ruLogSelectedType;
    const requestId = ++ruLogRequestCounter;
    try {
        const url = `/api/ru-log?ip=${encodeURIComponent(ip)}&ru=${ru}&type=${encodeURIComponent(logType)}`;
        const response = await fetch(url, {cache: "no-store"});
        const data = await response.json();
        if (requestId !== ruLogRequestCounter || ip !== selectedGNBIP ||
            ru !== selectedRU || logType !== ruLogSelectedType) return;
        if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
        const nearBottom = consoleEl.scrollHeight - consoleEl.scrollTop - consoleEl.clientHeight < 45;
        const content = data.content || "(Log is empty)";
        if (consoleEl.textContent !== content) {
            consoleEl.textContent = content;
            if (nearBottom) consoleEl.scrollTop = consoleEl.scrollHeight;
        }
    } catch (error) {
        if (requestId === ruLogRequestCounter) consoleEl.textContent = `RU Log: ${error.message}`;
    }
}

const ruLogTypeGroup = document.getElementById("ruLogTypeGroup");
if (ruLogTypeGroup) ruLogTypeGroup.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-ru-log]");
    if (!button) return;
    ruLogSelectedType = button.dataset.ruLog;
    ruLogTypeGroup.querySelectorAll("button[data-ru-log]").forEach(b => {
        const selected = b === button;
        b.classList.toggle("btn-primary", selected);
        b.classList.toggle("btn-outline-primary", !selected);
        b.classList.toggle("active", selected);
        b.setAttribute("aria-pressed", String(selected));
    });
    updateRuLog();
});

window.addEventListener("gnbChanged", updateRuLog);
setInterval(updateRuLog, 2000);
updateRuLog();

// Initialize gNB selector after the full dashboard script is ready.
loadGNBs();
