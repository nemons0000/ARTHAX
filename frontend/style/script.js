
document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const loadingScreen = document.getElementById('loadingScreen');
    const themeToggle = document.getElementById('themeToggle');
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    const navLinks = document.querySelectorAll('.nav-link');
    const userModal = document.getElementById('userModal');
    const userIdInput = document.getElementById('userIdInput');
    const setUserIdBtn = document.getElementById('setUserIdBtn');
    const toastContainer = document.getElementById('toastContainer');

    let userId = localStorage.getItem('artha_user_id');
    if (!userId) {
        userModal.classList.remove('hidden');
    }

    // Hide loading screen
    setTimeout(() => {
        loadingScreen.classList.add('fade-out');
    }, 800);

    // Theme toggle
    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        themeToggle.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
    });

    // Mobile nav toggle
    navToggle.addEventListener('click', () => {
        navMenu.classList.toggle('open');
    });

    // Smooth navigation
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = link.dataset.section;
            document.getElementById(target).scrollIntoView({ behavior: 'smooth' });
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            navMenu.classList.remove('open');
        });
    });

    // Set user ID
    setUserIdBtn.addEventListener('click', () => {
        const val = userIdInput.value.trim();
        if (val.length < 5) {
            showToast('Please enter a valid phone number', 'error');
            return;
        }
        userId = val;
        localStorage.setItem('artha_user_id', userId);
        userModal.classList.add('hidden');
        showToast('Welcome to Artha!', 'success');
    });

    /* API Calls */
    const analyzeBtn = document.getElementById('analyzeBtn');
    const spendingChart = document.getElementById('spendingChart');
    const spendingInsights = document.getElementById('spendingInsights');
    const chartPlaceholder = spendingChart.querySelector('.chart-placeholder');

    analyzeBtn.addEventListener('click', () => {
        if (!userId) return showToast('Please set your user ID first', 'error');
        chartPlaceholder.innerHTML = '<div class="loading-spinner"></div><p>Analyzing...</p>';

        fetch('/api/analyze_finances', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    showToast('Analysis completed', 'success');
                    renderSpendingChart(data.plot_image);
                    renderInsights(data.insights);
                } else {
                    showToast(data.message || 'Analysis failed', 'error');
                    chartPlaceholder.innerHTML = '<p>' + (data.message || 'Analysis failed') + '</p>';
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error', 'error');
                chartPlaceholder.innerHTML = '<p>Network error</p>';
            });
    });

    function renderSpendingChart(base64Image) {
        spendingChart.innerHTML = '<img src="data:image/png;base64,' + base64Image + '" alt="Spending Chart" style="width:100%;height:auto;border-radius:12px;">';
    }

    function renderInsights(insights) {
        spendingInsights.innerHTML = '';
        if (!insights || typeof insights !== 'object') return;
        const list = document.createElement('ul');
        for (const [key, value] of Object.entries(insights)) {
            const li = document.createElement('li');
            li.textContent = `${key}: ${value}`;
            list.appendChild(li);
        }
        spendingInsights.appendChild(list);
    }

    // Category Suggestion
    const suggestBtn = document.getElementById('suggestBtn');
    const transactionDesc = document.getElementById('transactionDesc');
    const categoryResult = document.getElementById('categoryResult');

    suggestBtn.addEventListener('click', () => {
        const desc = transactionDesc.value.trim();
        if (!desc) return showToast('Please enter a description', 'error');
        fetch('/api/suggest_category', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: desc, user_id: userId })
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    categoryResult.innerHTML = '<p>Suggested Category: <strong>' + data.suggestion + '</strong></p>';
                    showToast('Category suggested', 'success');
                } else {
                    showToast(data.message || 'Suggestion failed', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error', 'error');
            });
    });

    // Goal Breakdown
    const breakdownBtn = document.getElementById('breakdownBtn');
    const goalInput = document.getElementById('goalInput');
    const goalResult = document.getElementById('goalResult');

    breakdownBtn.addEventListener('click', () => {
        const goal = goalInput.value.trim();
        if (!goal) return showToast('Please enter your goal', 'error');
        fetch('/api/breakdown_goal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal, user_id: userId })
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    renderGoalBreakdown(data.breakdown);
                    showToast('Goal breakdown ready', 'success');
                } else {
                    showToast(data.message || 'Breakdown failed', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error', 'error');
            });
    });

    function renderGoalBreakdown(breakdown) {
        goalResult.innerHTML = '';
        if (typeof breakdown === 'string') {
            goalResult.textContent = breakdown;
            return;
        }
        const list = document.createElement('ul');
        for (const [step, detail] of Object.entries(breakdown)) {
            const li = document.createElement('li');
            li.innerHTML = '<strong>' + step + ':</strong> ' + detail;
            list.appendChild(li);
        }
        goalResult.appendChild(list);
    }

    // Home Loan Calculator
    const calculateLoanBtn = document.getElementById('calculateLoanBtn');
    const loanResult = document.getElementById('loanResult');

    calculateLoanBtn.addEventListener('click', () => {
        const income = parseFloat(document.getElementById('income').value) || 0;
        const debt = parseFloat(document.getElementById('debt').value) || 0;
        const loan_amount = parseFloat(document.getElementById('loanAmount').value) || 0;
        const interest_rate = parseFloat(document.getElementById('interestRate').value) || 0;
        const term_years = parseInt(document.getElementById('termYears').value) || 0;

        if (!userId) return showToast('Please set your user ID first', 'error');
        if (!income || !loan_amount || !interest_rate || !term_years) return showToast('Please fill all fields', 'error');

        loanResult.innerHTML = '<p>Calculating...</p>';

        fetch('/api/home_loan_affordability', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ income, debt, loan_amount, interest_rate, term_years, user_id: userId })
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    loanResult.textContent = JSON.stringify(data.result, null, 2);
                    showToast('Calculation done', 'success');
                } else {
                    loanResult.textContent = data.message || 'Calculation failed';
                    showToast(data.message || 'Calculation failed', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error', 'error');
            });
    });

    // Investment Strategy
    const getAdviceBtn = document.getElementById('getAdviceBtn');
    const investmentResult = document.getElementById('investmentResult');

    getAdviceBtn.addEventListener('click', () => {
        const risk_tolerance = document.getElementById('riskTolerance').value;
        const investment_horizon = parseInt(document.getElementById('investmentHorizon').value) || 0;
        if (!userId) return showToast('Please set your user ID first', 'error');
        if (!investment_horizon) return showToast('Please enter your investment horizon', 'error');
        investmentResult.innerHTML = '<p>Fetching advice...</p>';

        fetch('/api/lazy_investor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ risk_tolerance, investment_horizon, user_id: userId })
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    investmentResult.textContent = JSON.stringify(data.result, null, 2);
                    showToast('Strategy ready', 'success');
                } else {
                    investmentResult.textContent = data.message || 'Failed to get strategy';
                    showToast(data.message || 'Failed to get strategy', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                showToast('Network error', 'error');
            });
    });

    // Chat
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendChatBtn = document.getElementById('sendChatBtn');

    sendChatBtn.addEventListener('click', sendChatMessage);
    chatInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    function sendChatMessage() {
        const message = chatInput.value.trim();
        if (!message) return;
        appendMessage('user', message);
        chatInput.value = '';
        fetch('/api/chat_agent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_message: message, chat_history: [], user_id: userId })
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    appendMessage('bot', data.response);
                } else {
                    appendMessage('bot', data.response || 'Something went wrong');
                }
            })
            .catch(err => {
                console.error(err);
                appendMessage('bot', 'Network error');
            });
    }

    function appendMessage(type, text) {
        const messageEl = document.createElement('div');
        messageEl.classList.add('message', type === 'bot' ? 'bot-message' : 'user-message');
        messageEl.innerHTML = `
            <div class="message-avatar">
                <i class="fas ${type === 'bot' ? 'fa-robot' : 'fa-user'}"></i>
            </div>
            <div class="message-content">
                <p>${text}</p>
            </div>
        `;
        chatMessages.appendChild(messageEl);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Voice Mode Toggle
    const modeButtons = document.querySelectorAll('.mode-btn');
    const chatInterface = document.getElementById('chatInterface');
    const voiceInterface = document.getElementById('voiceInterface');
    let currentMode = 'chat';

    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            modeButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentMode = btn.dataset.mode;
            if (currentMode === 'chat') {
                chatInterface.style.display = 'flex';
                voiceInterface.style.display = 'none';
            } else {
                chatInterface.style.display = 'none';
                voiceInterface.style.display = 'flex';
            }
        });
    });

    // Wow voice agent (placeholder)
    const voiceBtn = document.getElementById('voiceBtn');
    const voiceResult = document.getElementById('voiceResult');

    voiceBtn.addEventListener('click', () => {
        voiceResult.textContent = 'Listening...';
        // Placeholder simulated response
        setTimeout(() => {
            voiceResult.textContent = 'Understood. How can I help you further?';
        }, 2000);
    });

    /* Toast helper */
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 400);
        }, 3000);
    }
});