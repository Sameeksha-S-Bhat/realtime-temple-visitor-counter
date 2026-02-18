// Global state
let isRunning = false;
let statsInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    console.log('Dashboard loaded');
    updateTimestamp();
    setInterval(updateTimestamp, 1000);

    // Get saved camera URL from localStorage
    const savedUrl = localStorage.getItem('cameraUrl');
    if (savedUrl) {
        document.getElementById('cameraUrl').value = savedUrl;
    }
});

// Update timestamp
function updateTimestamp() {
    const now = new Date();
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    document.getElementById('timestamp').textContent =
        now.toLocaleDateString('en-IN', options);
}

// Start system
async function startSystem() {
    const cameraUrl = document.getElementById('cameraUrl').value.trim();

    if (!cameraUrl) {
        alert('Please enter camera URL');
        return;
    }

    // Validate URL format
    if (!cameraUrl.startsWith('http://') && !cameraUrl.startsWith('https://')) {
        alert('Camera URL must start with http:// or https://');
        return;
    }

    // Save camera URL
    localStorage.setItem('cameraUrl', cameraUrl);

    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ camera_url: cameraUrl })
        });

        const data = await response.json();

        if (data.status === 'success') {
            isRunning = true;
            updateUIState();

            // Show video feed
            document.getElementById('videoFeed').src = '/video_feed';
            document.getElementById('videoOverlay').classList.add('hidden');

            // Start stats polling
            startStatsPolling();

            showNotification('System started successfully!', 'success');
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Start error:', error);
        alert('Failed to start system. Check console for details.');
    }
}

// Stop system
async function stopSystem() {
    if (!confirm('Are you sure you want to stop counting?')) {
        return;
    }

    try {
        const response = await fetch('/api/stop', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.status === 'success') {
            isRunning = false;
            updateUIState();

            // Hide video feed
            document.getElementById('videoFeed').src = '';
            document.getElementById('videoOverlay').classList.remove('hidden');

            // Stop stats polling
            stopStatsPolling();

            showNotification('System stopped. Data saved.', 'info');
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Stop error:', error);
        alert('Failed to stop system');
    }
}

// Reset count
async function resetCount() {
    const confirmed = confirm(
        '⚠️ WARNING: This will reset the count to zero.\n\n' +
        'Current data will be saved to CSV before reset.\n\n' +
        'Are you sure you want to continue?'
    );

    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch('/api/reset', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.status === 'success') {
            showNotification('Count reset successfully!', 'warning');
            updateStats(); // Refresh display
        } else {
            alert('Error: ' + data.message);
        }
    } catch (error) {
        console.error('Reset error:', error);
        alert('Failed to reset count');
    }
}

// Download CSV
function downloadCSV() {
    window.location.href = '/api/download';
    showNotification('Downloading CSV file...', 'info');
}

// Update stats
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        // Update counters
        document.getElementById('totalCount').textContent =
            formatNumber(data.total_count || 0);
        document.getElementById('trackingCount').textContent =
            data.current_tracking || 0;
        document.getElementById('detectionCount').textContent =
            data.current_detections || 0;

        // Update status indicator
        const statusElement = document.getElementById('systemStatus');
        if (data.is_running) {
            statusElement.innerHTML =
                '<span class="status-dot online"></span><span>Online</span>';
        } else {
            statusElement.innerHTML =
                '<span class="status-dot offline"></span><span>Offline</span>';
        }

        // Update hourly data
        if (data.hourly_data && data.hourly_data.length > 0) {
            updateHourlyList(data.hourly_data);
        }

    } catch (error) {
        console.error('Stats update error:', error);
    }
}

// Update hourly list
function updateHourlyList(hourlyData) {
    const listElement = document.getElementById('hourlyList');

    if (hourlyData.length === 0) {
        listElement.innerHTML =
            '<p class="empty-state">No data yet. Start counting to see hourly reports.</p>';
        return;
    }

    // Reverse to show latest first
    const reversedData = [...hourlyData].reverse();

    listElement.innerHTML = reversedData.map(item => `
        <div class="hourly-item">
            <span class="hourly-time">⏰ ${item.Time}</span>
            <span class="hourly-count">${formatNumber(item.Count)} people</span>
        </div>
    `).join('');
}

// Start stats polling
function startStatsPolling() {
    if (statsInterval) {
        clearInterval(statsInterval);
    }

    updateStats(); // Initial update
    statsInterval = setInterval(updateStats, 2000); // Every 2 seconds
}

// Stop stats polling
function stopStatsPolling() {
    if (statsInterval) {
        clearInterval(statsInterval);
        statsInterval = null;
    }
}

// Update UI state based on running status
function updateUIState() {
    document.getElementById('startBtn').disabled = isRunning;
    document.getElementById('stopBtn').disabled = !isRunning;
    document.getElementById('resetBtn').disabled = !isRunning;
    document.getElementById('cameraUrl').disabled = isRunning;
}

// Format number with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Show notification
function showNotification(message, type = 'info') {
    // Simple console log for now
    // You can enhance this with a toast notification library
    console.log(`[${type.toUpperCase()}] ${message}`);

    // Could add a toast notification here
    // For simplicity, using alert for errors
    if (type === 'error') {
        alert(message);
    }
}

// Handle page visibility change
document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        // Page hidden, stop polling to save resources
        if (isRunning && statsInterval) {
            clearInterval(statsInterval);
        }
    } else {
        // Page visible again, resume polling
        if (isRunning) {
            startStatsPolling();
        }
    }
});

// Check system status on load
setTimeout(updateStats, 1000);
