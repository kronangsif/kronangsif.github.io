// Kronängs IF Dashboard App

const DATA_URL = 'data/calendar.json';

let allActivities = [];
let teams = new Set();
let calendarMonth = null;
let calendarYear = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('team-filter').addEventListener('change', filterActivities);
    document.getElementById('type-filter').addEventListener('change', filterActivities);
    document.getElementById('show-past').addEventListener('change', filterActivities);
    document.getElementById('refresh-btn').addEventListener('click', () => {
        loadData();
    });
}

async function loadData() {
    const container = document.getElementById('activities-container');
    container.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Laddar kalender...</p>
        </div>
    `;

    try {
        // Add timestamp to prevent caching
        const response = await fetch(`${DATA_URL}?t=${Date.now()}`);
        if (!response.ok) {
            throw new Error('Failed to load data');
        }
        
        const data = await response.json();
        allActivities = data.activities || [];
        calendarMonth = data.month || null;
        calendarYear = data.year || null;

        // Update last updated time
        const lastUpdated = new Date(data.last_updated);
        document.getElementById('last-updated').textContent = 
            `Uppdaterad: ${lastUpdated.toLocaleString('sv-SE')}`;
        
        // Extract unique teams
        teams.clear();
        allActivities.forEach(a => {
            if (a.team) teams.add(a.team);
        });
        
        // Populate team filter
        populateTeamFilter();
        
        // Render activities (also updates stats)
        filterActivities();
        
    } catch (error) {
        console.error('Error loading data:', error);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <h3>Kunde inte ladda kalender</h3>
                <p>Försök igen senare eller kolla att data/calendar.json finns.</p>
            </div>
        `;
    }
}

function populateTeamFilter() {
    const select = document.getElementById('team-filter');
    const currentValue = select.value;
    
    // Keep the "Alla lag" option
    select.innerHTML = '<option value="all">Alla lag</option>';
    
    // Sort teams alphabetically
    const sortedTeams = Array.from(teams).sort();
    
    sortedTeams.forEach(team => {
        const option = document.createElement('option');
        option.value = team;
        option.textContent = team;
        select.appendChild(option);
    });
    
    // Restore previous selection if valid
    if (currentValue && (currentValue === 'all' || teams.has(currentValue))) {
        select.value = currentValue;
    }
}

function updateStats(activities) {
    const total = activities.length;
    const matches = activities.filter(a => a.type === 'Match').length;
    const training = activities.filter(a => a.type === 'Träning').length;
    
    document.getElementById('total-activities').textContent = total;
    document.getElementById('match-count').textContent = matches;
    document.getElementById('training-count').textContent = training;
}

function isPastActivity(activity) {
    if (!calendarMonth || !calendarYear) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dayDate = new Date(calendarYear, calendarMonth - 1, parseInt(activity.day));
    return dayDate < today;
}

function filterActivities() {
    const teamFilter = document.getElementById('team-filter').value;
    const typeFilter = document.getElementById('type-filter').value;
    const showPast = document.getElementById('show-past').checked;

    let filtered = allActivities;

    if (!showPast) {
        filtered = filtered.filter(a => !isPastActivity(a));
    }

    if (teamFilter !== 'all') {
        filtered = filtered.filter(a => a.team === teamFilter);
    }

    if (typeFilter !== 'all') {
        filtered = filtered.filter(a => a.type === typeFilter);
    }

    updateStats(filtered);
    renderActivities(filtered);
}

function renderActivities(activities) {
    const container = document.getElementById('activities-container');
    
    if (activities.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📅</div>
                <h3>Inga aktiviteter hittades</h3>
                <p>Prova att ändra filtren för att se fler resultat.</p>
            </div>
        `;
        return;
    }
    
    // Group activities by day
    const grouped = groupByDay(activities);
    
    let html = '';
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    Object.entries(grouped).forEach(([dayKey, dayActivities]) => {
        const dayInfo = dayActivities[0];
        const dayNum = dayInfo.day || dayKey.split('-')[2] || dayKey;
        const weekday = dayInfo.weekday || '';

        let isPast = false;
        if (calendarMonth && calendarYear) {
            const dayDate = new Date(calendarYear, calendarMonth - 1, parseInt(dayNum));
            isPast = dayDate < today;
        }

        html += `
            <div class="activity-date-group${isPast ? ' past' : ''}">
                <div class="date-header">
                    <span class="day-number">${dayNum}</span>
                    <span class="weekday">${weekday}</span>
                </div>
                <div class="activity-list">
                    ${dayActivities.map(a => renderActivity(a)).join('')}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function groupByDay(activities) {
    const grouped = {};
    
    activities.forEach(activity => {
        const day = activity.day || '0';
        const key = `day-${day}`;
        
        if (!grouped[key]) {
            grouped[key] = [];
        }
        grouped[key].push(activity);
    });
    
    // Sort by day number
    return Object.fromEntries(
        Object.entries(grouped).sort(([a], [b]) => {
            const dayA = parseInt(a.split('-')[1]) || 0;
            const dayB = parseInt(b.split('-')[1]) || 0;
            return dayA - dayB;
        })
    );
}

function renderActivity(activity) {
    const typeClass = activity.type === 'Match' ? 'match' : 
                      activity.type === 'Träning' ? 'training' : 'other';
    
    const location = activity.location ? `
        <div class="activity-location">${activity.location}</div>
    ` : '';
    
    return `
        <div class="activity-item">
            <div class="activity-time">${activity.time || 'TBD'}</div>
            <div class="activity-details">
                <div class="activity-team">${activity.team || 'Okänt lag'}</div>
                <div class="activity-description">${activity.description || activity.type || ''}</div>
                ${location}
            </div>
            <div class="activity-type ${typeClass}">${activity.type || 'Övrigt'}</div>
        </div>
    `;
}
