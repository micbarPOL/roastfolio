/**
 * auth.js — Roastfolio Cognito authentication module
 *
 * Uses amazon-cognito-identity-js (CDN, UMD build).
 * Library reference: https://github.com/aws-amplify/amplify-js/tree/main/packages/amazon-cognito-identity-js
 *
 * Supports:
 *  - Sign in  (SRP — never sends plain-text password to AWS)
 *  - Sign up  (email + nickname + password)
 *  - Email verification
 *  - Forgot password / confirm new password
 *  - Sign out (local + global)
 */
(function () {
    'use strict';

    // ── Configuration ──────────────────────────────────────────────────────────
    var cfg = window.__CONFIG__ || {};
    var USER_POOL_ID  = cfg.cognitoUserPoolId  || '';
    var CLIENT_ID     = cfg.cognitoClientId    || '';
    var DASHBOARD_URL = 'index.html';

    if (!USER_POOL_ID || !CLIENT_ID) {
        console.warn('[Auth] cognitoUserPoolId or cognitoClientId missing from config.js.');
    }

    // ── Cognito pool ────────────────────────────────────────────────────────────
    var poolData  = { UserPoolId: USER_POOL_ID, ClientId: CLIENT_ID };
    var userPool  = new AmazonCognitoIdentity.CognitoUserPool(poolData);

    // ── Per-flow state ──────────────────────────────────────────────────────────
    var pendingEmail    = '';   // carried between signup → verify
    var pendingForgotEmail = ''; // carried between forgot → reset

    // ── Helpers ─────────────────────────────────────────────────────────────────

    function makeCognitoUser(email) {
        return new AmazonCognitoIdentity.CognitoUser({
            Username: email.trim().toLowerCase(),
            Pool: userPool
        });
    }

    function showMsg(id, text, type) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.className = 'auth-message ' + (type || 'error');
    }

    function clearMsg(id) {
        var el = document.getElementById(id);
        if (el) { el.textContent = ''; el.className = 'auth-message'; }
    }

    function setLoading(btnId, loading) {
        var btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled = loading;
        btn.classList.toggle('loading', loading);
        // New markup: spinner lives inside the button
        var spinner = btn.querySelector('.btn-spinner');
        if (spinner) spinner.style.display = loading ? 'block' : '';
    }

    /** Map Cognito error codes to friendly messages */
    function friendlyError(err) {
        var code = (err && err.code) || '';
        var msg  = (err && err.message) || 'Something went wrong. Please try again.';

        var map = {
            NotAuthorizedException:       'Incorrect email or password.',
            UserNotFoundException:        'No account found with this email.',
            UsernameExistsException:      'An account with this email already exists.',
            InvalidPasswordException:     'Password must be at least 6 characters.',
            CodeMismatchException:        'Invalid code. Please double-check and try again.',
            ExpiredCodeException:         'This code has expired. Please request a new one.',
            LimitExceededException:       'Too many attempts. Please wait a few minutes.',
            TooManyRequestsException:     'Too many requests. Please slow down.',
            UserNotConfirmedException:    'Please verify your email before signing in.',
            InvalidParameterException:    msg,
            NetworkError:                 'Network error — please check your connection.',
        };

        return map[code] || msg;
    }

    // ── Auth API ─────────────────────────────────────────────────────────────────

    /**
     * Sign in with email + password (SRP auth flow).
     * On success, redirects to dashboard.
     */
    function signIn(email, password) {
        clearMsg('login-msg');
        setLoading('login-btn', true);

        var authDetails = new AmazonCognitoIdentity.AuthenticationDetails({
            Username: email.trim().toLowerCase(),
            Password: password
        });

        var user = makeCognitoUser(email);

        user.authenticateUser(authDetails, {
            onSuccess: function (result) {
                // Tokens are stored in localStorage automatically by the library
                setLoading('login-btn', false);
                window.location.replace(DASHBOARD_URL);
            },

            onFailure: function (err) {
                setLoading('login-btn', false);

                // If account exists but not verified → go to verify view
                if (err.code === 'UserNotConfirmedException') {
                    pendingEmail = email.trim().toLowerCase();
                    updateVerifySubtitle(pendingEmail);
                    showView('verify');
                    showMsg('verify-msg',
                        'Your email isn\'t verified yet. Enter the code we sent you.',
                        'success');
                    return;
                }

                showMsg('login-msg', friendlyError(err), 'error');
            },

            // Handle MFA if ever enabled on the pool
            mfaRequired: function () {
                setLoading('login-btn', false);
                showMsg('login-msg', 'MFA is not supported in this client.', 'error');
            }
        });
    }

    /**
     * Create a new account.
     * On success, transitions to email verification view.
     */
    function signUp(email, nickname, password) {
        clearMsg('signup-msg');
        setLoading('signup-btn', true);

        var attrs = [
            new AmazonCognitoIdentity.CognitoUserAttribute({ Name: 'email',    Value: email.trim().toLowerCase() }),
            new AmazonCognitoIdentity.CognitoUserAttribute({ Name: 'nickname', Value: nickname.trim() })
        ];

        userPool.signUp(
            email.trim().toLowerCase(),
            password,
            attrs,
            null, // validationData
            function (err, result) {
                setLoading('signup-btn', false);

                if (err) {
                    showMsg('signup-msg', friendlyError(err), 'error');
                    return;
                }

                pendingEmail = email.trim().toLowerCase();
                updateVerifySubtitle(pendingEmail);
                showView('verify');
                showMsg('verify-msg',
                    'Account created! Check your inbox for the verification code.',
                    'success');
            }
        );
    }

    /**
     * Confirm email with 6-digit code.
     * On success, signs the user in automatically.
     */
    function verifyEmail(code) {
        clearMsg('verify-msg');
        setLoading('verify-btn', true);

        if (!pendingEmail) {
            showMsg('verify-msg', 'Session expired — please sign in again.', 'error');
            setLoading('verify-btn', false);
            showView('login');
            return;
        }

        var user = makeCognitoUser(pendingEmail);

        user.confirmRegistration(code.trim(), true, function (err) {
            setLoading('verify-btn', false);

            if (err) {
                showMsg('verify-msg', friendlyError(err), 'error');
                return;
            }

            // Auto sign-in after verification (prompt user to sign in)
            showMsg('verify-msg',
                '✅ Email verified! You can now sign in.',
                'success');

            setTimeout(function () {
                var savedEmail = pendingEmail;
                pendingEmail = '';
                showView('login');
                var emailInput = document.getElementById('login-email');
                if (emailInput) emailInput.value = savedEmail;
            }, 1500);
        });
    }

    /**
     * Resend the email verification code.
     */
    function resendCode() {
        if (!pendingEmail) {
            showMsg('verify-msg', 'No pending email found. Please start over.', 'error');
            return;
        }

        var btn = document.getElementById('resend-btn');
        if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }

        var user = makeCognitoUser(pendingEmail);

        user.resendConfirmationCode(function (err) {
            if (btn) { btn.disabled = false; btn.textContent = 'Resend code'; }

            if (err) {
                showMsg('verify-msg', friendlyError(err), 'error');
                return;
            }

            showMsg('verify-msg', 'New code sent! Check your inbox.', 'success');
        });
    }

    /**
     * Initiate forgot-password flow (sends reset code via email).
     */
    function forgotPassword(email) {
        clearMsg('forgot-msg');
        setLoading('forgot-btn', true);

        pendingForgotEmail = email.trim().toLowerCase();
        var user = makeCognitoUser(pendingForgotEmail);

        user.forgotPassword({
            onSuccess: function () {
                setLoading('forgot-btn', false);
                showView('reset');
                showMsg('reset-msg',
                    'Reset code sent! Check your inbox.',
                    'success');
            },
            onFailure: function (err) {
                setLoading('forgot-btn', false);
                // UserNotFoundException is obscured by Cognito by default (ENABLED flag)
                // but show generic message if anything leaks through
                showMsg('forgot-msg', friendlyError(err), 'error');
            }
        });
    }

    /**
     * Confirm new password with code from email.
     */
    function confirmNewPassword(code, newPassword) {
        clearMsg('reset-msg');
        setLoading('reset-btn', true);

        if (!pendingForgotEmail) {
            showMsg('reset-msg', 'Session expired — please start the reset flow again.', 'error');
            setLoading('reset-btn', false);
            showView('forgot');
            return;
        }

        var user = makeCognitoUser(pendingForgotEmail);

        user.confirmPassword(code.trim(), newPassword, {
            onSuccess: function () {
                setLoading('reset-btn', false);
                pendingForgotEmail = '';
                showMsg('reset-msg', '✅ Password updated! You can now sign in.', 'success');
                setTimeout(function () { showView('login'); }, 1500);
            },
            onFailure: function (err) {
                setLoading('reset-btn', false);
                showMsg('reset-msg', friendlyError(err), 'error');
            }
        });
    }

    /**
     * Sign out the current user (clears local tokens).
     */
    function signOut() {
        var user = userPool.getCurrentUser();
        if (user) user.signOut();
        window.location.replace('auth.html');
    }

    // Expose so HTML onclick="Auth.resendCode()" can call it
    window.Auth = {
        signIn: signIn,
        signUp: signUp,
        verifyEmail: verifyEmail,
        resendCode: resendCode,
        forgotPassword: forgotPassword,
        confirmNewPassword: confirmNewPassword,
        signOut: signOut
    };

    // ── View management ──────────────────────────────────────────────────────────

    window.showView = function (name) {
        document.querySelectorAll('.auth-view').forEach(function (v) {
            v.classList.remove('active');
        });
        var target = document.getElementById('view-' + name);
        if (target) {
            target.classList.add('active');
            // If returning to main view, also reset tabs to sign-in pane
            if (name === 'login' && window.switchTab) switchTab('login');
            setTimeout(function () {
                var first = target.querySelector('input:not([type=hidden])');
                if (first) first.focus();
            }, 60);
        }
    };

    function updateVerifySubtitle(email) {
        var el = document.getElementById('verify-subtitle');
        if (el && email) {
            el.textContent = 'We sent a 6-digit code to ' + email + '. Enter it below.';
        }
    }

    // ── Password visibility toggle ───────────────────────────────────────────────

    window.togglePw = function (inputId, btn) {
        var input = document.getElementById(inputId);
        if (!input) return;
        var isText = input.type === 'text';
        input.type = isText ? 'password' : 'text';
        btn.textContent = isText ? '👁' : '🙈';
        btn.setAttribute('aria-label', isText ? 'Show password' : 'Hide password');
    };

    // ── Password strength meter ──────────────────────────────────────────────────

    window.checkPwStrength = function (input) {
        var pw = input.value;

        var isReset = (input.id === 'reset-password');
        var barWrapId = isReset ? 'reset-pw-strength-bar-wrap' : 'pw-strength-wrap';
        var barId     = isReset ? 'reset-pw-strength-bar'      : 'pw-strength-bar';

        var wrap = document.getElementById(barWrapId);
        var bar  = document.getElementById(barId);
        var hint = document.getElementById('pw-hint');

        // Requirement pills (signup only)
        var reqLen    = document.getElementById('req-len');
        var reqLetter = document.getElementById('req-letter');

        if (!bar) return;

        if (!pw) {
            if (wrap) wrap.classList.remove('visible');
            if (hint) hint.textContent = '';
            return;
        }

        if (wrap) wrap.classList.add('visible');

        var hasLen    = pw.length >= 6;
        var hasLetter = /[a-zA-Z]/.test(pw);
        var hasUpper  = /[A-Z]/.test(pw);
        var hasNum    = /[0-9]/.test(pw);
        var hasSpec   = /[^A-Za-z0-9]/.test(pw);

        // Update requirement pills
        if (reqLen)    reqLen.classList.toggle('met', hasLen);
        if (reqLetter) reqLetter.classList.toggle('met', hasLetter);

        // Score: 0–4
        var score = [hasLen, hasLetter, hasUpper, hasNum || hasSpec].filter(Boolean).length;

        var levels = [
            { pct: '15%',  color: '#e05555', label: 'Too short' },
            { pct: '35%',  color: '#e07835', label: 'Weak' },
            { pct: '60%',  color: '#d4a017', label: 'Fair' },
            { pct: '82%',  color: '#3dd68c', label: 'Good' },
            { pct: '100%', color: '#22c55e', label: 'Strong 💪' }
        ];

        var lvl = levels[Math.max(0, Math.min(score, 4))];
        bar.style.width      = lvl.pct;
        bar.style.background = lvl.color;

        if (hint) {
            hint.textContent = lvl.label;
            hint.style.color = lvl.color;
        }
    };

    // ── Form handlers ────────────────────────────────────────────────────────────

    document.addEventListener('DOMContentLoaded', function () {

        // ── If already authenticated, skip to dashboard
        var lastUser = '';
        var prefix   = 'CognitoIdentityServiceProvider.' + CLIENT_ID;
        try {
            lastUser = localStorage.getItem(prefix + '.LastAuthUser') || '';
        } catch (_) {}

        if (lastUser) {
            try {
                var token = localStorage.getItem(prefix + '.' + lastUser + '.idToken') || '';
                if (token) {
                    var parts   = token.split('.');
                    var payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
                    if (payload.exp > Math.floor(Date.now() / 1000)) {
                        window.location.replace(DASHBOARD_URL);
                        return;
                    }
                }
            } catch (_) {}
        }

        // ── Login form
        document.getElementById('login-form').addEventListener('submit', function (e) {
            e.preventDefault();
            var email = document.getElementById('login-email').value.trim();
            var pass  = document.getElementById('login-password').value;
            if (!email || !pass) {
                showMsg('login-msg', 'Please fill in all fields.', 'error');
                return;
            }
            signIn(email, pass);
        });

        // ── Sign up form
        document.getElementById('signup-form').addEventListener('submit', function (e) {
            e.preventDefault();
            var email    = document.getElementById('signup-email').value.trim();
            var nickname = document.getElementById('signup-nickname').value.trim();
            var pass     = document.getElementById('signup-password').value;
            var confirm  = document.getElementById('signup-confirm').value;

            if (!email || !nickname || !pass || !confirm) {
                showMsg('signup-msg', 'Please fill in all fields.', 'error');
                return;
            }
            if (pass !== confirm) {
                showMsg('signup-msg', 'Passwords do not match.', 'error');
                return;
            }
            if (pass.length < 6) {
                showMsg('signup-msg', 'Password must be at least 6 characters.', 'error');
                return;
            }
            signUp(email, nickname, pass);
        });

        // ── Verify form
        document.getElementById('verify-form').addEventListener('submit', function (e) {
            e.preventDefault();
            var code = document.getElementById('verify-code').value.trim();
            if (!code) {
                showMsg('verify-msg', 'Please enter the verification code.', 'error');
                return;
            }
            verifyEmail(code);
        });

        // ── Forgot password form
        document.getElementById('forgot-form').addEventListener('submit', function (e) {
            e.preventDefault();
            var email = document.getElementById('forgot-email').value.trim();
            if (!email) {
                showMsg('forgot-msg', 'Please enter your email address.', 'error');
                return;
            }
            forgotPassword(email);
        });

        // ── Reset password form
        document.getElementById('reset-form').addEventListener('submit', function (e) {
            e.preventDefault();
            var code    = document.getElementById('reset-code').value.trim();
            var pass    = document.getElementById('reset-password').value;
            var confirm = document.getElementById('reset-confirm').value;

            if (!code || !pass || !confirm) {
                showMsg('reset-msg', 'Please fill in all fields.', 'error');
                return;
            }
            if (pass !== confirm) {
                showMsg('reset-msg', 'Passwords do not match.', 'error');
                return;
            }
            if (pass.length < 6) {
                showMsg('reset-msg', 'Password must be at least 6 characters.', 'error');
                return;
            }
            confirmNewPassword(code, pass);
        });

        // ── Auto-format 6-digit code inputs (digits only)
        ['verify-code', 'reset-code'].forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', function () {
                el.value = el.value.replace(/\D/g, '').slice(0, 6);
            });
        });
    });

})();
