// ========== CURRENCY & LOCALIZATION ==========
let currentCurrency = 'INR';

const formatCurrency = (val, currency = currentCurrency) => {
  const isNegative = val < 0;
  let absVal = Math.abs(val);
  
  let formatted = '';
  if (currency === 'INR') {
    if (absVal >= 10000000) {
      formatted = '₹' + (absVal / 10000000).toFixed(2) + 'Cr';
    } else if (absVal >= 100000) {
      formatted = '₹' + (absVal / 100000).toFixed(1) + 'L';
    } else {
      formatted = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits:0 }).format(absVal);
    }
  } else {
    // Other currencies
    formatted = new Intl.NumberFormat('en-US', { style: 'currency', currency: currency, maximumFractionDigits:0 }).format(absVal);
  }
  return isNegative ? '-' + formatted : formatted;
};

// Update Globals globally
const updateAllCurrencies = () => {
  document.querySelectorAll('[data-base]').forEach(el => {
    el.innerText = formatCurrency(parseFloat(el.getAttribute('data-base')));
  });
  renderLists();
};

const currencySelect = document.getElementById('currencySelect');
if(currencySelect) {
  currencySelect.addEventListener('change', (e) => {
    currentCurrency = e.target.value;
    updateAllCurrencies();
  });
}

// ========== MOBILE MENU & NAVBAR ==========
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  if(navbar) navbar.style.boxShadow = window.scrollY > 50 ? '0 4px 24px rgba(0,0,0,0.4)' : 'none';
});

const mobileBtn = document.getElementById('mobileMenuBtn');
const navLinks = document.getElementById('navLinks');
const navActions = document.getElementById('navActions');
if (mobileBtn && navLinks) {
  mobileBtn.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('active');
    if(navbar) navbar.classList.toggle('mobile-open', isOpen);
    if(navActions) navActions.classList.toggle('active', isOpen);
    mobileBtn.classList.toggle('open');
  });
  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('active');
      if(navActions) navActions.classList.remove('active');
      if(navbar) navbar.classList.remove('mobile-open');
      mobileBtn.classList.remove('open');
    });
  });
  window.addEventListener('resize', () => {
    if(window.innerWidth > 900) {
      navLinks.classList.remove('active');
      if(navActions) navActions.classList.remove('active');
      if(navbar) navbar.classList.remove('mobile-open');
      mobileBtn.classList.remove('open');
    }
  });
}

// Dashboard mobile toggle
const dashMenuBtn = document.getElementById('dashMenuBtn');
if (dashMenuBtn) {
  dashMenuBtn.addEventListener('click', () => {
    document.querySelector('.sidebar').classList.toggle('mobile-active');
  });
}
document.querySelectorAll('.sidebar-link').forEach(link=>{
  link.addEventListener('click',()=>{
    document.querySelectorAll('.sidebar-link').forEach(l=>l.classList.remove('active'));
    link.classList.add('active');
    if(window.innerWidth <= 900) {
      const sb = document.querySelector('.sidebar');
      if(sb) sb.classList.remove('mobile-active');
    }
  });
});

// ========== UPLOAD SIMULATION (Index.html) ==========
function triggerUploadMock() {
  const dIdle = document.getElementById('stateIdle');
  const dProc = document.getElementById('stateProcessing');
  const dSucc = document.getElementById('stateSuccess');
  const statusTxt = document.getElementById('mockStatusText');
  const progBar = document.getElementById('mockProgressBar');
  
  if(!dIdle) return;
  dIdle.classList.remove('active');
  dProc.classList.add('active');
  
  let p = 0;
  statusTxt.innerText = "Encrypting and uploading payload...";
  const intv = setInterval(() => {
    p += Math.random() * 15;
    if(p >= 30 && statusTxt.innerText.includes('uploading')) statusTxt.innerText = "Running layout OCR on bank PDF...";
    if(p >= 60 && statusTxt.innerText.includes('OCR')) statusTxt.innerText = "NLP merchant normalization in progress...";
    if(p >= 90 && statusTxt.innerText.includes('NLP')) statusTxt.innerText = "Calculating financial intelligence vectors...";
    
    if(p >= 100) {
      p = 100;
      clearInterval(intv);
      setTimeout(()=>{
        dProc.classList.remove('active');
        dSucc.classList.add('active');
      }, 500);
    }
    progBar.style.width = p + '%';
  }, 400);
}

// Drag functionality
const uploadBox = document.getElementById('uploadBox');
if(uploadBox) {
  uploadBox.addEventListener('dragover', e => { e.preventDefault(); uploadBox.style.borderColor = 'var(--primary)'; });
  uploadBox.addEventListener('dragleave', () => uploadBox.style.borderColor = '');
  uploadBox.addEventListener('drop', e => {
    e.preventDefault();
    triggerUploadMock();
  });
}

