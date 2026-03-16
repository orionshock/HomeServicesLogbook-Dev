(function () {
    "use strict";

    function markExternalLinks() {
        document.querySelectorAll("a[href]").forEach(function (link) {
            if (link.hostname && link.hostname !== location.hostname) {
                link.classList.add("external");
            }
        });
    }

    document.addEventListener("DOMContentLoaded", markExternalLinks);
}());