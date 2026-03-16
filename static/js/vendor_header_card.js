(function () {
    "use strict";

    function buildPhoneHref(rawValue) {
        var digits = (rawValue || "").replace(/\D/g, "");

        if (digits.length === 7 || digits.length === 10) {
            return "tel:" + digits;
        }

        if (digits.length === 11) {
            return "tel:+" + digits;
        }

        return null;
    }

    function initPhoneLinks() {
        document.querySelectorAll(".js-phone-link[data-phone-number]").forEach(function (node) {
            var rawValue = node.getAttribute("data-phone-number") || "";
            var href = buildPhoneHref(rawValue);

            if (!href) {
                return;
            }

            var link = document.createElement("a");
            link.href = href;
            link.textContent = node.textContent;
            node.replaceWith(link);
        });
    }

    document.addEventListener("DOMContentLoaded", initPhoneLinks);
}());