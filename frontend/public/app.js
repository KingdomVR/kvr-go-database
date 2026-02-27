async function postJSON(path, data){
  const res = await fetch(path, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
  if(!res.ok) { const t = await res.json().catch(()=>null); throw t || { error: 'request failed' }; }
  return res.json();
}

function el(id){ return document.getElementById(id); }

const loginForm = el('loginForm');
const loginSection = el('loginSection');
const dashboard = el('dashboard');
const userGreeting = el('userGreeting');
const balanceEl = el('balance');
const chessPointsEl = el('chessPoints');
const leaderboardEl = el('leaderboard');
let currentUser = null;

loginForm.onsubmit = async (ev)=>{
  ev.preventDefault();
  const fd = new FormData(loginForm);
  const username = fd.get('username');
  const pin = fd.get('pin');
  try{
    await postJSON('/api/login', { username, pin });
    await loadMe();
    loginSection.classList.add('hidden');
    dashboard.classList.remove('hidden');
  }catch(e){ alert(e && e.error ? JSON.stringify(e) : 'Login failed'); }
};

async function loadMe(){
  const res = await fetch('/api/me');
  if(!res.ok){
    // propagate an error so callers know load failed (e.g. not authenticated)
    const body = await res.json().catch(()=>null);
    const err = new Error('Not authenticated');
    err.status = res.status;
    err.body = body;
    throw err;
  }
  const me = await res.json();
  currentUser = me.username;
  userGreeting.textContent = `Hello, ${me.username}`;
  balanceEl.innerHTML = `<span class="kcoin-amount"><span class="kcoin-icon">🪙</span>${Number(me.kvrcoin || 0).toFixed(2)}</span>`;
  const _k = balanceEl.querySelector('.kcoin-amount');
  if(_k){ _k.classList.add('pulse'); setTimeout(()=>_k.classList.remove('pulse'), 1400); }
  chessPointsEl.textContent = Number(me.chess_points || 0);
  await loadLeaderboard();
  return me;
}

el('logoutBtn').onclick = async ()=>{ await postJSON('/api/logout', {}); dashboard.classList.add('hidden'); loginSection.classList.remove('hidden'); };

el('transferForm').onsubmit = async (ev)=>{
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const to = fd.get('to');
  const amount = Number(fd.get('amount'));
  try{
    const res = await postJSON('/api/transfer', { to, amount });
    await loadMe();
    ev.target.reset();
    alert('Transfer successful');
  }catch(e){ alert(e && e.error ? JSON.stringify(e) : 'Transfer failed'); }
};

// Modal change PIN flow
const modalOverlay = el('modalOverlay');
const openChangePin = el('openChangePin');
const cancelModal = el('cancelModal');
const changePinModalForm = el('changePinModalForm');

function openModal(){ modalOverlay.classList.remove('hidden'); modalOverlay.setAttribute('aria-hidden','false'); const inp = changePinModalForm.querySelector('input[name=new_pin]'); inp.focus(); inp.select(); }
function closeModal(){ modalOverlay.classList.add('hidden'); modalOverlay.setAttribute('aria-hidden','true'); changePinModalForm.reset(); }

openChangePin.onclick = openModal;
cancelModal.onclick = closeModal;

changePinModalForm.onsubmit = async (ev)=>{
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const new_pin = fd.get('new_pin');
  const confirm_pin = fd.get('confirm_pin');
  const old_pin = fd.get('old_pin');
  if(!new_pin || !confirm_pin){ alert('Please provide PIN in both fields'); return; }
  if(new_pin !== confirm_pin){ alert('PINs do not match'); return; }
  try{
    await postJSON('/api/change-pin', { new_pin: new_pin, old_pin: old_pin });
    alert('PIN changed');
    closeModal();
    await loadMe();
  }catch(e){ alert(e && e.error ? JSON.stringify(e) : 'Change PIN failed'); }
};

async function loadLeaderboard(){
  try{
    // Note: backend doesn't support "around-user" queries, so fetch leaderboard
    // and slice around the current user client-side.
    const lb = await fetch('/api/chess/leaderboard').then(r=>r.json());
    leaderboardEl.innerHTML = '';
    if(!Array.isArray(lb) || lb.length === 0){ leaderboardEl.textContent = 'No leaderboard data'; return; }

    // Find current user's index
    const idx = currentUser ? lb.findIndex(r => r.username === currentUser) : -1;
    let start = 0, end = Math.min(lb.length, 5);
    if(idx >= 0){
      start = Math.max(0, idx - 2);
      end = Math.min(lb.length, idx + 3);
      // adjust to ensure we show 5 items when possible
      if(end - start < 5){
        if(start === 0) end = Math.min(lb.length, start + 5);
        else if(end === lb.length) start = Math.max(0, end - 5);
      }
    }

    for(let i = start; i < end; i++){
      const row = lb[i];
      const li = document.createElement('li');
      li.className = (row.username === currentUser) ? 'current-user' : '';
      const rank = i + 1;
      li.innerHTML = `<div><strong>#${rank}</strong> ${row.username}</div><div class="small">${row.chess_points}</div>`;
      leaderboardEl.appendChild(li);
    }
  }catch(e){ console.error('lb', e); }
}

el('refreshLeaderboard').onclick = loadLeaderboard;

// Try to auto-load session
(async ()=>{
  try{
    await loadMe();
    loginSection.classList.add('hidden');
    dashboard.classList.remove('hidden');
  }catch(e){
    // not authenticated — keep login visible
    console.log('No active session');
  }
})();
