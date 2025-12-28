// ===== DOM ELEMENTS =====
const incidentForm = document.getElementById('incidentForm');
const getLocationBtn = document.getElementById('getLocationBtn');
const latitudeInput = document.getElementById('latitude');
const longitudeInput = document.getElementById('longitude');
const submissionMessage = document.getElementById('submissionMessage');
const incidentsContainer = document.getElementById('incidentsContainer');
const incidentCount = document.getElementById('incidentCount');
const toggleIncidents = document.getElementById('toggleIncidents');
const emergencyAlert = document.getElementById('emergencyAlert');
const locationText = document.getElementById('locationText');
const liveGuidance = document.getElementById('liveGuidance');
const notesContainer = document.getElementById('notesContainer');
const closeGuidanceBtn = document.getElementById('closeGuidanceBtn');

// ===== BROWSER GEOLOCATION =====
    if (!getLocationBtn) {
        console.error("getLocationBtn not found in DOM");
        
    }

    getLocationBtn.addEventListener('click', () => {

        console.log("Get My Location clicked"); // 🔥 DEBUG LINE

        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser');
            return;
        }

        getLocationBtn.innerHTML = '📍 Detecting...';
        getLocationBtn.disabled = true;
        locationText.value = 'Fetching your location...';

        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;

                latitudeInput.value = lat.toFixed(6);
                longitudeInput.value = lng.toFixed(6);

                try {
                    const response = await fetch(
                        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`
                    );
                    const data = await response.json();
                    locationText.value = data.display_name || 'Location detected';
                } catch {
                    locationText.value = 'Location detected (address unavailable)';
                }

                getLocationBtn.innerHTML = '📍 Location Captured!';
                setTimeout(() => {
                    getLocationBtn.innerHTML = '📍 Get My Location';
                    getLocationBtn.disabled = false;
                }, 2000);
            },
            (error) => {
                alert("Location error: " + error.message);
                getLocationBtn.innerHTML = '📍 Get My Location';
                getLocationBtn.disabled = false;
            }
        );
    });




// ===== INCIDENT FORM SUBMISSION (REAL) =====
incidentForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Basic validation
    if (!latitudeInput.value || !longitudeInput.value) {
        alert("Please click 'Get My Location' before submitting.");
        return;
    }

    const formData = new FormData();
    formData.append("type", document.getElementById("incidentType").value);
    formData.append("description", document.getElementById("description").value);
    formData.append("latitude", latitudeInput.value);
    formData.append("longitude", longitudeInput.value);
    formData.append("user_id", 1); // demo user

    const mediaFile = document.getElementById("media").files[0];
    if (mediaFile) {
        formData.append("media", mediaFile);
    }

    try {
        const response = await fetch("/report", {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Failed to submit incident");
        }

        console.log("Incident saved:", result);
        const myIncidentId = result.incident_id;
localStorage.setItem("myIncidentId", myIncidentId);

document.getElementById("myReportStatus").style.display = "block";


        // SUCCESS UI
        incidentForm.style.display = "none";
        submissionMessage.style.display = "block";

        
        // ===== SHOW LIVE GUIDANCE =====
const incidentType = document.getElementById("incidentType").value;
const guidanceList = PRE_APPROVED_GUIDANCE[incidentType] || PRE_APPROVED_GUIDANCE.other;

notesContainer.innerHTML = guidanceList
    .map(text => `<div class="guidance-item">• ${text}</div>`)
    .join("");
liveGuidance.style.display = "block";
liveGuidance.scrollIntoView({ behavior: "smooth" });



        // Hide only the success message after 5 sec
setTimeout(() => {
    submissionMessage.style.display = "none";
}, 5000);

// ❌ DO NOT reset form automatically
// ❌ DO NOT touch liveGuidance


        loadNearbyIncidents();

    } catch (error) {
        console.error("Submit error:", error);
        alert("Failed to submit incident. Please try again.");
    }
});


// ===== LOAD NEARBY INCIDENTS =====

async function fetchMyReportStatus() {
    const incidentId = localStorage.getItem("myIncidentId");
    if (!incidentId) return;

    const res = await fetch(`/incident/${incidentId}/user-status`);
    const data = await res.json();

    document.getElementById("userReportStatus").innerText = data.status.toUpperCase();
    document.getElementById("claimedStatus").innerText =
        data.claimed ? "Claimed by responder" : "Not claimed yet";

    document.getElementById("etaStatus").innerText =
        data.eta || "Not available";

    document.getElementById("responderNote").innerText =
        data.responder_note || "No message yet";
}

// 🔁 refresh every 10 sec
setInterval(fetchMyReportStatus, 10000);


// ===== DISPLAY INCIDENTS =====
function displayIncidents(incidents) {
    if (!incidents || incidents.length === 0) {
        incidentsContainer.innerHTML = `
            <div class="no-incidents">
                ✅ No incidents reported in your area. Stay safe!
            </div>
        `;
        incidentCount.textContent = '0';
        return;
    }
    
    incidentCount.textContent = incidents.length;
    
    const incidentsHTML = incidents.map(incident => `
        <div class="incident-card">
            <div class="card-header">
                <div class="incident-type">${incident.type}</div>
                <span class="severity-badge severity-${incident.severity}">
                    ${incident.severity.toUpperCase()}
                </span>
            </div>
            
            <p class="description">${incident.description}</p>
            
            <div class="card-details">
                <div class="detail">📍 ${incident.distance} away</div>
                <div class="detail">🕐 ${incident.time}</div>
            </div>
            
            <div class="card-footer">
                <span class="status status-${incident.status.replace('-', '')}">
                    ${incident.status.replace('-', ' ').toUpperCase()}
                </span>
                ${incident.status === 'unverified' ? generateVerificationButtons(incident.id) : ''}
            </div>
        </div>
    `).join('');
    
    incidentsContainer.innerHTML = incidentsHTML;
    
    // Add event listeners to verification buttons
    document.querySelectorAll('.verify-btn').forEach(btn => {
        btn.addEventListener('click', handleVerification);
    });
}

// ===== VERIFICATION BUTTONS =====
function generateVerificationButtons(incidentId) {
    return `
        <div class="verification-buttons">
            <button class="verify-btn yes" data-id="${incidentId}" data-response="yes">
                ✅ Yes (Emergency)
            </button>
            <button class="verify-btn no" data-id="${incidentId}" data-response="no">
                ❌ No (False)
            </button>
            <button class="verify-btn not-sure" data-id="${incidentId}" data-response="not-sure">
                🤔 Not Sure
            </button>
        </div>
    `;
}

async function handleVerification(e) {
    const incidentId = e.target.dataset.id;
    const response = e.target.dataset.response;
    
    // Visual feedback
    e.target.innerHTML = 'Sending...';
    e.target.disabled = true;
    
    try {
        // Simulate API call (replace with actual fetch)
        console.log(`Verifying incident ${incidentId}: ${response}`);
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Success feedback
        e.target.innerHTML = '✅ Sent!';
        e.target.style.background = '#2ecc71';
        
        // Disable all buttons for this incident
        const buttons = e.target.parentElement.querySelectorAll('.verify-btn');
        buttons.forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.6';
        });
        
    } catch (error) {
        console.error('Error sending verification:', error);
        e.target.innerHTML = 'Failed. Try again.';
        e.target.style.background = '#e74c3c';
        setTimeout(() => {
            e.target.innerHTML = e.target.dataset.response === 'yes' ? '✅ Yes' : 
                                 e.target.dataset.response === 'no' ? '❌ No' : '🤔 Not Sure';
            e.target.disabled = false;
            e.target.style.background = '';
        }, 2000);
    }
}

// ===== EMERGENCY ALERT SYSTEM =====
function checkHighSeverityAlerts(incidents) {
    const highSeverity = incidents.filter(incident => 
        ['critical', 'serious'].includes(incident.severity) && 
        incident.distance.includes('km') && 
        parseFloat(incident.distance) < 1
    );
    
    if (highSeverity.length > 0) {
        showEmergencyAlert(highSeverity);
    }
}

function showEmergencyAlert(incidents) {
    emergencyAlert.style.display = 'flex';
    
    // Placeholder for siren/alert sound (user must opt-in)
    // if (userOptedInForAlerts && !isSilentMode) {
    //     playAlertSound();
    // }
}

function dismissAlert() {
    emergencyAlert.style.display = 'none';
}
// ===== PRE-APPROVED SAFE GUIDANCE (AI) =====
const PRE_APPROVED_GUIDANCE = {
    medical: [
        "🩸 Apply gentle pressure if there is bleeding",
        "🫁 Keep the person conscious and calm",
        "🚫 Do NOT give food, water, or medicine",
        "📞 Stay nearby until medical help arrives"
    ],
    fire: [
        "🔥 Move away from smoke and flames",
        "🚪 Use stairs, NOT elevators",
        "🫁 Cover nose and mouth with cloth",
        "🚫 Do NOT re-enter the building"
    ],
    accident: [
        "🚗 Move to a safe area away from traffic",
        "🚨 Turn on hazard lights if possible",
        "🚫 Do NOT move injured persons",
        "📞 Call emergency services if required"
    ],
    crime: [
        "👀 Stay in a safe, public area",
        "📱 Avoid confronting anyone",
        "📝 Note details only if safe",
        "🚔 Wait for police assistance"
    ],
    other: [
        "⚠️ Keep yourself safe",
        "📞 Stay alert and wait for help"
    ]
};

// ===== TOGGLE INCIDENTS VISIBILITY =====
toggleIncidents.addEventListener('click', () => {
    const container = document.getElementById('incidentsContainer');
    const isHidden = container.style.display === 'none';
    
    if (isHidden) {
        container.style.display = 'block';
        toggleIncidents.textContent = '−';
    } else {
        container.style.display = 'none';
        toggleIncidents.textContent = '+';
    }
});

// ===== INITIALIZE =====
document.addEventListener('DOMContentLoaded', () => {
    // Load nearby incidents on page load
    loadNearbyIncidents();
    
    // Auto-refresh incidents every 30 seconds
    setInterval(loadNearbyIncidents, 30000);
    
    // Try to get location on page load
    setTimeout(() => {
        if (navigator.geolocation && !latitudeInput.value) {
            getLocationBtn.click();
        }
    }, 1000);
});

closeGuidanceBtn.addEventListener('click', () => {
    liveGuidance.style.display = 'none';
});

// ===== ERROR HANDLING =====
window.addEventListener('error', (e) => {
    console.error('Global error:', e.error);
});

// ===== PLACEHOLDER FUNCTIONS =====
function playAlertSound() {
    // Placeholder for emergency siren/alert sound
    console.log('Emergency alert sound would play here (if user opted in)');
    
    // Example implementation:
    // const audio = new Audio('/static/sounds/alert.mp3');
    // audio.volume = 0.7;
    // audio.play().catch(e => console.log('Audio play failed:', e));
}

// Export for testing (remove in production)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        loadNearbyIncidents,
        handleVerification,
        checkHighSeverityAlerts
    };
}