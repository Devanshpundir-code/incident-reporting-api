document.getElementById("responderRegisterForm").addEventListener("submit", async function (e) {
    e.preventDefault();

    const form = e.target;
    const formData = new FormData(form);

    try {
        const response = await fetch("/responder/register", {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            alert("Registration successful!");
            window.location.href = "/responder"; // ✅ redirect to dashboard
        } else {
            alert(result.error || "Registration failed");
        }

    } catch (err) {
        console.error(err);
        alert("Server error. Try again.");
    }
});
