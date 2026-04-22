import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { format, differenceInDays, isPast } from 'date-fns';
import './App.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:5001';
const api = axios.create({ baseURL: API });

function parseAmount(s) {
  if (!s) return 0;
  const m = s.replace(/,/g, '').match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
}

function estimatePayoutNum(s) {
  const total = parseAmount(s);
  if (total < 1000) return 0;
  const net = total * 0.7;
  const cls = total >= 100e6 ? 200000 : total >= 50e6 ? 100000 : total >= 10e6 ? 30000 : 5000;
  return Math.round(net / cls);
}

function estimatePayout(s) {
  const pp = estimatePayoutNum(s);
  if (pp < 10) return null;
  return `$${Math.round(pp * 0.5).toLocaleString()} – $${Math.round(pp * 2).toLocaleString()}`;
}

function extractState(court) {
  if (!court) return 'National';
  const c = court.toLowerCase();
  // Check for state abbreviations in parentheses first: "Federal Court of Australia (NSW)"
  const m = c.match(/\((nsw|vic|qld|wa|sa|tas|act|nt)\)/);
  if (m) return m[1].toUpperCase();
  if (c.includes('nsw') || c.includes('new south wales')) return 'NSW';
  if (c.includes('vic') || c.includes('victoria')) return 'VIC';
  if (c.includes('qld') || c.includes('queensland')) return 'QLD';
  if (c.includes('western australia') || /\bwa\b/.test(c)) return 'WA';
  if (c.includes('south australia') || /\bsa\b/.test(c)) return 'SA';
  if (c.includes('tas') || c.includes('tasmania')) return 'TAS';
  if (c.includes('act') || c.includes('australian capital')) return 'ACT';
  if (c.includes('nt') || c.includes('northern territory')) return 'NT';
  return 'National';
}

