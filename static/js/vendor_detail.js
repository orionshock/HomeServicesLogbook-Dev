(function () {
    var form = document.getElementById("entry-form");
    var bodyText = document.getElementById("body_text");
    var fileInput = document.getElementById("attachment");
    var attachTrigger = document.getElementById("attach-trigger");
    var attachmentName = document.getElementById("attachment-name");
    var calendarTrigger = document.getElementById("calendar-trigger");
    var calendarPanel = document.getElementById("calendar-panel");
    var calendarTitle = document.getElementById("calendar_title");
    var calendarDate = document.getElementById("calendar_date");
    var calendarTime = document.getElementById("calendar_time");
    var calendarDescription = document.getElementById("calendar_description");
    var calendarDownload = document.getElementById("calendar-download");
    var calendarCancel = document.getElementById("calendar-cancel");
    if (!form || !fileInput) {
        return;
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
            attachmentName.textContent = "Selected: " + fileInput.files[0].name;
            return;
        }

        attachmentName.textContent = "No file selected";
    }

    function hasExtension(fileName) {
        var base = (fileName || "").split(/[\\/]/).pop();
        var lastDot = base.lastIndexOf(".");
        return lastDot > 0 && lastDot < base.length - 1;
    }

    function validateFileInput() {
        if (!fileInput.files || fileInput.files.length === 0) {
            fileInput.setCustomValidity("");
            return true;
        }

        var selectedName = fileInput.files[0].name;
        if (!hasExtension(selectedName)) {
            fileInput.setCustomValidity("Attached file must include an extension, such as .pdf or .jpg.");
            return false;
        }

        fileInput.setCustomValidity("");
        return true;
    }

    fileInput.addEventListener("change", function () {
        validateFileInput();
        setAttachmentName();
        fileInput.reportValidity();
    });

    if (attachTrigger) {
        attachTrigger.addEventListener("click", function () {
            fileInput.click();
        });
    }

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

    form.addEventListener("submit", function (event) {
        if (!validateFileInput()) {
            event.preventDefault();
            fileInput.reportValidity();
        }
    });
})();
