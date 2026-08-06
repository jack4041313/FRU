const MAX_POINTS = 1000;

let throughputChart =
new Chart(
document.getElementById("throughputChart"),
{
    type:"line",

    data:{
        labels:[],
        datasets:[
        {
            label:"DL Throughput (Mbps)",
            data:[],
            tension:0.3
        }]
    },

    options:{
        responsive:true,
        maintainAspectRatio:false
    }
});


function updateThroughput(){

    fetch("/api/throughput")

    .then(r=>r.json())

    .then(data=>{

        console.log(data);


        throughputChart.data.labels =
            data.map(x=>x.time);


        throughputChart.data.datasets[0].data =
            data.map(x=>x.value);


        throughputChart.update();

    });

}


updateThroughput();


setInterval(
    updateThroughput,
    5000
);