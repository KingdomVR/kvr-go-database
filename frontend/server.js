require('dotenv').config();
const express = require('express');
const session = require('express-session');
const fetch = require('node-fetch');
const path = require('path');
const cors = require('cors');

const app = express();
const PORT = process.env.FRONTEND_PORT || 3000;
const BACKEND = process.env.KVR_BACKEND_URL || 'http://localhost:5000';
const API_KEY = process.env.KVR_API_KEY || '';

if (!API_KEY) {
  console.warn('Warning: KVR_API_KEY not set. Frontend proxy will fail to contact backend without it.');
}

app.use(cors());
app.use(express.json());
app.use(session({
  secret: process.env.SESSION_SECRET || 'kvr-secret',
  resave: false,
  saveUninitialized: false,
  cookie: { secure: false }
}));

app.use(express.static(path.join(__dirname, 'public')));

function backendFetch(pathSuffix, opts = {}){
  const url = `${BACKEND}${pathSuffix}`;
  opts.headers = opts.headers || {};
  opts.headers['X-API-Key'] = API_KEY;
  if (opts.body && !opts.headers['Content-Type']){
    opts.headers['Content-Type'] = 'application/json';
  }
  return fetch(url, opts).then(async res => {
    const text = await res.text();
    let json = null;
    try{ json = text ? JSON.parse(text) : null; }catch(e){ json = { text }; }
    if(!res.ok){ const err = new Error('Backend error'); err.status = res.status; err.body = json; throw err; }
    return json;
  });
}

app.post('/api/login', async (req, res) => {
  const { username, pin } = req.body || {};
  if (!username || pin === undefined) return res.status(400).json({ error: 'username and pin required' });

  try{
    const user = await backendFetch(`/users/pin/${encodeURIComponent(pin)}`);
    if (!user || user.username !== username){
      return res.status(401).json({ error: 'Invalid username or pin' });
    }
    req.session.user = username;
    return res.json({ message: 'ok', user });
  }catch(err){
    if(err.status) return res.status(err.status).json(err.body || { error: 'backend' });
    return res.status(500).json({ error: err.message });
  }
});

app.post('/api/logout', (req, res) => {
  req.session.destroy(() => res.json({ message: 'logged out' }));
});

app.get('/api/me', async (req, res) => {
  const username = req.session.user;
  if(!username) return res.status(401).json({ error: 'not authenticated' });
  try{
    const user = await backendFetch(`/users/${encodeURIComponent(username)}`);
    return res.json(user);
  }catch(err){
    if(err.status) return res.status(err.status).json(err.body || { error: 'backend' });
    return res.status(500).json({ error: err.message });
  }
});

app.post('/api/transfer', async (req, res) => {
  const from = req.session.user;
  const { to, amount } = req.body || {};
  if(!from) return res.status(401).json({ error: 'not authenticated' });
  if(!to || amount === undefined) return res.status(400).json({ error: 'to and amount required' });
  const amt = Number(amount);
  if(isNaN(amt) || amt <= 0) return res.status(400).json({ error: 'invalid amount' });

  try{
    const sender = await backendFetch(`/users/${encodeURIComponent(from)}`);
    const receiver = await backendFetch(`/users/${encodeURIComponent(to)}`);
    if(Number(sender.kvrcoin) < amt) return res.status(400).json({ error: 'insufficient funds' });

    // Perform two PATCH requests
    await backendFetch(`/users/${encodeURIComponent(from)}`, { method: 'PATCH', body: JSON.stringify({ kvrcoin: Number(sender.kvrcoin) - amt }) });
    await backendFetch(`/users/${encodeURIComponent(to)}`, { method: 'PATCH', body: JSON.stringify({ kvrcoin: Number(receiver.kvrcoin) + amt }) });

    const updatedSender = await backendFetch(`/users/${encodeURIComponent(from)}`);
    return res.json({ message: 'ok', user: updatedSender });
  }catch(err){
    if(err.status) return res.status(err.status).json(err.body || { error: 'backend' });
    return res.status(500).json({ error: err.message });
  }
});

app.post('/api/change-pin', async (req, res) => {
  const username = req.session.user;
  const { new_pin, old_pin } = req.body || {};
  if(!username) return res.status(401).json({ error: 'not authenticated' });
  if(new_pin === undefined || old_pin === undefined) return res.status(400).json({ error: 'new_pin and old_pin required' });
  try{
    // verify old_pin matches the currently authenticated user
    const userByOldPin = await backendFetch(`/users/pin/${encodeURIComponent(old_pin)}`);
    if(!userByOldPin || userByOldPin.username !== username){
      return res.status(401).json({ error: 'Old PIN is incorrect' });
    }
    // proceed to update
    const updated = await backendFetch(`/users/${encodeURIComponent(username)}`, { method: 'PATCH', body: JSON.stringify({ pin: String(new_pin) }) });
    return res.json(updated);
  }catch(err){
    if(err.status) return res.status(err.status).json(err.body || { error: 'backend' });
    return res.status(500).json({ error: err.message });
  }
});

app.get('/api/chess/leaderboard', async (req, res) => {
  try{
    const lb = await backendFetch('/leaderboard/chess');
    return res.json(lb);
  }catch(err){
    if(err.status) return res.status(err.status).json(err.body || { error: 'backend' });
    return res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => console.log(`KVR Go frontend proxy listening on http://localhost:${PORT}`));
