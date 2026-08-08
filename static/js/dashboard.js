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
){

    return new Chart(
        document.getElementById(element),
        {

            type:"line",

            data:{

                labels:[],

                datasets:[

                    {
                        label:label,

                        data:[],

                        borderColor:color,

                        backgroundColor:bgColor,

                        tension:0.3,

                        fill:true
                    }

                ]

            },

            options:{

                responsive:true,

                maintainAspectRatio:false

            }

        }
    );

}



//=============================
// Charts
//=============================


// Cell-0 DL

const cell0DlChart =
createChart(
    "cell0DlChart",
    "Cell-0 DL Throughput (Mbps)",
    "#38bdf8",
    "rgba(56,189,248,0.15)"
);


// Cell-0 UL

const cell0UlChart =
createChart(
    "cell0UlChart",
    "Cell-0 UL Throughput (Mbps)",
    "#22c55e",
    "rgba(34,197,94,0.15)"
);



// Cell-1 DL

const cell1DlChart =
createChart(
    "cell1DlChart",
    "Cell-1 DL Throughput (Mbps)",
    "#f59e0b",
    "rgba(245,158,11,0.15)"
);



// Cell-1 UL

const cell1UlChart =
createChart(
    "cell1UlChart",
    "Cell-1 UL Throughput (Mbps)",
    "#ef4444",
    "rgba(239,68,68,0.15)"
);





//=====================================
// Update Chart Function
//=====================================

function updateChart(
    chart,
    data
){

    if(!data)
        return;


    chart.data.labels =
        data.map(
            x=>x.time
        );


    chart.data.datasets[0].data =
        data.map(
            x=>x.value
        );


    chart.update();

}





//=====================================
// Update Throughput
//=====================================

function updateThroughput(){


    fetch(
        "/api/throughput?range=" + range
    )


    .then(
        r=>r.json()
    )


    .then(
        data=>{


            console.log(data);



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




            //=========================
            // UL
            //=========================


            updateChart(
                cell0UlChart,
                data.cell0_ul
            );


            updateChart(
                cell1UlChart,
                data.cell1_ul
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
function(){

    range = this.value;


    updateThroughput();

});






//=====================================
// Initial Load
//=====================================

updateThroughput();



//=====================================
// Refresh
//=====================================

setInterval(
    updateThroughput,
    5000
);

//=====================================
// log viewer
//=====================================

function updateLogs(){


    fetch(
        "/api/logs"
    )


    .then(
        r=>r.json()
    )


    .then(
        data=>{


            document
            .getElementById(
                "logWindow1"
            )
            .innerText =
                data.log1;



            document
            .getElementById(
                "logWindow2"
            )
            .innerText =
                data.log2;


        }

    );


}


updateLogs();


setInterval(
    updateLogs,
    3000
);