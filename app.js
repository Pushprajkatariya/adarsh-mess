// ========================================================
// Adarsh Dining Hall - Public Student Booking Portal Logic
// Live SQLite Database Storage • Strict Time Enforcement
// Zero Emojis • Navy Blue Theme
// ========================================================

const API_BASE = '';

// DOM Elements
const liveClockEl = document.getElementById('liveClock');
const dispTodayDate = document.getElementById('dispTodayDate');
const messOrderForm = document.getElementById('messOrderForm');
const studentNameInput = document.getElementById('studentName');
const submitBtn = document.getElementById('submitBtn');
const selectionError = document.getElementById('selectionError');
const successCard = document.getElementById('successCard');
const submittedSummaryBox = document.getElementById('submittedSummaryBox');
const toastEl = document.getElementById('toast');

const MEAL_CONFIG = {
  tiffin: {
    name: 'Morning Tiffin',
    target: 'Next Day',
    box: document.getElementById('boxTiffin'),
    check: document.getElementById('checkTiffin'),
    badge: document.getElementById('badgeTiffinStatus'),
    dateTag: document.getElementById('tagDateTiffin'),
    closeHour: 23,
    closeMinute: 0,
    closeLabel: '11:00 PM'
  },
  lunch: {
    name: 'Lunch Late Thali',
    target: 'Today',
    box: document.getElementById('boxLunch'),
    check: document.getElementById('checkLunch'),
    badge: document.getElementById('badgeLunchStatus'),
    dateTag: document.getElementById('tagDateLunch'),
    closeHour: 13,
    closeMinute: 0,
    closeLabel: '01:00 PM'
  },
  dinner: {
    name: 'Dinner Late Thali',
    target: 'Today',
    box: document.getElementById('boxDinner'),
    check: document.getElementById('checkDinner'),
    badge: document.getElementById('badgeDinnerStatus'),
    dateTag: document.getElementById('tagDateDinner'),
    closeHour: 20,
    closeMinute: 30,
    closeLabel: '08:30 PM'
  }
};

let serverStatusCache = null;

// ========================================================
// Initializer
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  setupClock();
  fetchServerStatus();
  setupFormListener();
  
  // Re-sync with server every 30 seconds
  setInterval(fetchServerStatus, 30000);
});

// Format dates nicely (e.g., "Wed, 07 Oct 2026")
function formatDisplayDate(dateObj) {
  return dateObj.toLocaleDateString([], {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
}

function getTodayAndTomorrowDates() {
  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);
  return { today, tomorrow };
}

// Fetch status from SQLite backend
async function fetchServerStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    if (res.ok) {
      serverStatusCache = await res.json();
    }
  } catch (err) {
    console.warn('Backend status check fallback to client clock:', err);
  }
  applyTimeLockEnforcement();
}

// Live Clock & Cut-Off Enforcement
function setupClock() {
  const update = () => {
    const now = new Date();
    if (liveClockEl) {
      liveClockEl.textContent = now.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    }

    const { today, tomorrow } = getTodayAndTomorrowDates();
    if (dispTodayDate) {
      dispTodayDate.textContent = formatDisplayDate(today);
    }
    if (MEAL_CONFIG.tiffin.dateTag) {
      MEAL_CONFIG.tiffin.dateTag.textContent = `Serving Date: ${formatDisplayDate(tomorrow)}`;
    }
    if (MEAL_CONFIG.lunch.dateTag) {
      MEAL_CONFIG.lunch.dateTag.textContent = `Serving Date: ${formatDisplayDate(today)}`;
    }
    if (MEAL_CONFIG.dinner.dateTag) {
      MEAL_CONFIG.dinner.dateTag.textContent = `Serving Date: ${formatDisplayDate(today)}`;
    }
  };

  update();
  applyTimeLockEnforcement();
  setInterval(() => {
    update();
    applyTimeLockEnforcement();
  }, 1000);
}

// Strict Booking Window Evaluation
// All bookings open strictly at 09:00 AM
function isMealOpen(mealKey) {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const openMinutes = 9 * 60; // 09:00 AM

  if (currentMinutes < openMinutes) {
    return { open: false, reason: 'Closed (Opens at 09:00 AM)' };
  }

  const cfg = MEAL_CONFIG[mealKey];
  const closeMinutes = cfg.closeHour * 60 + cfg.closeMinute;

  if (currentMinutes > closeMinutes) {
    return { open: false, reason: `Closed (Cut-off passed)` };
  }

  return { open: true, reason: `Open (Closes ${cfg.closeLabel})` };
}

