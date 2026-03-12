// Kronängs IF Dashboard App

const DATA_URL = 'data/calendar.json';

let allActivities = [];
let teams = new Set();

// Today as ISO string "YYYY-MM-DD" for easy comparison with activity.date
function todayISO() {
    const d = new Date();
    return d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0');
}

function isPast(activity) {
    if (!activity.date) return false;
    return activity.date < todayISO();
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('team-filter').addEventListener('change', filterActivities);
    document.getElementById('type-filter').addEventListener('change', filterActivities);
    document.getElementById('show-past').addEventListener('change', filterActivities);
    document.getElementById('refresh-btn').addEventListener('click', loadData);
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
        const response = await fetch(`${DATA_URL}?t=${Date.now()}`);
        if (!response.ok) throw new Error('Failed to load data');

        const data = await response.json();
        allActivities = data.activities || [];

        const lastUpdated = new Date(data.last_updated);
        document.getElementById('last-updated').textContent =
            `Uppdaterad: ${lastUpdated.toLocaleString('sv-SE')}`;

        teams.clear();
        allActivities.forEach(a => { if (a.team) teams.add(a.team); });
        populateTeamFilter();
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
    select.innerHTML = '<option value="all">Alla lag</option>';
    Array.from(teams).sort().forEach(team => {
        const option = document.createElement('option');
        option.value = team;
        option.textContent = team;
        select.appendChild(option);
    });
    if (currentValue && (currentValue === 'all' || teams.has(currentValue))) {
        select.value = currentValue;
    }
}

function filterActivities() {
    const teamFilter = document.getElementById('team-filter').value;
    const typeFilter = document.getElementById('type-filter').value;
    const showPast   = document.getElementById('show-past').checked;

    let filtered = allActivities;

    if (!showPast) {
        filtered = filtered.filter(a => !isPast(a));
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

function updateStats(activities) {
    document.getElementById('total-activities').textContent = activities.length;
    document.getElementById('match-count').textContent    = activities.filter(a => a.type === 'Match').length;
    document.getElementById('training-count').textContent = activities.filter(a => a.type === 'Träning').length;
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

    const today = todayISO();
    const grouped = groupByDay(activities);
    let html = '';

    Object.entries(grouped).forEach(([dayKey, dayActivities]) => {
        const dayInfo   = dayActivities[0];
        const dayNum    = dayInfo.day || '';
        const weekday   = dayInfo.weekday || '';
        const past      = dayInfo.date && dayInfo.date < today;

        html += `
            <div class="activity-date-group${past ? ' past' : ''}">
                <div class="date-header">
                    <span class="day-number">${dayNum}</span>
                    <span class="weekday">${weekday}</span>
                </div>
                <div class="activity-list">
                    ${dayActivities.map(renderActivity).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function groupByDay(activities) {
    const grouped = {};
    activities.forEach(a => {
        const key = a.date || `day-${a.day}`;
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(a);
    });
    return Object.fromEntries(
        Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b))
    );
}

function renderActivity(activity) {
    const typeClass = activity.type === 'Match'   ? 'match'    :
                      activity.type === 'Träning' ? 'training' : 'other';
    const location = activity.location
        ? `<div class="activity-location">${activity.location}</div>` : '';

    // Weather info
    let weatherHtml = '';
    if (activity.weather) {
        const w = activity.weather;
        weatherHtml = `<div class="activity-weather" title="${w.desc}">${w.icon} ${w.temp}°C</div>`;
    }

    return `
        <div class="activity-item">
            <div class="activity-time">${activity.time || 'TBD'}</div>
            <div class="activity-details">
                <div class="activity-team">${activity.team || 'Okänt lag'}</div>
                <div class="activity-description">${activity.description || activity.type || ''}</div>
                ${location}
                ${weatherHtml}
            </div>
            <div class="activity-type ${typeClass}">${activity.type || 'Övrigt'}</div>
        </div>
    `;
}
