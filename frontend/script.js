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
    var activeView = "chat"; // "chat" | "docs"

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
    var docsCountBadge = document.getElementById("docsCountBadge");
    var docsSection = document.getElementById("docsSection");
    var inputArea = document.getElementById("inputArea");

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

    // ── SVG Templates ──
    var COPY_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    var CHECK_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    var PDF_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>';


    // ────────────────────────────────────────
    //  Initialization
    // ────────────────────────────────────────

    function init() {
        setRandomGreeting();
        bindEvents();
        checkHealth();
        ensureWorkspace().then(function () {
            loadDocuments(1);
        }).catch(function (e) {
            console.warn("Workspace setup deferred:", e);
        });
    }

    function setRandomGreeting() {
        var index = Math.floor(Math.random() * GREETINGS.length);
        if (emptyGreeting) emptyGreeting.textContent = GREETINGS[index];
    }

    // ────────────────────────────────────────
    //  Workspace Resolution (V2.2)
    // ────────────────────────────────────────

    function ensureWorkspace() {
        if (currentWorkspaceId) {
            return Promise.resolve(currentWorkspaceId);
        }
        var savedId = localStorage.getItem("rorak_workspace_id");

        return fetch(API_BASE + "/workspaces/?page=1&page_size=20")
            .then(function (res) {
                if (!res.ok) throw new Error("Could not list workspaces");
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
                // Create default workspace if none exists
                return fetch(API_BASE + "/workspaces/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name: "Default Workspace" })
                })
                    .then(function (r) { return r.json(); })
                    .then(function (ws) {
                        currentWorkspaceId = ws.id;
                        localStorage.setItem("rorak_workspace_id", currentWorkspaceId);
                        return currentWorkspaceId;
                    });
            })
            .catch(function (err) {
                console.warn("Falling back for workspace resolution:", err);
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

        // Document Library header actions
        if (docsUploadBtn) {
            docsUploadBtn.addEventListener("click", function () {
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

        // Backdrop click to close modals
        [docDetailsModal, docRenameModal, docDeleteModal].forEach(function (modal) {
            if (modal) {
                modal.addEventListener("click", function (e) {
                    if (e.target === modal) {
                        modal.style.display = "none";
                    }
                });
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

            if (docsSection) docsSection.style.display = "none";
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

            if (mainArea) mainArea.classList.remove("is-empty");
            if (emptyState) emptyState.style.display = "none";
            if (chatMessages) chatMessages.style.display = "none";
            if (inputArea) inputArea.style.display = "none";

            if (docsSection) docsSection.style.display = "flex";
            loadDocuments(docLibrary.page);
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
                return fetch(url);
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

        fetch(API_BASE + "/documents/" + encodeURIComponent(documentId))
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

        fetch(API_BASE + "/documents/" + encodeURIComponent(doc.id), {
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
        fetch(API_BASE + "/documents/" + encodeURIComponent(doc.id), {
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
    //  Chat Logic (Preserved V1 Experience)
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
        var RETRY_DELAYS = [1000, 2000];

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
        if (sendBtn) sendBtn.disabled = false;
        if (chatInput) chatInput.focus();
    }

    function addMessage(role, content) {
        messages.push({ role: role, content: content });

        if (messages.length === 1 && activeView === "chat") {
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
