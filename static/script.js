document.addEventListener("DOMContentLoaded", () => {
    const viewerStage = document.getElementById("viewerStage");
    const pdfCanvas = document.getElementById("pdfCanvas");
    const imagePreview = document.getElementById("imagePreview");
    const selectionBox = document.getElementById("selectionBox");
    const prevPageBtn = document.getElementById("prevPageBtn");
    const nextPageBtn = document.getElementById("nextPageBtn");
    const zoomInBtn = document.getElementById("zoomInBtn");
    const zoomOutBtn = document.getElementById("zoomOutBtn");
    const zoomValue = document.getElementById("zoomValue");
    const pageIndicator = document.getElementById("pageIndicator");
    const thumbSidebar = document.getElementById("thumbSidebar");
    const clearSelectionBtn = document.getElementById("clearSelectionBtn");

    const uploadForm = document.getElementById("uploadForm");
    const loaderOverlay = document.getElementById("loaderOverlay");
    const loaderLog = document.getElementById("loaderLog");
    const loaderProgressBar = document.getElementById("loaderProgressBar");
    const fileInput = document.getElementById("fileInput");
    const dropZone = document.getElementById("dropZone");
    const fileMeta = document.getElementById("fileMeta");
    const analyzeScope = document.getElementById("analyzeScope");
    const selectedRegionInput = document.getElementById("selectedRegion");
    const currentPageInput = document.getElementById("currentPage");
    const analysisButtons = document.querySelectorAll("[data-scope]");
    const reviewFileUrlInput = document.getElementById("reviewFileUrl");
    const reviewIsPdfInput = document.getElementById("reviewIsPdf");
    const reviewResultPanel = document.getElementById("reviewResultPanel");
    const reviewScoreRing = document.getElementById("reviewScoreRing");
    const reviewScoreValue = document.getElementById("reviewScoreValue");
    const reviewQuality = document.getElementById("reviewQuality");
    const reviewMlLabel = document.getElementById("reviewMlLabel");
    const reviewMlConfidence = document.getElementById("reviewMlConfidence");
    const reviewAiInsight = document.getElementById("reviewAiInsight");
    const reviewIssues = document.getElementById("reviewIssues");
    const reviewTextPreview = document.getElementById("reviewTextPreview");
    const debugTestMode = false;
    const isReviewPage = Boolean(reviewFileUrlInput || viewerStage);

    let selectedScope = "full_document";
    let pdfDoc = null;
    let pageNum = 1;
    let zoomLevel = 1;
    let fileType = reviewIsPdfInput?.value === "1" ? "application/pdf" : "";
    let selectedRegion = null;
    let isSelecting = false;
    let startX = 0;
    let startY = 0;
    let renderedTextMap = [];

    const ensurePdfJs = () => {
        if (window.pdfjsLib) return;
        const script = document.createElement("script");
        script.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
        script.onload = () => {
            window.pdfjsLib.GlobalWorkerOptions.workerSrc =
                "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
        };
        document.body.appendChild(script);
    };

    const formatFileSize = (size) => {
        if (size < 1024) return `${size} B`;
        if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`;
        return `${(size / (1024 * 1024)).toFixed(2)} MB`;
    };

    const setSelection = (x, y, width, height) => {
        if (!selectionBox || !selectedRegionInput) return;
        selectionBox.classList.remove("hidden");
        selectionBox.style.left = `${x}px`;
        selectionBox.style.top = `${y}px`;
        selectionBox.style.width = `${width}px`;
        selectionBox.style.height = `${height}px`;
        selectedRegion = { x, y, width, height, page: pageNum };
        selectedRegionInput.value = `x:${x}, y:${y}, w:${width}, h:${height}, page:${pageNum}`;
    };

    const setupSelection = () => {
        if (!viewerStage || !selectionBox) return;
        viewerStage.addEventListener("mousedown", (event) => {
            const rect = viewerStage.getBoundingClientRect();
            isSelecting = true;
            startX = event.clientX - rect.left;
            startY = event.clientY - rect.top;
            setSelection(startX, startY, 0, 0);
        });

        viewerStage.addEventListener("mousemove", (event) => {
            if (!isSelecting) return;
            const rect = viewerStage.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;
            const width = Math.abs(x - startX);
            const height = Math.abs(y - startY);
            setSelection(Math.min(startX, x), Math.min(startY, y), width, height);
        });

        window.addEventListener("mouseup", () => {
            isSelecting = false;
        });
    };

    const renderPdfPage = async () => {
        if (!pdfDoc || !pdfCanvas) return;
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: zoomLevel });
        const context = pdfCanvas.getContext("2d");
        pdfCanvas.height = viewport.height;
        pdfCanvas.width = viewport.width;
        await page.render({ canvasContext: context, viewport }).promise;

        const textContent = await page.getTextContent();
        renderedTextMap[pageNum] = textContent.items.map((item) => item.str).join(" ").toLowerCase();
        pageIndicator.textContent = `Page ${pageNum} / ${pdfDoc.numPages}`;
        if (currentPageInput) currentPageInput.value = String(pageNum);
        if (selectionBox) selectionBox.classList.add("hidden");
    };

    const drawThumbnails = async () => {
        if (!pdfDoc || !thumbSidebar) return;
        thumbSidebar.classList.remove("hidden");
        thumbSidebar.innerHTML = "";
        for (let i = 1; i <= pdfDoc.numPages; i += 1) {
            const thumb = document.createElement("button");
            thumb.type = "button";
            thumb.className = "thumb-item";
            thumb.textContent = `Page ${i}`;
            thumb.addEventListener("click", async () => {
                pageNum = i;
                await renderPdfPage();
            });
            thumbSidebar.appendChild(thumb);
        }
    };

    const loadPdfPreview = async (fileOrUrl) => {
        ensurePdfJs();
        const waitForLib = () =>
            new Promise((resolve) => {
                const check = () => {
                    if (window.pdfjsLib) resolve();
                    else setTimeout(check, 120);
                };
                check();
            });

        await waitForLib();
        const arrayBuffer =
            typeof fileOrUrl === "string"
                ? await fetch(fileOrUrl).then((response) => response.arrayBuffer())
                : await fileOrUrl.arrayBuffer();
        const loadingTask = window.pdfjsLib.getDocument({ data: arrayBuffer });
        pdfDoc = await loadingTask.promise;
        pageNum = 1;
        zoomLevel = 1;
        renderedTextMap = [];

        imagePreview.classList.add("hidden");
        pdfCanvas.classList.remove("hidden");
        await renderPdfPage();
        await drawThumbnails();
    };

    const loadImagePreview = (fileOrUrl) => {
        if (!thumbSidebar || !pdfCanvas || !imagePreview) return;
        thumbSidebar.classList.add("hidden");
        pdfCanvas.classList.add("hidden");
        imagePreview.classList.remove("hidden");
        imagePreview.src = typeof fileOrUrl === "string" ? fileOrUrl : URL.createObjectURL(fileOrUrl);
        pageIndicator.textContent = "Page 1 / 1";
        if (currentPageInput) currentPageInput.value = "1";
    };

    const showFileMeta = (file) => {
        fileMeta.classList.remove("hidden");
        fileMeta.innerHTML = `<strong>${file.name}</strong> <span>${formatFileSize(file.size)}</span>`;
    };

    const onFileSelected = async (file) => {
        if (!file) return;
        fileType = file.type;
        showFileMeta(file);
        if (!isReviewPage) return;

        if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
            await loadPdfPreview(file);
        } else {
            loadImagePreview(file);
        }
    };

    if (dropZone && fileInput) {
        dropZone.addEventListener("dragover", (event) => {
            event.preventDefault();
            dropZone.classList.add("drag-active");
        });
        dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-active"));
        dropZone.addEventListener("drop", async (event) => {
            event.preventDefault();
            dropZone.classList.remove("drag-active");
            const file = event.dataTransfer.files[0];
            if (!file) return;
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
            await onFileSelected(file);
        });
        fileInput.addEventListener("change", async (event) => {
            const file = event.target.files[0];
            await onFileSelected(file);
        });
    }

    if (fileInput?.files?.length) {
        onFileSelected(fileInput.files[0]);
    }

    const setAnalyzeButtonsDisabled = (isDisabled) => {
        analysisButtons.forEach((button) => {
            button.disabled = isDisabled;
            button.style.opacity = isDisabled ? "0.6" : "1";
            button.style.pointerEvents = isDisabled ? "none" : "auto";
        });
        if (clearSelectionBtn) clearSelectionBtn.disabled = isDisabled;
    };

    const updateReviewResults = (payload) => {
        if (
            !reviewResultPanel ||
            !reviewScoreRing ||
            !reviewScoreValue ||
            !reviewQuality ||
            !reviewMlLabel ||
            !reviewMlConfidence ||
            !reviewAiInsight ||
            !reviewIssues ||
            !reviewTextPreview
        ) {
            return;
        }
        reviewResultPanel.classList.remove("hidden");
        const score = Number(payload.score || 0);
        reviewScoreValue.textContent = `${score}%`;
        reviewQuality.textContent = payload.quality || "Needs Review";
        reviewMlLabel.textContent = payload.ml_label || "Unknown";
        reviewMlConfidence.textContent = String(payload.ml_confidence || 0);
        reviewAiInsight.textContent = payload.ai_insight || "No insight available.";

        reviewScoreRing.classList.remove("score-high", "score-mid", "score-low");
        if (score >= 75) reviewScoreRing.classList.add("score-high");
        else if (score >= 50) reviewScoreRing.classList.add("score-mid");
        else reviewScoreRing.classList.add("score-low");

        reviewIssues.innerHTML = "";
        const issues = Array.isArray(payload.issues) && payload.issues.length ? payload.issues : ["No issues detected."];
        issues.forEach((issue) => {
            const li = document.createElement("li");
            li.textContent = issue;
            reviewIssues.appendChild(li);
        });
        reviewTextPreview.textContent = payload.text_preview || "No text extracted.";
    };

    const runAnalysis = async (scope) => {
        if (!analyzeScope) return;
        selectedScope = scope || "full_document";
        analyzeScope.value = selectedScope;

        if (selectedScope === "selected_area" && !selectedRegion) {
            alert("Please select an area first.");
            return;
        }

        setAnalyzeButtonsDisabled(true);
        const logs = [
            "Extracting text using OCR...",
            "Processing with NLP...",
            "Comparing with dataset...",
        ];
        const progress = [30, 60, 90];
        let progressIndex = 0;
        if (loaderLog) loaderLog.textContent = logs[0];
        if (loaderProgressBar) loaderProgressBar.style.width = `${progress[0]}%`;
        if (loaderOverlay) loaderOverlay.classList.remove("hidden");

        const interval = window.setInterval(() => {
            progressIndex = (progressIndex + 1) % logs.length;
            if (loaderLog) loaderLog.textContent = logs[progressIndex];
            if (loaderProgressBar) loaderProgressBar.style.width = `${progress[progressIndex]}%`;
        }, 900);

        try {
            const response = await fetch("/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    analyze_scope: selectedScope,
                    current_page: currentPageInput?.value || "1",
                    selected_region: selectedRegionInput?.value || "",
                    debug_test_mode: debugTestMode,
                }),
            });
            let payload = {};
            try {
                payload = await response.json();
            } catch (parseError) {
                const rawText = await response.text();
                payload = { error: rawText || "Invalid server response." };
            }
            if (!response.ok || payload.status === "error") {
                const message = payload.message || payload.error || "Analysis failed.";
                alert(message);
                if (reviewResultPanel) reviewResultPanel.classList.remove("hidden");
                if (reviewTextPreview) reviewTextPreview.textContent = `Error: ${message}`;
                return;
            }
            if (payload.status !== "success") {
                throw new Error("Unexpected analyze response format.");
            }
            if (loaderProgressBar) loaderProgressBar.style.width = "100%";
            updateReviewResults(payload);
            if (payload.redirect_url) {
                window.location.href = payload.redirect_url;
                return;
            }
        } catch (error) {
            alert(`Unable to analyze right now. ${error?.message || "Please try again."}`);
        } finally {
            window.clearInterval(interval);
            setAnalyzeButtonsDisabled(false);
            if (loaderOverlay) loaderOverlay.classList.add("hidden");
        }
    };

    if (analysisButtons.length) {
        analysisButtons.forEach((button) => {
            button.addEventListener("click", () => {
                runAnalysis(button.dataset.scope || "full_document");
            });
        });
    }

    if (zoomInBtn) {
        zoomInBtn.addEventListener("click", async () => {
            zoomLevel = Math.min(zoomLevel + 0.1, 2.5);
            zoomValue.textContent = `${Math.round(zoomLevel * 100)}%`;
            if (pdfDoc) await renderPdfPage();
        });
    }
    if (zoomOutBtn) {
        zoomOutBtn.addEventListener("click", async () => {
            zoomLevel = Math.max(zoomLevel - 0.1, 0.5);
            zoomValue.textContent = `${Math.round(zoomLevel * 100)}%`;
            if (pdfDoc) await renderPdfPage();
        });
    }
    if (prevPageBtn) {
        prevPageBtn.addEventListener("click", async () => {
            if (!pdfDoc || pageNum <= 1) return;
            pageNum -= 1;
            await renderPdfPage();
        });
    }
    if (nextPageBtn) {
        nextPageBtn.addEventListener("click", async () => {
            if (!pdfDoc || pageNum >= pdfDoc.numPages) return;
            pageNum += 1;
            await renderPdfPage();
        });
    }

    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener("click", () => {
            selectedRegion = null;
            selectedRegionInput.value = "";
            selectionBox.classList.add("hidden");
        });
    }
    setupSelection();

    const initializeReviewFile = async () => {
        if (!reviewFileUrlInput?.value) return;
        const fileUrl = reviewFileUrlInput.value;
        const isPdf = reviewIsPdfInput?.value === "1";
        fileType = isPdf ? "application/pdf" : "image/*";

        if (isPdf) await loadPdfPreview(fileUrl);
        else loadImagePreview(fileUrl);
    };
    initializeReviewFile();

    const revealElements = document.querySelectorAll(".reveal-on-scroll");
    if (revealElements.length) {
        const revealObserver = new IntersectionObserver(
            (entries, observer) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("revealed");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.2 }
        );
        revealElements.forEach((element) => revealObserver.observe(element));
    }

    const floatingChatBtn = document.getElementById("floatingChatBtn");
    const floatingChatWidget = document.getElementById("floatingChatWidget");
    const floatingChatClose = document.getElementById("floatingChatClose");
    const floatingChatForm = document.getElementById("floatingChatForm");
    const floatingChatInput = document.getElementById("floatingChatInput");
    const floatingChatMessages = document.getElementById("floatingChatMessages");
    const FLOATING_CHAT_STORAGE_KEY = "ayushFloatingChatMessages";
    const isFullChatPage = window.location.pathname === "/chatbot";

    const scrollFloatingChatToBottom = () => {
        if (floatingChatMessages) {
            floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;
        }
    };

    const readStoredFloatingMessages = () => {
        try {
            const rawValue = localStorage.getItem(FLOATING_CHAT_STORAGE_KEY);
            if (!rawValue) return [];
            const parsed = JSON.parse(rawValue);
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            return [];
        }
    };

    const saveFloatingMessages = (messages) => {
        localStorage.setItem(FLOATING_CHAT_STORAGE_KEY, JSON.stringify(messages.slice(-40)));
    };

    const appendFloatingMessage = (sender, text, options = {}) => {
        if (!floatingChatMessages) return;
        const wrapper = document.createElement("div");
        wrapper.className = `floating-message ${sender}`;
        const bubble = document.createElement("div");
        bubble.className = "floating-bubble";

        if (options.streaming) {
            bubble.innerHTML = '<span class="floating-typing">Ayush AI is typing...</span>';
        } else {
            bubble.textContent = text;
        }

        wrapper.appendChild(bubble);
        floatingChatMessages.appendChild(wrapper);
        scrollFloatingChatToBottom();
        return bubble;
    };

    const streamFloatingResponse = (target, fullText) =>
        new Promise((resolve) => {
            target.textContent = "";
            let index = 0;
            const timer = setInterval(() => {
                if (index >= fullText.length) {
                    clearInterval(timer);
                    resolve();
                    return;
                }
                target.textContent += fullText[index];
                index += 1;
                scrollFloatingChatToBottom();
            }, 14);
        });

    const renderStoredFloatingMessages = () => {
        if (!floatingChatMessages) return;
        const stored = readStoredFloatingMessages();
        if (!stored.length) return;

        floatingChatMessages.innerHTML = "";
        stored.forEach((message) => {
            const sender = message.sender === "user" ? "user" : "ai";
            appendFloatingMessage(sender, String(message.text || ""));
        });
    };

    const handleFloatingChatSubmit = async (event) => {
        event.preventDefault();
        if (!floatingChatInput || !floatingChatMessages) return;

        const userMessage = floatingChatInput.value.trim();
        if (!userMessage) return;

        appendFloatingMessage("user", userMessage);
        floatingChatInput.value = "";

        const existingMessages = readStoredFloatingMessages();
        existingMessages.push({ sender: "user", text: userMessage });
        saveFloatingMessages(existingMessages);

        const aiBubble = appendFloatingMessage("ai", "", { streaming: true });
        try {
            const controller = new AbortController();
            const timeoutId = window.setTimeout(() => controller.abort(), 25000);
            const response = await fetch("/chat_api", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: userMessage }),
                signal: controller.signal,
            });
            window.clearTimeout(timeoutId);
            const payload = await response.json();
            const answer =
                response.ok && payload.response
                    ? String(payload.response)
                    : String(payload.error || "Unable to process your request right now.");
            if (aiBubble) {
                await streamFloatingResponse(aiBubble, answer);
            }
            const updatedMessages = readStoredFloatingMessages();
            updatedMessages.push({ sender: "ai", text: answer });
            saveFloatingMessages(updatedMessages);
        } catch (error) {
            const fallback = error?.name === "AbortError"
                ? "The response took too long. Please try again."
                : "Connection issue. Please try again.";
            if (aiBubble) aiBubble.textContent = fallback;
            const updatedMessages = readStoredFloatingMessages();
            updatedMessages.push({ sender: "ai", text: fallback });
            saveFloatingMessages(updatedMessages);
        }
    };

    if (floatingChatBtn && floatingChatWidget) {
        floatingChatBtn.addEventListener("click", () => {
            const isHidden = floatingChatWidget.classList.contains("hidden");
            floatingChatWidget.classList.toggle("hidden", !isHidden);
            floatingChatBtn.setAttribute("aria-expanded", String(isHidden));
            if (isHidden) {
                floatingChatInput?.focus();
                scrollFloatingChatToBottom();
            }
        });
    }

    if (isFullChatPage) {
        if (floatingChatWidget) floatingChatWidget.classList.add("hidden");
        if (floatingChatBtn) floatingChatBtn.classList.add("hidden");
    }

    if (floatingChatClose && floatingChatWidget) {
        floatingChatClose.addEventListener("click", () => {
            floatingChatWidget.classList.add("hidden");
            floatingChatBtn?.setAttribute("aria-expanded", "false");
        });
    }

    if (floatingChatForm) {
        floatingChatForm.addEventListener("submit", handleFloatingChatSubmit);
    }

    renderStoredFloatingMessages();
    if (!readStoredFloatingMessages().length) {
        saveFloatingMessages([
            {
                sender: "ai",
                text: "Hi! How can I help you?",
            },
        ]);
    }

    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const streamingResponse = document.getElementById("streamingResponse");
    const chatMessages = document.getElementById("chatMessages");
    const copyBtns = document.querySelectorAll(".copy-btn");
    const chips = document.querySelectorAll(".chip");
    const regenBtn = document.getElementById("regenBtn");

    const streamText = (target, fullText) => {
        target.textContent = "";
        let index = 0;
        const cursor = document.createElement("span");
        cursor.className = "blinking-cursor";
        cursor.textContent = "|";
        target.appendChild(cursor);

        const timer = setInterval(() => {
            if (index >= fullText.length) {
                clearInterval(timer);
                cursor.remove();
                return;
            }
            const nextChar = document.createTextNode(fullText[index]);
            target.insertBefore(nextChar, cursor);
            index += 1;
            if (chatMessages) {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        }, 14);
    };

    if (streamingResponse) {
        const response = streamingResponse.dataset.response || "";
        if (response) streamText(streamingResponse, response);
    }

    if (chatForm && chatInput) {
        chatInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                chatForm.submit();
            }
        });
    }

    if (chips.length && chatInput) {
        chips.forEach((chip) => {
            chip.addEventListener("click", () => {
                chatInput.value = chip.dataset.prompt || "";
                chatInput.focus();
            });
        });
    }

    if (copyBtns.length) {
        copyBtns.forEach((btn) => {
            btn.addEventListener("click", async () => {
                const msg = btn.closest(".message")?.querySelector(".message-body")?.textContent || "";
                if (!msg) return;
                await navigator.clipboard.writeText(msg);
                btn.textContent = "Copied";
                setTimeout(() => {
                    btn.textContent = "Copy";
                }, 900);
            });
        });
    }

    if (regenBtn && chatForm) {
        regenBtn.addEventListener("click", () => {
            chatForm.submit();
        });
    }

    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});
