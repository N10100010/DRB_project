import axios from "axios";
import {defineStore} from "pinia";

// function to convert milliseconds to min:sec:ms
const formatMilliseconds = ms => {
    if (!ms) {
        return '00:00.000';
    }
    return new Date(ms).toISOString().slice(14, -2);
};


// predefined colors for charts
const COLORS = ['#0C67F7', '#93E9ED', '#E0A9FA', '#E0B696', '#E0FAAC', '#F0E95A'];

export const useRennstrukturAnalyseState = defineStore({
    id: "base",
    state: () => ({
        filterOpen: false,
        loadingState: false,
        tableExport: [],
        data: {
            filterOptions: {
                "years": [0, 0],
                "competition_categories": []
            },
            raceData: [{
                "race_id": "",
                "display_name": "",
                "start_date": "",
                "venue": "",
                "boat_class": "",
                "result_time_world_best": 0,
                "result_time_best_of_current_olympia_cycle": 0,
                "progression_code": "",
                "pdf_urls": {
                    "result": "",
                    "race_data": ""
                },
                "race_boats": [{
                    "name": "",
                    "lane": 1,
                    "rank": 1,
                    "athletes": [{
                        "first_name": "",
                        "last_name": "",
                        "boat_position": ""
                    }],
                    "intermediates": {},
                    "race_data": {}
                }]
            }],
            analysis: null
        },
    }),
    getters: {
        getFilterState(state) {
            return state.filterOpen
        },
        getAnalysisData(state) {
            return state.data.analysis
        },
        getCompetitionData(state) {
            const data = state.data.raceData[0]
            data.worldBestTimeBoatClass = formatMilliseconds(data.worldBestTimeBoatClass);
            data.bestTimeBoatClassCurrentOZ = formatMilliseconds(data.bestTimeBoatClassCurrentOZ);
            return data
        },
        getRaceAnalysisFilterOptions(state) {
            return state.data.filterOptions
        },
        getOldTableData(state) {
            return state.data.raceData[0].data
        },
        getLoadingState(state) {
            return state.loadingState
        },
        getTableData(state) {
            const tableHead = ['Platz', 'Bahn', 'Nation', 'Mannschaft'];
            const intermediateDistances = state.data.raceData[0].race_boats[0].intermediates

            for (const key in intermediateDistances) {
                // ignore first as this is the starting value
                if (key !== '0') {
                    tableHead.push(key + "m", "Position")
                }
            }
            const tableData = [];
            tableData.push(tableHead);

            state.data.raceData[0].race_boats.forEach(dataObj => {
                if (dataObj.intermediates !== '0') {
                    const rowData = [dataObj.rank, dataObj.lane, dataObj.name];
                    const athleteNames = Object.values(dataObj.athletes).map(athlete => {
                      const link = `/athleten?athlete_id=${athlete.id}`;
                      const name = `(${athlete.boat_position}) ${athlete.first_name} ${athlete.last_name}`;
                      return { link, name };
                    });
                    rowData.push(athleteNames);

                    const firstArray = [];
                    const secondArray = [];
                    const speedValues = [];
                    const strokeValues = [];
                    const propulsionValues = [];

                    Object.values(dataObj.race_data).forEach(gpsData => {
                        if (dataObj.intermediates !== '0') {
                            speedValues.push(gpsData["speed [m/s]"] + "[m/s]");
                            strokeValues.push(gpsData["stroke [1/min]"] + "[1/min]");
                            propulsionValues.push(gpsData["propulsion [m/stroke]"].toFixed(2) + "[m/Schlag]");
                        }
                    });
                    for (const [index, [key, intermediate]] of Object.entries(dataObj.intermediates).entries()) {
                        if (key !== '0') {
                            firstArray.push(
                                formatMilliseconds(intermediate["time [millis]"]),
                                formatMilliseconds(intermediate["pace [millis]"]),
                                formatMilliseconds(intermediate["deficit [millis]"])
                            )
                            secondArray.push(["(" + intermediate["rank"] + ")", speedValues[index], strokeValues[index], propulsionValues[index]])
                        }
                    }
                    const chunkSize = 3;
                    const tempArray = [];
                    for (let i = 0; i < firstArray.length; i += chunkSize) {
                        tempArray.push(firstArray.slice(i, i + chunkSize));
                    }
                    tempArray.forEach((value, index) => {
                        rowData.push(value)
                        rowData.push(secondArray[index])
                    })
                    tableData.push(rowData);
                }
            })
            state.tableExport = tableData
            return tableData;
        },
        getDeficitInMeters(state) {
            const raceBoats = state.data.raceData[0].race_boats
            // determine winner
            const winnerIdx = raceBoats.findIndex(team => team.rank === 1);
            const winnerData = raceBoats.map(dataObj => dataObj.race_data)[winnerIdx]
            const winnerTeamSpeeds = Object.fromEntries(Object.entries(winnerData).map(
                ([key, val]) => [key, val["speed [m/s]"]]));

            // calculate difference to winner based on speed
            let speedPerTeam = {};
            let countries = []
            for (const i in raceBoats) {
                countries.push(raceBoats[i].name)
                const speedData = raceBoats.map(dataObj => dataObj.race_data)[i];
                let diffSpeedValues = {}

                const interval_list = Object.keys(speedData).map((element, index, arr) => (arr[index + 1] || 0) - element)
                const hashmap = interval_list.reduce((acc, val) => {
                    acc[val] = (acc[val] || 0) + 1
                    return acc
                }, {})
                const interval = Object.keys(hashmap).reduce((a, b) => hashmap[a] > hashmap[b] ? a : b)
                let prevValue = 0
                for (const [key, val] of Object.entries(speedData)) {
                    const speedWinner = winnerTeamSpeeds[key]
                    const speedCurrentTeam = val["speed [m/s]"]
                    let time = speedWinner !== 0 ? interval / speedWinner : 0;
                    if (Number(key) !== 0) {
                        prevValue = diffSpeedValues[key - interval]
                    }
                    diffSpeedValues[key] = prevValue + ((speedWinner * time) - (speedCurrentTeam * time))
                }
                speedPerTeam[i] = diffSpeedValues
            }
            let colorIndex = 0;
            const datasets = []
            Object.entries(speedPerTeam).forEach(([key, value], idx) => {
                const label = countries[idx]
                const backgroundColor = COLORS[colorIndex % 6]
                const borderColor = COLORS[colorIndex % 6]
                const data = Object.values(value)
                datasets.push({label, backgroundColor, borderColor, data})
                colorIndex++
            })
            const allKeys = Object.values(speedPerTeam).map(obj => Object.keys(obj))
            return {
                labels: Array.from(new Set([].concat(...allKeys))),
                datasets
            };
        },
        getGPSChartData(state) {
            const chartDataKeys = ['speed [m/s]', 'stroke [1/min]', 'propulsion [m/stroke]'];
            return chartDataKeys.map(key => {
                const datasets = [];
                let colorIndex = 0;

                state.data.raceData[0].race_boats.forEach(dataObj => {
                    const label = dataObj.name;
                    const backgroundColor = COLORS[colorIndex % 6];
                    const borderColor = COLORS[colorIndex % 6];
                    dataObj.race_data["0"] = {'speed [m/s]': 0, 'stroke [1/min]': 0, 'propulsion [m/stroke]': 0}
                    const data = Object.values(dataObj.race_data).map(obj => obj[key]);
                    datasets.push({label, backgroundColor, borderColor, data});
                    colorIndex++;
                });
                return {
                    labels: Object.keys(state.data.raceData[0].race_boats[0].race_data),
                    datasets
                };
            })
        },
        getIntermediateChartData(state) {
            const intermediateDataKeys = ["rank", "deficit [millis]"];
            return intermediateDataKeys.map(key => {
                const datasets = [];
                let colorIndex = 0;
                state.data.raceData[0].race_boats.forEach(dataObj => {
                    const label = dataObj.name;
                    const backgroundColor = COLORS[colorIndex % 6];
                    const borderColor = COLORS[colorIndex % 6];
                    // add zero values as start point
                    dataObj.intermediates["0"] = {"rank": 1, "deficit [millis]": 0}
                    let data = Object.values(dataObj.intermediates).map(distanceObj => distanceObj[key]);
                    if (key === "deficit [millis]") {
                        data = data.map(x => formatMilliseconds(x))
                    }
                    datasets.push({label, backgroundColor, borderColor, data});
                    colorIndex++;
                });
                const chartLabels = Object.keys(state.data.raceData[0].race_boats[0].intermediates)
                return {
                    labels: chartLabels,
                    datasets
                };
            })
        },
        getIntermediateChartOptions(state) {
            const max_val = Math.max(...state.data.raceData[0].race_boats.map(obj =>
                Math.max(...Object.values(obj.intermediates).map(el => el["deficit [millis]"]))
            ));

            return [{
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Strecke [m]'
                        }
                    },
                    y: {
                        reverse: true,
                        title: {
                            display: true,
                            text: 'Platzierung'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: "Platzierung"
                    }
                }
            },
                {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        x: {
            title: {
                display: true,
                text: 'Strecke [m]'
            }
        },
        y: {
            type: 'time',
            time: {
                parser: 'mm:ss.SS',
                unit: 'millisecond',
                displayFormats: {
                    millisecond: 'mm:ss.SS',
                    tooltip: 'mm:ss.SS'
                }
            },
            min: '00:00.00',
            max: formatMilliseconds(max_val + 100),
            title: {
                display: true,
                text: 'Rückstand [mm:ss.ms]'
            }
        }
    },
    plugins: {
        title: {
            display: true,
            text: "Rückstand zum Führenden [sek]"
        }
    }
}

            ]
        }
    },
    actions: {
        async getFilterOptions() {
            await axios.get(`${import.meta.env.VITE_BACKEND_API_BASE_URL}/race_analysis_filter_options/`)
                .then(response => {
                this.data.filterOptions = response.data
            }).catch(error => {
                console.error(`Request failed: ${error}`)
            })
        },
        async postFormData(data) {
            await axios.post(`${import.meta.env.VITE_BACKEND_API_BASE_URL}/race_analysis_filter_results`, {data})
                .then(response => {
                    this.data.analysis = response.data
                    this.loadingState = false
                }).catch(error => {
                    console.error(`Request failed: ${error}`)
                })
        },
        async fetchRaceData(raceId) {
            await axios.get(`${import.meta.env.VITE_BACKEND_API_BASE_URL}/get_race/${raceId}/`)
                .then(response => {
                    this.data.raceData[0] = response.data
                    this.loadingState = false
                }).catch(error => {
                    console.error(`Request failed: ${error}`)
                })
        },
        setFilterState(filterState) {
            this.filterOpen = !filterState
        },
        setToLoadingState() {
            this.loadingState = true
        },
        exportTableData() {
            let finalData = []
            for (const data of Object.values(this.tableExport)) {
                let rowData = []
                for (const [, value] of data.entries()) {
                    Array.isArray(value) ? rowData.push(value.join(" | ")) : rowData.push(value)
                }
                finalData.push(rowData)
            }
            const csvContent = "data:text/csv;charset=utf-8," + finalData.map(e => e.join(",")).join("\n");
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "rennstruktur.csv");
            document.body.appendChild(link);
            link.click();
        }
    }
});