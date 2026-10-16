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

function updateThroughput() {

    fetch(
        `/api/throughput?ip=${encodeURIComponent(selectedGNBIP)}&range=${range}`
    )

        .then(
            r => r.json()
        )

        .then(
            data => {

                console.log(
                    "THROUGHPUT DATA:",
                    data
                );


                //=========================
                // DL
                //=========================

                updateChart(
                    cell0DlChart,
                    data.cell0_dl
                );


                updateChart(
                    cell1DlChart,
                    data.cell1_dl
                );


                updateChart(
                    cell2DlChart,
                    data.cell2_dl
                );


                //=========================
                // UL
                //=========================

                updateChart(
                    cell0UlChart,
                    data.cell0_ul
                );

            }
        )

        .catch(
            error => {

                console.error(
                    "Failed to get throughput:",
                    error
                );

            }
        );

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

    // Refresh throughput and logs for the selected gNB
    updateThroughput();
    updateLogs();
}

// =====================================
// Update gNB SSH Status
// =====================================

async function updateGNBStatus() {

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

        if (data.connected === true) {

            statusElement.textContent = "Connected";
            statusElement.className = "badge bg-success";

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

