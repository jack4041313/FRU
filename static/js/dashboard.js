// Default time range
let range = "10m";


//=============================
// Cell-0 DL
//=============================

const cell0DlChart =
new Chart(
document.getElementById("cell0DlChart"),
{
    type:"line",

    data:{
        labels:[],
        datasets:[
        {
            label:"Cell-0 DL Throughput (Mbps)",
            data:[],
            borderColor:"#38bdf8",
            backgroundColor:"rgba(56,189,248,0.15)",
            tension:0.3,
            fill:true
        }]
    },

    options:{
        responsive:true,
        maintainAspectRatio:false
    }
});


//=============================
// Cell-0 UL
//=============================

const cell0UlChart =
new Chart(
document.getElementById("cell0UlChart"),
{
    type:"line",

    data:{
        labels:[],
        datasets:[
        {
            label:"Cell-0 UL Throughput (Mbps)",
            data:[],
            borderColor:"#22c55e",
            backgroundColor:"rgba(34,197,94,0.15)",
            tension:0.3,
            fill:true
        }]
    },

    options:{
        responsive:true,
        maintainAspectRatio:false
    }
});


//=============================
// Cell-1 DL
//=============================

const cell1DlChart =
new Chart(
document.getElementById("cell1DlChart"),
{
    type:"line",

    data:{
        labels:[],
        datasets:[
        {
            label:"Cell-1 DL Throughput (Mbps)",
            data:[],
            borderColor:"#f59e0b",
            backgroundColor:"rgba(245,158,11,0.15)",
            tension:0.3,
            fill:true
        }]
    },

    options:{
        responsive:true,
        maintainAspectRatio:false
    }
});


//=============================
// Cell-1 UL
//=============================

const cell1UlChart =
new Chart(
document.getElementById("cell1UlChart"),
{
    type:"line",

    data:{
        labels:[],
        datasets:[
        {
            label:"Cell-1 UL Throughput (Mbps)",
            data:[],
            borderColor:"#ef4444",
            backgroundColor:"rgba(239,68,68,0.15)",
            tension:0.3,
            fill:true
        }]
    },

    options:{
        responsive:true,
        maintainAspectRatio:false
    }
});




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

            // Cell-0 DL
            if(data.cell0_dl)
            {

                cell0DlChart.data.labels =
                    data.cell0_dl.map(
                        x=>x.time
                    );


                cell0DlChart.data.datasets[0].data =
                    data.cell0_dl.map(
                        x=>x.value
                    );


                cell0DlChart.update();

            }


            // Cell-1 DL

            if(data.cell1_dl)
            {

                cell1DlChart.data.labels =
                    data.cell1_dl.map(
                        x=>x.time
                    );


                cell1DlChart.data.datasets[0].data =
                    data.cell1_dl.map(
                        x=>x.value
                    );


                cell1DlChart.update();

            }



            //
            // 下面三張圖先更新空資料
            // 等後端完成再修改
            //

            cell0UlChart.data.labels = [];
            cell0UlChart.data.datasets[0].data = [];
            cell0UlChart.update();

            cell1UlChart.data.labels = [];
            cell1UlChart.data.datasets[0].data = [];
            cell1UlChart.update();

        });

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
// Refresh every 5 sec
//=====================================

setInterval(
    updateThroughput,
    5000
);