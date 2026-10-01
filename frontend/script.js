/* ============================================================
   Rorak V2.2 — Frontend Application Logic
   ============================================================
   Consumes Rorak Backend API:
     GET    /health/
     GET    /ready/
     GET    /workspaces/?page=1&page_size=20
     POST   /workspaces/
     GET    /documents/?workspace_id=<uuid>&page=1&page_size=20
     GET    /documents/{document_id}
     POST   /documents/upload?workspace_id=<uuid>
     PATCH  /documents/{document_id}
     DELETE /documents/{document_id}
     POST   /chat/
   ============================================================ */

(function () {
    "use strict";

    // ── Configuration ──
    var API_BASE = window.RORAK_API_BASE || (
        window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
            ? (window.location.port === "8000" ? "" : "http://localhost:8000")
            : "https://api.rorak.tech"
    );

    // ── Greetings ──
    var GREETINGS = [
        "Ready when you are.",
        "Hi Beautiful!",
        "Hi Gorgeous!",
        "Hi Sunshine!",
        "Hi Brilliant!",
        "Hi Superstar!",
        "Hi Champion!",
        "Hi Genius!",
        "Hi Rockstar!",
        "Ready to explore your documents."
    ];

    // ── Application State ──
    var messages = [];
    var uploadedFileName = null;
    var activeDocumentId = null;
    var isLoading = false;
    var currentWorkspaceId = null;
    var currentUserId = null;
    var currentUser = null;
    var activeConversationId = null;
    var activeView = "chat"; // "chat" | "docs" | "memory"

    // Authentication & Storage Keys (V2.6)
    var RORAK_TOKEN_KEY = "rorak_access_token";
    var RORAK_USER_KEY = "rorak_user";

    // Document library state
    var docLibrary = {
        documents: [],
        page: 1,
        pageSize: 20,
        total: 0,
        totalPages: 1,
        isLoading: false,
        pendingActionDoc: null
    };

    // Conversation state (Step 10)
    var conversationLibrary = {
        conversations: [],
        isLoading: false,
        pendingActionConv: null
    };

    // Memory state (Step 11)
    var memoryLibrary = {
        memories: [],
        page: 1,
        pageSize: 20,
        total: 0,
        totalPages: 1,
        isLoading: false,
        pendingDeleteMemory: null
    };

    // ── DOM References ──
    var mainArea = document.getElementById("mainArea");
    var emptyState = document.getElementById("emptyState");
    var emptyGreeting = document.getElementById("emptyGreeting");
    var chatMessages = document.getElementById("chatMessages");
    var chatInput = document.getElementById("chatInput");
    var uploadBtn = document.getElementById("uploadBtn");
    var sendBtn = document.getElementById("sendBtn");
    var fileInput = document.getElementById("fileInput");
    var uploadIndicator = document.getElementById("uploadIndicator");
    var notification = document.getElementById("notification");
    var menuToggle = document.getElementById("menuToggle");
    var sidebar = document.getElementById("sidebar");
    var sidebarOverlay = document.getElementById("sidebarOverlay");

    // Navigation & Views
    var navChatBtn = document.getElementById("navChatBtn");
    var navDocsBtn = document.getElementById("navDocsBtn");
    var navMemoryBtn = document.getElementById("navMemoryBtn");
    var docsCountBadge = document.getElementById("docsCountBadge");
    var memoriesCountBadge = document.getElementById("memoriesCountBadge");
    var docsSection = document.getElementById("docsSection");
    var memorySection = document.getElementById("memorySection");
    var inputArea = document.getElementById("inputArea");

    // Conversations DOM (Step 10)
    var btnNewChat = document.getElementById("btnNewChat");
    var convListContainer = document.getElementById("convListContainer");
    var convList = document.getElementById("convList");

    var convRenameModal = document.getElementById("convRenameModal");
    var convRenameInput = document.getElementById("convRenameInput");
    var convRenameCharCount = document.getElementById("convRenameCharCount");
    var convRenameError = document.getElementById("convRenameError");
    var convRenameCloseBtn = document.getElementById("convRenameCloseBtn");
    var convRenameCancelBtn = document.getElementById("convRenameCancelBtn");
    var convRenameSubmitBtn = document.getElementById("convRenameSubmitBtn");

    var convDeleteModal = document.getElementById("convDeleteModal");
    var deleteConvTitle = document.getElementById("deleteConvTitle");
    var convDeleteCloseBtn = document.getElementById("convDeleteCloseBtn");
    var convDeleteCancelBtn = document.getElementById("convDeleteCancelBtn");
    var convDeleteConfirmBtn = document.getElementById("convDeleteConfirmBtn");

    // Memory DOM (Step 11)
    var memoriesRefreshBtn = document.getElementById("memoriesRefreshBtn");
    var memoriesAddBtn = document.getElementById("memoriesAddBtn");
    var metricTotalMemories = document.getElementById("metricTotalMemories");
    var metricWorkspaceMemories = document.getElementById("metricWorkspaceMemories");
    var metricPersonalMemories = document.getElementById("metricPersonalMemories");
    var memoriesList = document.getElementById("memoriesList");
    var memoriesPagination = document.getElementById("memoriesPagination");
    var btnPrevMemPage = document.getElementById("btnPrevMemPage");
    var btnNextMemPage = document.getElementById("btnNextMemPage");
    var memPageIndicator = document.getElementById("memPageIndicator");

    var memoryDeleteModal = document.getElementById("memoryDeleteModal");
    var deleteMemoryPreview = document.getElementById("deleteMemoryPreview");
    var memoryDeleteCloseBtn = document.getElementById("memoryDeleteCloseBtn");
    var memoryDeleteCancelBtn = document.getElementById("memoryDeleteCancelBtn");
    var memoryDeleteConfirmBtn = document.getElementById("memoryDeleteConfirmBtn");

    var memoryAddModal = document.getElementById("memoryAddModal");
    var memoryAddContent = document.getElementById("memoryAddContent");
    var memoryAddType = document.getElementById("memoryAddType");
    var memoryAddScope = document.getElementById("memoryAddScope");
    var memoryAddError = document.getElementById("memoryAddError");
    var memoryAddCloseBtn = document.getElementById("memoryAddCloseBtn");
    var memoryAddCancelBtn = document.getElementById("memoryAddCancelBtn");
    var memoryAddSubmitBtn = document.getElementById("memoryAddSubmitBtn");

    // Document Library DOM
    var docsUploadBtn = document.getElementById("docsUploadBtn");
    var docsRefreshBtn = document.getElementById("docsRefreshBtn");
    var docsUploadProgress = document.getElementById("docsUploadProgress");
    var progressFileName = document.getElementById("progressFileName");
    var progressStatusText = document.getElementById("progressStatusText");
    var progressBar = document.getElementById("progressBar");
    var docsList = document.getElementById("docsList");
    var docsPagination = document.getElementById("docsPagination");
    var btnPrevPage = document.getElementById("btnPrevPage");
    var btnNextPage = document.getElementById("btnNextPage");
    var pageIndicator = document.getElementById("pageIndicator");

    // Metrics
    var metricTotalDocs = document.getElementById("metricTotalDocs");
    var metricReadyDocs = document.getElementById("metricReadyDocs");
    var metricTotalChunks = document.getElementById("metricTotalChunks");
    var metricTotalPages = document.getElementById("metricTotalPages");

    // Modals
    var docDetailsModal = document.getElementById("docDetailsModal");
    var docDetailsContent = document.getElementById("docDetailsContent");
    var docDetailsCloseBtn = document.getElementById("docDetailsCloseBtn");
    var docDetailsDoneBtn = document.getElementById("docDetailsDoneBtn");

    var docRenameModal = document.getElementById("docRenameModal");
    var renameInput = document.getElementById("renameInput");
    var renameCharCount = document.getElementById("renameCharCount");
    var renameError = document.getElementById("renameError");
    var docRenameCloseBtn = document.getElementById("docRenameCloseBtn");
    var docRenameCancelBtn = document.getElementById("docRenameCancelBtn");
    var docRenameSubmitBtn = document.getElementById("docRenameSubmitBtn");

    var docDeleteModal = document.getElementById("docDeleteModal");
    var deleteDocName = document.getElementById("deleteDocName");
    var docDeleteCloseBtn = document.getElementById("docDeleteCloseBtn");
    var docDeleteCancelBtn = document.getElementById("docDeleteCancelBtn");
    var docDeleteConfirmBtn = document.getElementById("docDeleteConfirmBtn");

    // Authentication DOM (V2.6)
    var authModal = document.getElementById("authModal");
    var authCloseBtn = document.getElementById("authCloseBtn");
    var authSubtitle = document.getElementById("authSubtitle");
    var authTabLogin = document.getElementById("authTabLogin");
    var authTabRegister = document.getElementById("authTabRegister");

    var loginForm = document.getElementById("loginForm");
    var loginEmail = document.getElementById("loginEmail");
    var loginPassword = document.getElementById("loginPassword");
    var loginError = document.getElementById("loginError");
    var loginSubmitBtn = document.getElementById("loginSubmitBtn");
    var toggleLoginPassword = document.getElementById("toggleLoginPassword");
    var switchToRegisterLink = document.getElementById("switchToRegisterLink");

    var registerForm = document.getElementById("registerForm");
    var registerEmail = document.getElementById("registerEmail");
    var registerPassword = document.getElementById("registerPassword");
    var registerConfirmPassword = document.getElementById("registerConfirmPassword");
    var registerError = document.getElementById("registerError");
    var registerSubmitBtn = document.getElementById("registerSubmitBtn");
    var toggleRegisterPassword = document.getElementById("toggleRegisterPassword");
    var switchToLoginLink = document.getElementById("switchToLoginLink");

    var userProfileWidget = document.getElementById("userProfileWidget");
    var sidebarUserAvatar = document.getElementById("sidebarUserAvatar");
    var sidebarUserEmail = document.getElementById("sidebarUserEmail");
    var sidebarLogoutBtn = document.getElementById("sidebarLogoutBtn");
    var sidebarSignInBtn = document.getElementById("sidebarSignInBtn");

    // ── SVG Templates ──
    var COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    var CHECK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    var PDF_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>';
    var MESSAGE_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
    var EDIT_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>';
    var TRASH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>';


    // ────────────────────────────────────────
    //  Initialization
    // ────────────────────────────────────────

    function init() {
        setRandomGreeting();
        bindEvents();
        checkHealth();

        // Restore user profile from storage if available
        var savedUserStr = localStorage.getItem(RORAK_USER_KEY);
        if (savedUserStr) {
            try {
                currentUser = JSON.parse(savedUserStr);
                currentUserId = currentUser ? currentUser.id : null;
            } catch (e) {}
        }
        updateUserProfileUI();

        var token = getAccessToken();
        if (!token) {
            showAuthModal("login");
            return;
        }

        var urlParams = new URLSearchParams(window.location.search);
        var initialConvId = urlParams.get("conversation_id");

        ensureUser()
            .then(ensureWorkspace)
            .then(function () {
                loadDocuments(1);
                loadMemoriesCount();
                return loadConversations();
            })
            .then(function () {
                if (initialConvId) {
                    selectConversation(initialConvId, true);
                }
            })
            .catch(function (e) {
                console.warn("Session initialization error:", e);
                clearAuthSession();
                showAuthModal("login", "Please sign in to continue.");
            });
    }

    function setRandomGreeting() {
        var index = Math.floor(Math.random() * GREETINGS.length);
        if (emptyGreeting) emptyGreeting.textContent = GREETINGS[index];
    }

    // ────────────────────────────────────────
    //  Authentication & Token Management (V2.6)
    // ────────────────────────────────────────

    function getAccessToken() {
        return localStorage.getItem(RORAK_TOKEN_KEY);
    }

    function setAuthSession(token, user) {
        if (token) {
            localStorage.setItem(RORAK_TOKEN_KEY, token);
        }
        if (user) {
            currentUser = user;
            currentUserId = user.id;
            localStorage.setItem(RORAK_USER_KEY, JSON.stringify(user));
            localStorage.setItem("rorak_user_id", user.id);
        }
        updateUserProfileUI();
    }

    function clearAuthSession() {
        localStorage.removeItem(RORAK_TOKEN_KEY);
        localStorage.removeItem(RORAK_USER_KEY);
        localStorage.removeItem("rorak_user_id");
        localStorage.removeItem("rorak_workspace_id");
        currentUser = null;
        currentUserId = null;
        currentWorkspaceId = null;
        activeConversationId = null;
        messages = [];
        docLibrary.documents = [];
        conversationLibrary.conversations = [];
        memoryLibrary.memories = [];
        updateUserProfileUI();
    }

    function updateUserProfileUI() {
        if (currentUser && currentUser.email) {
            if (userProfileWidget) userProfileWidget.style.display = "flex";
            if (sidebarSignInBtn) sidebarSignInBtn.style.display = "none";
            if (sidebarUserEmail) {
                sidebarUserEmail.textContent = currentUser.email;
                sidebarUserEmail.title = currentUser.email;
            }
            if (sidebarUserAvatar) {
                sidebarUserAvatar.textContent = (currentUser.email[0] || "U").toUpperCase();
            }
        } else {
            if (userProfileWidget) userProfileWidget.style.display = "none";
            if (sidebarSignInBtn) sidebarSignInBtn.style.display = "flex";
        }
    }

    function apiFetch(url, options) {
        options = options || {};
        var headers = options.headers || {};
        var token = getAccessToken();

        if (typeof headers.append !== "function") {
            options.headers = Object.assign({}, headers);
            if (token) {
                options.headers["Authorization"] = "Bearer " + token;
            }
        } else {
            if (token) {
                headers.set("Authorization", "Bearer " + token);
            }
        }

        return fetch(url, options).then(function (res) {
            if (res.status === 401) {
                var isAuthRoute = url.indexOf("/auth/login") !== -1 || url.indexOf("/auth/register") !== -1;
                if (!isAuthRoute) {
                    handleUnauthorized();
                }
            }
            return res;
        });
    }

    function handleUnauthorized() {
        clearAuthSession();
        startNewChat(true);
        renderConversationList();
        renderDocumentList();
        renderMemoryList();
        showAuthModal("login", "Your session has expired. Please sign in again.");
    }

    // ────────────────────────────────────────
    //  Auth Modal Controller (V2.6)
    // ────────────────────────────────────────

    function showAuthModal(tab, subtitleText) {
        if (!authModal) return;
        switchAuthTab(tab || "login");
        if (subtitleText && authSubtitle) {
            authSubtitle.textContent = subtitleText;
        } else if (authSubtitle) {
            authSubtitle.textContent = "Sign in to access your workspaces, documents, and conversations.";
        }
        if (loginError) {
            loginError.style.display = "none";
            loginError.textContent = "";
        }
        if (registerError) {
            registerError.style.display = "none";
            registerError.textContent = "";
        }
        authModal.style.display = "flex";
        setTimeout(function () {
            if (tab === "register" && registerEmail) {
                registerEmail.focus();
            } else if (loginEmail) {
                loginEmail.focus();
            }
        }, 50);
    }

    function hideAuthModal() {
        if (!authModal) return;
        authModal.style.display = "none";
        if (loginError) loginError.style.display = "none";
        if (registerError) registerError.style.display = "none";
    }

    function switchAuthTab(tab) {
        var isLogin = tab === "login";
        if (authTabLogin) {
            authTabLogin.classList.toggle("active", isLogin);
            authTabLogin.setAttribute("aria-selected", isLogin ? "true" : "false");
        }
        if (authTabRegister) {
            authTabRegister.classList.toggle("active", !isLogin);
            authTabRegister.setAttribute("aria-selected", !isLogin ? "true" : "false");
        }
        if (loginForm) loginForm.style.display = isLogin ? "flex" : "none";
        if (registerForm) registerForm.style.display = !isLogin ? "flex" : "none";
        if (loginError) loginError.style.display = "none";
        if (registerError) registerError.style.display = "none";
    }

    function togglePasswordVisibility(inputElem, toggleBtn) {
        if (!inputElem || !toggleBtn) return;
        var isPassword = inputElem.type === "password";
        inputElem.type = isPassword ? "text" : "password";
        var eyeOpen = toggleBtn.querySelector(".eye-open");
        var eyeClosed = toggleBtn.querySelector(".eye-closed");
        if (eyeOpen && eyeClosed) {
            eyeOpen.style.display = isPassword ? "none" : "block";
            eyeClosed.style.display = isPassword ? "block" : "none";
        }
    }

    function showAuthError(elem, message) {
        if (!elem) return;
        elem.textContent = message;
        elem.style.display = "block";
    }

    function setSubmitLoading(btn, isLoadingState, defaultText) {
        if (!btn) return;
        btn.disabled = isLoadingState;
        var span = btn.querySelector("span") || btn;
        span.textContent = defaultText;
    }

    function handleLoginSubmit(e) {
        if (e) e.preventDefault();
        var email = (loginEmail ? loginEmail.value : "").trim().toLowerCase();
        var password = (loginPassword ? loginPassword.value : "");

        if (!email || !password) {
            showAuthError(loginError, "Please enter both email and password.");
            return;
        }

        setSubmitLoading(loginSubmitBtn, true, "Signing in...");
        if (loginError) loginError.style.display = "none";

        fetch(API_BASE + "/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email, password: password })
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, status: res.status, data: data };
                });
            })
            .then(function (result) {
                setSubmitLoading(loginSubmitBtn, false, "Sign In");
                if (!result.ok) {
                    var msg = "Invalid email or password.";
                    if (result.data && result.data.detail) {
                        if (typeof result.data.detail === "object" && result.data.detail.error) {
                            msg = result.data.detail.error.message || msg;
                        } else if (typeof result.data.detail === "string") {
                            msg = result.data.detail;
                        }
                    }
                    showAuthError(loginError, msg);
                    return;
                }

                var token = result.data.access_token;
                var user = result.data.user;
                setAuthSession(token, user);
                hideAuthModal();
                if (loginPassword) loginPassword.value = "";
                showNotification("Welcome back, " + user.email + "!");

                postAuthInit();
            })
            .catch(function () {
                setSubmitLoading(loginSubmitBtn, false, "Sign In");
                showAuthError(loginError, "Network error: Unable to connect to server.");
            });
    }

    function handleRegisterSubmit(e) {
        if (e) e.preventDefault();
        var email = (registerEmail ? registerEmail.value : "").trim().toLowerCase();
        var password = (registerPassword ? registerPassword.value : "");
        var confirmPassword = (registerConfirmPassword ? registerConfirmPassword.value : "");

        var emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
        if (!email || !emailRegex.test(email)) {
            showAuthError(registerError, "Please enter a valid email address.");
            return;
        }

        if (password.length < 8) {
            showAuthError(registerError, "Password must be at least 8 characters long.");
            return;
        }

        if (password !== confirmPassword) {
            showAuthError(registerError, "Passwords do not match.");
            return;
        }

        setSubmitLoading(registerSubmitBtn, true, "Creating account...");
        if (registerError) registerError.style.display = "none";

        fetch(API_BASE + "/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email, password: password })
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, status: res.status, data: data };
                });
            })
            .then(function (regResult) {
                if (!regResult.ok) {
                    setSubmitLoading(registerSubmitBtn, false, "Create Account");
                    var msg = "Registration failed.";
                    if (regResult.status === 409) {
                        msg = "An account with this email already exists. Please sign in.";
                    } else if (regResult.data && regResult.data.detail) {
                        if (typeof regResult.data.detail === "object" && regResult.data.detail.error) {
                            msg = regResult.data.detail.error.message || msg;
                        } else if (typeof regResult.data.detail === "string") {
                            msg = regResult.data.detail;
                        }
                    }
                    showAuthError(registerError, msg);
                    return;
                }

                // Automatically log in after registration
                return fetch(API_BASE + "/auth/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email: email, password: password })
                })
                    .then(function (res) { return res.json(); })
                    .then(function (loginData) {
                        setSubmitLoading(registerSubmitBtn, false, "Create Account");
                        var token = loginData.access_token;
                        var user = loginData.user;
                        setAuthSession(token, user);
                        hideAuthModal();
                        if (registerPassword) registerPassword.value = "";
                        if (registerConfirmPassword) registerConfirmPassword.value = "";
                        showNotification("Account created! Welcome, " + user.email + "!");

                        postAuthInit();
                    });
            })
            .catch(function () {
                setSubmitLoading(registerSubmitBtn, false, "Create Account");
                showAuthError(registerError, "Network error: Unable to connect to server.");
            });
    }

    function handleLogout() {
        clearAuthSession();
        startNewChat(true);
        renderConversationList();
        renderDocumentList();
        renderMemoryList();
        showNotification("Signed out successfully.");
        showAuthModal("login", "Sign in to access your workspaces, documents, and conversations.");
    }

    function postAuthInit() {
        ensureWorkspace()
            .then(function () {
                loadDocuments(1);
                loadMemoriesCount();
                return loadConversations();
            })
            .catch(function (e) {
                console.warn("Post-auth data load deferred:", e);
            });
    }

    // ────────────────────────────────────────
    //  User & Workspace Resolution
    // ────────────────────────────────────────

    function ensureUser() {
        if (currentUser && currentUserId) {
            return Promise.resolve(currentUserId);
        }
        var token = getAccessToken();
        if (!token) {
            showAuthModal("login");
            return Promise.reject(new Error("Authentication required"));
        }

        return fetch(API_BASE + "/auth/me", {
            headers: { "Authorization": "Bearer " + token }
        })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error("Could not resolve authenticated user (" + res.status + ")");
                }
                return res.json();
            })
            .then(function (user) {
                setAuthSession(token, user);
                return currentUserId;
            });
    }

    function ensureWorkspace() {
        if (currentWorkspaceId) {
            return Promise.resolve(currentWorkspaceId);
        }
        var savedId = localStorage.getItem("rorak_workspace_id");

        return apiFetch(API_BASE + "/workspaces/?page=1&page_size=20")
            .then(function (res) {
                if (!res.ok) throw new Error("Could not list workspaces (" + res.status + ")");
                return res.json();
            })
            .then(function (data) {
                var list = (data && data.workspaces) || [];
                if (savedId && list.some(function (w) { return w.id === savedId; })) {
                    currentWorkspaceId = savedId;
                    return currentWorkspaceId;
                }
                if (list.length > 0) {
                    currentWorkspaceId = list[0].id;
                    localStorage.setItem("rorak_workspace_id", currentWorkspaceId);
                    return currentWorkspaceId;
                }
                // Create personal workspace for this user
                var createPayload = { name: "Personal Workspace" };
                return apiFetch(API_BASE + "/workspaces/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(createPayload)
                })
                    .then(function (r) { return r.json(); })
                    .then(function (ws) {
                        currentWorkspaceId = ws.id;
                        localStorage.setItem("rorak_workspace_id", currentWorkspaceId);
                        return currentWorkspaceId;
                    });
            })
            .catch(function (err) {
                console.warn("Workspace resolution fallback:", err);
                if (savedId) {
                    currentWorkspaceId = savedId;
                    return currentWorkspaceId;
                }
                throw err;
            });
    }


    // ────────────────────────────────────────
    //  Event Bindings
    // ────────────────────────────────────────

    function bindEvents() {
        // Send message
        if (sendBtn) sendBtn.addEventListener("click", handleSend);
        if (chatInput) {
            chatInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                }
            });
            chatInput.addEventListener("focus", function () {
                setTimeout(function () {
                    scrollToBottom();
                    window.scrollTo(0, 0);
                }, 150);
            });
        }

        // File upload from chat bar
        if (uploadBtn) {
            uploadBtn.addEventListener("click", function () {
                if (!getAccessToken()) {
                    showAuthModal("login", "Please sign in to upload documents.");
                    return;
                }
                fileInput.click();
            });
        }
        if (fileInput) {
            fileInput.addEventListener("change", handleFileSelect);
        }

        // Navigation
        if (navChatBtn) {
            navChatBtn.addEventListener("click", function (e) {
                e.preventDefault();
                switchView("chat");
                closeSidebar();
            });
        }
        if (navDocsBtn) {
            navDocsBtn.addEventListener("click", function (e) {
                e.preventDefault();
                switchView("docs");
                closeSidebar();
            });
        }

        // Conversations events (Step 10)
        if (btnNewChat) {
            btnNewChat.addEventListener("click", function () {
                if (!getAccessToken()) {
                    showAuthModal("login", "Please sign in to start a new chat.");
                    return;
                }
                startNewChat();
                closeSidebar();
            });
        }

        // Conversation Rename Modal
        if (convRenameCloseBtn) convRenameCloseBtn.addEventListener("click", closeConvRenameModal);
        if (convRenameCancelBtn) convRenameCancelBtn.addEventListener("click", closeConvRenameModal);
        if (convRenameSubmitBtn) convRenameSubmitBtn.addEventListener("click", submitConvRename);
        if (convRenameInput) {
            convRenameInput.addEventListener("input", function () {
                var len = convRenameInput.value.length;
                if (convRenameCharCount) convRenameCharCount.textContent = len + " / 255";
                if (convRenameError) convRenameError.style.display = "none";
            });
            convRenameInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    submitConvRename();
                }
            });
        }

        // Conversation Delete Modal
        if (convDeleteCloseBtn) convDeleteCloseBtn.addEventListener("click", closeConvDeleteModal);
        if (convDeleteCancelBtn) convDeleteCancelBtn.addEventListener("click", closeConvDeleteModal);
        if (convDeleteConfirmBtn) convDeleteConfirmBtn.addEventListener("click", confirmConvDelete);

        // Memory events (Step 11)
        if (navMemoryBtn) {
            navMemoryBtn.addEventListener("click", function (e) {
                e.preventDefault();
                switchView("memory");
                closeSidebar();
            });
        }
        if (memoriesRefreshBtn) {
            memoriesRefreshBtn.addEventListener("click", function () {
                loadMemories(memoryLibrary.page);
            });
        }
        if (memoriesAddBtn) {
            memoriesAddBtn.addEventListener("click", function () {
                if (!getAccessToken()) {
                    showAuthModal("login", "Please sign in to add memories.");
                    return;
                }
                openMemoryAddModal();
            });
        }
        if (btnPrevMemPage) {
            btnPrevMemPage.addEventListener("click", function () {
                if (memoryLibrary.page > 1) {
                    loadMemories(memoryLibrary.page - 1);
                }
            });
        }
        if (btnNextMemPage) {
            btnNextMemPage.addEventListener("click", function () {
                if (memoryLibrary.page < memoryLibrary.totalPages) {
                    loadMemories(memoryLibrary.page + 1);
                }
            });
        }

        // Memory Delete Modal
        if (memoryDeleteCloseBtn) memoryDeleteCloseBtn.addEventListener("click", closeMemoryDeleteModal);
        if (memoryDeleteCancelBtn) memoryDeleteCancelBtn.addEventListener("click", closeMemoryDeleteModal);
        if (memoryDeleteConfirmBtn) memoryDeleteConfirmBtn.addEventListener("click", confirmDeleteMemory);

        // Memory Add Modal
        if (memoryAddCloseBtn) memoryAddCloseBtn.addEventListener("click", closeMemoryAddModal);
        if (memoryAddCancelBtn) memoryAddCancelBtn.addEventListener("click", closeMemoryAddModal);
        if (memoryAddSubmitBtn) memoryAddSubmitBtn.addEventListener("click", submitAddMemory);

        // Document Library header actions
        if (docsUploadBtn) {
            docsUploadBtn.addEventListener("click", function () {
                if (!getAccessToken()) {
                    showAuthModal("login", "Please sign in to upload documents.");
                    return;
                }
                fileInput.click();
            });
        }
        if (docsRefreshBtn) {
            docsRefreshBtn.addEventListener("click", function () {
                loadDocuments(docLibrary.page);
            });
        }

        // Pagination
        if (btnPrevPage) {
            btnPrevPage.addEventListener("click", function () {
                if (docLibrary.page > 1) {
                    loadDocuments(docLibrary.page - 1);
                }
            });
        }
        if (btnNextPage) {
            btnNextPage.addEventListener("click", function () {
                if (docLibrary.page < docLibrary.totalPages) {
                    loadDocuments(docLibrary.page + 1);
                }
            });
        }

        // Details Modal
        if (docDetailsCloseBtn) docDetailsCloseBtn.addEventListener("click", closeDetailsModal);
        if (docDetailsDoneBtn) docDetailsDoneBtn.addEventListener("click", closeDetailsModal);

        // Rename Modal
        if (docRenameCloseBtn) docRenameCloseBtn.addEventListener("click", closeRenameModal);
        if (docRenameCancelBtn) docRenameCancelBtn.addEventListener("click", closeRenameModal);
        if (docRenameSubmitBtn) docRenameSubmitBtn.addEventListener("click", submitRename);
        if (renameInput) {
            renameInput.addEventListener("input", function () {
                var len = renameInput.value.length;
                if (renameCharCount) renameCharCount.textContent = len + " / 255";
                if (renameError) renameError.style.display = "none";
            });
            renameInput.addEventListener("keydown", function (e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    submitRename();
                }
            });
        }

        // Delete Modal
        if (docDeleteCloseBtn) docDeleteCloseBtn.addEventListener("click", closeDeleteModal);
        if (docDeleteCancelBtn) docDeleteCancelBtn.addEventListener("click", closeDeleteModal);
        if (docDeleteConfirmBtn) docDeleteConfirmBtn.addEventListener("click", confirmDelete);

        // Authentication Events (V2.6)
        if (authCloseBtn) {
            authCloseBtn.addEventListener("click", function () {
                hideAuthModal();
            });
        }
        if (authTabLogin) {
            authTabLogin.addEventListener("click", function () {
                switchAuthTab("login");
            });
        }
        if (authTabRegister) {
            authTabRegister.addEventListener("click", function () {
                switchAuthTab("register");
            });
        }
        if (switchToRegisterLink) {
            switchToRegisterLink.addEventListener("click", function (e) {
                e.preventDefault();
                switchAuthTab("register");
            });
        }
        if (switchToLoginLink) {
            switchToLoginLink.addEventListener("click", function (e) {
                e.preventDefault();
                switchAuthTab("login");
            });
        }
        if (loginForm) {
            loginForm.addEventListener("submit", handleLoginSubmit);
        }
        if (registerForm) {
            registerForm.addEventListener("submit", handleRegisterSubmit);
        }
        if (toggleLoginPassword) {
            toggleLoginPassword.addEventListener("click", function () {
                togglePasswordVisibility(loginPassword, toggleLoginPassword);
            });
        }
        if (toggleRegisterPassword) {
            toggleRegisterPassword.addEventListener("click", function () {
                togglePasswordVisibility(registerPassword, toggleRegisterPassword);
            });
        }
        if (sidebarSignInBtn) {
            sidebarSignInBtn.addEventListener("click", function () {
                showAuthModal("login");
                closeSidebar();
            });
        }
        if (sidebarLogoutBtn) {
            sidebarLogoutBtn.addEventListener("click", function () {
                handleLogout();
                closeSidebar();
            });
        }

        // Backdrop click to close modals
        [
            docDetailsModal,
            docRenameModal,
            docDeleteModal,
            convRenameModal,
            convDeleteModal,
            memoryDeleteModal,
            memoryAddModal
        ].forEach(function (modal) {
            if (modal) {
                modal.addEventListener("click", function (e) {
                    if (e.target === modal) {
                        modal.style.display = "none";
                    }
                });
            }
        });

        if (authModal) {
            authModal.addEventListener("click", function (e) {
                if (e.target === authModal && getAccessToken()) {
                    hideAuthModal();
                }
            });
        }

        // Browser navigation history restoration (Back / Forward)
        window.addEventListener("popstate", function (e) {
            var urlParams = new URLSearchParams(window.location.search);
            var convId = urlParams.get("conversation_id");
            if (convId) {
                selectConversation(convId, true);
            } else {
                startNewChat(true);
            }
        });

        // Mobile sidebar
        if (menuToggle) menuToggle.addEventListener("click", toggleSidebar);
        if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
        var sidebarCloseBtn = document.getElementById("sidebarCloseBtn");
        if (sidebarCloseBtn) sidebarCloseBtn.addEventListener("click", closeSidebar);

        if (window.visualViewport) {
            window.visualViewport.addEventListener("resize", function () {
                scrollToBottom();
                window.scrollTo(0, 0);
            });
        }
    }


    // ────────────────────────────────────────
    //  View Switching
    // ────────────────────────────────────────

    function switchView(view) {
        activeView = view;

        if (view === "chat") {
            if (navChatBtn) navChatBtn.classList.add("active");
            if (navDocsBtn) navDocsBtn.classList.remove("active");
            if (navMemoryBtn) navMemoryBtn.classList.remove("active");

            if (docsSection) docsSection.style.display = "none";
            if (memorySection) memorySection.style.display = "none";
            if (inputArea) inputArea.style.display = "";

            if (messages.length === 0) {
                if (mainArea) mainArea.classList.add("is-empty");
                if (emptyState) emptyState.style.display = "";
                if (chatMessages) {
                    chatMessages.style.display = "none";
                    chatMessages.classList.remove("active");
                }
            } else {
                if (mainArea) mainArea.classList.remove("is-empty");
                if (emptyState) emptyState.style.display = "none";
                if (chatMessages) {
                    chatMessages.style.display = "";
                    chatMessages.classList.add("active");
                }
            }
        } else if (view === "docs") {
            if (navDocsBtn) navDocsBtn.classList.add("active");
            if (navChatBtn) navChatBtn.classList.remove("active");
            if (navMemoryBtn) navMemoryBtn.classList.remove("active");

            if (mainArea) mainArea.classList.remove("is-empty");
            if (emptyState) emptyState.style.display = "none";
            if (chatMessages) chatMessages.style.display = "none";
            if (inputArea) inputArea.style.display = "none";

            if (memorySection) memorySection.style.display = "none";
            if (docsSection) docsSection.style.display = "flex";
            loadDocuments(docLibrary.page);
        } else if (view === "memory") {
            if (navMemoryBtn) navMemoryBtn.classList.add("active");
            if (navChatBtn) navChatBtn.classList.remove("active");
            if (navDocsBtn) navDocsBtn.classList.remove("active");

            if (mainArea) mainArea.classList.remove("is-empty");
            if (emptyState) emptyState.style.display = "none";
            if (chatMessages) chatMessages.style.display = "none";
            if (inputArea) inputArea.style.display = "none";

            if (docsSection) docsSection.style.display = "none";
            if (memorySection) memorySection.style.display = "flex";
            loadMemories(memoryLibrary.page);
        }
    }


    // ────────────────────────────────────────
    //  Document Library: Fetch & Render (V2.2)
    // ────────────────────────────────────────

    function loadDocuments(page) {
        docLibrary.isLoading = true;
        docLibrary.page = page || 1;

        if (docsList && docLibrary.documents.length === 0) {
            docsList.innerHTML = '<div class="docs-loading-state"><p>Loading documents…</p></div>';
        }

        ensureWorkspace()
            .then(function (wsId) {
                var url = API_BASE + "/documents/?workspace_id=" + encodeURIComponent(wsId) +
                    "&page=" + encodeURIComponent(docLibrary.page) +
                    "&page_size=" + encodeURIComponent(docLibrary.pageSize);
                return apiFetch(url);
            })
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to load documents (" + res.status + ")");
                return res.json();
            })
            .then(function (data) {
                docLibrary.documents = data.documents || [];
                if (data.pagination) {
                    docLibrary.total = data.pagination.total;
                    docLibrary.totalPages = Math.max(1, data.pagination.total_pages);
                } else {
                    docLibrary.total = docLibrary.documents.length;
                    docLibrary.totalPages = 1;
                }
                renderDocumentList();
                updateMetrics();
            })
            .catch(function (err) {
                console.error("Document load error:", err);
                if (docsList) {
                    docsList.innerHTML =
                        '<div class="docs-error-state">' +
                            '<p style="color:#f87171;">Failed to load documents.</p>' +
                            '<button class="btn-secondary" id="btnRetryLoad">Retry</button>' +
                        '</div>';
                    var retryBtn = document.getElementById("btnRetryLoad");
                    if (retryBtn) {
                        retryBtn.addEventListener("click", function () {
                            loadDocuments(docLibrary.page);
                        });
                    }
                }
            })
            .finally(function () {
                docLibrary.isLoading = false;
            });
    }

    function renderDocumentList() {
        if (!docsList) return;

        if (docLibrary.documents.length === 0) {
            docsList.innerHTML =
                '<div class="docs-empty-state">' +
                    '<div class="docs-empty-icon">' +
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>' +
                            '<polyline points="14 2 14 8 20 8"></polyline>' +
                            '<line x1="12" y1="18" x2="12" y2="12"></line>' +
                            '<line x1="9" y1="15" x2="15" y2="15"></line>' +
                        '</svg>' +
                    '</div>' +
                    '<h3 class="docs-empty-title">No documents yet</h3>' +
                    '<p class="docs-empty-desc">Upload PDF documents to create durable workspace knowledge and ground AI answers with verifiable citations.</p>' +
                    '<button class="btn-primary" id="btnEmptyUpload">' +
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                            '<line x1="12" y1="5" x2="12" y2="19"></line>' +
                            '<line x1="5" y1="12" x2="19" y2="12"></line>' +
                        '</svg>' +
                        'Upload First Document' +
                    '</button>' +
                '</div>';

            var emptyUploadBtn = document.getElementById("btnEmptyUpload");
            if (emptyUploadBtn) {
                emptyUploadBtn.addEventListener("click", function () {
                    fileInput.click();
                });
            }
            if (docsPagination) docsPagination.style.display = "none";
            return;
        }

        docsList.innerHTML = "";

        docLibrary.documents.forEach(function (doc) {
            var card = createDocumentCard(doc);
            docsList.appendChild(card);
        });

        // Pagination controls update
        if (docsPagination) {
            if (docLibrary.totalPages > 1) {
                docsPagination.style.display = "flex";
                if (pageIndicator) {
                    pageIndicator.textContent = "Page " + docLibrary.page + " of " + docLibrary.totalPages;
                }
                if (btnPrevPage) btnPrevPage.disabled = (docLibrary.page <= 1);
                if (btnNextPage) btnNextPage.disabled = (docLibrary.page >= docLibrary.totalPages);
            } else {
                docsPagination.style.display = "none";
            }
        }
    }

    function createDocumentCard(doc) {
        var card = document.createElement("div");
        card.className = "doc-card";
        card.dataset.id = doc.id;

        // Top info
        var top = document.createElement("div");
        top.className = "doc-card-top";

        var icon = document.createElement("div");
        icon.className = "doc-icon-badge";
        icon.innerHTML = PDF_ICON;
        top.appendChild(icon);

        var titleArea = document.createElement("div");
        titleArea.className = "doc-title-area";

        var nameEl = document.createElement("div");
        nameEl.className = "doc-display-name";
        nameEl.textContent = doc.display_name || doc.original_filename || doc.filename;
        titleArea.appendChild(nameEl);

        if (doc.original_filename && doc.original_filename !== doc.display_name) {
            var origEl = document.createElement("div");
            origEl.className = "doc-original-file";
            origEl.textContent = "File: " + doc.original_filename;
            titleArea.appendChild(origEl);
        }

        top.appendChild(titleArea);

        // Status badge
        var badge = createStatusBadge(doc.status);
        top.appendChild(badge);

        card.appendChild(top);

        // Metadata row
        var meta = document.createElement("div");
        meta.className = "doc-card-meta";

        if (doc.file_size !== undefined && doc.file_size !== null) {
            var sizePill = document.createElement("span");
            sizePill.className = "meta-pill";
            sizePill.textContent = formatBytes(doc.file_size);
            meta.appendChild(sizePill);
        }

        var pagesPill = document.createElement("span");
        pagesPill.className = "meta-pill";
        pagesPill.textContent = (doc.page_count || 0) + " pages";
        meta.appendChild(pagesPill);

        var chunksPill = document.createElement("span");
        chunksPill.className = "meta-pill";
        chunksPill.textContent = (doc.chunk_count || 0) + " chunks";
        meta.appendChild(chunksPill);

        if (doc.created_at) {
            var timePill = document.createElement("span");
            timePill.className = "meta-pill";
            timePill.textContent = formatDate(doc.created_at);
            meta.appendChild(timePill);
        }

        card.appendChild(meta);

        // Failure banner if status is FAILED
        if (doc.status === "FAILED" && doc.failure_reason) {
            var failBanner = document.createElement("div");
            failBanner.className = "doc-failure-banner";
            failBanner.textContent = "Processing failed: " + doc.failure_reason;
            card.appendChild(failBanner);
        }

        // Actions
        var actions = document.createElement("div");
        actions.className = "doc-card-actions";

        var detailsBtn = document.createElement("button");
        detailsBtn.className = "btn-doc-action";
        detailsBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg> Details';
        detailsBtn.addEventListener("click", function () {
            openDetailsModal(doc.id);
        });
        actions.appendChild(detailsBtn);

        var renameBtn = document.createElement("button");
        renameBtn.className = "btn-doc-action";
        renameBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg> Rename';
        renameBtn.addEventListener("click", function () {
            openRenameModal(doc);
        });
        actions.appendChild(renameBtn);

        var deleteBtn = document.createElement("button");
        deleteBtn.className = "btn-doc-action action-delete";
        deleteBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg> Delete';
        deleteBtn.addEventListener("click", function () {
            openDeleteModal(doc);
        });
        actions.appendChild(deleteBtn);

        // Retry action for FAILED documents (Requirement 7: accurately reflects backend capability)
        if (doc.status === "FAILED") {
            var retryBtn = document.createElement("button");
            retryBtn.className = "btn-doc-action action-retry disabled";
            retryBtn.title = "Automatic retry is not supported by the backend. Please delete and re-upload.";
            retryBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Retry (Unavailable)';
            retryBtn.addEventListener("click", function (e) {
                e.preventDefault();
                showNotification("Retry is not supported by current backend. Please delete and re-upload.");
            });
            actions.appendChild(retryBtn);
        }

        card.appendChild(actions);
        return card;
    }

    function createStatusBadge(status) {
        var badge = document.createElement("span");
        var normalized = (status || "").toUpperCase();

        if (normalized === "INDEXED") {
            badge.className = "doc-status-badge badge-indexed";
            badge.textContent = "Ready";
        } else if (normalized === "PROCESSING") {
            badge.className = "doc-status-badge badge-processing";
            badge.textContent = "Processing";
        } else if (normalized === "UPLOADED") {
            badge.className = "doc-status-badge badge-uploaded";
            badge.textContent = "Uploaded";
        } else if (normalized === "FAILED") {
            badge.className = "doc-status-badge badge-failed";
            badge.textContent = "Failed";
        } else {
            badge.className = "doc-status-badge";
            badge.textContent = status || "Unknown";
        }
        return badge;
    }

    function updateMetrics() {
        var total = docLibrary.total || docLibrary.documents.length;
        var ready = 0;
        var chunks = 0;
        var pages = 0;

        docLibrary.documents.forEach(function (d) {
            if (d.status === "INDEXED") ready++;
            chunks += (d.chunk_count || 0);
            pages += (d.page_count || 0);
        });

        if (metricTotalDocs) metricTotalDocs.textContent = total;
        if (metricReadyDocs) metricReadyDocs.textContent = ready;
        if (metricTotalChunks) metricTotalChunks.textContent = chunks;
        if (metricTotalPages) metricTotalPages.textContent = pages;
        if (docsCountBadge) docsCountBadge.textContent = total;
    }


    // ────────────────────────────────────────
    //  Document Upload with Progress (V2.2)
    // ────────────────────────────────────────

    function handleFileSelect(e) {
        var file = e.target.files[0];
        if (!file) return;

        fileInput.value = "";

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showNotification("Only PDF documents (.pdf) are supported in V2.2.");
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            showNotification("File exceeds 10 MB maximum allowed upload size.");
            return;
        }

        uploadDocumentFile(file);
    }

    function uploadDocumentFile(file) {
        var token = getAccessToken();
        if (!token) {
            showAuthModal("login", "Please sign in to upload documents.");
            return;
        }

        showUploadProgress(file.name);
        if (uploadBtn) uploadBtn.disabled = true;
        if (docsUploadBtn) docsUploadBtn.disabled = true;

        ensureWorkspace()
            .then(function (wsId) {
                var formData = new FormData();
                formData.append("file", file);

                var xhr = new XMLHttpRequest();
                var uploadUrl = API_BASE + "/documents/upload?workspace_id=" + encodeURIComponent(wsId);

                xhr.open("POST", uploadUrl, true);
                if (token) {
                    xhr.setRequestHeader("Authorization", "Bearer " + token);
                }

                // Real progress tracking
                xhr.upload.onprogress = function (event) {
                    if (event.lengthComputable) {
                        var percent = Math.round((event.loaded / event.total) * 100);
                        updateProgressBar(percent, "Uploading (" + percent + "%)…");
                    }
                };

                xhr.onload = function () {
                    hideUploadProgress();
                    if (uploadBtn) uploadBtn.disabled = false;
                    if (docsUploadBtn) docsUploadBtn.disabled = false;

                    if (xhr.status === 401) {
                        handleUnauthorized();
                        return;
                    }

                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            var data = JSON.parse(xhr.responseText);
                            var doc = data.document || data;
                            var chunkCount = data.chunk_count || doc.chunk_count || 0;
                            var displayName = doc.display_name || doc.original_filename || file.name;

                            uploadedFileName = displayName;
                            activeDocumentId = doc.id;
                            renderUploadChip(displayName, chunkCount);

                            showNotification("Document indexed (" + chunkCount + " chunks created). Ready for questions!");
                            setTimeout(hideNotification, 4000);

                            // Refresh library
                            loadDocuments(1);
                        } catch (err) {
                            showNotification("Document uploaded, but could not parse response.");
                            loadDocuments(1);
                        }
                    } else {
                        var errMsg = "Upload failed (" + xhr.status + ")";
                        try {
                            var errData = JSON.parse(xhr.responseText);
                            errMsg = errData.detail || (errData.error && errData.error.message) || errMsg;
                        } catch (e) {}
                        showNotification("Upload failed: " + errMsg);
                    }
                };

                xhr.onerror = function () {
                    hideUploadProgress();
                    if (uploadBtn) uploadBtn.disabled = false;
                    if (docsUploadBtn) docsUploadBtn.disabled = false;
                    showNotification("Network error occurred during document upload.");
                };

                xhr.send(formData);
            })
            .catch(function (err) {
                hideUploadProgress();
                if (uploadBtn) uploadBtn.disabled = false;
                if (docsUploadBtn) docsUploadBtn.disabled = false;
                showNotification("Could not resolve workspace for upload: " + (err.message || err));
            });
    }

    function showUploadProgress(fileName) {
        if (progressFileName) progressFileName.textContent = fileName;
        if (progressStatusText) progressStatusText.textContent = "Uploading (0%)…";
        if (progressBar) progressBar.style.width = "0%";
        if (docsUploadProgress) docsUploadProgress.style.display = "block";
        showNotification("Uploading " + fileName + "…");
    }

    function updateProgressBar(percent, statusText) {
        if (progressBar) progressBar.style.width = percent + "%";
        if (progressStatusText) progressStatusText.textContent = statusText;
    }

    function hideUploadProgress() {
        if (docsUploadProgress) docsUploadProgress.style.display = "none";
    }

    function renderUploadChip(name, chunkCount) {
        if (!uploadIndicator) return;
        var title = name + (chunkCount ? " (" + chunkCount + " chunks)" : "");
        uploadIndicator.innerHTML =
            '<div class="upload-chip">' +
                '<span>📄 ' + escapeHtml(title) + '</span>' +
                '<button class="upload-chip-remove" title="Unlink from chat">&times;</button>' +
            '</div>';
        uploadIndicator.classList.add("active");

        var removeBtn = uploadIndicator.querySelector(".upload-chip-remove");
        if (removeBtn) {
            removeBtn.addEventListener("click", function () {
                uploadedFileName = null;
                activeDocumentId = null;
                uploadIndicator.innerHTML = "";
                uploadIndicator.classList.remove("active");
                showNotification("Document unlinked from active chat session.");
                setTimeout(hideNotification, 2000);
            });
        }
    }


    // ────────────────────────────────────────
    //  Document Details Modal (V2.2 Metadata)
    // ────────────────────────────────────────

    function openDetailsModal(documentId) {
        if (!docDetailsModal || !docDetailsContent) return;

        docDetailsContent.innerHTML = '<p style="color:#888;">Fetching document metadata…</p>';
        docDetailsModal.style.display = "flex";

        apiFetch(API_BASE + "/documents/" + encodeURIComponent(documentId))
            .then(function (res) {
                if (!res.ok) throw new Error("Document not found (" + res.status + ")");
                return res.json();
            })
            .then(function (doc) {
                renderDetailsContent(doc);
            })
            .catch(function (err) {
                docDetailsContent.innerHTML = '<p style="color:#f87171;">Failed to load details: ' + escapeHtml(err.message) + '</p>';
            });
    }

    function renderDetailsContent(doc) {
        // Excludes storage_key, raw filesystem paths, secrets, or internal tracebacks
        var html = '<table class="meta-table">' +
            '<tr><td>Display Name</td><td><strong>' + escapeHtml(doc.display_name || doc.original_filename || "—") + '</strong></td></tr>' +
            '<tr><td>Original File</td><td>' + escapeHtml(doc.original_filename || doc.filename || "—") + '</td></tr>' +
            '<tr><td>Status</td><td>' + createStatusBadge(doc.status).outerHTML + '</td></tr>' +
            '<tr><td>File Size</td><td>' + formatBytes(doc.file_size) + ' (' + (doc.file_size || 0).toLocaleString() + ' bytes)</td></tr>' +
            '<tr><td>Pages</td><td>' + (doc.page_count !== undefined ? doc.page_count : "—") + '</td></tr>' +
            '<tr><td>Chunks Indexed</td><td>' + (doc.chunk_count !== undefined ? doc.chunk_count : "—") + '</td></tr>' +
            '<tr><td>MIME Type</td><td><code>' + escapeHtml(doc.mime_type || "application/pdf") + '</code></td></tr>' +
            '<tr><td>Created</td><td>' + formatDate(doc.created_at, true) + '</td></tr>' +
            '<tr><td>Updated</td><td>' + formatDate(doc.updated_at, true) + '</td></tr>';

        if (doc.status === "FAILED" && doc.failure_reason) {
            html += '<tr><td>Failure Reason</td><td><span style="color:#f87171;">' + escapeHtml(doc.failure_reason) + '</span></td></tr>';
        }

        html += '</table>';
        docDetailsContent.innerHTML = html;
    }

    function closeDetailsModal() {
        if (docDetailsModal) docDetailsModal.style.display = "none";
    }


    // ────────────────────────────────────────
    //  Document Rename Modal (V2.2 PATCH)
    // ────────────────────────────────────────

    function openRenameModal(doc) {
        docLibrary.pendingActionDoc = doc;
        if (!docRenameModal || !renameInput) return;

        renameInput.value = doc.display_name || doc.original_filename || "";
        if (renameCharCount) renameCharCount.textContent = renameInput.value.length + " / 255";
        if (renameError) renameError.style.display = "none";

        docRenameModal.style.display = "flex";
        setTimeout(function () {
            renameInput.focus();
            renameInput.select();
        }, 100);
    }

    function closeRenameModal() {
        if (docRenameModal) docRenameModal.style.display = "none";
        docLibrary.pendingActionDoc = null;
    }

    function submitRename() {
        var doc = docLibrary.pendingActionDoc;
        if (!doc || !renameInput) return;

        var newName = renameInput.value.trim();

        if (!newName) {
            showRenameError("Display name cannot be empty.");
            return;
        }

        if (newName.length > 255) {
            showRenameError("Display name must be 255 characters or fewer.");
            return;
        }

        if (docRenameSubmitBtn) {
            docRenameSubmitBtn.disabled = true;
            docRenameSubmitBtn.textContent = "Saving…";
        }

        apiFetch(API_BASE + "/documents/" + encodeURIComponent(doc.id), {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ display_name: newName })
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) {
                        var msg = (data && data.error && data.error.message) || data.detail || "Rename failed";
                        throw new Error(msg);
                    }
                    return data;
                });
            })
            .then(function (updated) {
                closeRenameModal();
                showNotification("Document renamed to \"" + updated.display_name + "\"");
                setTimeout(hideNotification, 3000);

                // Update in active chip if present
                if (activeDocumentId === updated.id) {
                    uploadedFileName = updated.display_name;
                    renderUploadChip(updated.display_name, updated.chunk_count);
                }

                // Refresh document list
                loadDocuments(docLibrary.page);
            })
            .catch(function (err) {
                showRenameError(err.message || "Failed to rename document.");
            })
            .finally(function () {
                if (docRenameSubmitBtn) {
                    docRenameSubmitBtn.disabled = false;
                    docRenameSubmitBtn.textContent = "Save";
                }
            });
    }

    function showRenameError(msg) {
        if (!renameError) return;
        renameError.textContent = msg;
        renameError.style.display = "block";
    }


    // ────────────────────────────────────────
    //  Document Delete Modal (V2.2 DELETE)
    // ────────────────────────────────────────

    function openDeleteModal(doc) {
        docLibrary.pendingActionDoc = doc;
        if (!docDeleteModal || !deleteDocName) return;

        deleteDocName.textContent = '"' + (doc.display_name || doc.original_filename || "this document") + '"';
        docDeleteModal.style.display = "flex";
    }

    function closeDeleteModal() {
        if (docDeleteModal) docDeleteModal.style.display = "none";
        docLibrary.pendingActionDoc = null;
    }

    function confirmDelete() {
        var doc = docLibrary.pendingActionDoc;
        if (!doc) return;

        if (docDeleteConfirmBtn) {
            docDeleteConfirmBtn.disabled = true;
            docDeleteConfirmBtn.textContent = "Deleting…";
        }

        // Call per-document DELETE endpoint; never global /documents/clear
        apiFetch(API_BASE + "/documents/" + encodeURIComponent(doc.id), {
            method: "DELETE"
        })
            .then(function (res) {
                if (!res.ok && res.status !== 204) {
                    throw new Error("Failed to delete document (" + res.status + ")");
                }
                closeDeleteModal();
                showNotification("Document deleted.");
                setTimeout(hideNotification, 3000);

                // Remove chip if this was active
                if (activeDocumentId === doc.id) {
                    uploadedFileName = null;
                    activeDocumentId = null;
                    if (uploadIndicator) {
                        uploadIndicator.innerHTML = "";
                        uploadIndicator.classList.remove("active");
                    }
                }

                loadDocuments(docLibrary.page);
            })
            .catch(function (err) {
                showNotification("Delete failed: " + (err.message || err));
            })
            .finally(function () {
                if (docDeleteConfirmBtn) {
                    docDeleteConfirmBtn.disabled = false;
                    docDeleteConfirmBtn.textContent = "Delete Permanently";
                }
            });
    }


    // ────────────────────────────────────────
    //  Step 10 — Conversation Experience
    // ────────────────────────────────────────

    function loadConversations() {
        conversationLibrary.isLoading = true;
        if (convList && conversationLibrary.conversations.length === 0) {
            convList.innerHTML = '<div class="conv-loading-state">Loading chats…</div>';
        }

        return ensureWorkspace()
            .then(function (wsId) {
                var url = API_BASE + "/conversations/?workspace_id=" + encodeURIComponent(wsId) + "&page=1&page_size=50";
                return apiFetch(url);
            })
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to load conversations (" + res.status + ")");
                return res.json();
            })
            .then(function (data) {
                conversationLibrary.conversations = data.conversations || [];
                renderConversationList();
                return conversationLibrary.conversations;
            })
            .catch(function (err) {
                console.error("Conversation load error:", err);
                if (convList) {
                    convList.innerHTML =
                        '<div class="conv-error-state">' +
                            '<p style="color:#f87171;">Could not load chats.</p>' +
                            '<button class="btn-secondary" id="btnRetryConvs">Retry</button>' +
                        '</div>';
                    var retryBtn = document.getElementById("btnRetryConvs");
                    if (retryBtn) retryBtn.addEventListener("click", loadConversations);
                }
            })
            .finally(function () {
                conversationLibrary.isLoading = false;
            });
    }

    function renderConversationList() {
        if (!convList) return;

        if (conversationLibrary.conversations.length === 0) {
            convList.innerHTML = '<div class="conv-empty-state">No conversations yet</div>';
            return;
        }

        convList.innerHTML = "";
        conversationLibrary.conversations.forEach(function (conv) {
            var item = document.createElement("div");
            item.className = "conv-item" + (conv.id === activeConversationId ? " active" : "");
            item.dataset.id = conv.id;

            var left = document.createElement("div");
            left.className = "conv-item-left";
            left.innerHTML = '<span class="conv-icon">' + MESSAGE_ICON + '</span>' +
                '<span class="conv-title" title="' + escapeHtml(conv.title) + '">' + escapeHtml(conv.title) + '</span>';
            item.appendChild(left);

            var actions = document.createElement("div");
            actions.className = "conv-actions";

            var renameBtn = document.createElement("button");
            renameBtn.className = "conv-action-btn";
            renameBtn.title = "Rename conversation";
            renameBtn.innerHTML = EDIT_ICON;
            renameBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                openConvRenameModal(conv);
            });
            actions.appendChild(renameBtn);

            var deleteBtn = document.createElement("button");
            deleteBtn.className = "conv-action-btn action-delete";
            deleteBtn.title = "Delete conversation";
            deleteBtn.innerHTML = TRASH_ICON;
            deleteBtn.addEventListener("click", function (e) {
                e.stopPropagation();
                openConvDeleteModal(conv);
            });
            actions.appendChild(deleteBtn);

            item.appendChild(actions);

            item.addEventListener("click", function () {
                selectConversation(conv.id);
            });

            convList.appendChild(item);
        });
    }

    function selectConversation(convId, skipHistoryPush) {
        if (activeConversationId === convId && activeView === "chat") {
            return;
        }
        activeConversationId = convId;

        if (!skipHistoryPush) {
            var url = new URL(window.location);
            url.searchParams.set("conversation_id", convId);
            window.history.pushState({ conversation_id: convId }, "", url);
        }

        switchView("chat");
        renderConversationList();
        closeSidebar();
        loadConversationMessages(convId);
    }

    function startNewChat(skipHistoryPush) {
        activeConversationId = null;
        messages = [];
        if (chatMessages) {
            chatMessages.innerHTML = "";
            chatMessages.style.display = "none";
            chatMessages.classList.remove("active");
        }

        if (!skipHistoryPush) {
            var url = new URL(window.location);
            url.searchParams.delete("conversation_id");
            window.history.pushState({}, "", url);
        }

        renderConversationList();
        switchView("chat");
        setRandomGreeting();
        if (chatInput) chatInput.focus();
    }

    function loadConversationMessages(convId) {
        if (!chatMessages) return;

        chatMessages.innerHTML =
            '<div class="chat-loading-history">' +
                '<div class="loading-dots"><span></span><span></span><span></span></div>' +
                '<span>Restoring conversation history…</span>' +
            '</div>';
        chatMessages.style.display = "";
        chatMessages.classList.add("active");
        if (emptyState) emptyState.style.display = "none";
        if (mainArea) mainArea.classList.remove("is-empty");

        ensureWorkspace().then(function (wsId) {
            var url = API_BASE + "/conversations/" + encodeURIComponent(convId) + "/messages?workspace_id=" + encodeURIComponent(wsId) + "&page=1&page_size=100";
            return apiFetch(url);
        })
            .then(function (res) {
                if (res.status === 404) {
                    // Deleted conversation state: gracefully recover
                    showNotification("This conversation no longer exists or was deleted.");
                    startNewChat(false);
                    loadConversations();
                    return null;
                }
                if (!res.ok) throw new Error("Failed to load messages (" + res.status + ")");
                return res.json();
            })
            .then(function (data) {
                if (!data) return;
                chatMessages.innerHTML = "";
                messages = [];
                var list = data.messages || [];
                if (list.length === 0) {
                    if (mainArea) mainArea.classList.add("is-empty");
                    if (emptyState) emptyState.style.display = "";
                    chatMessages.style.display = "none";
                    return;
                }

                list.forEach(function (msg) {
                    messages.push({ role: msg.role, content: msg.content });
                    renderMessage(msg.role, msg.content, formatDate(msg.created_at, true), true);
                });
                scrollToBottom();
            })
            .catch(function (err) {
                console.error("Messages load error:", err);
                chatMessages.innerHTML =
                    '<div class="conv-error-state">' +
                        '<p style="color:#f87171;">Failed to load messages.</p>' +
                        '<button class="btn-secondary" id="btnRetryMessages">Retry</button>' +
                    '</div>';
                var retryBtn = document.getElementById("btnRetryMessages");
                if (retryBtn) {
                    retryBtn.addEventListener("click", function () {
                        loadConversationMessages(convId);
                    });
                }
            });
    }

    function openConvRenameModal(conv) {
        conversationLibrary.pendingActionConv = conv;
        if (!convRenameModal || !convRenameInput) return;
        convRenameInput.value = conv.title || "";
        if (convRenameCharCount) convRenameCharCount.textContent = (conv.title || "").length + " / 255";
        if (convRenameError) convRenameError.style.display = "none";
        convRenameModal.style.display = "flex";
        setTimeout(function () { convRenameInput.focus(); }, 100);
    }

    function closeConvRenameModal() {
        if (convRenameModal) convRenameModal.style.display = "none";
        conversationLibrary.pendingActionConv = null;
    }

    function submitConvRename() {
        var conv = conversationLibrary.pendingActionConv;
        if (!conv || !convRenameInput) return;

        var newTitle = convRenameInput.value.trim();
        if (!newTitle) {
            showConvRenameError("Title cannot be empty.");
            return;
        }
        if (newTitle.length > 255) {
            showConvRenameError("Title exceeds 255 characters.");
            return;
        }

        if (convRenameSubmitBtn) {
            convRenameSubmitBtn.disabled = true;
            convRenameSubmitBtn.textContent = "Saving…";
        }

        ensureWorkspace().then(function (wsId) {
            var url = API_BASE + "/conversations/" + encodeURIComponent(conv.id) + "?workspace_id=" + encodeURIComponent(wsId);
            return apiFetch(url, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: newTitle })
            });
        })
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to rename conversation (" + res.status + ")");
                return res.json();
            })
            .then(function (updated) {
                closeConvRenameModal();
                showNotification("Conversation renamed.");
                setTimeout(hideNotification, 2500);

                var idx = conversationLibrary.conversations.findIndex(function (c) { return c.id === conv.id; });
                if (idx !== -1) {
                    conversationLibrary.conversations[idx].title = updated.title;
                }
                renderConversationList();
            })
            .catch(function (err) {
                showConvRenameError(err.message || "Failed to rename conversation.");
            })
            .finally(function () {
                if (convRenameSubmitBtn) {
                    convRenameSubmitBtn.disabled = false;
                    convRenameSubmitBtn.textContent = "Save";
                }
            });
    }

    function showConvRenameError(msg) {
        if (!convRenameError) return;
        convRenameError.textContent = msg;
        convRenameError.style.display = "block";
    }

    function openConvDeleteModal(conv) {
        conversationLibrary.pendingActionConv = conv;
        if (!convDeleteModal || !deleteConvTitle) return;
        deleteConvTitle.textContent = '"' + (conv.title || "this conversation") + '"';
        convDeleteModal.style.display = "flex";
    }

    function closeConvDeleteModal() {
        if (convDeleteModal) convDeleteModal.style.display = "none";
        conversationLibrary.pendingActionConv = null;
    }

    function confirmConvDelete() {
        var conv = conversationLibrary.pendingActionConv;
        if (!conv) return;

        if (convDeleteConfirmBtn) {
            convDeleteConfirmBtn.disabled = true;
            convDeleteConfirmBtn.textContent = "Deleting…";
        }

        ensureWorkspace().then(function (wsId) {
            var url = API_BASE + "/conversations/" + encodeURIComponent(conv.id) + "?workspace_id=" + encodeURIComponent(wsId);
            return apiFetch(url, { method: "DELETE" });
        })
            .then(function (res) {
                if (!res.ok && res.status !== 200 && res.status !== 204) {
                    throw new Error("Failed to delete conversation (" + res.status + ")");
                }
                closeConvDeleteModal();
                showNotification("Conversation deleted.");
                setTimeout(hideNotification, 2500);

                if (activeConversationId === conv.id) {
                    startNewChat();
                }
                return loadConversations();
            })
            .catch(function (err) {
                showNotification("Delete failed: " + (err.message || err));
            })
            .finally(function () {
                if (convDeleteConfirmBtn) {
                    convDeleteConfirmBtn.disabled = false;
                    convDeleteConfirmBtn.textContent = "Delete Permanently";
                }
            });
    }


    // ────────────────────────────────────────
    //  Step 11 — Memory UI Experience
    // ────────────────────────────────────────

    function loadMemoriesCount() {
        return ensureUser().then(function (userId) {
            return ensureWorkspace().then(function (wsId) {
                var url = API_BASE + "/memories/?user_id=" + encodeURIComponent(userId) +
                    "&workspace_id=" + encodeURIComponent(wsId) +
                    "&page=1&page_size=1";
                return apiFetch(url);
            });
        })
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (data) {
                if (data && data.pagination && memoriesCountBadge) {
                    memoriesCountBadge.textContent = data.pagination.total;
                }
            })
            .catch(function (e) {
                console.warn("Memories count load error:", e);
            });
    }

    function loadMemories(page) {
        memoryLibrary.isLoading = true;
        memoryLibrary.page = page || 1;

        if (memoriesList && memoryLibrary.memories.length === 0) {
            memoriesList.innerHTML = '<div class="docs-loading-state"><p>Loading memories…</p></div>';
        }

        ensureUser().then(function (userId) {
            return ensureWorkspace().then(function (wsId) {
                var url = API_BASE + "/memories/?user_id=" + encodeURIComponent(userId) +
                    "&workspace_id=" + encodeURIComponent(wsId) +
                    "&include_global=true" +
                    "&page=" + encodeURIComponent(memoryLibrary.page) +
                    "&page_size=" + encodeURIComponent(memoryLibrary.pageSize);
                return apiFetch(url);
            });
        })
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to load memories (" + res.status + ")");
                return res.json();
            })
            .then(function (data) {
                memoryLibrary.memories = data.memories || [];
                if (data.pagination) {
                    memoryLibrary.total = data.pagination.total;
                    memoryLibrary.totalPages = Math.max(1, data.pagination.total_pages);
                } else {
                    memoryLibrary.total = memoryLibrary.memories.length;
                    memoryLibrary.totalPages = 1;
                }
                if (memoriesCountBadge) {
                    memoriesCountBadge.textContent = memoryLibrary.total;
                }
                renderMemoryList();
                updateMemoryMetrics();
            })
            .catch(function (err) {
                console.error("Memories load error:", err);
                if (memoriesList) {
                    memoriesList.innerHTML =
                        '<div class="docs-error-state">' +
                            '<p style="color:#f87171;">Failed to load memories.</p>' +
                            '<button class="btn-secondary" id="btnRetryMemories">Retry</button>' +
                        '</div>';
                    var retryBtn = document.getElementById("btnRetryMemories");
                    if (retryBtn) {
                        retryBtn.addEventListener("click", function () {
                            loadMemories(memoryLibrary.page);
                        });
                    }
                }
            })
            .finally(function () {
                memoryLibrary.isLoading = false;
            });
    }

    function updateMemoryMetrics() {
        if (metricTotalMemories) metricTotalMemories.textContent = memoryLibrary.total;
        var wsCount = memoryLibrary.memories.filter(function (m) { return m.workspace_id !== null && m.workspace_id !== undefined; }).length;
        var personalCount = memoryLibrary.memories.filter(function (m) { return m.workspace_id === null || m.workspace_id === undefined; }).length;
        if (metricWorkspaceMemories) metricWorkspaceMemories.textContent = wsCount;
        if (metricPersonalMemories) metricPersonalMemories.textContent = personalCount;
    }

    function renderMemoryList() {
        if (!memoriesList) return;

        if (memoryLibrary.memories.length === 0) {
            memoriesList.innerHTML =
                '<div class="docs-empty-state">' +
                    '<div class="docs-empty-icon">' +
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="M12 2a5 5 0 0 1 5 5v1a5 5 0 0 1-10 0V7a5 5 0 0 1 5-5z"></path>' +
                            '<path d="M19 11v1a7 7 0 0 1-14 0v-1"></path>' +
                            '<line x1="12" y1="19" x2="12" y2="22"></line>' +
                            '<line x1="8" y1="22" x2="16" y2="22"></line>' +
                        '</svg>' +
                    '</div>' +
                    '<h3 class="docs-empty-title">No memories stored yet</h3>' +
                    '<p class="docs-empty-desc">Rorak AI captures user preferences and workspace facts to assemble rich context during chat conversations.</p>' +
                    '<button class="btn-primary" id="btnEmptyAddMem">' +
                        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
                            '<line x1="12" y1="5" x2="12" y2="19"></line>' +
                            '<line x1="5" y1="12" x2="19" y2="12"></line>' +
                        '</svg>' +
                        'Add First Memory' +
                    '</button>' +
                '</div>';

            var emptyAddBtn = document.getElementById("btnEmptyAddMem");
            if (emptyAddBtn) emptyAddBtn.addEventListener("click", openMemoryAddModal);
            if (memoriesPagination) memoriesPagination.style.display = "none";
            return;
        }

        memoriesList.innerHTML = "";
        memoryLibrary.memories.forEach(function (mem) {
            var card = createMemoryCard(mem);
            memoriesList.appendChild(card);
        });

        // Pagination
        if (memoriesPagination) {
            if (memoryLibrary.totalPages > 1) {
                memoriesPagination.style.display = "flex";
                if (memPageIndicator) {
                    memPageIndicator.textContent = "Page " + memoryLibrary.page + " of " + memoryLibrary.totalPages;
                }
                if (btnPrevMemPage) btnPrevMemPage.disabled = (memoryLibrary.page <= 1);
                if (btnNextMemPage) btnNextMemPage.disabled = (memoryLibrary.page >= memoryLibrary.totalPages);
            } else {
                memoriesPagination.style.display = "none";
            }
        }
    }

    function createMemoryCard(mem) {
        var card = document.createElement("div");
        card.className = "memory-card";
        card.dataset.id = mem.id;

        var top = document.createElement("div");
        top.className = "memory-card-top";

        var badges = document.createElement("div");
        badges.className = "memory-card-badges";

        var isWs = (mem.workspace_id !== null && mem.workspace_id !== undefined);
        var scopeBadge = document.createElement("span");
        scopeBadge.className = isWs ? "badge-scope-workspace" : "badge-scope-user";
        scopeBadge.textContent = isWs ? "Workspace Scope" : "Personal Scope";
        badges.appendChild(scopeBadge);

        var typeBadge = document.createElement("span");
        typeBadge.className = "badge-type";
        typeBadge.textContent = formatMemoryType(mem.memory_type);
        badges.appendChild(typeBadge);

        top.appendChild(badges);

        var deleteBtn = document.createElement("button");
        deleteBtn.className = "btn-doc-action action-delete";
        deleteBtn.title = "Delete Memory";
        deleteBtn.innerHTML = TRASH_ICON + "<span>Delete</span>";
        deleteBtn.addEventListener("click", function () {
            openMemoryDeleteModal(mem);
        });
        top.appendChild(deleteBtn);

        card.appendChild(top);

        var contentBox = document.createElement("div");
        contentBox.className = "memory-content-box";
        contentBox.textContent = mem.content;
        card.appendChild(contentBox);

        var footer = document.createElement("div");
        footer.className = "memory-card-footer";
        var dateEl = document.createElement("span");
        dateEl.textContent = "Added " + formatDate(mem.created_at, true);
        footer.appendChild(dateEl);
        card.appendChild(footer);

        return card;
    }

    function formatMemoryType(typeStr) {
        if (!typeStr) return "Directive";
        return typeStr
            .split("_")
            .map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1); })
            .join(" ");
    }

    function openMemoryDeleteModal(mem) {
        memoryLibrary.pendingDeleteMemory = mem;
        if (!memoryDeleteModal || !deleteMemoryPreview) return;
        deleteMemoryPreview.textContent = '"' + mem.content + '"';
        memoryDeleteModal.style.display = "flex";
    }

    function closeMemoryDeleteModal() {
        if (memoryDeleteModal) memoryDeleteModal.style.display = "none";
        memoryLibrary.pendingDeleteMemory = null;
    }

    function confirmDeleteMemory() {
        var mem = memoryLibrary.pendingDeleteMemory;
        if (!mem) return;

        if (memoryDeleteConfirmBtn) {
            memoryDeleteConfirmBtn.disabled = true;
            memoryDeleteConfirmBtn.textContent = "Deleting…";
        }

        ensureUser().then(function (userId) {
            return ensureWorkspace().then(function (wsId) {
                var url = API_BASE + "/memories/" + encodeURIComponent(mem.id) +
                    "?user_id=" + encodeURIComponent(userId) +
                    "&workspace_id=" + encodeURIComponent(wsId);
                return apiFetch(url, { method: "DELETE" });
            });
        })
            .then(function (res) {
                if (!res.ok && res.status !== 200 && res.status !== 204) {
                    throw new Error("Failed to delete memory (" + res.status + ")");
                }
                closeMemoryDeleteModal();
                showNotification("Memory deleted.");
                setTimeout(hideNotification, 2500);
                loadMemories(memoryLibrary.page);
            })
            .catch(function (err) {
                showNotification("Delete memory failed: " + (err.message || err));
            })
            .finally(function () {
                if (memoryDeleteConfirmBtn) {
                    memoryDeleteConfirmBtn.disabled = false;
                    memoryDeleteConfirmBtn.textContent = "Delete Permanently";
                }
            });
    }

    function openMemoryAddModal() {
        if (!memoryAddModal || !memoryAddContent) return;
        memoryAddContent.value = "";
        if (memoryAddError) memoryAddError.style.display = "none";
        memoryAddModal.style.display = "flex";
        setTimeout(function () { memoryAddContent.focus(); }, 100);
    }

    function closeMemoryAddModal() {
        if (memoryAddModal) memoryAddModal.style.display = "none";
    }

    function submitAddMemory() {
        if (!memoryAddContent) return;
        var content = memoryAddContent.value.trim();
        if (!content) {
            if (memoryAddError) {
                memoryAddError.textContent = "Content cannot be empty.";
                memoryAddError.style.display = "block";
            }
            return;
        }

        var type = memoryAddType ? memoryAddType.value : "system_directive";
        var scope = memoryAddScope ? memoryAddScope.value : "workspace";

        if (memoryAddSubmitBtn) {
            memoryAddSubmitBtn.disabled = true;
            memoryAddSubmitBtn.textContent = "Saving…";
        }

        ensureUser().then(function (userId) {
            return ensureWorkspace().then(function (wsId) {
                var payload = {
                    user_id: userId,
                    content: content,
                    memory_type: type,
                    workspace_id: (scope === "workspace" ? wsId : null)
                };
                return apiFetch(API_BASE + "/memories/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            });
        })
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to save memory (" + res.status + ")");
                return res.json();
            })
            .then(function () {
                closeMemoryAddModal();
                showNotification("Memory saved.");
                setTimeout(hideNotification, 2500);
                loadMemories(1);
            })
            .catch(function (err) {
                if (memoryAddError) {
                    memoryAddError.textContent = err.message || "Failed to save memory.";
                    memoryAddError.style.display = "block";
                }
            })
            .finally(function () {
                if (memoryAddSubmitBtn) {
                    memoryAddSubmitBtn.disabled = false;
                    memoryAddSubmitBtn.textContent = "Save Memory";
                }
            });
    }


    // ────────────────────────────────────────
    //  Chat Logic (Preserved V1 Experience & Continuity)
    // ────────────────────────────────────────

    function handleSend() {
        if (!getAccessToken()) {
            showAuthModal("login", "Please sign in to send messages.");
            return;
        }

        var question = chatInput.value.trim();

        if (!question) {
            chatInput.classList.add("shake");
            setTimeout(function () {
                chatInput.classList.remove("shake");
            }, 400);
            return;
        }

        if (isLoading) return;

        hideNotification();
        addMessage("user", question);
        chatInput.value = "";

        isLoading = true;
        sendBtn.disabled = true;
        var loadingId = showLoadingDots();

        executeChatWithRetry(question, 0, loadingId);
    }

    function executeChatWithRetry(question, retryCount, loadingId) {
        var MAX_RETRIES = 2;
        var RETRY_DELAYS = [1000, 2000];

        ensureUser().then(function (userId) {
            return ensureWorkspace().then(function (wsId) {
                var payload = {
                    question: question,
                    workspace_id: wsId,
                    user_id: userId
                };
                if (activeConversationId) {
                    payload.conversation_id = activeConversationId;
                }

                return apiFetch(API_BASE + "/chat/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
            });
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) {
                        var errObj = new Error((data && data.error && data.error.message) || data.detail || "Chat request failed");
                        errObj.status = res.status;
                        throw errObj;
                    }
                    return data;
                });
            })
            .then(function (data) {
                removeLoadingDots(loadingId);
                hideNotification();
                if (!activeConversationId && data.conversation_id) {
                    activeConversationId = data.conversation_id;
                    var url = new URL(window.location);
                    url.searchParams.set("conversation_id", activeConversationId);
                    window.history.replaceState({ conversation_id: activeConversationId }, "", url);
                    loadConversations();
                }
                addMessage("assistant", data.answer);
                finishChat();
            })
            .catch(function (error) {
                var isTransient = !error.status || error.status >= 500;

                if (isTransient && retryCount < MAX_RETRIES) {
                    var delay = RETRY_DELAYS[retryCount];
                    var nextAttempt = retryCount + 1;
                    showNotification("Temporary backend issue. Retrying in " + (delay / 1000) + "s… (Attempt " + nextAttempt + "/" + MAX_RETRIES + ")");

                    setTimeout(function () {
                        executeChatWithRetry(question, retryCount + 1, loadingId);
                    }, delay);
                } else {
                    removeLoadingDots(loadingId);
                    var userMessage = error.message || "Something went wrong. Please try again.";
                    showNotification(userMessage);
                    finishChat();
                }
            });
    }

    function finishChat() {
        isLoading = false;
        if (sendBtn) sendBtn.disabled = false;
        if (chatInput) chatInput.focus();
    }

    function addMessage(role, content) {
        messages.push({ role: role, content: content });
        renderMessage(role, content, getCurrentTime(), false);
    }

    function renderMessage(role, content, timestamp, skipAutoScroll) {
        if (activeView === "chat") {
            if (mainArea) mainArea.classList.remove("is-empty");
            if (emptyState) emptyState.style.display = "none";
            if (chatMessages) {
                chatMessages.style.display = "";
                chatMessages.classList.add("active");
            }
        }

        var msgEl = document.createElement("div");
        msgEl.className = "message message-" + role;

        var headerEl = document.createElement("div");
        headerEl.className = "message-header";

        if (role === "assistant") {
            var avatarEl = document.createElement("div");
            avatarEl.className = "message-avatar";
            avatarEl.textContent = "R";
            headerEl.appendChild(avatarEl);
        }

        var labelEl = document.createElement("div");
        labelEl.className = "message-label";
        labelEl.textContent = role === "user" ? "YOU" : "RORAK";
        headerEl.appendChild(labelEl);

        msgEl.appendChild(headerEl);

        var contentEl = document.createElement("div");
        contentEl.className = "message-content markdown-body";
        contentEl.innerHTML = formatContent(content, role);
        msgEl.appendChild(contentEl);

        if (role === "assistant") {
            var footerEl = document.createElement("div");
            footerEl.className = "message-footer";

            var timeEl = document.createElement("span");
            timeEl.className = "message-time";
            timeEl.textContent = timestamp || getCurrentTime();
            footerEl.appendChild(timeEl);

            var copyBtn = document.createElement("button");
            copyBtn.className = "btn-copy";
            copyBtn.title = "Copy";
            copyBtn.innerHTML = COPY_ICON;
            copyBtn.addEventListener("click", function () {
                copyToClipboard(content, copyBtn);
            });
            footerEl.appendChild(copyBtn);

            msgEl.appendChild(footerEl);
        }

        if (chatMessages) chatMessages.appendChild(msgEl);
        if (!skipAutoScroll) scrollToBottom();
    }

    function formatContent(text, role) {
        if (role === "user") {
            var safe = escapeHtml(text);
            return safe.replace(/\n/g, "<br>");
        }

        if (window.marked && window.DOMPurify) {
            try {
                var rawHtml = window.marked.parse(text, {
                    breaks: true,
                    gfm: true
                });
                return window.DOMPurify.sanitize(rawHtml);
            } catch (e) {}
        }

        var safeText = escapeHtml(text);
        safeText = safeText.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        safeText = safeText.replace(/\n/g, "<br>");
        return safeText;
    }

    function getCurrentTime() {
        var now = new Date();
        var hours = now.getHours();
        var minutes = now.getMinutes();
        var ampm = hours >= 12 ? "PM" : "AM";
        hours = hours % 12;
        hours = hours ? hours : 12;
        minutes = minutes < 10 ? "0" + minutes : minutes;
        return hours + ":" + minutes + " " + ampm;
    }

    function copyToClipboard(text, btn) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
                showCopied(btn);
            }).catch(function () {
                fallbackCopy(text, btn);
            });
        } else {
            fallbackCopy(text, btn);
        }
    }

    function fallbackCopy(text, btn) {
        var textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand("copy");
            showCopied(btn);
        } catch (e) {}
        document.body.removeChild(textarea);
    }

    function showCopied(btn) {
        btn.innerHTML = CHECK_ICON;
        btn.classList.add("copied");
        setTimeout(function () {
            btn.innerHTML = COPY_ICON;
            btn.classList.remove("copied");
        }, 2000);
    }

    function showLoadingDots() {
        var id = "loading-" + Date.now();

        var msgEl = document.createElement("div");
        msgEl.className = "message message-assistant";
        msgEl.id = id;

        var headerEl = document.createElement("div");
        headerEl.className = "message-header";

        var avatarEl = document.createElement("div");
        avatarEl.className = "message-avatar";
        avatarEl.textContent = "R";
        headerEl.appendChild(avatarEl);

        var labelEl = document.createElement("div");
        labelEl.className = "message-label";
        labelEl.textContent = "RORAK";
        headerEl.appendChild(labelEl);

        var dotsEl = document.createElement("div");
        dotsEl.className = "loading-dots";
        dotsEl.innerHTML = "<span></span><span></span><span></span>";

        msgEl.appendChild(headerEl);
        msgEl.appendChild(dotsEl);
        chatMessages.appendChild(msgEl);

        scrollToBottom();
        return id;
    }

    function removeLoadingDots(id) {
        var el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        requestAnimationFrame(function () {
            if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }


    // ────────────────────────────────────────
    //  Health & Notifications
    // ────────────────────────────────────────

    function checkHealth() {
        fetch(API_BASE + "/health/")
            .then(function (res) {
                if (!res.ok) throw new Error("unhealthy");
                return res.json();
            })
            .then(function (data) {
                if (data.status !== "healthy") {
                    showNotification("Backend service is initializing. Some features may take a moment.");
                }
            })
            .catch(function () {
                showNotification("Cannot connect to server. Ensure the backend is reachable.");
            });
    }

    function showNotification(message) {
        if (!notification) return;
        notification.textContent = message;
        notification.classList.add("active");
    }

    function hideNotification() {
        if (!notification) return;
        notification.classList.remove("active");
        notification.textContent = "";
    }


    // ────────────────────────────────────────
    //  Mobile Sidebar
    // ────────────────────────────────────────

    function toggleSidebar() {
        if (!sidebar) return;
        var isOpen = sidebar.classList.contains("open");
        if (isOpen) {
            closeSidebar();
        } else {
            sidebar.classList.add("open");
            if (sidebarOverlay) sidebarOverlay.classList.add("active");
        }
    }

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove("open");
        if (sidebarOverlay) sidebarOverlay.classList.remove("active");
    }


    // ────────────────────────────────────────
    //  Formatters & Helpers
    // ────────────────────────────────────────

    function formatBytes(bytes) {
        if (bytes === 0 || bytes === undefined || bytes === null) return "0 B";
        var k = 1024;
        var sizes = ["B", "KB", "MB", "GB"];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        var value = (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1);
        return value + " " + sizes[i];
    }

    function formatDate(isoStr, includeTime) {
        if (!isoStr) return "—";
        try {
            var d = new Date(isoStr);
            if (isNaN(d.getTime())) return isoStr;
            var opts = { month: "short", day: "numeric", year: "numeric" };
            if (includeTime) {
                opts.hour = "numeric";
                opts.minute = "2-digit";
            }
            return d.toLocaleDateString(undefined, opts);
        } catch (e) {
            return isoStr;
        }
    }

    function escapeHtml(text) {
        if (text === null || text === undefined) return "";
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }


    // ── Start on Load ──
    document.addEventListener("DOMContentLoaded", init);

})();
