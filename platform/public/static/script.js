const getAnalyticsButton = document.getElementById("get-analytics");
const analyticsDiv = document.getElementById("analytics");

getAnalyticsButton.addEventListener("click", async () => {
    const response = await fetch("/analytics");
    const data = await response.json();
    analyticsDiv.innerHTML = "";
    data.data.forEach((item) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = `ID: ${item.id}, Data: ${item.data}`;
        analyticsDiv.appendChild(paragraph);
    });
    data.insights.forEach((insight) => {
        const paragraph = document.createElement("p");
        paragraph.textContent = `Insight: ${insight.prediction}`;
        analyticsDiv.appendChild(paragraph);
    });
});