const SORT_OPTIONS = [
  { value: 'default', label: 'Default' },
  { value: 'payout-desc', label: 'Payout: High to Low' },
  { value: 'settlement-desc', label: 'Settlement: High to Low' },
  { value: 'deadline-asc', label: 'Deadline: Soonest' },
  { value: 'state', label: 'State / Court' },
  { value: 'status', label: 'Status' },
  { value: 'law-firm', label: 'Law Firm' },
];

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(null);
  const [view, setView] = useState(localStorage.getItem('token') ? 'cases' : 'landing');
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [answers, setAnswers] = useState({});
  const [submitResult, setSubmitResult] = useState(null);
  const [myResults, setMyResults] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authForm, setAuthForm] = useState({ email: '', password: '', name: '' });
  const [showArchived, setShowArchived] = useState(false);
  const [sortBy, setSortBy] = useState('default');
  const [filterState, setFilterState] = useState('');

  // Quiz state
  const [quiz, setQuiz] = useState(null);
  const [quizIndex, setQuizIndex] = useState(0);
  const [stats, setStats] = useState(null);
  const [showUpgrade, setShowUpgrade] = useState(false);

  useEffect(() => {
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      localStorage.setItem('token', token);
    } else {
      delete api.defaults.headers.common['Authorization'];
      localStorage.removeItem('token');
    }
  }, [token]);

  useEffect(() => {
    api.get('/api/stats').then(r => setStats(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (token) {
      api.get('/api/auth/me').then(r => {
        setUser(r.data.user);
        if (!r.data.user.quiz_completed) {
          loadQuiz();
          setView('quiz');
        } else {
          setView('cases');
        }
      }).catch(() => { setToken(null); setUser(null); setView('landing'); });
    }
  }, [token]);

  const fetchCases = useCallback(async () => {
    try {
      setLoading(true);
      const params = search ? { search } : {};
      const r = await api.get('/api/class-actions', { params });
      setCases(r.data.cases);
      setError(null);
    } catch { setError('Failed to load cases. Is the backend running?'); }
    finally { setLoading(false); }
  }, [search]);

  useEffect(() => {
    const t = setTimeout(fetchCases, 300);
    return () => clearTimeout(t);
  }, [fetchCases]);

  const loadQuiz = async () => {
    try {
      const r = await api.get('/api/quiz');
      setQuiz(r.data);
      const firstUnanswered = r.data.items.findIndex(it => it.answer === null);
      setQuizIndex(firstUnanswered >= 0 ? firstUnanswered : r.data.items.length);
    } catch { /* non-critical */ }
  };

  const answerQuiz = async (caseId, answer) => {
    try {
      await api.post('/api/quiz/answer', { case_id: caseId, answer });
      if (answer === 'no') {
        try { await api.post(`/api/archive/${caseId}`); } catch {}
      }
      setQuiz(prev => {
        const items = prev.items.map(it =>
          it.case_id === caseId ? { ...it, answer } : it
        );
        return { ...prev, items, answered: items.filter(it => it.answer).length };
      });
      setQuizIndex(i => i + 1);
    } catch { setError('Failed to save answer'); }
  };

  const finishQuiz = async () => {
    try {
      await api.post('/api/quiz/complete');
      setUser(u => ({ ...u, quiz_completed: true }));
      setView('cases');
      fetchCases();
    } catch { setError('Failed to complete quiz'); }
  };

  const leaveQuiz = () => {
    setView('cases');
    fetchCases();
  };

  const handleAuth = async (e, isLogin) => {
    e.preventDefault(); setError(null);
    try {
      const endpoint = isLogin ? '/api/auth/login' : '/api/auth/register';
      const body = isLogin
        ? { email: authForm.email, password: authForm.password }
        : { email: authForm.email, password: authForm.password, name: authForm.name };
      const r = await api.post(endpoint, body);
      setToken(r.data.token); setUser(r.data.user);
      setAuthForm({ email: '', password: '', name: '' });
      if (!isLogin && !r.data.user.quiz_completed) {
        api.defaults.headers.common['Authorization'] = `Bearer ${r.data.token}`;
        loadQuiz();
        setView('quiz');
      } else if (r.data.user.quiz_completed) {
        setView('cases');
      } else {
        api.defaults.headers.common['Authorization'] = `Bearer ${r.data.token}`;
        loadQuiz();
        setView('quiz');
      }
      fetchCases();
    } catch (err) { setError(err.response?.data?.error || 'Failed'); }
  };

  const logout = () => { setToken(null); setUser(null); setQuiz(null); setView('landing'); };

  const handleUpgrade = async (plan) => {
    try {
      const r = await api.post('/api/billing/checkout', { plan });
      if (r.data.url) {
        window.location.href = r.data.url;
      } else {
        setError(r.data.error || 'Payment not available yet. Contact support.');
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Payment system not configured yet');
    }
  };

  const openCase = async (caseId) => {
    try {
      setLoading(true);
      const r = await api.get(`/api/class-actions/${caseId}`);
      setSelectedCase(r.data); setAnswers({}); setSubmitResult(null); setView('case-detail');
      if (r.data.user_answers) {
        setAnswers(r.data.user_answers);
        setSubmitResult({
          is_eligible: r.data.user_eligible, claim_portal_url: r.data.claim_portal_url,
          law_firm: r.data.law_firm, law_firm_contact: r.data.law_firm_contact,
          law_firm_website: r.data.law_firm_website, settlement_amount: r.data.settlement_amount,
        });
      }
    } catch { setError('Failed to load case details'); }
    finally { setLoading(false); }
  };

  // Answer a question — check immediately if the answer disqualifies
  const answerQuestion = (questionId, value) => {
    const newAnswers = { ...answers, [String(questionId)]: value };
    setAnswers(newAnswers);

    // If the user picked a disqualifying answer (not "not_sure"), auto-submit
    if (value !== 'not_sure' && selectedCase?.questions) {
      const q = selectedCase.questions.find(q => q.id === questionId);
      if (q) {
        const userBool = value === true || value === 'yes';
        if (userBool !== q.required_answer) {
          // Fill remaining unanswered questions with null-safe defaults, then submit
          const fullAnswers = {};
          for (const sq of selectedCase.questions) {
            const existing = newAnswers[String(sq.id)];
            if (existing !== undefined) {
              fullAnswers[String(sq.id)] = existing === 'not_sure' ? true : existing;
            } else {
              // Fill with opposite of required to not affect the result
              fullAnswers[String(sq.id)] = !sq.required_answer;
            }
          }
          submitWithAnswers(fullAnswers, false);
          return;
        }
      }
    }
  };

  const submitWithAnswers = async (processedAnswers, isEligible) => {
    if (!user) { setView('login'); return; }
    try {
      setLoading(true);
      const r = await api.post(`/api/class-actions/${selectedCase.id}/submit`, { answers: processedAnswers });
      r.data.settlement_amount = selectedCase.settlement_amount;
      setSubmitResult(r.data);
      setUser(u => ({ ...u, checks_remaining: (u.checks_remaining || 0) - (u.is_premium ? 0 : 1) }));
      if (!r.data.is_eligible) {
        try { await api.post(`/api/archive/${selectedCase.id}`); } catch {}
      }
      fetchCases();
    } catch (err) {
      if (err.response?.data?.error === 'upgrade_required') {
        setShowUpgrade(true);
      } else {
        setError(err.response?.data?.error || 'Failed');
      }
    }
    finally { setLoading(false); }
  };

  const submitEligibility = async () => {
    if (!user) { setView('login'); return; }
    const sa = {};
    for (const [k, v] of Object.entries(answers)) sa[k] = v === 'not_sure' ? true : v;
    try {
      setLoading(true);
      const r = await api.post(`/api/class-actions/${selectedCase.id}/submit`, { answers: sa });
      r.data.settlement_amount = selectedCase.settlement_amount;
      setSubmitResult(r.data);
      setUser(u => ({ ...u, checks_remaining: (u.checks_remaining || 0) - (u.is_premium ? 0 : 1) }));
      if (!r.data.is_eligible) {
        try { await api.post(`/api/archive/${selectedCase.id}`); } catch {}
      }
      fetchCases();
    } catch (err) {
      if (err.response?.data?.error === 'upgrade_required') {
        setShowUpgrade(true);
      } else {
        setError(err.response?.data?.error || 'Failed');
      }
    }
    finally { setLoading(false); }
  };

  const toggleArchive = async (caseId, isArchived) => {
    try {
      if (isArchived) {
        await api.delete(`/api/archive/${caseId}`);
      } else {
        await api.post(`/api/archive/${caseId}`);
      }
      fetchCases();
    } catch { setError('Failed to update archive'); }
  };

  const loadMyResults = async () => {
    try {
      setLoading(true);
      const r = await api.get('/api/my-results');
      setMyResults(r.data.results); setView('my-results');
    } catch { setError('Failed to load results'); }
    finally { setLoading(false); }
  };

  const allQA = selectedCase?.questions?.every(q => answers[String(q.id)] !== undefined);
  const hasNotSure = Object.values(answers).some(v => v === 'not_sure');
  const archivedCount = cases.filter(c => c.archived).length;

  // Available states for filter
  const availableStates = [...new Set(cases.map(c => extractState(c.court)))].sort();

  // Filter then sort
  const visibleCases = cases
    .filter(c => showArchived || !c.archived)
    .filter(c => !filterState || extractState(c.court) === filterState)
    .sort((a, b) => {
      switch (sortBy) {
        case 'payout-desc': return estimatePayoutNum(b.settlement_amount) - estimatePayoutNum(a.settlement_amount);
        case 'settlement-desc': return parseAmount(b.settlement_amount) - parseAmount(a.settlement_amount);
        case 'deadline-asc': {
          const da = a.claim_deadline ? new Date(a.claim_deadline).getTime() : Infinity;
          const db = b.claim_deadline ? new Date(b.claim_deadline).getTime() : Infinity;
          return da - db;
        }
        case 'state': return extractState(a.court).localeCompare(extractState(b.court));
        case 'status': {
          const order = { 'Active': 0, 'Settlement Pending': 1, 'Settlement Approved': 2, 'Closed': 3 };
          return (order[a.status] ?? 9) - (order[b.status] ?? 9);
        }
        case 'law-firm': return (a.law_firm || '').localeCompare(b.law_firm || '');
        default: return 0;
      }
    });

  const fmtDl = (dl) => {
    if (!dl) return null;
    const d = new Date(dl);
    if (isPast(d)) return { text: 'Expired', cls: 'deadline-expired' };
    const days = differenceInDays(d, new Date());
    if (days <= 30) return { text: `${days}d left`, cls: 'deadline-urgent' };
    return { text: format(d, 'dd MMM yyyy'), cls: 'deadline-normal' };
  };

  const sb = (s) => s === 'Active' ? 'active' : s === 'Settlement Approved' ? 'settled' : 'pending';

  return (
    <div className="app">
      <header className="header">
        <div className="container header-inner">
          <div className="header-left" onClick={() => { if (!user) { setView('landing'); } else if (user?.quiz_completed !== false) { setView('cases'); setSubmitResult(null); }}} style={{cursor:'pointer'}}>
            <h1>Settle<span>Care</span></h1>
            <p>Check if you're eligible for class action settlements</p>
          </div>
          <div className="header-right">
            {user ? (
              <>
                {user.is_premium && <span className="badge badge-premium">PRO</span>}
                {user && !user.quiz_completed && view !== 'quiz' && (
                  <button className="btn btn-resume" onClick={() => { loadQuiz(); setView('quiz'); }}>Resume Quiz</button>
                )}
                <span className="user-name">{user.name || user.email}</span>
                {!user.is_premium && <button className="btn btn-sm btn-upgrade" onClick={() => setShowUpgrade(true)}>Upgrade</button>}
                <button className="btn btn-sm btn-ghost" onClick={loadMyResults}>Results</button>
                <button className="btn btn-sm btn-ghost" onClick={logout}>Logout</button>
              </>
            ) : (
              <>
                <button className="btn btn-sm btn-ghost" onClick={() => { setView('login'); setError(null); }}>Log In</button>
                <button className="btn btn-sm btn-primary" onClick={() => { setView('signup'); setError(null); }}>Sign Up</button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className={view === 'landing' ? 'main-landing' : 'container main'}>
        {error && (
          <div className="error-banner" style={view === 'landing' ? {maxWidth: 900, margin: '0 auto 20px', padding: '12px 24px'} : {}}>
            <p>{error}</p><button onClick={() => setError(null)}>Dismiss</button>
          </div>
        )}

        {/* ─── UPGRADE MODAL ─── */}
        {showUpgrade && (
          <div className="modal-overlay" onClick={() => setShowUpgrade(false)}>
            <div className="modal upgrade-modal" onClick={e => e.stopPropagation()}>
              <button className="modal-close" onClick={() => setShowUpgrade(false)}>&times;</button>
              <div className="upgrade-icon">&#9733;</div>
              <h2>Upgrade to Premium</h2>
              <p>You've used all 3 free eligibility checks. Upgrade to unlock unlimited checks and priority alerts.</p>
              <div className="pricing-cards-sm">
                <div className="price-card-sm">
                  <span className="price-label">Monthly</span>
                  <span className="price-amount">$4.99<span>/mo</span></span>
                  <button className="btn btn-primary btn-full" onClick={() => handleUpgrade('monthly')}>Subscribe Monthly</button>
                </div>
                <div className="price-card-sm best-value">
                  <span className="best-tag">Save 50%</span>
                  <span className="price-label">Yearly</span>
                  <span className="price-amount">$29.99<span>/yr</span></span>
                  <button className="btn btn-primary btn-full" onClick={() => handleUpgrade('yearly')}>Subscribe Yearly</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ─── LANDING PAGE ─── */}
        {view === 'landing' && (
          <div className="landing">
            <section className="hero">
              <div className="hero-inner">
                <span className="hero-tag">Australian Class Action Settlements</span>
                <h1>You could be owed money.<br/>Find out in <span>60 seconds</span>.</h1>
                <p>Millions of Australians are eligible for class action payouts and don't even know it. SettleCare scans {stats?.total_cases || '70'}+ active settlements and matches you with ones you qualify for.</p>
                <div className="hero-btns">
                  <button className="btn btn-primary btn-lg" onClick={() => setView('signup')}>Check My Eligibility &mdash; Free</button>
                  <button className="btn btn-white btn-lg" onClick={() => setView('login')}>Log In</button>
                </div>
                <p className="hero-sub">Free to start. No credit card required.</p>
              </div>
            </section>

            <section className="stats-bar">
              <div className="stats-inner">
                <div className="stat"><span className="stat-num">{stats?.total_cases || '76'}</span><span className="stat-label">Settlements Tracked</span></div>
                <div className="stat"><span className="stat-num">{stats?.active_cases || '40'}+</span><span className="stat-label">Active Right Now</span></div>
                <div className="stat"><span className="stat-num">$2B+</span><span className="stat-label">Total Settlements</span></div>
                <div className="stat"><span className="stat-num">{stats?.total_users || '0'}</span><span className="stat-label">Users Checking</span></div>
              </div>
            </section>

            <section className="how-it-works">
              <div className="hiw-inner">
                <h2>How SettleCare Works</h2>
                <div className="hiw-steps">
                  <div className="hiw-step">
                    <div className="hiw-num">1</div>
                    <h3>Quick Screen</h3>
                    <p>Answer one question per case. Takes 2 minutes to scan all active settlements.</p>
                  </div>
                  <div className="hiw-step">
                    <div className="hiw-num">2</div>
                    <h3>Eligibility Check</h3>
                    <p>For matches, answer a few more questions. Instant result — eligible or not.</p>
                  </div>
                  <div className="hiw-step">
                    <div className="hiw-num">3</div>
                    <h3>Claim Your Money</h3>
                    <p>We connect you directly to the official claim portal. No middleman.</p>
                  </div>
                </div>
              </div>
            </section>

            <section className="pricing">
              <div className="pricing-inner">
                <h2>Simple Pricing</h2>
                <p className="pricing-sub">Start free. Upgrade when you need more.</p>
                <div className="pricing-cards">
                  <div className="price-card">
                    <h3>Free</h3>
                    <div className="price">$0</div>
                    <ul>
                      <li>Browse all settlements</li>
                      <li>Quick screening quiz</li>
                      <li>3 full eligibility checks</li>
                      <li>Direct claim portal links</li>
                    </ul>
                    <button className="btn btn-outline btn-full" onClick={() => setView('signup')}>Get Started Free</button>
                  </div>
                  <div className="price-card price-card-premium">
                    <span className="popular-tag">Most Popular</span>
                    <h3>Premium</h3>
                    <div className="price">$4.99<span>/mo</span></div>
                    <ul>
                      <li>Everything in Free</li>
                      <li>Unlimited eligibility checks</li>
                      <li>New settlement email alerts</li>
                      <li>Priority support</li>
                      <li>Early access to new features</li>
                    </ul>
                    <button className="btn btn-primary btn-full" onClick={() => setView('signup')}>Start Free, Upgrade Anytime</button>
                  </div>
                  <div className="price-card">
                    <h3>Yearly</h3>
                    <div className="price">$29.99<span>/yr</span></div>
                    <p className="save-note">Save 50% vs monthly</p>
                    <ul>
                      <li>Everything in Premium</li>
                      <li>Best value</li>
                      <li>Lock in price for 12 months</li>
                    </ul>
                    <button className="btn btn-outline btn-full" onClick={() => setView('signup')}>Start Free, Upgrade Anytime</button>
                  </div>
                </div>
              </div>
            </section>

            <section className="social-proof">
              <div className="sp-inner">
                <h2>Trusted by Australians</h2>
                <div className="testimonials">
                  <div className="testimonial">
                    <p>"I had no idea I was eligible for the Optus settlement. SettleCare found it for me in under a minute. Got $340."</p>
                    <span>— Sarah M., Sydney</span>
                  </div>
                  <div className="testimonial">
                    <p>"Checked after the quiz and turns out I qualify for 3 different class actions. Incredible tool."</p>
                    <span>— James K., Melbourne</span>
                  </div>
                  <div className="testimonial">
                    <p>"Simple, clear, and actually useful. Way better than trying to Google class actions yourself."</p>
                    <span>— Priya T., Brisbane</span>
                  </div>
                </div>
              </div>
            </section>

            <section className="final-cta">
              <div className="cta-inner">
                <h2>Don't leave money on the table</h2>
                <p>New settlements are added weekly. Check now before deadlines pass.</p>
                <button className="btn btn-primary btn-lg" onClick={() => setView('signup')}>Check My Eligibility &mdash; Free</button>
              </div>
            </section>
          </div>
        )}

        {/* ─── AUTH ─── */}
        {(view === 'login' || view === 'signup') && (
          <div className="auth-card">
            <h2>{view === 'login' ? 'Log In' : 'Create Account'}</h2>
            <form onSubmit={e => handleAuth(e, view === 'login')}>
              {view === 'signup' && (
                <input type="text" placeholder="Your name" value={authForm.name}
                  onChange={e => setAuthForm(f => ({...f, name: e.target.value}))} />
              )}
              <input type="email" placeholder="Email" required value={authForm.email}
                onChange={e => setAuthForm(f => ({...f, email: e.target.value}))} />
              <input type="password" placeholder={view === 'signup' ? 'Password (min 6 chars)' : 'Password'}
                required minLength={view === 'signup' ? 6 : undefined} value={authForm.password}
                onChange={e => setAuthForm(f => ({...f, password: e.target.value}))} />
              <button type="submit" className="btn btn-primary btn-full">
                {view === 'login' ? 'Log In' : 'Create Account'}
              </button>
            </form>
            <p className="auth-switch">
              {view === 'login'
                ? <>Don't have an account? <button onClick={() => { setView('signup'); setError(null); }}>Sign up</button></>
                : <>Already have an account? <button onClick={() => { setView('login'); setError(null); }}>Log in</button></>}
            </p>
          </div>
        )}

        {/* ─── QUIZ ─── */}
        {view === 'quiz' && quiz && (
          <div className="quiz-container">
            <div className="quiz-header">
              <h2>Quick Eligibility Screen</h2>
              <p>Answer one question per case to quickly find which class actions might apply to you.</p>
              <div className="quiz-progress">
                <div className="quiz-progress-bar">
                  <div className="quiz-progress-fill" style={{width: `${Math.round((quiz.answered / quiz.total) * 100)}%`}} />
                </div>
                <span className="quiz-progress-text">{quiz.answered} / {quiz.total} ({Math.round((quiz.answered / quiz.total) * 100)}%)</span>
              </div>
            </div>

            {quizIndex < quiz.items.length ? (
              <div className="quiz-card">
                <div className="quiz-card-header">
                  <span className="quiz-case-num">Case {quizIndex + 1} of {quiz.total}</span>
                  <h3>{quiz.items[quizIndex].case_name}</h3>
                  <p className="quiz-defendant">vs {quiz.items[quizIndex].defendant}</p>
                  {quiz.items[quizIndex].settlement_amount && (
                    <span className="amount">{quiz.items[quizIndex].settlement_amount}</span>
                  )}
                </div>
                <div className="quiz-question">
                  <p>{quiz.items[quizIndex].question}</p>
                  <div className="q-buttons quiz-buttons">
                    <button className="q-btn q-btn-yes" onClick={() => answerQuiz(quiz.items[quizIndex].case_id, 'yes')}>Yes</button>
                    <button className="q-btn q-btn-no-btn" onClick={() => answerQuiz(quiz.items[quizIndex].case_id, 'no')}>No</button>
                    <button className="q-btn q-btn-unsure" onClick={() => answerQuiz(quiz.items[quizIndex].case_id, 'not_sure')}>Not Sure</button>
                  </div>
                </div>
                <div className="quiz-actions">
                  {quizIndex > 0 && <button className="btn btn-outline btn-sm" onClick={() => setQuizIndex(i => i - 1)}>&#8249; Previous</button>}
                  <button className="btn btn-ghost-dark btn-sm" onClick={() => setQuizIndex(i => i + 1)}>Skip</button>
                  <button className="btn btn-sm" style={{marginLeft:'auto'}} onClick={finishQuiz}>Finish &amp; browse cases</button>
                </div>
              </div>
            ) : (
              <div className="quiz-done">
                <div className="quiz-done-icon">&#10003;</div>
                <h3>Screening Complete!</h3>
                <p>You screened {quiz.answered} of {quiz.total} cases.
                  {quiz.items.filter(i => i.answer === 'yes').length > 0 && (
                    <> You said <strong>"Yes"</strong> to {quiz.items.filter(i => i.answer === 'yes').length} — open those to do the full eligibility check.</>
                  )}
                </p>
                <button className="btn btn-primary btn-lg" onClick={finishQuiz}>Browse All Cases</button>
              </div>
            )}

            <button className="quiz-leave" onClick={leaveQuiz}>
              Leave quiz &amp; come back later
            </button>
          </div>
        )}

        {/* ─── CASES LIST ─── */}
        {view === 'cases' && (
          <>
            <div className="search-section">
              <input type="text" className="search-input"
                placeholder="Search cases by name, company, or keyword..."
                value={search} onChange={e => setSearch(e.target.value)} />
              <div className="controls-row">
                <div className="controls-left">
                  <select className="sort-select" value={sortBy} onChange={e => setSortBy(e.target.value)}>
                    {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <select className="sort-select" value={filterState} onChange={e => setFilterState(e.target.value)}>
                    <option value="">All States</option>
                    {availableStates.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="controls-right">
                  <span className="case-count">{visibleCases.length} case{visibleCases.length !== 1 ? 's' : ''}</span>
                  {user && archivedCount > 0 && (
                    <button className="btn-link" onClick={() => setShowArchived(!showArchived)}>
                      {showArchived ? 'Hide' : 'Show'} {archivedCount} archived
                    </button>
                  )}
                </div>
              </div>
            </div>

            {loading && cases.length === 0 ? (
              <div className="loading"><div className="spinner" /><p>Loading cases...</p></div>
            ) : (
              <div className="cases-list">
                {visibleCases.map(c => {
                  const dl = fmtDl(c.claim_deadline);
                  const pay = estimatePayout(c.settlement_amount);
                  return (
                    <div key={c.id} className={`case-row ${c.archived ? 'case-row-archived' : ''}`} onClick={() => openCase(c.id)}>
                      <div className="case-row-main">
                        <div className="case-row-top">
                          <span className={`badge badge-${sb(c.status)}`}>{c.status}</span>
                          {c.user_checked ? (
                            <span className={`badge ${c.user_eligible ? 'badge-eligible' : 'badge-ineligible'}`}>
                              {c.user_eligible ? 'You may be eligible' : 'Not eligible'}
                            </span>
                          ) : user && (
                            <span className="badge badge-check-now">Check Now</span>
                          )}
                          {c.archived && <span className="badge badge-archived">Archived</span>}
                          {dl && <span className={`deadline-tag ${dl.cls}`}>{dl.text}</span>}
                        </div>
                        <h3>{c.case_name}</h3>
                        <p className="case-row-defendant">vs {c.defendant}</p>
                        <p className="case-row-desc">{c.description?.substring(0, 180)}...</p>
                        <div className="case-row-meta">
                          {c.settlement_amount && <span className="amount">{c.settlement_amount}</span>}
                          {pay && <span className="payout-est">Est. per person: {pay}*</span>}
                          {c.law_firm && <span>{c.law_firm}</span>}
                          <span className="meta-state">{extractState(c.court)}</span>
                        </div>
                      </div>
                      <div className="case-row-side">
                        {user && (
                          <button className="archive-btn" title={c.archived ? 'Unarchive' : 'Archive'}
                            onClick={(e) => { e.stopPropagation(); toggleArchive(c.id, c.archived); }}>
                            {c.archived ? '↩' : '✕'}
                          </button>
                        )}
                        <div className="case-row-arrow">&#8250;</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ─── CASE DETAIL ─── */}
        {view === 'case-detail' && selectedCase && (
          <div className="case-detail">
            <button className="back-btn" onClick={() => { setView('cases'); setSubmitResult(null); }}>&#8249; Back to all cases</button>
            <div className="case-detail-header">
              <span className={`badge badge-${sb(selectedCase.status)}`}>{selectedCase.status}</span>
              <h2>{selectedCase.case_name}</h2>
              <p className="file-number">{selectedCase.file_number} &middot; {selectedCase.court}</p>
            </div>
            <div className="case-detail-grid">
              <div className="case-info">
                <div className="info-row"><label>Defendant</label><p>{selectedCase.defendant}</p></div>
                {selectedCase.applicant && <div className="info-row"><label>Applicant</label><p>{selectedCase.applicant}</p></div>}
                {selectedCase.settlement_amount && (
                  <div className="info-row">
                    <label>Total Settlement</label>
                    <p className="amount">{selectedCase.settlement_amount}</p>
                    {estimatePayout(selectedCase.settlement_amount) && (
                      <p className="payout-estimate">Estimated per person: <strong>{estimatePayout(selectedCase.settlement_amount)}</strong></p>
                    )}
                  </div>
                )}
                {selectedCase.claim_deadline && (
                  <div className="info-row"><label>Claim Deadline</label><p>{format(new Date(selectedCase.claim_deadline), 'dd MMMM yyyy')}</p></div>
                )}
                <div className="info-section"><h4>About this case</h4><p>{selectedCase.description}</p></div>
                {selectedCase.eligibility_criteria && (
                  <div className="info-section"><h4>Who is eligible?</h4><p>{selectedCase.eligibility_criteria}</p></div>
                )}
                {estimatePayout(selectedCase.settlement_amount) && (
                  <div className="payout-disclaimer">*Estimated payout is purely speculative. Actual amounts may vary significantly. Not financial or legal advice.</div>
                )}
              </div>

              <div className="questionnaire">
                {submitResult ? (
                  <div className={`result-card ${submitResult.is_eligible ? 'result-eligible' : 'result-ineligible'}`}>
                    {submitResult.is_eligible ? (
                      <>
                        <div className="result-icon">&#10003;</div>
                        <h3>You may be eligible</h3>
                        <p>Based on your answers, you may qualify for this class action.</p>
                        {estimatePayout(submitResult.settlement_amount) && (
                          <div className="payout-highlight">
                            <span className="payout-label">Estimated individual payout</span>
                            <span className="payout-amount">{estimatePayout(submitResult.settlement_amount)}</span>
                            <span className="payout-note">*Speculative estimate only</span>
                          </div>
                        )}
                        <div className="law-firm-card">
                          <h4>{submitResult.law_firm}</h4>
                          {submitResult.law_firm_contact && <p>Phone: <strong>{submitResult.law_firm_contact}</strong></p>}
                          {submitResult.law_firm_website && (
                            <a href={submitResult.law_firm_website} target="_blank" rel="noopener noreferrer" className="btn btn-sm">Visit Law Firm</a>
                          )}
                        </div>
                        {submitResult.claim_portal_url && (
                          <a href={submitResult.claim_portal_url} target="_blank" rel="noopener noreferrer"
                            className="btn btn-primary btn-full btn-lg claim-btn">Go to Claim Portal &rarr;</a>
                        )}
                        {hasNotSure && <p className="not-sure-note">You answered "Not Sure" to some questions. Contact the law firm to confirm eligibility.</p>}
                      </>
                    ) : (
                      <>
                        <div className="result-icon result-icon-no">&#10007;</div>
                        <h3>Likely not eligible</h3>
                        <p>Based on your answers, you may not qualify. Contact the law firm if you disagree.</p>
                        {selectedCase.law_firm && <p className="contact-anyway">Contact {selectedCase.law_firm}: {selectedCase.law_firm_contact}</p>}
                        <button className="btn btn-outline btn-full" onClick={() => { setSubmitResult(null); setAnswers({}); }}>Retake</button>
                      </>
                    )}
                  </div>
                ) : (
                  <>
                    <h3>Check Your Eligibility</h3>
                    <p className="q-intro">Answer these questions to see if you may qualify.</p>
                    {user && !user.is_premium && (
                      <div className="checks-remaining">
                        <span>{user.checks_remaining} free check{user.checks_remaining !== 1 ? 's' : ''} remaining</span>
                        {user.checks_remaining <= 1 && <button className="btn btn-sm btn-upgrade" onClick={() => setShowUpgrade(true)}>Upgrade</button>}
                      </div>
                    )}
                    {!user && (
                      <div className="login-prompt">
                        <p>Log in to check eligibility and save results.</p>
                        <div className="login-prompt-btns">
                          <button className="btn btn-primary" onClick={() => setView('login')}>Log In</button>
                          <button className="btn btn-outline" onClick={() => setView('signup')}>Sign Up</button>
                        </div>
                      </div>
                    )}
                    {user && selectedCase.questions?.map((q, i) => (
                      <div key={q.id} className="question">
                        <p className="q-text"><span className="q-num">{i + 1}.</span> {q.question_text}</p>
                        <div className="q-buttons">
                          <button className={`q-btn q-btn-yes ${answers[String(q.id)] === true ? 'q-btn-selected' : ''}`}
                            onClick={() => answerQuestion(q.id, true)}>Yes</button>
                          <button className={`q-btn q-btn-no-btn ${answers[String(q.id)] === false ? 'q-btn-selected q-btn-no' : ''}`}
                            onClick={() => answerQuestion(q.id, false)}>No</button>
                          <button className={`q-btn q-btn-unsure ${answers[String(q.id)] === 'not_sure' ? 'q-btn-selected q-btn-maybe' : ''}`}
                            onClick={() => answerQuestion(q.id, 'not_sure')}>Not Sure</button>
                        </div>
                      </div>
                    ))}
                    {user && (
                      <button className="btn btn-primary btn-full btn-lg" disabled={!allQA || loading} onClick={submitEligibility}>
                        {loading ? 'Checking...' : 'Check My Eligibility'}
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ─── MY RESULTS ─── */}
        {view === 'my-results' && (
          <div className="my-results">
            <button className="back-btn" onClick={() => setView('cases')}>&#8249; Back to all cases</button>
            <h2>My Eligibility Results</h2>
            {myResults.length === 0 ? (
              <p className="empty">You haven't checked any cases yet.</p>
            ) : (
              <div className="results-list">
                {myResults.map(r => (
                  <div key={r.id} className={`result-row ${r.is_eligible ? 'result-row-eligible' : 'result-row-ineligible'}`}
                    onClick={() => openCase(r.class_action_id)}>
                    <div className="result-row-status">
                      {r.is_eligible ? <span className="result-check">&#10003;</span> : <span className="result-x">&#10007;</span>}
                    </div>
                    <div className="result-row-info">
                      <h4>{r.case?.case_name}</h4>
                      <p>vs {r.case?.defendant}</p>
                      {r.is_eligible && r.case?.settlement_amount && estimatePayout(r.case.settlement_amount) && (
                        <span className="result-payout">Est. payout: {estimatePayout(r.case.settlement_amount)}*</span>
                      )}
                      {r.is_eligible && r.case?.claim_portal_url && (
                        <a href={r.case.claim_portal_url} target="_blank" rel="noopener noreferrer"
                          onClick={e => e.stopPropagation()} className="result-claim-link">Go to Claim Portal &rarr;</a>
                      )}
                    </div>
                    <div className="result-row-badge">
                      <span className={r.is_eligible ? 'badge badge-eligible' : 'badge badge-ineligible'}>
                        {r.is_eligible ? 'Eligible' : 'Not Eligible'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="container">
          <p><strong>Disclaimer:</strong> SettleCare is informational only. Estimated payouts are speculative. Consult a qualified legal professional before acting.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
