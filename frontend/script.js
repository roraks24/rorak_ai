/* ========================================
   Rorak V1 — Frontend Logic
   ========================================
   Consumes the existing backend API:
     GET  /health/
     POST /documents/upload   (multipart, field: "file")
     POST /chat/              (JSON: { question })
   ======================================== */

(function () {
    "use strict";

    // ── Configuration ──
    // Change this if the backend runs on a different host/port.
    var API_BASE = "https://rorak-api-871304734461.asia-south1.run.app";


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
    var sidebarOverlay = document.getElementById("sidebarOverlay");


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

        // Reset the input so the same file can be re-selected.
        fileInput.value = "";

        // Client-side validation
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
                // Backend returns: { message, filename, "Chunks Created" }
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

        // Validate
        if (!question) {
            chatInput.classList.add("shake");
            setTimeout(function () {
                chatInput.classList.remove("shake");
            }, 400);
            return;
        }

        if (isLoading) return;

        hideNotification();

        // Add user message to the UI
        addMessage("user", question);
        chatInput.value = "";

        // Show loading
        isLoading = true;
        sendBtn.disabled = true;
        var loadingId = showLoadingDots();

        // Call existing POST /chat/ endpoint
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

        var labelEl = document.createElement("div");
        labelEl.className = "message-label";
        labelEl.textContent = role === "user" ? "You" : "Rorak";

        var contentEl = document.createElement("div");
        contentEl.className = "message-content";
        // Escape HTML to prevent injection, then preserve newlines.
        contentEl.innerHTML = escapeHtml(content).replace(/\n/g, "<br>");

        msgEl.appendChild(labelEl);
        msgEl.appendChild(contentEl);
        chatMessages.appendChild(msgEl);

        scrollToBottom();
    }

    function showLoadingDots() {
        var id = "loading-" + Date.now();

        var msgEl = document.createElement("div");
        msgEl.className = "message message-assistant";
        msgEl.id = id;

        var labelEl = document.createElement("div");
        labelEl.className = "message-label";
        labelEl.textContent = "Rorak";

        var dotsEl = document.createElement("div");
        dotsEl.className = "loading-dots";
        dotsEl.innerHTML = "<span></span><span></span><span></span>";

        msgEl.appendChild(labelEl);
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
        sidebar.classList.toggle("open");
        sidebarOverlay.classList.toggle("active");
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
