// ========================================================
// Adarsh Dining Hall - Public Student Booking Portal Logic
// Live SQLite Database Storage • Strict Time Enforcement
// Device Lock (1 Phone = 1 Meal) • Room Number Lock
// Zero Emojis • Navy Blue Theme
// ========================================================

const API_BASE = '';
const DEVICE_ID_KEY = 'adarsh_device_id_v2';
const DEVICE_LOCK_KEY = 'adarsh_device_bookings_v2';

// DOM Elements
const liveClockEl = document.getElementById('liveClock');
const dispTodayDate = document.getElementById('dispTodayDate');
const messOrderForm = document.getElementById('messOrderForm');
const studentNameInput = document.getElementById('studentName');
const roomNumberInput = document.getElementById('roomNumber');
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
let activeDeviceBookings = {};

// ========================================================
// Device Lock Helpers (Server is the Single Source of Truth)
// 1 Booking per Phone per Date • Unlocked ONLY when Manager Clears
// ========================================================
function getOrCreateDeviceId() {
  let devId = null;
  try {
    devId = localStorage.getItem(DEVICE_ID_KEY);
  } catch (e) {}

  if (!devId) {
    const match = document.cookie.match(/(?:^|;\s*)adarsh_device_id=([^;]+)/);
    if (match) {
      devId = decodeURIComponent(match[1]);
    }
  }

  if (!devId) {
    devId = 'phone_' + Math.random().toString(36).substring(2, 11) + Date.now().toString(36);
  }

  try {
    localStorage.setItem(DEVICE_ID_KEY, devId);
  } catch (e) {}

  try {
    document.cookie = `adarsh_device_id=${encodeURIComponent(devId)}; path=/; max-age=31536000; SameSite=Lax`;
  } catch (e) {}

  return devId;
}

function getStoredDeviceBookings() {
  try {
    const raw = localStorage.getItem(DEVICE_LOCK_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

// Initial cache from storage
activeDeviceBookings = getStoredDeviceBookings();

function saveDeviceBooking(mealKey, studentName, roomNumber, mealDate) {
  activeDeviceBookings[mealKey] = {
    booked: true,
    student_name: studentName,
    room_number: roomNumber,
    meal_date: mealDate,
    bookedAt: new Date().toISOString()
  };
  try {
    localStorage.setItem(DEVICE_LOCK_KEY, JSON.stringify(activeDeviceBookings));
  } catch (e) {}
}

function isBookedOnThisDevice(mealKey) {
  const rec = activeDeviceBookings ? activeDeviceBookings[mealKey] : null;
  return (rec && rec.booked) ? rec : null;
}

// Date helpers
function getIsoString(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getTodayAndTomorrowDates() {
  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);
  return { today, tomorrow };
}

function formatDisplayDate(dateObj) {
  return dateObj.toLocaleDateString([], {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  });
}

// ========================================================
// Initializer
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  getOrCreateDeviceId();
  setupClock();
  fetchServerStatus();
  setupFormListener();
  
  // Fast re-sync every 3 seconds so manager actions unlock students immediately
  setInterval(fetchServerStatus, 3000);
  window.addEventListener('focus', fetchServerStatus);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') fetchServerStatus();
  });
});

