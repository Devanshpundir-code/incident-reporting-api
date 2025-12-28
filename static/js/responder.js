// responder.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const incidentsContainer = document.getElementById('incidents-container');
    const loadingElement = document.getElementById('loading');
    const errorState = document.getElementById('error-state');
    const noIncidents = document.getElementById('no-incidents');
    const refreshBtn = document.getElementById('refresh-btn');
    const retryBtn = document.getElementById('retry-btn');
    const severityFilter = document.getElementById('severity-filter');
    const statusFilter = document.getElementById('status-filter');
    const incidentModal = document.getElementById('incident-modal');
    const reportsModal = document.getElementById('reports-modal');
    const modalCloseButtons = document.querySelectorAll('.modal-close');
    const lastUpdatedSpan = document.getElementById('last-updated');
    
    // State
    let lastIncidentSnapshot = {};
    let incidents = [];
    let refreshInterval;
    const REFRESH_INTERVAL = 30000; // 30 seconds
    
    // Severity mapping
    const SEVERITY_MAP = {
        'critical': { label: 'Critical', color: 'critical', emoji: '🔴' },
        'serious': { label: 'Serious', color: 'serious', emoji: '🟠' },
        'medium': { label: 'Medium', color: 'medium', emoji: '🟡' },
        'minor': { label: 'Minor', color: 'minor', emoji: '🟢' }
    };
    
    // Status mapping
    const STATUS_MAP = {
        'unverified': { label: 'Unverified', color: 'unverified' },
        'verified': { label: 'Verified', color: 'verified' },
        'in_progress': { label: 'In Progress', color: 'in_progress' },
        'resolved': { label: 'Resolved', color: 'resolved' }
    };
    
    // Incident type icons
    const TYPE_ICONS = {
        'fire': 'fas fa-fire',
        'medical': 'fas fa-ambulance',
        'police': 'fas fa-shield-alt',
        'accident': 'fas fa-car-crash',
        'hazard': 'fas fa-radiation',
        'other': 'fas fa-exclamation-triangle'
    };
    
    // Initialize
    init();
    
    function init() {
        // Load incidents immediately
        loadIncidents();
        
        // Set up refresh interval
        refreshInterval = setInterval(loadIncidents, REFRESH_INTERVAL);
        
        // Event listeners
        refreshBtn.addEventListener('click', function() {
            loadIncidents();
            // Visual feedback
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Refreshing';
            setTimeout(() => {
                refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh';
            }, 1000);
        });
        
        retryBtn.addEventListener('click', loadIncidents);
        
        severityFilter.addEventListener('change', renderIncidents);
        statusFilter.addEventListener('change', renderIncidents);
        
        // Modal close handlers
        modalCloseButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                incidentModal.classList.add('hidden');
                reportsModal.classList.add('hidden');
            });
        });
        
        // Close modal on outside click
        window.addEventListener('click', function(event) {
            if (event.target === incidentModal) {
                incidentModal.classList.add('hidden');
            }
            if (event.target === reportsModal) {
                reportsModal.classList.add('hidden');
            }
        });
    }
    
    // Load incidents from API
    async function loadIncidents() {
        try {
            showLoading();
            
            // In a real app, this would be your Flask endpoint
            const response = await fetch('/responder/incidents');
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
const newIncidents = data.incidents || [];

// 🔁 Detect changes
let changed = false;

newIncidents.forEach(inc => {
    const prev = lastIncidentSnapshot[inc.id];
    if (
        !prev ||
        prev.status !== inc.status ||
        prev.claimed_by !== inc.claimed_by ||
        prev.responder_priority !== inc.responder_priority
    ) {
        changed = true;
    }
});

// Update snapshot
lastIncidentSnapshot = {};
newIncidents.forEach(inc => {
    lastIncidentSnapshot[inc.id] = inc;
});

incidents = newIncidents;

// Update stats always
updateStats(incidents);

// Re-render ONLY if something changed
if (changed) {
    renderIncidents();
}

            
            // Update timestamp
            const now = new Date();
            lastUpdatedSpan.textContent = now.toLocaleTimeString([], { 
                hour: '2-digit', 
                minute: '2-digit',
                second: '2-digit'
            });
            
            // Hide error state if shown
            errorState.classList.add('hidden');
            
        } catch (error) {
            console.error('Error loading incidents:', error);
            showError('Failed to load incidents. Please check your connection and try again.');
        }
    }
    
    // Update statistics counters
    function updateStats(incidents) {
        const counts = {
            critical: 0,
            serious: 0,
            medium: 0,
            minor: 0,
            total: incidents.length
        };
        
        incidents.forEach(incident => {
            if (counts.hasOwnProperty(incident.severity)) {
                counts[incident.severity]++;
            }
        });
        
        document.getElementById('critical-count').textContent = counts.critical;
        document.getElementById('serious-count').textContent = counts.serious;
        document.getElementById('medium-count').textContent = counts.medium;
        document.getElementById('minor-count').textContent = counts.minor;
        document.getElementById('total-count').textContent = counts.total;
    }
    
    // Render incidents based on current filters
    function renderIncidents() {
        const severityFilterValue = severityFilter.value;
        const statusFilterValue = statusFilter.value;
        
        // Filter incidents
        let filteredIncidents = incidents;
        
        if (severityFilterValue !== 'all') {
            filteredIncidents = filteredIncidents.filter(
                incident => incident.severity === severityFilterValue
            );
        }
        
        if (statusFilterValue !== 'all') {
            filteredIncidents = filteredIncidents.filter(
                incident => incident.status === statusFilterValue
            );
        }
        
        // Clear container
        incidentsContainer.innerHTML = '';
        
        // Show/hide no incidents message
        if (filteredIncidents.length === 0) {
            noIncidents.classList.remove('hidden');
            incidentsContainer.classList.add('hidden');
        } else {
            noIncidents.classList.add('hidden');
            incidentsContainer.classList.remove('hidden');
            
            // Sort by severity (critical first)
            filteredIncidents.sort((a, b) => {
                const severityOrder = { critical: 0, serious: 1, medium: 2, minor: 3 };
                return severityOrder[a.severity] - severityOrder[b.severity];
            });
            
            // Render each incident
            filteredIncidents.forEach(incident => {
                incidentsContainer.appendChild(createIncidentCard(incident));
            });
        }
        
        // Hide loading
        loadingElement.classList.add('hidden');
    }
    
    // Create incident card HTML
    function createIncidentCard(incident) {
        const severity = SEVERITY_MAP[incident.severity] || SEVERITY_MAP.medium;
        const status = STATUS_MAP[incident.status] || STATUS_MAP.unverified;
        const iconClass = TYPE_ICONS[incident.type] || TYPE_ICONS.other;

        const card = document.createElement('div');
        card.className = 'incident-card';
        card.dataset.id = incident.id;
        
        card.innerHTML = `
            <div class="incident-header">
                <span class="incident-id">ID: ${incident.id}</span>
                <span class="severity-badge severity-${severity.color}">
                    ${severity.emoji} ${severity.label}
                </span>
            </div>
            <div class="incident-body">
                <div class="incident-type">
                    <i class="${iconClass}"></i>
                    ${incident.type.charAt(0).toUpperCase() + incident.type.slice(1)}
                </div>
                <p class="incident-description">${incident.description || 'No description provided'}</p>
                
                <div class="incident-details">
                    <div class="detail-item">
                        <span class="detail-label">Location</span>
                        <span class="detail-value">${incident.location_text || 'Unknown'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Coordinates</span>
                        <span class="detail-value">${incident.latitude}, ${incident.longitude}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Time Reported</span>
                        <span class="detail-value">${formatTime(incident.created_at)}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Duplicate Reports</span>
                        <span class="detail-value">${incident.duplicate_count || 0}</span>
                    </div>
                </div>
                
                ${incident.ai_severity ? `
                <div class="ai-severity">
                    <div class="ai-label">
                        <i class="fas fa-robot"></i> AI Suggested Severity
                    </div>
                    <div class="ai-value">
                        ${SEVERITY_MAP[incident.ai_severity]?.emoji || ''} 
                        ${SEVERITY_MAP[incident.ai_severity]?.label || incident.ai_severity}
                        (${incident.ai_confidence || 'N/A'} confidence)
                    </div>
                </div>
                ` : ''}
                
                <div class="related-reports">
                    <i class="fas fa-copy"></i>
                    <span>${incident.related_reports_count || 0} related reports</span>
                </div>
            </div>
            <div class="incident-footer">
                <span class="status-badge status-${status.color}">${status.label}</span>
                <div class="priority-section">
    <label>Priority:</label>

    <select class="priority-select">
        <option value="">Set Priority</option>
        <option value="low" ${incident.responder_priority === 'low' ? 'selected' : ''}>🟢 Low</option>
        <option value="medium" ${incident.responder_priority === 'medium' ? 'selected' : ''}>🟡 Medium</option>
        <option value="high" ${incident.responder_priority === 'high' ? 'selected' : ''}>🟠 High</option>
        <option value="critical" ${incident.responder_priority === 'critical' ? 'selected' : ''}>🔴 Critical</option>
    </select>

    ${incident.responder_priority ? `
        <span class="priority-badge priority-${incident.responder_priority}">
            ${incident.responder_priority.toUpperCase()}
        </span>
    ` : ''}
</div>
    <button class="btn-secondary btn-note">
        📝 Send Note
    </button>

                ${
    incident.claimed_by
    ? `<button class="btn-disabled claimed-btn" disabled>
           ✅ Already Claimed
       </button>`
    : `<button class="btn-primary btn-claim">
           🚑 Claim
       </button>`
}


                <div class="action-buttons">
                    <button class="btn-secondary btn-view-details">
                        <i class="fas fa-eye"></i> Details
                    </button>
                    <button class="btn-secondary btn-view-reports" ${(incident.related_reports_count || 0) === 0 ? 'disabled' : ''}>
                        <i class="fas fa-copy"></i> Related
                    </button>
                    <select class="status-select" ${incident.status === 'resolved' ? 'disabled' : ''}>
                        <option value="">Update Status</option>
                        <option value="in_progress" ${incident.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                        <option value="resolved" ${incident.status === 'resolved' ? 'selected' : ''}>Resolved</option>
                    </select>
                </div>
            </div>
        `;
        const claimBtn = card.querySelector('.btn-claim');

        if (claimBtn) {
            claimBtn.addEventListener('click', () => {
                claimIncident(incident.id);
            });
        }
        const noteBtn = card.querySelector('.btn-note');

noteBtn.addEventListener('click', () => {
    const msg = prompt("Enter instruction for user:");
    if (msg) {
        sendNote(incident.id, msg);
    }
});

        // Add event listeners to buttons in this card
        const viewDetailsBtn = card.querySelector('.btn-view-details');
        const viewReportsBtn = card.querySelector('.btn-view-reports');
        const statusSelect = card.querySelector('.status-select');
        
        const prioritySelect = card.querySelector('.priority-select');

prioritySelect.addEventListener('change', function () {
    if (this.value) {
        updateIncidentPriority(incident.id, this.value);
    }
});

        viewDetailsBtn.addEventListener('click', () => showIncidentDetails(incident));
        
        if ((incident.related_reports_count || 0) > 0) {
            viewReportsBtn.addEventListener('click', () => showRelatedReports(incident));
        }
        
        statusSelect.addEventListener('change', function() {
            if (this.value) {
                updateIncidentStatus(incident.id, this.value);
            }
        });
        
        return card;
    }
    
    // Show incident details in modal
    function showIncidentDetails(incident) {
        const severity = SEVERITY_MAP[incident.severity] || SEVERITY_MAP.medium;
        const status = STATUS_MAP[incident.status] || STATUS_MAP.unverified;
        const iconClass = TYPE_ICONS[incident.type] || TYPE_ICONS.other;
        
        document.getElementById('modal-body').innerHTML = `
            <div class="incident-details-modal">
                <div class="detail-row">
                    <strong>Incident ID:</strong> ${incident.id}
                </div>
                <div class="detail-row">
                    <strong>Type:</strong> 
                    <i class="${iconClass}"></i>
                    ${incident.type.charAt(0).toUpperCase() + incident.type.slice(1)}
                </div>
                <div class="detail-row">
                    <strong>Severity:</strong>
                    <span class="severity-badge severity-${severity.color}">
                        ${severity.emoji} ${severity.label}
                    </span>
                </div>
                <div class="detail-row">
                    <strong>Status:</strong>
                    <span class="status-badge status-${status.color}">${status.label}</span>
                </div>
                <div class="detail-row">
                    <strong>Location:</strong> ${incident.location_text || 'Not specified'}
                </div>
                <div class="detail-row">
                    <strong>Coordinates:</strong> ${incident.latitude}, ${incident.longitude}
                </div>
                <div class="detail-row">
                    <strong>Time Reported:</strong> ${formatTime(incident.created_at)}
                </div>
                <div class="detail-row">
                    <strong>Last Updated:</strong> ${formatTime(incident.updated_at)}
                </div>
                <div class="detail-row">
                    <strong>Description:</strong>
                    <p>${incident.full_description || incident.description || 'No description provided'}</p>
                </div>
                
                ${incident.ai_severity ? `
                <div class="ai-section">
                    <h3><i class="fas fa-robot"></i> AI Analysis</h3>
                    <div class="detail-row">
                        <strong>Suggested Severity:</strong>
                        ${SEVERITY_MAP[incident.ai_severity]?.emoji || ''} 
                        ${SEVERITY_MAP[incident.ai_severity]?.label || incident.ai_severity}
                    </div>
                    <div class="detail-row">
                        <strong>Confidence:</strong> ${incident.ai_confidence || 'N/A'}
                    </div>
                    ${incident.ai_reasoning ? `
                    <div class="detail-row">
                        <strong>AI Reasoning:</strong>
                        <p>${incident.ai_reasoning}</p>
                    </div>
                    ` : ''}
                    <p class="note"><em>Note: AI suggestions are for reference only. Responders have final authority.</em></p>
                </div>
                ` : ''}
                
                <div class="actions-section">
                    <h3>Actions</h3>
                    <div class="action-buttons-horizontal">
                        <button class="btn-status" onclick="updateIncidentStatus('${incident.id}', 'in_progress')" ${incident.status === 'in_progress' || incident.status === 'resolved' ? 'disabled' : ''}>
                            <i class="fas fa-play-circle"></i> Mark In Progress
                        </button>
                        <button class="btn-status" onclick="updateIncidentStatus('${incident.id}', 'resolved')" ${incident.status === 'resolved' ? 'disabled' : ''}>
                            <i class="fas fa-check-circle"></i> Mark Resolved
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        incidentModal.classList.remove('hidden');
    }
    
    // Show related reports in modal
    function showRelatedReports(incident) {
        // In a real app, you would fetch related reports from the API
        // For now, we'll show a mock list
        document.getElementById('related-reports-list').innerHTML = `
            <p>Related reports for incident ${incident.id}:</p>
            <div class="reports-list">
                ${incident.related_reports && incident.related_reports.length > 0 
                    ? incident.related_reports.map(report => `
                        <div class="report-item">
                            <strong>Report ID:</strong> ${report.id}<br>
                            <strong>Time:</strong> ${formatTime(report.created_at)}<br>
                            <strong>Similarity:</strong> ${report.similarity || 'N/A'}%
                        </div>
                    `).join('')
                    : '<p>No related reports found.</p>'
                }
            </div>
            <p class="note"><em>Showing ${incident.related_reports_count || 0} duplicate/related reports.</em></p>
        `;
        
        reportsModal.classList.remove('hidden');
    }
    
    // Update incident status
    async function updateIncidentStatus(incidentId, newStatus) {
        try {
            const response = await fetch(`/incident/${incidentId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            if (!response.ok) {
                throw new Error(`Failed to update status: ${response.status}`);
            }
            
            // Update local incidents array
            const incidentIndex = incidents.findIndex(inc => inc.id === incidentId);
            if (incidentIndex !== -1) {
                incidents[incidentIndex].status = newStatus;
                incidents[incidentIndex].updated_at = new Date().toISOString();
            }
            
            // Re-render incidents
            renderIncidents();
            
            // Show success message (in a real app, you might want a toast notification)
            alert(`Incident ${incidentId} status updated to ${STATUS_MAP[newStatus]?.label || newStatus}`);
            
        } catch (error) {
            console.error('Error updating incident status:', error);
            alert('Failed to update incident status. Please try again.');
        }
    }
    async function claimIncident(incidentId) {
    try {
        const response = await fetch(`/incident/${incidentId}/claim`, {
            method: 'POST'
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Failed to claim');
        }

        // Update local state
        const idx = incidents.findIndex(i => i.id === incidentId);
        if (idx !== -1) {
           incidents[idx].claimed_by = result.claimed_by;

        }

        renderIncidents();
        alert('Incident claimed successfully');

    } catch (err) {
        alert(err.message);
    }
}

    async function sendNote(incidentId, message) {
    const eta = prompt("Enter ETA (e.g. 5–10 mins):");

    const res = await fetch(`/incident/${incidentId}/responder-update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            note: message,
            eta: eta
        })
    });

    if (res.ok) {
        alert("Update sent to user");
    } else {
        alert("Failed to send update");
    }
}


    async function updateIncidentPriority(incidentId, priority) {
    try {
        const response = await fetch(`/incident/${incidentId}/priority`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ priority })
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || 'Failed to update priority');
        }

        // ✅ Update local state safely
        const idx = incidents.findIndex(i => i.id === incidentId);
        if (idx !== -1) {
            incidents[idx].responder_priority = priority;
        }

        renderIncidents();
        alert(`Priority set to ${priority.toUpperCase()}`);

    } catch (err) {
        console.error('Priority update error:', err);
        alert(err.message); // ✅ show REAL error
    }
}

    // UI State Management
    function showLoading() {
        loadingElement.classList.remove('hidden');
        errorState.classList.add('hidden');
        incidentsContainer.classList.add('hidden');
        noIncidents.classList.add('hidden');
    }
    
    function showError(message) {
        loadingElement.classList.add('hidden');
        errorState.classList.remove('hidden');
        incidentsContainer.classList.add('hidden');
        noIncidents.classList.add('hidden');
        
        document.getElementById('error-message').textContent = message;
    }
    
    // Helper Functions
    function formatTime(timestamp) {
        if (!timestamp) return 'Unknown';
        
        const date = new Date(timestamp);
        return date.toLocaleString([], {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    // Make updateIncidentStatus available globally for modal buttons
    window.updateIncidentStatus = updateIncidentStatus;

    window.updateIncidentPriority = updateIncidentPriority;

});


