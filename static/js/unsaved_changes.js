(function () {
    "use strict";

    var forms = Array.prototype.slice.call(document.querySelectorAll('form[data-unsaved-warning="true"]'));
    if (!forms.length) {
        return;
    }

    var hasBeforeUnloadListener = false;
    var suppressBeforeUnloadOnce = false;

    function buildStableFormState(form) {
        var entries = [];
        var formData = new FormData(form);

        formData.forEach(function (value, key) {
            if (value instanceof File) {
                if (!value.name && value.size === 0) {
                    entries.push([key, "__file__", "__empty__"]);
                    return;
                }

                entries.push([key, "__file__", value.name, String(value.size), String(value.lastModified)]);
                return;
            }

            entries.push([key, "__value__", String(value)]);
        });

        return JSON.stringify(entries);
    }

    function isFormDirty(formState) {
        if (formState.submitting) {
            return false;
        }

        if (formState.initialState === null) {
            return false;
        }

        return buildStableFormState(formState.form) !== formState.initialState;
    }

    var formStates = forms.map(function (form) {
        return {
            form: form,
            initialState: null,
            submitting: false,
        };
    });

    // Defer baseline capture so all synchronous page scripts (e.g. datetime
    // field population, label-picker hidden-input init) finish first.
    window.setTimeout(function () {
        formStates.forEach(function (formState) {
            if (formState.initialState === null) {
                formState.initialState = buildStableFormState(formState.form);
            }
        });
    }, 50);

    function hasDirtyForms() {
        for (var i = 0; i < formStates.length; i += 1) {
            if (isFormDirty(formStates[i])) {
                return true;
            }
        }

        return false;
    }

    function onBeforeUnload(event) {
        if (suppressBeforeUnloadOnce) {
            return;
        }

        if (!hasDirtyForms()) {
            return;
        }

        event.preventDefault();
        event.returnValue = "";
    }

    function ensureBeforeUnloadListener() {
        if (hasBeforeUnloadListener) {
            return;
        }

        window.addEventListener("beforeunload", onBeforeUnload);
        hasBeforeUnloadListener = true;
    }

    formStates.forEach(function (formState) {
        var form = formState.form;

        function onPossibleChange() {
            formState.submitting = false;
        }

        form.addEventListener("input", onPossibleChange);
        form.addEventListener("change", onPossibleChange);

        form.addEventListener("submit", function () {
            formState.submitting = true;
        });
    });

    ensureBeforeUnloadListener();

    document.addEventListener("click", function (event) {
        if (!event.isTrusted || event.defaultPrevented) {
            return;
        }

        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
        }

        var link = event.target.closest("a[href]");
        if (!link) {
            return;
        }

        if (link.hasAttribute("download")) {
            return;
        }

        var target = link.getAttribute("target");
        if (target && target.toLowerCase() === "_blank") {
            return;
        }

        var href = link.getAttribute("href");
        if (!href || href.charAt(0) === "#") {
            return;
        }

        var destination;
        try {
            destination = new URL(link.href, window.location.href);
        } catch (error) {
            return;
        }

        if (destination.origin !== window.location.origin) {
            return;
        }

        if (!hasDirtyForms()) {
            return;
        }

        var confirmed = window.confirm("You have unsaved changes. Leave this page?");
        if (!confirmed) {
            event.preventDefault();
            return;
        }

        suppressBeforeUnloadOnce = true;
        window.setTimeout(function () {
            suppressBeforeUnloadOnce = false;
        }, 0);
    });
})();