// ========== SUPABASE AUTH (Sign in with Google) ==========
// Public values (safe to ship). Do NOT put service_role or JWT secret in frontend.
const SUPABASE_URL = "https://tgmvethwaquialwxenld.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_QVxcf5DEQufi3bdpxlNtYg_aT9kI4o3";

let supabaseClient = null;
if (window.supabase && SUPABASE_URL && SUPABASE_ANON_KEY) {
  supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

const googleSignInBtn = document.getElementById("googleSignInBtn");
if (googleSignInBtn) {
  googleSignInBtn.addEventListener("click", async () => {
    if (!supabaseClient) {
      alert("Sign-in is not configured yet. Please set your Supabase URL and anon key on the frontend.");
      return;
    }
    try {
      const { error } = await supabaseClient.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: "https://lens-flow.shtar.space/auth/callback",
        },
      });
      if (error) {
        console.error("Google sign-in error", error);
        alert("Unable to start Google sign-in. Please try again.");
      }
    } catch (err) {
      console.error("Unexpected sign-in error", err);
      alert("Unexpected error during sign-in.");
    }
  });
}

// ========== DATA MOCKS FOR DASHBOARD ==========
const upiTxns = [
  {name: 'Swiggy/Zomato', subtitle: 'Food Delivery', amt: 8400, icon: '🍔'},
  {name: 'Zepto/Blinkit', subtitle: 'Quick Commerce', amt: 4200, icon: '🛒'},
  {name: 'Uber India', subtitle: 'Transport', amt: 2800, icon: '🚖'},
  {name: 'Scan & Pay (POS)', subtitle: 'Local Merchants', amt: 6400, icon: '📱'}
];

const emiList = [
  {name: 'Home Loan', subtitle: 'HDFC Bank', amt: 32000, icon: '🏠'},
  {name: 'Car Loan', subtitle: 'Kotak Mahindra', amt: 12500, icon: '🚗'},
  {name: 'Credit Card EMI', subtitle: 'iPhone 15', amt: 5600, icon: '📱'}
];

const leaks = [
  {title: "Duplicate OTT", desc: "You are paying for Netflix via direct card and Apple subs. Monthly loss detected.", impact: 799, sev: 'High', action: "Cancel Apple Sub"},
  {title: "Ghost Subscription", desc: "Cult.fit membership active but no gym visits tracked in 3 months.", impact: 1499, sev: 'Medium', action: "Pause Membership"},
  {title: "Impulse Spike", desc: "Weekend Swiggy orders jumped 40% vs Jan average.", impact: 3200, sev: 'Low', action: "Set Weekend Budget"}
];

const savingsArr = [
  {title: "Switch Broadband Plan", desc: "JioFiber ₹999 plan offers same speed as your current ₹1499 Airtel tier.", potential: 500, badge: "Quick Win"},
  {title: "Optimize Food Delivery", desc: "Cut 2 weekend orders to hit your emergency fund goal 1 month earlier.", potential: 1400, badge: "Lifestyle"},
  {title: "Excess Liquidity Sweep", desc: "₹62k sitting in 0% current account. Move to Sweep-in FD.", potential: 310, badge: "Long-term"}
];

const transactions = [
  {title: "Amazon India", sub: "Shopping · Credit Card", amt: -2499, icon: 'A'},
  {title: "Salary Imps", sub: "Company HR · HDFC Acct", amt: 145000, icon: 'S'},
  {title: "Swiggy Instamart", sub: "Groceries · UPI", amt: -421, icon: 'S'},
  {title: "Bescom Power", sub: "Utility · Auto-debit", amt: -1840, icon: 'B'},
  {title: "SIP Deduction", sub: "Mutual Funds · Auto-debit", amt: -15000, icon: 'M'}
];

const goals = [
  {name: "Emergency Fund", target: 500000, cur: 340000},
  {name: "Europe Trip '25", target: 300000, cur: 120000},
  {name: "New Laptop", target: 125000, cur: 105000}
];

const trendData = [
  {m: 'Sep', in: 135000, out: 85000}, {m: 'Oct', in: 135000, out: 92000},
  {m: 'Nov', in: 140000, out: 110000}, {m: 'Dec', in: 180000, out: 125000},
  {m: 'Jan', in: 145000, out: 81000}, {m: 'Feb', in: 145000, out: 82400}
];