function applyTimeLockEnforcement() {
  let anyMealOpen = false;

  for (const [key, cfg] of Object.entries(MEAL_CONFIG)) {
    const status = isMealOpen(key);

    if (status.open) {
      anyMealOpen = true;
      if (cfg.check) cfg.check.disabled = false;
      if (cfg.box) cfg.box.classList.remove('disabled');
      if (cfg.badge) {
        cfg.badge.textContent = status.reason;
        cfg.badge.className = 'time-status-badge open';
      }
    } else {
      if (cfg.check) {
        cfg.check.disabled = true;
        cfg.check.checked = false;
      }
      if (cfg.box) {
        cfg.box.classList.add('disabled');
        cfg.box.classList.remove('selected');
      }
      if (cfg.badge) {
        cfg.badge.textContent = status.reason;
        cfg.badge.className = 'time-status-badge closed';
      }
    }
  }

  // Update submit button state
  if (submitBtn) {
    if (!anyMealOpen) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Bookings Closed (Opens at 09:00 AM)';
    } else {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Confirm Meal Booking';
    }
  }
}

// Card Tap Toggle
window.toggleMealCard = function(type) {
  const cfg = MEAL_CONFIG[type];
  if (!cfg || !cfg.check || !cfg.box) return;

  if (cfg.check.disabled) {
    showToast('Booking for this meal is currently closed.');
    return;
  }

  cfg.check.checked = !cfg.check.checked;

  if (cfg.check.checked) {
    cfg.box.classList.add('selected');
    if (selectionError) selectionError.classList.add('hidden');
  } else {
    cfg.box.classList.remove('selected');
  }
};

// Form Submission to SQLite Database Backend
function setupFormListener() {
  if (!messOrderForm) return;

  messOrderForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const name = studentNameInput.value.trim();
    if (!name) return;

    const selectedMeals = [];
    for (const [key, cfg] of Object.entries(MEAL_CONFIG)) {
      if (cfg.check && cfg.check.checked && !cfg.check.disabled) {
        selectedMeals.push(key);
      }
    }

    if (selectedMeals.length === 0) {
      if (selectionError) {
        selectionError.classList.remove('hidden');
        selectionError.textContent = 'Please select at least one open meal option.';
        selectionError.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    if (selectionError) selectionError.classList.add('hidden');

    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving to Database...';

    try {
      const response = await fetch(`${API_BASE}/api/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_name: name,
          meals: selectedMeals
        })
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Failed to save booking.');
      }

      showSuccessState(name, result.created);
    } catch (err) {
      console.error('Booking submission error:', err);
      showToast(err.message || 'Error saving booking. Please try again.');
      submitBtn.disabled = false;
      submitBtn.textContent = 'Confirm Meal Booking';
    }
  });
}

function showSuccessState(studentName, createdEntries) {
  messOrderForm.classList.add('hidden');
  successCard.classList.remove('hidden');

  let entriesHtml = createdEntries.map(entry => `
    <div style="padding: 0.35rem 0; border-bottom: 1px solid #e2e8f0;">
      <strong>${entry.meal_label}</strong> (${entry.target_label}): 
      <span style="color: #1e3a8a; font-weight: 700;">${entry.meal_date}</span>
    </div>
  `).join('');

  submittedSummaryBox.innerHTML = `
    <div><strong>Student Name:</strong> ${escapeHtml(studentName)}</div>
    <div style="margin-top: 0.5rem;">
      ${entriesHtml}
    </div>
  `;

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

window.resetFormForNewEntry = function() {
  messOrderForm.reset();
  for (const cfg of Object.values(MEAL_CONFIG)) {
    if (cfg.box) cfg.box.classList.remove('selected');
    if (cfg.check) cfg.check.checked = false;
  }
  if (selectionError) selectionError.classList.add('hidden');
  successCard.classList.add('hidden');
  messOrderForm.classList.remove('hidden');
  applyTimeLockEnforcement();
};

function showToast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  setTimeout(() => {
    toastEl.classList.remove('show');
  }, 2800);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}