// Fetch status from SQLite backend (Database is source of truth)
async function fetchServerStatus() {
  try {
    const devId = getOrCreateDeviceId();
    const res = await fetch(`${API_BASE}/api/status?device_id=${encodeURIComponent(devId)}`);
    if (res.ok) {
      serverStatusCache = await res.json();
      // When manager clears bookings in manager site, device_bookings becomes empty
      // Overwrite local state so student is immediately unlocked!
      activeDeviceBookings = serverStatusCache.device_bookings || {};
      try {
        localStorage.setItem(DEVICE_LOCK_KEY, JSON.stringify(activeDeviceBookings));
      } catch (e) {}
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
    const timeStatus = isMealOpen(key);
    const deviceRecord = isBookedOnThisDevice(key);

    if (deviceRecord) {
      // Locked on this phone for this meal!
      if (cfg.check) {
        cfg.check.disabled = true;
        cfg.check.checked = false;
      }
      if (cfg.box) {
        cfg.box.classList.add('disabled');
        cfg.box.classList.remove('selected');
      }
      if (cfg.badge) {
        const studentInfo = deviceRecord.student_name ? ` (${deviceRecord.student_name})` : '';
        cfg.badge.textContent = `Already Booked on This Phone${studentInfo}`;
        cfg.badge.className = 'time-status-badge closed';
      }
    } else if (timeStatus.open) {
      anyMealOpen = true;
      if (cfg.check) cfg.check.disabled = false;
      if (cfg.box) cfg.box.classList.remove('disabled');
      if (cfg.badge) {
        cfg.badge.textContent = timeStatus.reason;
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
        cfg.badge.textContent = timeStatus.reason;
        cfg.badge.className = 'time-status-badge closed';
      }
    }
  }

  // Update submit button state
  if (submitBtn) {
    if (!anyMealOpen) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Bookings Closed';
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

  const deviceRecord = isBookedOnThisDevice(type);

  if (deviceRecord) {
    showToast(`You have already booked ${cfg.name} from this phone.`);
    return;
  }

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
    const room = roomNumberInput ? roomNumberInput.value.trim().toUpperCase() : '';

    if (!name) {
      studentNameInput.focus();
      return;
    }

    if (!room) {
      if (selectionError) {
        selectionError.classList.remove('hidden');
        selectionError.textContent = 'Please enter your Room Number.';
      }
      roomNumberInput.focus();
      return;
    }

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

    // Device lock check
    for (const mealKey of selectedMeals) {
      if (isBookedOnThisDevice(mealKey)) {
        if (selectionError) {
          selectionError.classList.remove('hidden');
          selectionError.textContent = `You have already reserved ${MEAL_CONFIG[mealKey].name} from this phone.`;
          selectionError.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        return;
      }
    }

    if (selectionError) selectionError.classList.add('hidden');

    submitBtn.disabled = true;
    submitBtn.textContent = 'Verifying & Saving...';

    try {
      const devId = getOrCreateDeviceId();
      const response = await fetch(`${API_BASE}/api/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_name: name,
          room_number: room,
          device_id: devId,
          meals: selectedMeals
        })
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Failed to save booking.');
      }

      // Record device lock on this phone
      for (const entry of result.created) {
        saveDeviceBooking(entry.meal_type, name, room, entry.meal_date);
      }

      showSuccessState(name, room, result.created);
    } catch (err) {
      console.error('Booking submission error:', err);
      if (selectionError) {
        selectionError.classList.remove('hidden');
        selectionError.textContent = err.message;
        selectionError.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        showToast(err.message);
      }
      submitBtn.disabled = false;
      submitBtn.textContent = 'Confirm Meal Booking';
    }
  });
}

function showSuccessState(studentName, roomNumber, createdEntries) {
  messOrderForm.classList.add('hidden');
  successCard.classList.remove('hidden');

  let entriesHtml = createdEntries.map(entry => `
    <div style="padding: 0.4rem 0; border-bottom: 1px solid #27272a;">
      <strong style="color:#ffffff;">${entry.meal_label}</strong> (${entry.target_label}): 
      <span style="color: #60a5fa; font-weight: 700;">${entry.meal_date}</span>
    </div>
  `).join('');

  submittedSummaryBox.innerHTML = `
    <div style="margin-bottom:0.35rem;"><strong>Student:</strong> ${escapeHtml(studentName)}</div>
    <div style="margin-bottom:0.35rem;"><strong>Room:</strong> <span style="color:#60a5fa; font-weight:800; font-size:1.05rem;">${escapeHtml(roomNumber)}</span></div>
    <div style="margin-top: 0.5rem;">
      ${entriesHtml}
    </div>
    <div style="margin-top:0.65rem; font-size:0.78rem; color:#94a3b8; border-top:1px dashed #27272a; padding-top:0.45rem;">
      Your room reservation is saved in the kitchen database. Extra bookings from this device are locked for this date.
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
  fetchServerStatus();
};

function showToast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  setTimeout(() => {
    toastEl.classList.remove('show');
  }, 3200);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}
