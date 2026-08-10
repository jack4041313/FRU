// =========================================================
// Default time range
// =========================================================

let range = "10m";


// =========================================================
// Chart Creator
// =========================================================

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


// =========================================================
// Charts
// =========================================================


// ---------------------------------------------------------
// Cell-0 DL
// ---------------------------------------------------------

const cell0DlChart =
    createChart(
        "cell0DlChart",
        "Cell-0 DL Throughput (Mbps)",
        "#38bdf8",
        "rgba(56,189,248,0.15)"
    );


// ---------------------------------------------------------
// Cell-0 UL
// ---------------------------------------------------------

const cell0UlChart =
    createChart(
        "cell0UlChart",
        "Cell-0 UL Throughput (Mbps)",
        "#22c55e",
        "rgba(34,197,94,0.15)"
    );


// ---------------------------------------------------------
// Cell-1 DL
// ---------------------------------------------------------

const cell1DlChart =
    createChart(
        "cell1DlChart",
        "Cell-1 DL Throughput (Mbps)",
        "#f59e0b",
        "rgba(245,158,11,0.15)"
    );


// ---------------------------------------------------------
// Cell-1 UL
// ---------------------------------------------------------

const cell1UlChart =
    createChart(
        "cell1UlChart",
        "Cell-1 UL Throughput (Mbps)",
        "#ef4444",
        "rgba(239,68,68,0.15)"
    );


// =========================================================
// Update Chart Function
// =========================================================

function updateChart(
    chart,
    data
) {

    if (!data) {

        return;

    }


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


// =========================================================
// Update Throughput
// =========================================================

function updateThroughput() {

    fetch(
        "/api/throughput?range=" + range
    )

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
                "THROUGHPUT DATA:",
                data
            );


            // =================================================
            // Cell-0 DL
            // =================================================

            updateChart(
                cell0DlChart,
                data.cell0_dl
            );


            // =================================================
            // Cell-0 UL
            // =================================================

            updateChart(
                cell0UlChart,
                data.cell0_ul
            );


            // =================================================
            // Cell-1 DL
            // =================================================

            updateChart(
                cell1DlChart,
                data.cell1_dl
            );


            // =================================================
            // Cell-1 UL
            // =================================================

            updateChart(
                cell1UlChart,
                data.cell1_ul
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


// =========================================================
// Time Range
// =========================================================

const timeRangeElement =
    document.getElementById(
        "timeRange"
    );


if (timeRangeElement) {

    timeRangeElement.addEventListener(
        "change",
        function () {

            range =
                this.value;


            updateThroughput();

        }
    );

}


// =========================================================
// Initial Throughput Load
// =========================================================

updateThroughput();


// =========================================================
// Refresh Throughput
//
// Every 5 seconds
// =========================================================

setInterval(
    updateThroughput,
    5000
);


// =========================================================
// Update Logs
//
// Includes:
//     - Netconf
//     - RU Manager
//     - L1 Up-Time
// =========================================================

function updateLogs() {

    fetch(
        "/api/logs"
    )

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


            // =================================================
            // L1 Up-Time
            // =================================================

            const uptimeElement =
                document.getElementById(
                    "uptime"
                );


            if (uptimeElement) {

                if (
                    data.uptime !== undefined &&
                    data.uptime !== null &&
                    data.uptime !== ""
                ) {

                    uptimeElement.textContent =
                        data.uptime;

                }

                else {

                    uptimeElement.textContent =
                        "Unknown";

                }

            }

            else {

                console.error(
                    "uptime element not found"
                );

            }


            // =================================================
            // Netconf Server
            // =================================================

            const netconfConsole =
                document.getElementById(
                    "netconfConsole"
                );


            if (netconfConsole) {

                // -------------------------------------------------
                // Check whether user is already near bottom
                // -------------------------------------------------

                const netconfAtBottom =
                    netconfConsole.scrollHeight -
                    netconfConsole.scrollTop -
                    netconfConsole.clientHeight <
                    50;


                // -------------------------------------------------
                // Update Netconf log
                // -------------------------------------------------

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


                // -------------------------------------------------
                // Auto scroll
                // -------------------------------------------------

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


            // =================================================
            // RU Manager
            // =================================================

            const rumanagerConsole =
                document.getElementById(
                    "rumanagerConsole"
                );


            if (rumanagerConsole) {

                // -------------------------------------------------
                // Check whether user is already near bottom
                // -------------------------------------------------

                const rumanagerAtBottom =
                    rumanagerConsole.scrollHeight -
                    rumanagerConsole.scrollTop -
                    rumanagerConsole.clientHeight <
                    50;


                // -------------------------------------------------
                // Update RU Manager log
                // -------------------------------------------------

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


                // -------------------------------------------------
                // Auto scroll
                // -------------------------------------------------

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


// =========================================================
// Initial Log Load
// =========================================================

updateLogs();


// =========================================================
// Refresh Logs
//
// Every 3 seconds
// =========================================================

setInterval(
    updateLogs,
    3000
);

