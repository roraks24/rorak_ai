/* ========================================
   Rorak V1 — Frontend Logic (Dark Theme)
   ========================================
   Consumes Rorak Backend API:
     GET  /health/
     GET  /ready/
     POST /documents/upload   (multipart, field: "file")
     POST /chat/              (JSON: { question })
   ======================================== */

(function () {
    "use strict";

    // ── Configuration ──
    var API_BASE = window.RORAK_API_BASE || "https://api.rorak.tech";

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

    // ── State ──
    var messages = [];
    var uploadedFileName = null;
    var isLoading = false;

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

    // ── SVG Templates ──
    var COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    var CHECK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';


    // ────────────────────────────────────────
    //  Initialization
    // ────────────────────────────────────────

    function init() {
        setRandomGreeting();
        bindEvents();
        checkHealth();
        clearBackendDocuments();
    }

    function clearBackendDocuments() {
        fetch(API_BASE + "/documents/clear", {
            method: "DELETE"
        }).catch(function () {
            // Ignore background clear errors
        });
    }

    function resetConversation() {
        messages = [];
        uploadedFileName = null;
        chatMessages.innerHTML = "";
        chatMessages.classList.remove("active");
        if (mainArea) mainArea.classList.add("is-empty");
        if (emptyState) emptyState.style.display = "";
        if (uploadIndicator) {
            uploadIndicator.innerHTML = "";
            uploadIndicator.classList.remove("active");
        }
        clearBackendDocuments();
        setRandomGreeting();
        chatInput.value = "";
    }

    function setRandomGreeting() {
        var index = Math.floor(Math.random() * GREETINGS.length);
        emptyGreeting.textContent = GREETINGS[index];
    }

    function bindEvents() {
        // Send message
        sendBtn.addEventListener("click", handleSend);
        chatInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });

        // File upload
        uploadBtn.addEventListener("click", function () {
            fileInput.click();
        });
        fileInput.addEventListener("change", handleFileSelect);

        // Mobile keyboard focus & viewport adjustments
        chatInput.addEventListener("focus", function () {
            setTimeout(function () {
                scrollToBottom();
                window.scrollTo(0, 0);
            }, 150);
            setTimeout(function () {
                scrollToBottom();
                window.scrollTo(0, 0);
            }, 350);
        });

        if (window.visualViewport) {
            window.visualViewport.addEventListener("resize", function () {
                scrollToBottom();
                window.scrollTo(0, 0);
            });
            window.visualViewport.addEventListener("scroll", function () {
                window.scrollTo(0, 0);
            });
        }

        // Navigation
        var navChatBtn = document.getElementById("navChatBtn");
        if (navChatBtn) {
            navChatBtn.addEventListener("click", function (e) {
                e.preventDefault();
                resetConversation();
                closeSidebar();
            });
        }

        // Mobile sidebar
        menuToggle.addEventListener("click", toggleSidebar);
        sidebarOverlay.addEventListener("click", closeSidebar);
        var sidebarCloseBtn = document.getElementById("sidebarCloseBtn");
        if (sidebarCloseBtn) {
            sidebarCloseBtn.addEventListener("click", closeSidebar);
        }
    }


    // ────────────────────────────────────────
    //  Health & Readiness Check
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
                showNotification("Cannot connect to server. Please check your network or ensure backend is reachable.");
            });
    }


    // ────────────────────────────────────────
    //  Document Upload
    // ────────────────────────────────────────

    function handleFileSelect(e) {
        var file = e.target.files[0];
        if (!file) return;

        fileInput.value = "";

        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showNotification("Only PDF files (.pdf) are supported in V1.");
            return;
        }

        // 10 MB client check
        if (file.size > 10 * 1024 * 1024) {
            showNotification("File exceeds 10 MB maximum allowed upload size.");
            return;
        }

        showNotification("Uploading and indexing " + file.name + "…");
        uploadBtn.disabled = true;

        var formData = new FormData();
        formData.append("file", file);

        fetch(API_BASE + "/documents/upload", {
            method: "POST",
            body: formData
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) {
                        var msg = (data && data.error && data.error.message) || data.detail || "Upload failed";
                        throw new Error(msg);
                    }
                    return data;
                });
            })
            .then(function (data) {
                uploadedFileName = data.filename;
                renderUploadChip(data.filename, data.chunks_created);
                showNotification("Document indexed (" + data.chunks_created + " chunks created). Ready for questions!");
                setTimeout(hideNotification, 4000);
            })
            .catch(function (error) {
                showNotification(error.message || "Upload failed. Please try again.");
            })
            .finally(function () {
                uploadBtn.disabled = false;
            });
    }

    function renderUploadChip(filename, chunkCount) {
        var title = filename + (chunkCount ? " (" + chunkCount + " chunks)" : "");
        uploadIndicator.innerHTML =
            '<div class="upload-chip">' +
                '<span>📄 ' + escapeHtml(title) + '</span>' +
                '<button class="upload-chip-remove" title="Remove">&times;</button>' +
            '</div>';
        uploadIndicator.classList.add("active");

        uploadIndicator.querySelector(".upload-chip-remove")
            .addEventListener("click", removeUploadChip);
    }

    function removeUploadChip() {
        uploadedFileName = null;
        uploadIndicator.innerHTML = "";
        uploadIndicator.classList.remove("active");

        // Clear active documents and reset vector store on backend
        fetch(API_BASE + "/documents/clear", {
            method: "DELETE"
        }).catch(function () {
            // Ignore background clear error
        });
        showNotification("Document removed.");
        setTimeout(hideNotification, 2500);
    }


    // ────────────────────────────────────────
    //  Chat with Exponential Backoff Retry
    // ────────────────────────────────────────

    function handleSend() {
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
        var RETRY_DELAYS = [1000, 2000]; // 1s, 2s backoff

        fetch(API_BASE + "/chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: question })
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
        sendBtn.disabled = false;
        chatInput.focus();
    }


    // ────────────────────────────────────────
    //  Message Rendering & Markdown
    // ────────────────────────────────────────

    function addMessage(role, content) {
        messages.push({ role: role, content: content });

        // Transition from centered empty landing state to active chat view
        if (messages.length === 1) {
            if (mainArea) {
                mainArea.classList.remove("is-empty");
            }
            if (emptyState) {
                emptyState.style.display = "none";
            }
            if (chatMessages) {
                chatMessages.classList.add("active");
            }
        }

        var msgEl = document.createElement("div");
        msgEl.className = "message message-" + role;

        // Header (avatar + label)
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

        // Content
        var contentEl = document.createElement("div");
        contentEl.className = "message-content markdown-body";
        contentEl.innerHTML = formatContent(content, role);
        msgEl.appendChild(contentEl);

        // Footer (timestamp + copy) for assistant messages
        if (role === "assistant") {
            var footerEl = document.createElement("div");
            footerEl.className = "message-footer";

            var timeEl = document.createElement("span");
            timeEl.className = "message-time";
            timeEl.textContent = getCurrentTime();
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

        chatMessages.appendChild(msgEl);
        scrollToBottom();
    }

    function formatContent(text, role) {
        if (role === "user") {
            var safe = escapeHtml(text);
            return safe.replace(/\n/g, "<br>");
        }

        // Assistant markdown rendering
        if (window.marked && window.DOMPurify) {
            try {
                var rawHtml = window.marked.parse(text, {
                    breaks: true,
                    gfm: true
                });
                return window.DOMPurify.sanitize(rawHtml);
            } catch (e) {
                // fallback on parser error
            }
        }

        // Fallback simple formatter
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
        } catch (e) {
            // fail silently
        }
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
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }


    // ────────────────────────────────────────
    //  Notifications
    // ────────────────────────────────────────

    function showNotification(message) {
        notification.textContent = message;
        notification.classList.add("active");
    }

    function hideNotification() {
        notification.classList.remove("active");
        notification.textContent = "";
    }


    // ────────────────────────────────────────
    //  Mobile Sidebar
    // ────────────────────────────────────────

    function toggleSidebar() {
        var isOpen = sidebar.classList.contains("open");
        if (isOpen) {
            closeSidebar();
        } else {
            sidebar.classList.add("open");
            sidebarOverlay.classList.add("active");
        }
    }

    function closeSidebar() {
        sidebar.classList.remove("open");
        sidebarOverlay.classList.remove("active");
    }


    // ────────────────────────────────────────
    //  Utilities
    // ────────────────────────────────────────

    function escapeHtml(text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }


    // ── Start ──
    document.addEventListener("DOMContentLoaded", init);

})();
