// ========================================================
// Adarsh Dining Hall - Mobile-First Kitchen Manager Portal
// Live SQLite Database Sync • Zero Emojis • Navy Blue Theme
// ========================================================

const API_BASE = '';

// Date helpers
function getTodayIso() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDisplayDate(isoDateStr) {
  if (!isoDateStr) return '';
  const [y, m, d] = isoDateStr.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  return dateObj.toLocaleDateString([], { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
}

let currentBookings = [];
let currentViewingDate = getTodayIso();
let activeFilterTab = 'all';

// DOM Elements
const liveClockEl = document.getElementById('liveClock');
const adminDateFilter = document.getElementById('adminDateFilter');
const lblActiveViewDate = document.getElementById('lblActiveViewDate');
const managerSearchInput = document.getElementById('managerSearchInput');

// Tab Badges
const tabBadgeAll = document.getElementById('tabBadgeAll');
const tabBadgeTiffin = document.getElementById('tabBadgeTiffin');
const tabBadgeLunch = document.getElementById('tabBadgeLunch');
const tabBadgeDinner = document.getElementById('tabBadgeDinner');

// Sections
const sectionTiffin = document.getElementById('sectionTiffin');
const sectionLunch = document.getElementById('sectionLunch');
const sectionDinner = document.getElementById('sectionDinner');

// Total Counters
const tiffinTotalCount = document.getElementById('tiffinTotalCount');
const lunchTotalCount = document.getElementById('lunchTotalCount');
const dinnerTotalCount = document.getElementById('dinnerTotalCount');

// Lists
const listTiffin = document.getElementById('listTiffin');
const listLunch = document.getElementById('listLunch');
const listDinner = document.getElementById('listDinner');

// Empty Messages
const emptyTiffinMsg = document.getElementById('emptyTiffinMsg');
const emptyLunchMsg = document.getElementById('emptyLunchMsg');
const emptyDinnerMsg = document.getElementById('emptyDinnerMsg');

const toastEl = document.getElementById('toast');

// ========================================================
// Initializer
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  setupClock();
  initAdminDate();
  loadBookingsFromDb();

  // Background poller every 2.5 seconds
  setInterval(() => {
    loadBookingsFromDb(true);
  }, 2500);
});

function initAdminDate() {
  if (adminDateFilter && !adminDateFilter.value) {
    adminDateFilter.value = getTodayIso();
    currentViewingDate = adminDateFilter.value;
  }
}

