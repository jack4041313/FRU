const MAX_POINTS = 1000;


// Default time range
let range = "10m";



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


    fetch(
        "/api/throughput?range=" + range
    )


    .then(
        r=>r.json()
    )


    .then(
        data=>{


            console.log(data);



            throughputChart.data.labels =

                data.map(
                    x=>x.time
                );



            throughputChart.data.datasets[0].data =

                data.map(
                    x=>x.value
                );



            throughputChart.update();


        }

    );

}




// Time range selector

document
.getElementById("timeRange")
.addEventListener(
"change",
function(){


    range = this.value;


    updateThroughput();


});





// First load

updateThroughput();



// Refresh every 5 seconds

setInterval(
    updateThroughput,
    5000
);