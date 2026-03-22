(function () {
    var adminRoot = document.querySelector("[data-label-admin]");
    var list = document.querySelector(".label-management-list");
    var emptyState = document.querySelector("[data-label-empty-state]");
    var createRowEl = document.querySelector("[data-label-create-row]");
    var newTrigger = document.querySelector("[data-label-new-trigger]");

    if (!adminRoot) {
        return;
    }

    var createUrl = adminRoot.dataset.labelCreateUrl || "";
    var renameUrlTemplate = adminRoot.dataset.labelRenameUrlTemplate || "";
    var colorUrlTemplate = adminRoot.dataset.labelColorUrlTemplate || "";
    var deleteUrlTemplate = adminRoot.dataset.labelDeleteUrlTemplate || "";

    // --- shared helpers -------------------------------------------------

    function buildLabelUrl(template, labelUid) {
        if (!template) {
            return "";
        }
        return template.replace("__LABEL_UID__", encodeURIComponent(labelUid));
    }

    function updateEmptyState() {
        if (!list || !emptyState) {
            return;
        }
        emptyState.hidden = list.querySelectorAll("[data-label-row]").length !== 0;
    }

    function parseResponse(response) {
        return response.json().catch(function () {
            return {};
        });
    }

    function closeAllEditRows() {
        list.querySelectorAll("[data-label-row].is-editing").forEach(function (r) {
            r.classList.remove("is-editing");
        });
    }

    function hideCreateRow() {
        if (!createRowEl) {
            return;
        }
        createRowEl.hidden = true;
        var nameIn = createRowEl.querySelector("[data-create-name-input]");
        var colorIn = createRowEl.querySelector("[data-create-color-input]");
        var errEl = createRowEl.querySelector("[data-create-row-error]");
        if (nameIn) { nameIn.value = ""; }
        if (colorIn) { colorIn.value = "#3a7ebf"; }
        if (errEl) { errEl.hidden = true; errEl.textContent = ""; }
    }

    // --- existing row setup ---------------------------------------------

    function setupRow(row) {
        var labelUid = row.dataset.labelUid || "";
        var currentName = row.dataset.labelName || "";
        var currentColor = row.dataset.labelColor || "#000000";

        var nameText = row.querySelector("[data-label-name-text]");
        var editTrigger = row.querySelector("[data-label-edit-trigger]");
        var nameInput = row.querySelector("[data-label-name-input]");
        var nameSave = row.querySelector("[data-label-name-save]");
        var nameCancel = row.querySelector("[data-label-name-cancel]");
        var colorInput = row.querySelector("[data-label-color-input]");
        var colorValue = row.querySelector("[data-label-color-value]"); // optional
        var deleteButton = row.querySelector("[data-label-delete]");
        var rowError = row.querySelector("[data-label-row-error]");

        var isSavingName = false;
        var isSavingColor = false;
        var isDeleting = false;

        if (!labelUid || !nameText || !editTrigger || !nameInput || !nameSave || !nameCancel || !colorInput || !deleteButton || !rowError) {
            return;
        }

        function showError(message) {
            rowError.textContent = message || "An unexpected error occurred.";
            rowError.hidden = false;
        }

        function clearError() {
            rowError.textContent = "";
            rowError.hidden = true;
        }

        function refreshBusyState() {
            var isBusy = isSavingName || isSavingColor || isDeleting;
            row.classList.toggle("is-row-busy", isBusy);
            editTrigger.disabled = isBusy;
            nameSave.disabled = isBusy;
            nameCancel.disabled = isBusy;
            colorInput.disabled = isBusy;
            deleteButton.disabled = isBusy;
        }

        function setEditing(isEditing) {
            row.classList.toggle("is-editing", isEditing);
            if (isEditing) {
                nameInput.focus();
                nameInput.select();
            }
        }

        function syncColorValue() {
            if (colorValue) {
                colorValue.textContent = (colorInput.value || "#000000").toUpperCase();
            }
        }

        function applyColor(color) {
            currentColor = color || "#000000";
            row.dataset.labelColor = currentColor;
            colorInput.value = currentColor;
            colorInput.defaultValue = currentColor;
            syncColorValue();
        }

        function applyName(name) {
            currentName = name;
            row.dataset.labelName = currentName;
            nameText.textContent = currentName;
            nameInput.value = currentName;
            nameInput.defaultValue = currentName;
        }

        async function renameLabel() {
            if (isSavingName || isDeleting) {
                return;
            }

            var submittedName = String(nameInput.value || "").trim();
            if (!submittedName) {
                showError("Label name is required");
                return;
            }

            if (submittedName === currentName) {
                clearError();
                setEditing(false);
                return;
            }

            clearError();
            isSavingName = true;
            refreshBusyState();

            try {
                var response = await fetch(buildLabelUrl(renameUrlTemplate, labelUid), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json", "Accept": "application/json" },
                    body: JSON.stringify({ name: submittedName }),
                });
                var payload = await parseResponse(response);
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "Unable to rename label.");
                }
                applyName(payload.name || submittedName);
                applyColor(payload.color || currentColor);
                setEditing(false);
            } catch (error) {
                showError(error.message || "Unable to rename label.");
            } finally {
                isSavingName = false;
                refreshBusyState();
            }
        }

        async function saveColorIfChanged() {
            if (isSavingColor || isSavingName || isDeleting) {
                return;
            }

            var submittedColor = String(colorInput.value || "").trim();
            if (!submittedColor || submittedColor.toUpperCase() === currentColor.toUpperCase()) {
                return;
            }

            clearError();
            isSavingColor = true;
            refreshBusyState();

            try {
                var response = await fetch(buildLabelUrl(colorUrlTemplate, labelUid), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json", "Accept": "application/json" },
                    body: JSON.stringify({ color: submittedColor }),
                });
                var payload = await parseResponse(response);
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "Unable to save color.");
                }
                applyColor(payload.color || submittedColor);
            } catch (error) {
                applyColor(currentColor);
                showError(error.message || "Unable to save color.");
            } finally {
                isSavingColor = false;
                refreshBusyState();
            }
        }

        async function deleteLabel() {
            if (isDeleting || isSavingName || isSavingColor) {
                return;
            }

            if (!window.confirm("Delete this label?")) {
                return;
            }

            clearError();
            isDeleting = true;
            refreshBusyState();

            try {
                var response = await fetch(buildLabelUrl(deleteUrlTemplate, labelUid), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json", "Accept": "application/json" },
                    body: JSON.stringify({}),
                });
                var payload = await parseResponse(response);
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "Unable to delete label.");
                }
                row.remove();
                updateEmptyState();
            } catch (error) {
                showError(error.message || "Unable to delete label.");
                isDeleting = false;
                refreshBusyState();
            }
        }

        editTrigger.addEventListener("click", function () {
            hideCreateRow();
            clearError();
            setEditing(true);
        });

        nameInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                renameLabel();
                return;
            }
            if (event.key === "Escape") {
                nameInput.value = currentName;
                clearError();
                setEditing(false);
            }
        });

        nameSave.addEventListener("click", function () { renameLabel(); });
        nameCancel.addEventListener("click", function () {
            nameInput.value = currentName;
            clearError();
            setEditing(false);
        });

        colorInput.addEventListener("input", syncColorValue);
        colorInput.addEventListener("change", function () { syncColorValue(); saveColorIfChanged(); });
        colorInput.addEventListener("blur", function () { saveColorIfChanged(); });
        deleteButton.addEventListener("click", function () { deleteLabel(); });

        applyName(currentName);
        applyColor(currentColor);
        setEditing(false);
        refreshBusyState();
    }

    // --- create row setup ------------------------------------------------

    function setupCreateRow() {
        if (!createRowEl) {
            return;
        }

        var nameInput = createRowEl.querySelector("[data-create-name-input]");
        var colorInput = createRowEl.querySelector("[data-create-color-input]");
        var saveButton = createRowEl.querySelector("[data-create-save]");
        var cancelButton = createRowEl.querySelector("[data-create-cancel]");
        var rowError = createRowEl.querySelector("[data-create-row-error]");

        if (!nameInput || !colorInput || !saveButton || !cancelButton || !rowError) {
            return;
        }

        var isSaving = false;

        function showError(message) {
            rowError.textContent = message || "An unexpected error occurred.";
            rowError.hidden = false;
        }

        function clearError() {
            rowError.textContent = "";
            rowError.hidden = true;
        }

        function setBusy(busy) {
            isSaving = busy;
            saveButton.disabled = busy;
            cancelButton.disabled = busy;
            colorInput.disabled = busy;
            nameInput.disabled = busy;
        }

        function buildNewRow(label) {
            var li = document.createElement("li");
            li.className = "label-management-item";
            li.dataset.labelRow = "";
            li.dataset.labelUid = label.label_uid;
            li.dataset.labelName = label.name;
            li.dataset.labelColor = label.color || "#000000";
            li.innerHTML = [
                '<div class="label-management-row">',
                '  <div class="label-management-color-column">',
                '    <input type="color" value="' + (label.color || "#000000") + '" class="label-management-color-input" data-label-color-input>',
                '  </div>',
                '  <div class="label-management-name-column">',
                '    <div class="label-management-name-view">',
                '      <span class="label-management-name" data-label-name-text>' + escapeHtml(label.name) + '</span>',
                '      <button type="button" class="label-management-edit-trigger" data-label-edit-trigger aria-label="Edit ' + escapeHtml(label.name) + '">\u270F\uFE0F</button>',
                '    </div>',
                '    <div class="label-management-name-edit" hidden>',
                '      <input type="text" value="' + escapeHtml(label.name) + '" data-label-name-input class="label-management-name-input" maxlength="60">',
                '      <button type="button" class="btn btn-secondary" data-label-name-save>Save</button>',
                '      <button type="button" class="btn btn-secondary" data-label-name-cancel>Cancel</button>',
                '    </div>',
                '  </div>',
                '  <div class="label-management-delete-column">',
                '    <button type="button" class="btn btn-danger" data-label-delete>Delete</button>',
                '  </div>',
                '</div>',
                '<p class="label-row-error" data-label-row-error hidden></p>',
            ].join("\n");
            return li;
        }

        async function createLabel() {
            if (isSaving) {
                return;
            }

            var submittedName = String(nameInput.value || "").trim();
            if (!submittedName) {
                showError("Label name is required");
                nameInput.focus();
                return;
            }

            clearError();
            setBusy(true);

            try {
                var response = await fetch(createUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json", "Accept": "application/json" },
                    body: JSON.stringify({ name: submittedName, color: colorInput.value }),
                });
                var payload = await parseResponse(response);
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "Unable to create label.");
                }

                var newRow = buildNewRow(payload);
                list.appendChild(newRow);
                setupRow(newRow);
                hideCreateRow();
                updateEmptyState();
            } catch (error) {
                showError(error.message || "Unable to create label.");
            } finally {
                setBusy(false);
            }
        }

        saveButton.addEventListener("click", function () { createLabel(); });
        cancelButton.addEventListener("click", function () { hideCreateRow(); });

        nameInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                createLabel();
                return;
            }
            if (event.key === "Escape") {
                hideCreateRow();
            }
        });
    }

    // --- small helper to safely insert text into innerHTML ---------------

    function escapeHtml(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // --- new label trigger -----------------------------------------------

    var rainbowColors = [
        "#FF6B6B", // red
        "#FF8E72", // orange-red
        "#FFD93D", // orange-yellow
        "#6BCB77", // green
        "#4D96FF", // blue
        "#9D84B7", // purple
        "#FF6B9D", // pink
    ];

    function getRandomColor() {
        // Collect colors currently in use
        var usedColors = new Set();
        list.querySelectorAll("[data-label-row]").forEach(function (row) {
            var color = (row.dataset.labelColor || "").toUpperCase();
            if (color) {
                usedColors.add(color);
            }
        });

        // Filter to unused colors
        var availableColors = rainbowColors.filter(function (c) {
            return !usedColors.has(c.toUpperCase());
        });

        // Pick from available, or fall back to all if none available
        var palette = availableColors.length > 0 ? availableColors : rainbowColors;
        return palette[Math.floor(Math.random() * palette.length)];
    }

    if (newTrigger && createRowEl) {
        newTrigger.addEventListener("click", function () {
            closeAllEditRows();
            var colorIn = createRowEl.querySelector("[data-create-color-input]");
            if (colorIn) {
                colorIn.value = getRandomColor();
            }
            createRowEl.hidden = false;
            var nameIn = createRowEl.querySelector("[data-create-name-input]");
            if (nameIn) {
                nameIn.focus();
            }
        });
    }

    // --- init ------------------------------------------------------------

    document.querySelectorAll("[data-label-row]").forEach(setupRow);
    setupCreateRow();
    updateEmptyState();
})();