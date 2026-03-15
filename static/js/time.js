(function () {
    function formatLocalDateTime(dateValue) {
        return dateValue.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function localizeTimeElements() {
        var timeNodes = document.querySelectorAll(".js-local-time");
        if (!timeNodes.length) {
            return;
        }

        for (var index = 0; index < timeNodes.length; index += 1) {
            var node = timeNodes[index];
            var rawValue = (node.getAttribute("datetime") || "").trim();
            if (!rawValue) {
                continue;
            }

            var parsed = new Date(rawValue);
            if (Number.isNaN(parsed.getTime())) {
                continue;
            }

            node.textContent = formatLocalDateTime(parsed);
            node.setAttribute("title", rawValue + " UTC");
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", localizeTimeElements);
        return;
    }

    localizeTimeElements();
})();