// Live Clock
function setupClock() {
  const update = () => {
    const now = new Date();
    if (liveClockEl) {
      liveClockEl.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  };
  update();
  setInterval(update, 1000);
}

let isViewingActiveShift = true;

const lblTiffinTargetDate = document.getElementById('lblTiffinTargetDate');
const lblLunchTargetDate  = document.getElementById('lblLunchTargetDate');
const lblDinnerTargetDate = document.getElementById('lblDinnerTargetDate');

// Mobile Date Stepper
window.stepDate = function(offsetDays) {
  if (!adminDateFilter) return;
  isViewingActiveShift = false;
  const currentVal = adminDateFilter.value || getTodayIso();
  const [y, m, d] = currentVal.split('-').map(Number);
  const dateObj = new Date(y, m - 1, d);
  dateObj.setDate(dateObj.getDate() + offsetDays);

  const year = dateObj.getFullYear();
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  adminDateFilter.value = `${year}-${month}-${day}`;
  loadBookingsFromDb();
};

window.resetToCurrentDate = function() {
  if (!adminDateFilter) return;
  isViewingActiveShift = true;
  adminDateFilter.value = getTodayIso();
  loadBookingsFromDb();
};

// Segmented Tab Filter Switcher
window.setFilterTab = function(tabKey) {
  activeFilterTab = tabKey;
  ['all', 'tiffin', 'lunch', 'dinner'].forEach(k => {
    const btn = document.getElementById(`tab${k.charAt(0).toUpperCase() + k.slice(1)}`);
    if (btn) {
      btn.classList.toggle('active', k === tabKey);
    }
  });

  applyTabVisibility();
};

function applyTabVisibility() {
  if (sectionTiffin) {
    sectionTiffin.classList.toggle('hidden', activeFilterTab !== 'all' && activeFilterTab !== 'tiffin');
  }
  if (sectionLunch) {
    sectionLunch.classList.toggle('hidden', activeFilterTab !== 'all' && activeFilterTab !== 'lunch');
  }
  if (sectionDinner) {
    sectionDinner.classList.toggle('hidden', activeFilterTab !== 'all' && activeFilterTab !== 'dinner');
  }
}

// ========================================================
// Load from SQLite Backend
// ========================================================
window.loadBookingsFromDb = async function(isSilent = false) {
  let url = `${API_BASE}/api/bookings`;
  if (isViewingActiveShift) {
    url += '?view=active';
  } else {
    const selectedDate = adminDateFilter ? (adminDateFilter.value || getTodayIso()) : getTodayIso();
    currentViewingDate = selectedDate;
    url += `?date=${encodeURIComponent(selectedDate)}`;
  }

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('Database fetch failed');
    const data = await res.json();
    currentBookings = data.bookings || [];

    if (isViewingActiveShift) {
      if (lblActiveViewDate) {
        lblActiveViewDate.textContent = 'Active Shift (Live)';
      }
      if (lblTiffinTargetDate && data.tomorrow) {
        lblTiffinTargetDate.textContent = `Serving: Tomorrow (${formatDisplayDate(data.tomorrow)})`;
      }
      if (lblLunchTargetDate && data.today) {
        lblLunchTargetDate.textContent = `Serving: Today (${formatDisplayDate(data.today)})`;
      }
      if (lblDinnerTargetDate && data.today) {
        lblDinnerTargetDate.textContent = `Serving: Today (${formatDisplayDate(data.today)})`;
      }
    } else {
      const selectedDate = adminDateFilter ? adminDateFilter.value : getTodayIso();
      if (lblActiveViewDate) {
        lblActiveViewDate.textContent = formatDisplayDate(selectedDate);
      }
      const dateText = `Serving Date: ${formatDisplayDate(selectedDate)}`;
      if (lblTiffinTargetDate) lblTiffinTargetDate.textContent = dateText;
      if (lblLunchTargetDate) lblLunchTargetDate.textContent = dateText;
      if (lblDinnerTargetDate) lblDinnerTargetDate.textContent = dateText;
    }

    renderManagerDashboard();
  } catch (err) {
    if (!isSilent) {
      console.error('Error fetching bookings from database:', err);
      showToast('Could not sync with database. Reconnecting...');
    }
  }
};

// Render Mobile Student Lists
window.renderManagerDashboard = function() {
  const searchTerm = (managerSearchInput ? managerSearchInput.value : '').toLowerCase().trim();

  const filtered = currentBookings.filter(b => {
    if (!searchTerm) return true;
    const nameMatch = b.student_name && b.student_name.toLowerCase().includes(searchTerm);
    const roomMatch = b.room_number && b.room_number.toLowerCase().includes(searchTerm);
    return nameMatch || roomMatch;
  });

  const tiffinList = filtered.filter(b => b.meal_type === 'tiffin');
  const lunchList  = filtered.filter(b => b.meal_type === 'lunch');
  const dinnerList = filtered.filter(b => b.meal_type === 'dinner');

  // Update Counters & Badges
  if (tabBadgeAll) tabBadgeAll.textContent = filtered.length;
  if (tabBadgeTiffin) tabBadgeTiffin.textContent = tiffinList.length;
  if (tabBadgeLunch) tabBadgeLunch.textContent = lunchList.length;
  if (tabBadgeDinner) tabBadgeDinner.textContent = dinnerList.length;

  if (tiffinTotalCount) tiffinTotalCount.textContent = `${tiffinList.length} booked`;
  if (lunchTotalCount)  lunchTotalCount.textContent  = `${lunchList.length} booked`;
  if (dinnerTotalCount) dinnerTotalCount.textContent = `${dinnerList.length} booked`;

  renderStudentMobileList(tiffinList, listTiffin, emptyTiffinMsg);
  renderStudentMobileList(lunchList,  listLunch,  emptyLunchMsg);
  renderStudentMobileList(dinnerList, listDinner, emptyDinnerMsg);

  applyTabVisibility();
};

