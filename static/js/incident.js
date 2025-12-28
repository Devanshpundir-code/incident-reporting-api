// static/js/incident.js
class IncidentPage {
    constructor() {
        this.incidentId = window.incidentId;
        this.isResponder = window.isResponder;
        this.pollInterval = 10000; // 10 seconds
        this.pollTimer = null;
        this.isLoading = true;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadIncidentData();
        this.startPolling();
        
        // Show responder controls if user is responder
        if (this.isResponder) {
            document.getElementById('responderSection').style.display = 'block';
        }
    }
    
    bindEvents() {
        // Toggle related reports
        document.getElementById('toggleRelated').addEventListener('click', (e) => {
            const list = document.getElementById('relatedList');
            const btn = e.currentTarget;
            const icon = btn.querySelector('i');
            
            if (list.style.maxHeight && list.style.maxHeight !== '300px') {
                list.style.maxHeight = '300px';
                btn.innerHTML = '<span>Show All Reports</span><i class="fas fa-chevron-down"></i>';
            } else {
                list.style.maxHeight = 'none';
                btn.innerHTML = '<span>Show Less</span><i class="fas fa-chevron-up"></i>';
            }
        });
        
        // Status update form
        const form = document.getElementById('statusUpdateForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.updateIncidentStatus();
            });
        }
    }
    
    async loadIncidentData() {
        try {
            this.showLoading(true);
            
            const response = await fetch(`/api/incident/${this.incidentId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.renderIncidentData(data.incident);
                this.renderVerification(data.verification_counts);
                this.renderRelatedReports(data.related_reports);
                this.renderGuidance(data.guidance);
                this.updateUIState(data.incident);
                
                document.getElementById('mainContent').style.display = 'block';
                document.getElementById('loading').style.display = 'none';
                this.isLoading = false;
            } else {
                throw new Error(data.message || 'Failed to load incident data');
            }
        } catch (error) {
            console.error('Error loading incident:', error);
            this.showError(error.message);
        }
    }
    
    renderIncidentData(incident) {
        // Basic information
        document.getElementById('incidentType').textContent = incident.type || '—';
        document.getElementById('timestamp').textContent = this.formatTimestamp(incident.timestamp);
        document.getElementById('location').textContent = incident.location || '—';
        document.getElementById('description').textContent = incident.description || '—';
        
        // Status
        const statusBadge = document.getElementById('statusBadge');
        statusBadge.textContent = this.formatStatus(incident.status);
        statusBadge.className = `status-badge status-${incident.status}`;
        
        // Severity
        this.renderSeverity(incident.severity, incident.ai_severity);
        
        // Last updated
        document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
    }
    
    renderSeverity(severity, aiSeverity) {
        const severityMap = {
            'low': { badge: '🟢', text: 'Low', class: 'severity-low' },
            'medium': { badge: '🟡', text: 'Medium', class: 'severity-medium' },
            'high': { badge: '🟠', text: 'High', class: 'severity-high' },
            'critical': { badge: '🔴', text: 'Critical', class: 'severity-critical' }
        };
        
        const severityInfo = severityMap[severity] || { badge: '—', text: 'Unknown', class: '' };
        const aiSeverityInfo = severityMap[aiSeverity] || { badge: '—', text: 'Unknown', class: '' };
        
        const severityBadge = document.getElementById('severityBadge');
        severityBadge.textContent = severityInfo.badge;
        severityBadge.className = `severity-badge ${severityInfo.class}`;
        
        document.getElementById('severityText').textContent = severityInfo.text;
        
        const aiSeverityBadge = document.getElementById('aiSeverityBadge');
        aiSeverityBadge.textContent = aiSeverityInfo.badge;
        aiSeverityBadge.className = `ai-severity-badge ${aiSeverityInfo.class}`;
    }
    
    renderVerification(counts) {
        const total = counts.yes + counts.no + counts.unsure;
        const yesPercent = total > 0 ? (counts.yes / total) * 100 : 0;
        
        document.getElementById('verifiedYes').textContent = counts.yes;
        document.getElementById('verifiedNo').textContent = counts.no;
        document.getElementById('verifiedUnsure').textContent = counts.unsure;
        document.getElementById('verifiedBar').style.width = `${yesPercent}%`;
    }
    
    renderRelatedReports(reports) {
        const container = document.getElementById('relatedList');
        const countBadge = document.getElementById('relatedCount');
        
        if (!reports || reports.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clipboard-check"></i>
                    <p>No related reports found</p>
                </div>
            `;
            countBadge.textContent = '0';
            return;
        }
        
        countBadge.textContent = reports.length.toString();
        
        const reportsHtml = reports.map(report => `
            <div class="related-item">
                <div class="reporter-id">
                    ${report.reporter_id ? `User #${report.reporter_id}` : '<span class="anonymous">Anonymous</span>'}
                </div>
                <p class="related-description">${this.escapeHtml(report.description || 'No description')}</p>
                ${report.media_url ? `
                    <div class="related-media">
                        <img src="${report.media_url}" alt="Report media" class="media-preview" onerror="this.style.display='none'">
                    </div>
                ` : ''}
                <div class="related-timestamp">
                    Reported: ${this.formatTimestamp(report.timestamp)}
                </div>
            </div>
        `).join('');
        
        container.innerHTML = reportsHtml;
    }
    
    renderGuidance(guidance) {
        const section = document.getElementById('guidanceSection');
        const content = document.getElementById('guidanceContent');
        
        if (!guidance || guidance.length === 0) {
            section.style.display = 'none';
            return;
        }
        
        section.style.display = 'block';
        
        const guidanceHtml = guidance.map(item => `
            <div class="guidance-item">
                <h4><i class="fas fa-${item.icon || 'bullhorn'}"></i> ${item.title}</h4>
                <p>${item.instruction}</p>
            </div>
        `).join('');
        
        content.innerHTML = guidanceHtml;
    }
    
    updateUIState(incident) {
        // Update status select
        const statusSelect = document.getElementById('statusSelect');
        if (statusSelect) {
            statusSelect.value = incident.status;
            
            // Disable if resolved
            if (incident.status === 'resolved') {
                statusSelect.disabled = true;
                document.querySelector('#statusUpdateForm button[type="submit"]').disabled = true;
                this.showResolutionInfo(incident.resolved_at);
            }
        }
        
        // Show/hide guidance based on status
        const guidanceSection = document.getElementById('guidanceSection');
        if (incident.status === 'resolved') {
            guidanceSection.style.display = 'none';
        }
    }
    
    showResolutionInfo(resolvedAt) {
        const infoDiv = document.getElementById('resolutionInfo');
        const timeSpan = document.getElementById('resolvedTime');
        
        if (resolvedAt) {
            timeSpan.textContent = this.formatTimestamp(resolvedAt);
        } else {
            timeSpan.textContent = 'Just now';
        }
        
        infoDiv.style.display = 'block';
    }
    
    async updateIncidentStatus() {
        const form = document.getElementById('statusUpdateForm');
        const statusSelect = document.getElementById('statusSelect');
        const notes = document.getElementById('responderNotes');
        const feedback = document.getElementById('formFeedback');
        
        const newStatus = statusSelect.value;
        const notesText = notes.value.trim();
        
        if (!newStatus) {
            this.showFormFeedback('Please select a status', 'error');
            return;
        }
        
        try {
            const response = await fetch(`/api/incident/${this.incidentId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: newStatus,
                    notes: notesText
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.showFormFeedback('Status updated successfully', 'success');
                notes.value = '';
                
                // Reload data to reflect changes
                setTimeout(() => this.loadIncidentData(), 1000);
            } else {
                throw new Error(data.message || 'Failed to update status');
            }
        } catch (error) {
            console.error('Error updating status:', error);
            this.showFormFeedback(error.message, 'error');
        }
    }
    
    showFormFeedback(message, type) {
        const feedback = document.getElementById('formFeedback');
        feedback.textContent = message;
        feedback.className = `form-feedback ${type}`;
        
        // Clear after 5 seconds
        setTimeout(() => {
            feedback.textContent = '';
            feedback.className = 'form-feedback';
        }, 5000);
    }
    
    startPolling() {
        this.pollTimer = setInterval(() => {
            if (!this.isLoading) {
                this.loadIncidentData();
            }
        }, this.pollInterval);
    }
    
    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
        }
    }
    
    showLoading(show) {
        this.isLoading = show;
        document.getElementById('loading').style.display = show ? 'block' : 'none';
        
        if (show) {
            document.getElementById('mainContent').style.display = 'none';
            document.getElementById('errorState').style.display = 'none';
        }
    }
    
    showError(message) {
        this.isLoading = false;
        document.getElementById('loading').style.display = 'none';
        document.getElementById('mainContent').style.display = 'none';
        
        const errorDiv = document.getElementById('errorState');
        document.getElementById('errorMessage').textContent = message || 'An unexpected error occurred';
        errorDiv.style.display = 'block';
    }
    
    // Utility functions
    formatStatus(status) {
        const statusMap = {
            'unverified': 'Unverified',
            'verified': 'Verified',
            'in_progress': 'In Progress',
            'resolved': 'Resolved'
        };
        return statusMap[status] || status;
    }
    
    formatTimestamp(timestamp) {
        if (!timestamp) return '—';
        
        const date = new Date(timestamp);
        return date.toLocaleString();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global refresh function
function refreshData() {
    if (window.incidentPage) {
        window.incidentPage.loadIncidentData();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.incidentPage = new IncidentPage();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.incidentPage) {
        window.incidentPage.stopPolling();
    }
});