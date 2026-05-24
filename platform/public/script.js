const redemptionForm = document.getElementById("redemption-form");

redemptionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const userId = document.getElementById("user-id").value;
    const awardPoints = document.getElementById("award-points").value;
    const redemptionDate = document.getElementById("redemption-date").value;

    const response = await fetch("/award_points_redemption", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            user_id: userId,
            award_points: awardPoints,
            redemption_date: redemptionDate
        })
    });

    const data = await response.json();
    console.log(data);
});