function renderStudentMobileList(list, listEl, emptyMsgEl) {
  if (!listEl) return;
  listEl.innerHTML = '';

  if (list.length === 0) {
    listEl.classList.add('hidden');
    if (emptyMsgEl) emptyMsgEl.classList.remove('hidden');
    return;
  }

  listEl.classList.remove('hidden');
  if (emptyMsgEl) emptyMsgEl.classList.add('hidden');

  list.forEach((entry, idx) => {
    const row = document.createElement('div');
    const isDone = Boolean(entry.is_done);
    row.className = `mobile-student-row ${isDone ? 'row-collected' : ''}`;
    const roomLabel = entry.room_number ? `Room ${escapeHtml(entry.room_number)}` : 'Room -';

    row.innerHTML = `
      <div class="mobile-student-left">
        <span class="student-sr-pill">${idx + 1}</span>
        <div class="student-details-wrap">
          <span class="student-room-badge">${roomLabel}</span>
          <span class="student-name-text">${escapeHtml(entry.student_name)}</span>
        </div>
      </div>
      <div class="row-actions-right">
        <button type="button" class="btn-delete-row" title="Cancel Booking & Unlock Student" onclick="event.stopPropagation(); deleteSingleBooking('${entry.id}', '${escapeHtml(entry.student_name)}')">&times;</button>
        <div class="student-done-btn ${isDone ? 'checked' : ''}" title="Mark Collected"></div>
      </div>
    `;

    // Tap anywhere on the row to toggle status
    row.addEventListener('click', () => {
      toggleDoneStatus(entry.id, !isDone);
    });

    listEl.appendChild(row);
  });
}

// Delete Single Booking & Unlock Student
window.deleteSingleBooking = async function(entryId, studentName) {
  if (!confirm(`Cancel booking for "${studentName}"? This will allow them to book again.`)) {
    return;
  }

  // Optimistic UI update
  currentBookings = currentBookings.filter(b => b.id !== entryId);
  renderManagerDashboard();

  try {
    const res = await fetch(`${API_BASE}/api/bookings/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: entryId })
    });
    if (!res.ok) throw new Error('Delete failed');
    showToast(`Removed "${studentName}". Student is now unlocked to re-book.`);
  } catch (err) {
    console.error('Failed to delete booking:', err);
    showToast('Failed to delete booking.');
    loadBookingsFromDb(true);
  }
};

// Toggle Done in SQLite Database
window.toggleDoneStatus = async function(entryId, targetState) {
  // Optimistic UI update
  const localItem = currentBookings.find(b => b.id === entryId);
  if (localItem) localItem.is_done = targetState ? 1 : 0;
  renderManagerDashboard();

  try {
    const res = await fetch(`${API_BASE}/api/bookings/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: entryId,
        is_done: targetState ? 1 : 0
      })
    });
    if (!res.ok) throw new Error('Toggle save failed');
  } catch (err) {
    console.error('Failed to update toggle in database:', err);
    showToast('Failed to update status on server.');
    loadBookingsFromDb(true);
  }
};

// Clear Database Records
window.clearDateBookings = async function() {
  const confirmMsg = isViewingActiveShift
    ? 'Are you sure you want to clear all active bookings (Tiffins for tomorrow, Lunch & Dinner for today)? Students will be unlocked to book again.'
    : `Are you sure you want to clear all records for ${formatDisplayDate(adminDateFilter.value)}? Students will be unlocked to book again.`;

  if (!confirm(confirmMsg)) {
    return;
  }

  try {
    const payload = isViewingActiveShift ? {} : { date: adminDateFilter.value };
    const res = await fetch(`${API_BASE}/api/bookings/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Clear failed');
    currentBookings = [];
    renderManagerDashboard();
    showToast('Records cleared. Students are now unlocked to book again.');
  } catch (err) {
    console.error('Failed to clear database records:', err);
    showToast('Error clearing records.');
  }
};

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'"]/g, 
    tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
  );
}

function showToast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  setTimeout(() => {
    toastEl.classList.remove('show');
  }, 2800);
}
