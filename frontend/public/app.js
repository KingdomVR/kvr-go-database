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

loginForm.onsubmit = async (ev)=>{
  ev.preventDefault();
  const fd = new FormData(loginForm);
  const username = fd.get('username');
  const pin = Number(fd.get('pin'));
  try{
    await postJSON('/api/login', { username, pin });
    await loadMe();
    loginSection.classList.add('hidden');
    dashboard.classList.remove('hidden');
  }catch(e){ alert(e && e.error ? JSON.stringify(e) : 'Login failed'); }
};

async function loadMe(){
  try{
    const me = await fetch('/api/me').then(r=>r.json());
    userGreeting.textContent = `Hello, ${me.username}`;
    balanceEl.textContent = Number(me.kvrcoin).toFixed(2);
    chessPointsEl.textContent = Number(me.chess_points || 0);
    await loadLeaderboard();
  }catch(e){ console.error(e); }
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

el('changePinForm').onsubmit = async (ev)=>{
  ev.preventDefault();
  const fd = new FormData(ev.target);
  const new_pin = Number(fd.get('new_pin'));
  try{
    await postJSON('/api/change-pin', { new_pin });
    alert('PIN changed');
    ev.target.reset();
  }catch(e){ alert(e && e.error ? JSON.stringify(e) : 'Change PIN failed'); }
};

async function loadLeaderboard(){
  try{
    const lb = await fetch('/api/chess/leaderboard').then(r=>r.json());
    leaderboardEl.innerHTML = '';
    for(const row of lb){
      const li = document.createElement('li'); li.textContent = `${row.username}: ${row.chess_points}`; leaderboardEl.appendChild(li);
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
  }catch(e){ /* not signed in */ }
})();
