(function () {
    var form = document.getElementById("entry-form");
    var bodyText = document.getElementById("entry_body_text");
    var fileInput = document.getElementById("attachment");
    var attachmentName = document.getElementById("attachment-name");
    var calendarTrigger = document.getElementById("calendar-trigger");
    var calendarPanel = document.getElementById("calendar-panel");
    var calendarTitle = document.getElementById("calendar_title");
    var calendarDate = document.getElementById("calendar_date");
    var calendarTime = document.getElementById("calendar_time");
    var calendarDescription = document.getElementById("calendar_description");
    var calendarDownload = document.getElementById("calendar-download");
    var calendarCancel = document.getElementById("calendar-cancel");
    var interactionAtLocalInput = document.getElementById("entry_interaction_at_local");
    var interactionAtUtcInput = document.getElementById("entry_interaction_at");
    var entryFormLayout = document.querySelector(".entry-form-layout");
    var entryFormPrimary = document.querySelector(".entry-form-primary");
    var entryHistorySidebar = document.querySelector(".entry-history-sidebar");
    var entryHistoryList = document.querySelector(".entry-history-sidebar .entry-history-list");
    var entryLayoutResizer = document.getElementById("entry-layout-resizer");
    var entryLayoutStorageKeyPct = "hsl.entryLayout.sidebarWidthPct";
    if (!form || !fileInput) {
        return;
    }

    function syncHistorySidebarHeight() {
        if (!entryFormPrimary || !entryHistorySidebar) {
            return;
        }

        if (window.matchMedia("(max-width: 900px)").matches) {
            entryHistorySidebar.style.height = "";
            if (entryHistoryList) {
                entryHistoryList.style.overflowY = "";
            }
            return;
        }

        // Measure natural content height first, then only constrain when overflow would occur.
        entryHistorySidebar.style.height = "";
        if (entryHistoryList) {
            entryHistoryList.style.overflowY = "visible";
        }

        var formPanelHeight = entryFormPrimary.offsetHeight;
        var naturalSidebarHeight = entryHistorySidebar.offsetHeight;

        if (naturalSidebarHeight > formPanelHeight) {
            entryHistorySidebar.style.height = formPanelHeight + "px";
            if (entryHistoryList) {
                entryHistoryList.style.overflowY = "auto";
            }
        }
    }

    function initLayoutResizer() {
        if (!entryFormLayout || !entryHistorySidebar || !entryLayoutResizer || window.matchMedia("(max-width: 900px)").matches) {
            return;
        }

        var isDragging = false;
        var startX = 0;
        var startSidebarWidth = 0;

        function clampSidebarWidth(width) {
            var layoutWidth = entryFormLayout.clientWidth;
            var minSidebar = 220;
            var minPrimary = 360;
            var maxSidebar = Math.max(minSidebar, layoutWidth - minPrimary);
            return Math.min(Math.max(width, minSidebar), maxSidebar);
        }

        function widthPxToPct(widthPx) {
            var layoutWidth = entryFormLayout.clientWidth;
            if (!layoutWidth) {
                return 30;
            }
            return (widthPx / layoutWidth) * 100;
        }

        function applySidebarWidth(widthPx) {
            var clampedWidth = clampSidebarWidth(widthPx);
            var percentWidth = widthPxToPct(clampedWidth);
            entryFormLayout.style.setProperty("--entry-sidebar-width", percentWidth.toFixed(2) + "%");
            return clampedWidth;
        }

        function saveSidebarWidth(width) {
            try {
                window.localStorage.setItem(entryLayoutStorageKeyPct, widthPxToPct(width).toFixed(2));
            } catch (_err) {
                // Ignore storage errors (private mode / disabled storage).
            }
        }

        function loadSavedSidebarWidth() {
            try {
                var rawPct = window.localStorage.getItem(entryLayoutStorageKeyPct);
                if (rawPct) {
                    var parsedPct = Number(rawPct);
                    if (Number.isFinite(parsedPct) && parsedPct > 0) {
                        return (entryFormLayout.clientWidth * parsedPct) / 100;
                    }
                }
            } catch (_err) {
                // Ignore storage access errors.
            }

            return null;
        }

        var savedSidebarWidth = loadSavedSidebarWidth();
        if (savedSidebarWidth !== null) {
            applySidebarWidth(savedSidebarWidth);
        }

        function onPointerMove(event) {
            if (!isDragging) {
                return;
            }

            var deltaX = event.clientX - startX;
            var nextSidebarWidth = clampSidebarWidth(startSidebarWidth - deltaX);
            applySidebarWidth(nextSidebarWidth);
            syncHistorySidebarHeight();
        }

        function onPointerUp() {
            if (!isDragging) {
                return;
            }

            isDragging = false;
            entryLayoutResizer.classList.remove("is-dragging");
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
            saveSidebarWidth(entryHistorySidebar.getBoundingClientRect().width);
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", onPointerUp);
        }

        entryLayoutResizer.addEventListener("pointerdown", function (event) {
            isDragging = true;
            startX = event.clientX;
            startSidebarWidth = entryHistorySidebar.getBoundingClientRect().width;
            entryLayoutResizer.classList.add("is-dragging");
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
            window.addEventListener("pointermove", onPointerMove);
            window.addEventListener("pointerup", onPointerUp);
        });
    }

    function todayIsoDate() {
        var now = new Date();
        var y = String(now.getFullYear());
        var m = String(now.getMonth() + 1).padStart(2, "0");
        var d = String(now.getDate()).padStart(2, "0");
        return y + "-" + m + "-" + d;
    }

    function formatCalendarSummary(title, dateValue, timeValue) {
        var pieces = ["[Calendar Event]"];
        pieces.push("Title: " + title);
        pieces.push("Date: " + dateValue);
        if (timeValue) {
            pieces.push("Time: " + timeValue);
        }
        return pieces.join("\n");
    }

    function appendCalendarBlockToEntry(title, dateValue, timeValue, description) {
        if (!bodyText) {
            return;
        }

        var summary = formatCalendarSummary(title, dateValue, timeValue);
        if (description) {
            summary += "\nDescription: " + description;
        }

        var current = bodyText.value || "";
        if (current && !current.endsWith("\n")) {
            current += "\n";
        }

        bodyText.value = current + "\n" + summary + "\n";
    }

    function setCalendarDefaults() {
        if (!calendarTitle || !calendarDate || !calendarDescription) {
            return;
        }

        if (!calendarTitle.value.trim()) {
            var titleBase = document.title.split(" — ")[0] || "Vendor";
            calendarTitle.value = "Follow-up with " + titleBase;
        }

        if (!calendarDate.value) {
            calendarDate.value = todayIsoDate();
        }

        if (bodyText && !calendarDescription.value.trim()) {
            calendarDescription.value = bodyText.value.trim();
        }
    }

    function submitCalendarDownload(title, dateValue, timeValue, description) {
        var postForm = document.createElement("form");
        postForm.method = "post";
        postForm.action = "/calendar/export";
        postForm.target = "_blank";

        function addField(name, value) {
            var input = document.createElement("input");
            input.type = "hidden";
            input.name = name;
            input.value = value;
            postForm.appendChild(input);
        }

        addField("title", title);
        addField("event_date", dateValue);
        addField("event_time", timeValue);
        addField("description", description);

        document.body.appendChild(postForm);
        postForm.submit();
        document.body.removeChild(postForm);
    }

    function setAttachmentName() {
        if (!attachmentName) {
            return;
        }

        if (fileInput.files && fileInput.files.length > 0) {
            if (fileInput.files.length === 1) {
                attachmentName.textContent = "Selected: " + fileInput.files[0].name;
                return;
            }

            attachmentName.textContent = "Selected " + fileInput.files.length + " files";
            return;
        }

        attachmentName.textContent = "No file selected";
    }

    function hasExtension(fileName) {
        var base = (fileName || "").split(/[\\/]/).pop();
        var lastDot = base.lastIndexOf(".");
        return lastDot > 0 && lastDot < base.length - 1;
    }

    function toDatetimeLocalValue(dateValue) {
        var y = String(dateValue.getFullYear());
        var m = String(dateValue.getMonth() + 1).padStart(2, "0");
        var d = String(dateValue.getDate()).padStart(2, "0");
        var hh = String(dateValue.getHours()).padStart(2, "0");
        var mm = String(dateValue.getMinutes()).padStart(2, "0");
        return y + "-" + m + "-" + d + "T" + hh + ":" + mm;
    }

    function setInteractionDefaults() {
        if (!interactionAtLocalInput || !interactionAtUtcInput) {
            return;
        }

        if (interactionAtLocalInput.value) {
            return;
        }

        var utcValue = (interactionAtLocalInput.dataset.utcValue || interactionAtUtcInput.value || "").trim();
        if (!utcValue) {
            return;
        }

        var parsed = new Date(utcValue);
        if (Number.isNaN(parsed.getTime())) {
            return;
        }

        interactionAtLocalInput.value = toDatetimeLocalValue(parsed);
        interactionAtUtcInput.value = utcValue;
    }

    function setInteractionUtcForSubmit() {
        if (!interactionAtLocalInput || !interactionAtUtcInput) {
            return true;
        }

        var localValue = (interactionAtLocalInput.value || "").trim();
        if (!localValue) {
            interactionAtUtcInput.value = "";
            interactionAtLocalInput.setCustomValidity("");
            return true;
        }

        var parsed = new Date(localValue);
        if (Number.isNaN(parsed.getTime())) {
            interactionAtLocalInput.setCustomValidity("Interaction Date is invalid.");
            return false;
        }

        interactionAtUtcInput.value = parsed.toISOString().replace(".000Z", "Z");
        interactionAtLocalInput.setCustomValidity("");
        return true;
    }

    function validateFileInput() {
        if (!fileInput.files || fileInput.files.length === 0) {
            fileInput.setCustomValidity("");
            return true;
        }

        for (var index = 0; index < fileInput.files.length; index += 1) {
            var selectedName = fileInput.files[index].name;
            if (!hasExtension(selectedName)) {
                fileInput.setCustomValidity("Attached files must include an extension, such as .pdf or .jpg.");
                return false;
            }
        }

        fileInput.setCustomValidity("");
        return true;
    }

    fileInput.addEventListener("change", function () {
        validateFileInput();
        setAttachmentName();
        fileInput.reportValidity();
    });

    if (calendarTrigger && calendarPanel) {
        calendarTrigger.addEventListener("click", function () {
            var nowHidden = !calendarPanel.hidden;
            calendarPanel.hidden = nowHidden;
            if (!calendarPanel.hidden) {
                setCalendarDefaults();
                if (calendarTitle) {
                    calendarTitle.focus();
                }
            }
        });
    }

    if (calendarCancel && calendarPanel) {
        calendarCancel.addEventListener("click", function () {
            calendarPanel.hidden = true;
        });
    }

    if (calendarDownload && calendarPanel) {
        calendarDownload.addEventListener("click", function () {
            var titleValue = (calendarTitle && calendarTitle.value || "").trim();
            var dateValue = (calendarDate && calendarDate.value || "").trim();
            var timeValue = (calendarTime && calendarTime.value || "").trim();
            var descriptionValue = (calendarDescription && calendarDescription.value || "").trim();

            if (!titleValue) {
                alert("Calendar title is required.");
                if (calendarTitle) {
                    calendarTitle.focus();
                }
                return;
            }

            if (!dateValue) {
                alert("Calendar date is required.");
                if (calendarDate) {
                    calendarDate.focus();
                }
                return;
            }

            submitCalendarDownload(titleValue, dateValue, timeValue, descriptionValue);
            appendCalendarBlockToEntry(titleValue, dateValue, timeValue, descriptionValue);
            calendarPanel.hidden = true;
        });
    }

    setAttachmentName();
    setInteractionDefaults();
    initLayoutResizer();
    syncHistorySidebarHeight();

    if (window.ResizeObserver && entryFormPrimary) {
        var formPanelObserver = new ResizeObserver(function () {
            syncHistorySidebarHeight();
        });
        formPanelObserver.observe(entryFormPrimary);
    }

    window.addEventListener("resize", syncHistorySidebarHeight);

    if (bodyText) {
        bodyText.addEventListener("input", syncHistorySidebarHeight);
        bodyText.addEventListener("mouseup", syncHistorySidebarHeight);
    }

    form.addEventListener("submit", function (event) {
        if (!setInteractionUtcForSubmit()) {
            event.preventDefault();
            interactionAtLocalInput.reportValidity();
            return;
        }
        if (!validateFileInput()) {
            event.preventDefault();
            fileInput.reportValidity();
        }
    });
})();
