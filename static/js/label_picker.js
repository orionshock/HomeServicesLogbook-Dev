(() => {
    "use strict";

    function normalizeName(value) {
        return String(value || "").trim().replace(/\s+/g, " ");
    }

    function createPickerState() {
        return {
            existingByUid: new Map(),
            newByNameKey: new Map(),
            latestSuggestions: [],
            requestToken: 0,
            debounceTimer: null,
        };
    }

    function toNameKey(name) {
        return normalizeName(name).toLowerCase();
    }

    function renderChip(label, removeHandler) {
        const chip = document.createElement("span");
        chip.className = "label-chip";

        const dot = document.createElement("span");
        dot.className = "label-chip-dot";
        if (label.color) {
            dot.style.backgroundColor = label.color;
        }
        chip.appendChild(dot);

        const text = document.createElement("span");
        text.className = "label-chip-text";
        text.textContent = label.name;
        chip.appendChild(text);

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "label-chip-remove";
        removeButton.textContent = "\u00d7";
        removeButton.setAttribute("aria-label", `Remove ${label.name}`);
        removeButton.addEventListener("click", removeHandler);
        chip.appendChild(removeButton);

        return chip;
    }

    function buildSuggestionItem(label, onSelect) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "label-suggestion-item";

        const dot = document.createElement("span");
        dot.className = "label-chip-dot";
        if (label.color) {
            dot.style.backgroundColor = label.color;
        }
        button.appendChild(dot);

        const text = document.createElement("span");
        text.textContent = label.name;
        button.appendChild(text);

        button.addEventListener("click", () => onSelect(label));
        return button;
    }

    function setupPicker(picker) {
        const input = picker.querySelector("[data-label-input]");
        const addButton = picker.querySelector("[data-add-label]");
        const chipsHost = picker.querySelector("[data-label-picker-selected]");
        const hiddenInputsHost = picker.querySelector("[data-label-hidden-inputs]");
        const suggestionsHost = picker.querySelector("[data-label-suggestions]");

        if (!input || !addButton || !chipsHost || !hiddenInputsHost || !suggestionsHost) {
            return;
        }

        const existingFieldName = picker.dataset.fieldNameLabelUids || "label_uids";
        const newFieldName = picker.dataset.fieldNameNewLabelNames || "new_label_names";
        const suggestUrl = picker.dataset.suggestUrl || "";
        const state = createPickerState();

        function syncInitialState() {
            const initialChips = chipsHost.querySelectorAll("[data-label-chip]");
            initialChips.forEach((chip) => {
                const uid = chip.dataset.labelUid || "";
                const name = normalizeName(chip.dataset.labelName || "");
                const color = chip.dataset.labelColor || "";
                if (!name) {
                    return;
                }

                if (uid) {
                    state.existingByUid.set(uid, { label_uid: uid, name, color });
                    return;
                }

                state.newByNameKey.set(toNameKey(name), { name, color: "" });
            });
        }

        function renderHiddenInputs() {
            hiddenInputsHost.innerHTML = "";

            state.existingByUid.forEach((label) => {
                const hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = existingFieldName;
                hidden.value = label.label_uid;
                hiddenInputsHost.appendChild(hidden);
            });

            state.newByNameKey.forEach((label) => {
                const hidden = document.createElement("input");
                hidden.type = "hidden";
                hidden.name = newFieldName;
                hidden.value = label.name;
                hiddenInputsHost.appendChild(hidden);
            });
        }

        function renderChips() {
            chipsHost.innerHTML = "";

            state.existingByUid.forEach((label) => {
                const chip = renderChip(label, () => {
                    state.existingByUid.delete(label.label_uid);
                    renderChips();
                    renderHiddenInputs();
                });
                chipsHost.appendChild(chip);
            });

            state.newByNameKey.forEach((label, key) => {
                const chip = renderChip(label, () => {
                    state.newByNameKey.delete(key);
                    renderChips();
                    renderHiddenInputs();
                });
                chipsHost.appendChild(chip);
            });
        }

        function clearSuggestions() {
            suggestionsHost.innerHTML = "";
            suggestionsHost.classList.remove("is-visible");
        }

        function applySuggestionList(list) {
            state.latestSuggestions = list;
            suggestionsHost.innerHTML = "";

            if (!list.length) {
                suggestionsHost.classList.remove("is-visible");
                return;
            }

            list.forEach((label) => {
                const item = buildSuggestionItem(label, (selected) => {
                    addExistingLabel(selected);
                    input.value = "";
                    clearSuggestions();
                });
                suggestionsHost.appendChild(item);
            });

            suggestionsHost.classList.add("is-visible");
        }

        function addExistingLabel(label) {
            if (!label || !label.label_uid || !label.name) {
                return;
            }
            state.existingByUid.set(label.label_uid, {
                label_uid: label.label_uid,
                name: normalizeName(label.name),
                color: label.color || "",
            });
            state.newByNameKey.delete(toNameKey(label.name));
            renderChips();
            renderHiddenInputs();
        }

        function addNewLabel(rawName) {
            const normalized = normalizeName(rawName);
            if (!normalized) {
                return;
            }

            const match = state.latestSuggestions.find(
                (item) => normalizeName(item.name).toLowerCase() === normalized.toLowerCase(),
            );
            if (match) {
                addExistingLabel(match);
                return;
            }

            const key = toNameKey(normalized);
            state.newByNameKey.set(key, {
                name: normalized,
                color: "",
            });
            renderChips();
            renderHiddenInputs();
        }

        async function fetchSuggestions(query) {
            if (!suggestUrl) {
                clearSuggestions();
                return;
            }

            const token = ++state.requestToken;
            try {
                const requestUrl = new URL(suggestUrl, window.location.origin);
                requestUrl.searchParams.set("q", query);
                const response = await fetch(requestUrl.toString(), {
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    clearSuggestions();
                    return;
                }
                const payload = await response.json();
                if (token !== state.requestToken) {
                    return;
                }
                if (Array.isArray(payload)) {
                    applySuggestionList(payload);
                } else {
                    clearSuggestions();
                }
            } catch (_) {
                clearSuggestions();
            }
        }

        function queueSuggestions() {
            const query = normalizeName(input.value);
            if (state.debounceTimer) {
                clearTimeout(state.debounceTimer);
            }
            if (!query) {
                clearSuggestions();
                return;
            }
            state.debounceTimer = setTimeout(() => {
                fetchSuggestions(query);
            }, 140);
        }

        addButton.addEventListener("click", () => {
            addNewLabel(input.value);
            input.value = "";
            clearSuggestions();
        });

        input.addEventListener("input", queueSuggestions);
        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                addNewLabel(input.value);
                input.value = "";
                clearSuggestions();
            }
            if (event.key === "Escape") {
                clearSuggestions();
            }
        });

        document.addEventListener("click", (event) => {
            if (!picker.contains(event.target)) {
                clearSuggestions();
            }
        });

        syncInitialState();
        renderChips();
        renderHiddenInputs();
    }

    document.querySelectorAll("[data-label-picker]").forEach(setupPicker);
})();