/* ========================================
   Rorak V1 — Frontend Logic (Dark Theme)
   ========================================
   Consumes the existing backend API:
     GET  /health/
     POST /documents/upload   (multipart, field: "file")
     POST /chat/              (JSON: { question })
   ======================================== */

(function () {
    "use strict";

    // ── Configuration ──
    var API_BASE = "http://localhost:8000";


    // ── State ──
    var messages = [];
    var uploadedFileName = null;
    var isLoading = false;


    // ── DOM References ──
    var emptyState = document.getElementById("emptyState");
    var chatMessages = document.getElementById("chatMessages");
    var chatInput = document.getElementById("chatInput");
    var uploadBtn = document.getElementById("uploadBtn");
    var sendBtn = document.getElementById("sendBtn");
    var fileInput = document.getElementById("fileInput");
    var uploadIndicator = document.getElementById("uploadIndicator");
    var notification = document.getElementById("notification");
    var menuToggle = document.getElementById("menuToggle");
    var sidebar = document.getElementById("sidebar");
    var toolbar = document.getElementById("toolbar");
    var sidebarOverlay = document.getElementById("sidebarOverlay");


    // ── SVG Templates ──
    var COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    var CHECK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';


    // ────────────────────────────────────────
    //  Initialization
    // ────────────────────────────────────────

    function init() {
        bindEvents();
        checkHealth();
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

        // Mobile sidebar
        menuToggle.addEventListener("click", toggleSidebar);
        sidebarOverlay.addEventListener("click", closeSidebar);
    }


    // ────────────────────────────────────────
    //  Health Check
    // ────────────────────────────────────────

    function checkHealth() {
        fetch(API_BASE + "/health/")
            .then(function (res) {
                if (!res.ok) throw new Error("unhealthy");
                return res.json();
            })
            .then(function (data) {
                if (data.status !== "healthy") {
                    showNotification("Backend is not healthy. Some features may not work.");
                }
            })
            .catch(function () {
                showNotification("Cannot connect to server. Please ensure the backend is running on " + API_BASE);
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
            showNotification("Only PDF files are supported.");
            return;
        }

        showNotification("Uploading " + file.name + "\u2026");
        uploadBtn.disabled = true;

        var formData = new FormData();
        formData.append("file", file);

        fetch(API_BASE + "/documents/upload", {
            method: "POST",
            body: formData
        })
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (err) {
                        throw new Error(err.detail || "Upload failed");
                    });
                }
                return res.json();
            })
            .then(function (data) {
                uploadedFileName = data.filename;
                renderUploadChip(data.filename);
                hideNotification();
            })
            .catch(function (error) {
                showNotification(error.message || "Upload failed. Please try again.");
            })
            .finally(function () {
                uploadBtn.disabled = false;
            });
    }

    function renderUploadChip(filename) {
        uploadIndicator.innerHTML =
            '<div class="upload-chip">' +
                '<span>' + escapeHtml(filename) + '</span>' +
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
    }


    // ────────────────────────────────────────
    //  Chat
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

        fetch(API_BASE + "/chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: question })
        })
            .then(function (res) {
                if (!res.ok) throw new Error("Chat request failed");
                return res.json();
            })
            .then(function (data) {
                removeLoadingDots(loadingId);
                addMessage("assistant", data.answer);
            })
            .catch(function () {
                removeLoadingDots(loadingId);
                showNotification("Something went wrong. Please try again.");
            })
            .finally(function () {
                isLoading = false;
                sendBtn.disabled = false;
                chatInput.focus();
            });
    }


    // ────────────────────────────────────────
    //  Message Rendering
    // ────────────────────────────────────────

    function addMessage(role, content) {
        messages.push({ role: role, content: content });

        // Transition from empty state to chat on first message
        if (messages.length === 1) {
            emptyState.style.display = "none";
            chatMessages.classList.add("active");
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
        contentEl.className = "message-content";
        contentEl.innerHTML = formatContent(content);
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

    function formatContent(text) {
        // Escape HTML first
        var safe = escapeHtml(text);
        // Render **bold** markers
        safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        // Preserve newlines
        safe = safe.replace(/\n/g, "<br>");
        return safe;
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
            // silently fail
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
            toolbar.classList.add("open");
            sidebarOverlay.classList.add("active");
        }
    }

    function closeSidebar() {
        sidebar.classList.remove("open");
        toolbar.classList.remove("open");
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