// ========== DASHBOARD RENDERER ==========
function renderLists() {
  const upiEl = document.getElementById('upiList');
  if(upiEl) upiEl.innerHTML = upiTxns.map(t => `<div class="list-row"><div class="list-icon">${t.icon}</div><div class="list-info"><div class="list-title">${t.name}</div><div class="list-sub">${t.subtitle}</div></div><div class="list-val"><div class="list-amt">${formatCurrency(t.amt)}</div></div></div>`).join('');

  const emiEl = document.getElementById('emiList');
  if(emiEl) emiEl.innerHTML = emiList.map(t => `<div class="list-row"><div class="list-icon">${t.icon}</div><div class="list-info"><div class="list-title">${t.name}</div><div class="list-sub">${t.subtitle}</div></div><div class="list-val"><div class="list-amt text-red">-${formatCurrency(t.amt)}</div></div></div>`).join('');

  const lkEl = document.getElementById('leaksContainer');
  if(lkEl) lkEl.innerHTML = leaks.map(l => `<div class="insight-card"><div class="insight-top"><div class="insight-title">${l.title} <span class="badge ${l.sev==='High'?'badge-red':'badge-blue'}">${l.sev}</span></div><div class="insight-amt text-red">-${formatCurrency(l.impact)}/mo</div></div><div class="insight-desc">${l.desc}</div><div class="insight-action"><span class="text-muted">Requires 2 mins</span><button class="btn btn-outline btn-sm">${l.action}</button></div></div>`).join('');

  const savEl = document.getElementById('savingsContainer');
  if(savEl) savEl.innerHTML = savingsArr.map(s => `<div class="insight-card"><div class="insight-top"><div class="insight-title">${s.title}</div><div class="insight-amt text-green">+${formatCurrency(s.potential)}/mo</div></div><div class="insight-desc">${s.desc}</div><div class="insight-action"><span class="text-muted">${s.badge}</span><button class="btn btn-outline btn-sm">Mark Applied</button></div></div>`).join('');

  const gEl = document.getElementById('goalsContainer');
  if(gEl) gEl.innerHTML = goals.map(g => `<div style="margin-bottom:16px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px"><span>${g.name}</span><span style="font-weight:600">${formatCurrency(g.cur)} / ${formatCurrency(g.target)}</span></div><div class="progress-container" style="margin:0"><div class="progress-bar" style="width:${(g.cur/g.target)*100}%;background:var(--green)"></div></div></div>`).join('');

  const txEl = document.getElementById('txContainer');
  if(txEl) txEl.innerHTML = transactions.map(t => `<div class="list-row"><div class="list-icon" style="background:${t.amt>0?'var(--green-bg)':'var(--surface)'};color:${t.amt>0?'var(--green)':'var(--fg)'}">${t.icon}</div><div class="list-info"><div class="list-title">${t.title}</div><div class="list-sub">${t.sub}</div></div><div class="list-val"><div class="list-amt ${t.amt>0?'text-green':''}">${t.amt>0?'+':''}${formatCurrency(t.amt)}</div></div></div>`).join('');
}

// ========== CHARTS ==========
if(typeof Chart !== 'undefined') {
  Chart.defaults.color = '#a1a1aa';
  Chart.defaults.borderColor = 'hsla(0,0%,100%,0.1)';
  Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";

  const tCtx = document.getElementById('trendChart');
  if(tCtx) {
    new Chart(tCtx, {
      type:'line',
      data:{
        labels:trendData.map(t=>t.m),
        datasets:[
          {label:'Inflow',data:trendData.map(t=>t.in),borderColor:'hsl(142,70%,45%)',backgroundColor:'hsla(142,70%,45%,0.1)',fill:true,tension:.4,borderWidth:2},
          {label:'Outflow',data:trendData.map(t=>t.out),borderColor:'hsl(24,85%,50%)',backgroundColor:'hsla(24,85%,50%,0.1)',fill:true,tension:.4,borderWidth:2}
        ]
      },
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{ticks:{callback:v=>formatCurrency(v,'INR').replace('.0L','')},grid:{color:'hsla(0,0%,100%,0.05)'}},x:{grid:{display:false}}}}
    });
  }

  const bCtx = document.getElementById('burnChart');
  if(bCtx) {
    new Chart(bCtx, {
      type:'bar',
      data:{labels:['Days 1-10','Days 11-20','Days 21-30'],datasets:[{data:[62000, 15000, 5400],backgroundColor:'hsl(217,90%,60%)',borderRadius:4}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{display:false},x:{grid:{display:false}}}}
    });
  }

  const dCtx = document.getElementById('donutChart');
  if(dCtx) {
    new Chart(dCtx, {
      type:'doughnut',
      data:{labels:['Fixed (EMIs, Rent)','Variable (Food, Shop)'],datasets:[{data:[48200, 34200],backgroundColor:['hsl(24,85%,50%)','hsl(217,90%,60%)'],borderWidth:0}]},
      options:{responsive:true,maintainAspectRatio:false,cutout:'70%',plugins:{legend:{display:false}}}
    });
  }
}

// Initial render
updateAllCurrencies();
