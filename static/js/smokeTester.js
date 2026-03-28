(() => {
  "use strict";

  const MIN_ACTION_PAUSE_MS = 150;
  const appRootPath = String(document.body && document.body.dataset.rootPath || "").replace(/\/$/, "");

  function appUrl(path) {
    if (!path || path === "/") {
      return appRootPath || "/";
    }

    return `${appRootPath}${path.startsWith("/") ? path : `/${path}`}`;
  }

  // Dev-only route exerciser / sample data loader.
  // Uses the app's real form POST endpoints so it exercises request parsing,
  // normalization, DB writes, redirects, and archive behavior.
  //
  // Usage examples in browser console:
  //   await window.HSLDevSeed.run();
  //   await window.HSLDevSeed.run({ vendors: 15, entriesPerVendor: 22, archiveCount: 5 });
  //   await window.HSLDevSeed.run({ vendors: 18, entriesPerVendor: 25, archiveCount: 6, dryRun: false });

  const DEFAULTS = {
    vendors: 8,
    entriesPerVendor: 10,
    archiveCount: 5,
    pauseMsBetweenVendors: 250,
    pauseMsBetweenEntries: 200,
    endpointTests: true,
    dryRun: false,
    logPrefix: "[HSL Dev Seed]",
  };

  const REAL_VENDOR_NAMES = [
    "AT&T Fiber",
    "Spectrum",
    "GEICO",
    "Terminix",
    "TruGreen",
    "ABC Home & Commercial Services",
    "Intelligent Design",
    "Gold Medal Service",
    "TOPTEC",
  ];

  const FICTIONAL_VENDOR_NAMES = [
    "Copper Mesa Plumbing",
    "Desert Peak Electric",
    "North Rim HVAC",
    "Canyon View Roofing",
    "Sunline Water Services",
    "Ponderosa Appliance Repair",
    "MesaShield Insurance",
    "Juniper Yard Care",
    "Red Rock Handyman Co.",
    "Blue Basin Garage Doors",
    "High Country Pest Defense",
    "Silver Pine Cleaning Services",
    "Cactus Valley Septic",
    "Prairie Wind Fencing",
    "South Ridge Solar",
    "Stone Creek Pool Service",
    "Timberline Gutter Works",
    "Hearth & Home Chimney",
    "Ironwood Locksmith",
    "Clear Current Irrigation",
  ];

  const CATEGORIES = [
    "Internet",
    "Utility",
    "Insurance",
    "Pest Control",
    "Landscaping",
    "Plumbing",
    "Electrical",
    "HVAC",
    "Roofing",
    "Appliance Repair",
    "Cleaning",
    "Handyman",
    "Water",
    "Solar",
    "Garage Door",
  ];

  const GENERATED_LABEL_PREFIXES = [
    "Follow-up",
    "Urgent",
    "Seasonal",
    "Annual",
    "Pending",
    "Resolved",
    "Warranty",
    "Billing",
    "Inspection",
    "Safety",
    "Estimate",
    "Install",
  ];

  const GENERATED_LABEL_SUFFIXES = [
    "Review",
    "Check",
    "Call",
    "Window",
    "Docs",
    "Visit",
    "Reminder",
    "Alert",
    "Plan",
    "Update",
  ];

  const LABEL_COLOR_SWATCHES = [
    "#1d4ed8",
    "#0f766e",
    "#be185d",
    "#b45309",
    "#4c1d95",
    "#b91c1c",
    "#155e75",
    "#14532d",
    "#7c2d12",
    "#334155",
    "#4338ca",
    "#0369a1",
  ];

  const FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Sam", "Jamie",
    "Chris", "Avery", "Drew", "Cameron", "Dana", "Logan", "Robin", "Parker",
  ];

  const TITLE_PARTS = [
    "Initial call",
    "Billing follow-up",
    "Technician visit",
    "Estimate received",
    "Invoice question",
    "Service interruption",
    "Routine maintenance",
    "Warranty issue",
    "Dispatch update",
    "Repair completed",
    "Parts delay",
    "Portal issue",
    "Reschedule request",
    "Contract renewal",
    "Inspection notes",
    "Account update",
  ];

  const NOTE_OPENERS = [
    "Spoke with support regarding",
    "Technician confirmed",
    "Received an update about",
    "Called in to ask about",
    "Portal message referenced",
    "Followed up on",
    "Vendor advised that",
    "Service team noted",
    "Office staff confirmed",
    "Reviewed paperwork for",
  ];

  const NOTE_SUBJECTS = [
    "slow service speeds",
    "an appointment window",
    "a billing discrepancy",
    "preventive maintenance",
    "a site inspection",
    "replacement scheduling",
    "a follow-up callback",
    "a no-show concern",
    "a partial repair",
    "warranty documentation",
    "meter access",
    "the exterior connection point",
    "the latest invoice",
    "a seasonal service plan",
    "photos uploaded to the portal",
  ];

  const NOTE_CLOSERS = [
    "No immediate action required.",
    "Will monitor and add another note if anything changes.",
    "Rep said the account now shows the update.",
    "Asked for written confirmation via email.",
    "Suggested checking again after the next business day.",
    "Ticket remains open pending field review.",
    "The explanation sounded reasonable and matched prior notes.",
    "This should be compared against the next invoice.",
    "Need to keep an eye on whether the issue repeats.",
    "Saved here so the history is easy to find later.",
  ];

  const labelCacheByNameKey = new Map();

  function logProgress(reportProgress, message) {
    reportProgress(message);
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  function shortError(error) {
    if (!error) {
      return "Unknown error";
    }
    if (error instanceof Error) {
      return error.message;
    }
    return String(error);
  }

  function createEndpointReport() {
    return {
      checks: [],
      passed: 0,
      failed: 0,
      startedAt: new Date().toISOString(),
      completedAt: null,
    };
  }

  function addEndpointResult(report, result) {
    report.checks.push(result);
    if (result.ok) {
      report.passed += 1;
    } else {
      report.failed += 1;
    }
  }

  function finalizeEndpointReport(report) {
    report.completedAt = new Date().toISOString();
    return report;
  }

  function endpointSummaryText(report) {
    const total = report.checks.length;
    return `Endpoint checks: ${report.passed}/${total} passed, ${report.failed} failed.`;
  }

  function printEndpointReport(report, logPrefix) {
    const total = report.checks.length;
    const rows = report.checks.map(item => ({
      method: item.method,
      path: item.path,
      ok: item.ok,
      status: item.status,
      durationMs: item.durationMs,
      detail: item.detail || "",
    }));
    console.group(`${logPrefix} Endpoint Report (${report.passed}/${total} passed)`);
    console.table(rows);
    if (report.failed) {
      const failures = report.checks.filter(item => !item.ok);
      console.warn(`${logPrefix} Failed endpoint checks`, failures);
    }
    console.groupEnd();
  }

  function randInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function pick(arr) {
    return arr[randInt(0, arr.length - 1)];
  }

  function maybe(value, probability = 0.5) {
    return Math.random() < probability ? value : "";
  }

  function randomDigits(length) {
    let out = "";
    for (let i = 0; i < length; i += 1) out += String(randInt(0, 9));
    return out;
  }

  function normalizeLabelName(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function toNameKey(value) {
    return normalizeLabelName(value).toLowerCase();
  }

  function randomLabelColor() {
    // Keep some labels uncolored so the seed data reflects optional color usage.
    if (Math.random() < 0.33) {
      return "";
    }
    return pick(LABEL_COLOR_SWATCHES);
  }

  function randomGeneratedLabelName(vendorName) {
    const vendorToken = slugify(vendorName).split("-")[0] || "home";
    const withVendor = Math.random() < 0.3;
    const base = `${pick(GENERATED_LABEL_PREFIXES)} ${pick(GENERATED_LABEL_SUFFIXES)}`;
    return withVendor ? `${base} ${vendorToken}` : base;
  }

  async function findLabelByExactName(name) {
    const response = await fetch(appUrl(`/api/labels/suggest?q=${encodeURIComponent(name)}`), {
      method: "GET",
      credentials: "same-origin",
    });
    if (!response.ok) {
      return null;
    }

    const payload = await response.json().catch(() => []);
    if (!Array.isArray(payload)) {
      return null;
    }

    const wantedKey = toNameKey(name);
    const match = payload.find(item => toNameKey(item.name) === wantedKey);
    return match || null;
  }

  async function createLabel(name, color) {
    const response = await fetch(appUrl("/labels/new"), {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name,
        color,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (response.ok && payload && payload.ok) {
      return {
        label_uid: payload.label_uid,
        name,
        color: color || "",
      };
    }

    if (response.status === 409) {
      const existing = await findLabelByExactName(name);
      if (existing) {
        return existing;
      }
    }

    const message = payload && payload.error ? payload.error : `Status ${response.status}`;
    throw new Error(`Label create failed for "${name}": ${message}`);
  }

  async function ensureLabel(name, color) {
    const normalized = normalizeLabelName(name);
    if (!normalized) {
      return null;
    }

    const key = toNameKey(normalized);
    const cached = labelCacheByNameKey.get(key);
    if (cached) {
      return cached;
    }

    const label = await createLabel(normalized, color);
    labelCacheByNameKey.set(key, label);
    return label;
  }

  async function generateLabelUids(vendorName, minCount, maxCount) {
    const count = randInt(minCount, maxCount);
    const uidSet = new Set();

    for (let i = 0; i < count; i += 1) {
      const name = randomGeneratedLabelName(vendorName);
      const label = await ensureLabel(name, randomLabelColor());
      if (label && label.label_uid) {
        uidSet.add(label.label_uid);
      }
    }

    return Array.from(uidSet);
  }

  function slugify(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/&/g, "and")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function randomPortalUrl(vendorName, vendorLabel) {
    const cleanSlug = slugify(vendorName).replace(/-/g, "");
    const domainBase = (cleanSlug || slugify(vendorLabel) || "vendor") + ".com";
    const hostPrefixes = ["portal", "myaccount", "customer", "accounts"];
    const paths = ["/login", "/account", "/dashboard", "/signin"];
    return `https://${pick(hostPrefixes)}.${domainBase}${pick(paths)}`;
  }

  function randomPortalUsername() {
    const patterns = [
      `user${randomDigits(6)}`,
      `customer${randomDigits(5)}`,
      `acct${randomDigits(6)}`,
      `homeowner${randomDigits(4)}`,
      `member${randomDigits(5)}`,
    ];
    return pick(patterns);
  }

  function randomPhoneNumber() {
    const areaCodes = ["212", "303", "404", "480", "512", "602", "619", "702", "720", "818", "917", "928"];
    const centralOfficeCode = String(randInt(200, 989));
    const stationCode = randomDigits(4);
    return `${pick(areaCodes)}-${centralOfficeCode}-${stationCode}`;
  }

  function randomStreetAddress() {
    const streetNames = [
      "Maple",
      "Oak",
      "Cedar",
      "Willow",
      "Juniper",
      "Canyon",
      "Sunset",
      "Ridge",
      "Meadow",
      "Pine",
      "Elm",
      "Lakeview",
    ];
    const streetTypes = ["St", "Ave", "Blvd", "Dr", "Ln", "Rd", "Ct", "Way", "Pl"];
    const cities = ["Phoenix", "Scottsdale", "Tempe", "Mesa", "Chandler", "Gilbert", "Glendale", "Peoria"];
    const state = "AZ";
    const zip = `${randInt(85000, 86999)}`;
    const line1 = `${randInt(100, 9999)} ${pick(streetNames)} ${pick(streetTypes)}`;
    return `${line1}, ${pick(cities)}, ${state} ${zip}`;
  }

  function randomTicket() {
    return `${randInt(10, 99)}-${randomDigits(6)}`;
  }

  function randomPastUtcIso(daysBack = 540) {
    const now = Date.now();
    const offsetMs = randInt(0, daysBack * 24 * 60 * 60 * 1000);
    const d = new Date(now - offsetMs);
    d.setMinutes(randInt(0, 11) * 5, 0, 0);
    return d.toISOString();
  }

  function buildVendorPool() {
    const combined = [...REAL_VENDOR_NAMES, ...FICTIONAL_VENDOR_NAMES];
    return combined.map((name, idx) => ({
      vendor_name: name,
      vendor_label: CATEGORIES[idx % CATEGORIES.length],
    }));
  }

  function buildVendorPayload(vendorName, vendorLabel, index, labelUids) {
    const params = new URLSearchParams({
      vendor_name: vendorName,
      vendor_account_number: `${randInt(1000, 9999)}-${randomDigits(6)}`,
      vendor_portal_url: randomPortalUrl(vendorName, vendorLabel),
      vendor_portal_username: randomPortalUsername(),
      vendor_phone_number: randomPhoneNumber(),
      vendor_address: randomStreetAddress(),
      vendor_notes: `Seeded vendor ${index + 1}. Primary label: ${vendorLabel}. Added for UI testing and route exercise.`,
    });
    (labelUids || []).forEach(labelUid => params.append("label_uids", labelUid));
    return params;
  }

  function buildEntryPayload(vendorName, vendorLabel, entryIndex, labelUids) {
    const titleBase = pick(TITLE_PARTS);
    const includeTicket = Math.random() < 0.55;
    const title = includeTicket
      ? `${titleBase} - ${randomTicket()}`
      : titleBase;

    const rep = `${pick(FIRST_NAMES)} ${String.fromCharCode(randInt(65, 90))}.`;
    const body = [
      `${pick(NOTE_OPENERS)} ${pick(NOTE_SUBJECTS)} for ${vendorName}.`,
      `Vendor label context: ${vendorLabel}.`,
      `Rep: ${rep}.`,
      maybe(`Reference discussed: ${randomTicket()}.`, 0.45),
      pick(NOTE_CLOSERS),
    ].filter(Boolean).join(" ");

    const params = new URLSearchParams({
      entry_title: title,
      entry_interaction_at: randomPastUtcIso(),
      entry_rep_name: rep,
      entry_body_text: body,
    });
    (labelUids || []).forEach(labelUid => params.append("label_uids", labelUid));
    return params;
  }

  async function postForm(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body: body.toString(),
      redirect: "follow",
      credentials: "same-origin",
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`POST ${url} failed (${response.status}) ${text.slice(0, 300)}`);
    }

    return response;
  }

  async function getPage(url) {
    const response = await fetch(url, {
      method: "GET",
      redirect: "follow",
      credentials: "same-origin",
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "");
      throw new Error(`GET ${url} failed (${response.status}) ${text.slice(0, 300)}`);
    }

    return response;
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body && body.error ? body.error : `Status ${response.status}`;
      throw new Error(`POST ${url} failed: ${message}`);
    }

    return body;
  }

  async function runEndpointCheck(reportProgress, endpointReport, spec, checkFn) {
    const started = performance.now();
    try {
      const maybeDetail = await checkFn();
      const durationMs = Math.round(performance.now() - started);
      const detail = typeof maybeDetail === "string" ? maybeDetail : "";
      addEndpointResult(endpointReport, {
        name: spec.name,
        method: spec.method,
        path: spec.path,
        ok: true,
        status: "OK",
        durationMs,
        detail,
      });
      logProgress(reportProgress, `Endpoint OK: ${spec.method} ${spec.path} (${durationMs} ms)`);
      return true;
    } catch (error) {
      const durationMs = Math.round(performance.now() - started);
      const detail = shortError(error);
      addEndpointResult(endpointReport, {
        name: spec.name,
        method: spec.method,
        path: spec.path,
        ok: false,
        status: "FAILED",
        durationMs,
        detail,
      });
      logProgress(reportProgress, `Endpoint FAILED: ${spec.method} ${spec.path} (${durationMs} ms) - ${detail}`);
      return false;
    }
  }

  async function assertGetOk(path) {
    const response = await fetch(appUrl(path), {
      method: "GET",
      redirect: "follow",
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`Status ${response.status}; ${body.slice(0, 180)}`);
    }
    return response;
  }

  async function assertPostFormOk(path, fields) {
    const response = await fetch(appUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
      },
      body: fields.toString(),
      redirect: "follow",
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`Status ${response.status}; ${body.slice(0, 180)}`);
    }
    return response;
  }

  async function assertPostJsonOk(path, payload) {
    const response = await fetch(appUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      redirect: "follow",
      credentials: "same-origin",
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body && body.error ? body.error : `Status ${response.status}`;
      throw new Error(message);
    }
    return body;
  }

  function extractDynamicUidsFromVendorHtml(html) {
    const entryUids = new Set();
    const attachmentUids = new Set();
    const entryRegex = /\/entry\/([^/?#"']+)\/edit/gi;
    const attachmentRegex = /\/attachments\/([^/?#"']+)/gi;
    let match = null;

    while ((match = entryRegex.exec(html)) !== null) {
      if (match[1]) {
        entryUids.add(decodeURIComponent(match[1]));
      }
    }

    while ((match = attachmentRegex.exec(html)) !== null) {
      if (match[1]) {
        attachmentUids.add(decodeURIComponent(match[1]));
      }
    }

    return {
      entryUids: Array.from(entryUids),
      attachmentUids: Array.from(attachmentUids),
    };
  }

  async function createAttachmentEntry(vendor) {
    const form = new FormData();
    form.append("entry_title", `Attachment smoke ${randomTicket()}`);
    form.append("entry_rep_name", `${pick(FIRST_NAMES)} ${String.fromCharCode(randInt(65, 90))}.`);
    form.append("entry_body_text", `Attachment endpoint smoke test note for ${vendor.vendor_name}.`);
    form.append("entry_interaction_at", randomPastUtcIso());

    const fileName = `smoke-${randomDigits(6)}.txt`;
    const fileBody = `Smoke attachment for ${vendor.vendor_name} at ${new Date().toISOString()}\n`;
    const blob = new Blob([fileBody], { type: "text/plain" });
    const upload = new File([blob], fileName, { type: "text/plain" });
    form.append("attachments", upload);

    const response = await fetch(appUrl(`/vendor/${encodeURIComponent(vendor.vendorUid)}/entries`), {
      method: "POST",
      body: form,
      redirect: "follow",
      credentials: "same-origin",
    });
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`Attachment entry create failed (${response.status}) ${body.slice(0, 200)}`);
    }
  }

  async function exerciseCommonEndpointChecks(reportProgress, endpointReport) {
    const staticGetChecks = [
      { name: "Home", method: "GET", path: "/" },
      { name: "Vendors list", method: "GET", path: "/vendors" },
      { name: "Vendor new form", method: "GET", path: "/vendors/new" },
      { name: "Entry vendor picker", method: "GET", path: "/entries/new" },
      { name: "Logbook", method: "GET", path: "/logbook" },
      { name: "Labels admin", method: "GET", path: "/labels" },
      { name: "Settings form", method: "GET", path: "/settings" },
      { name: "Label suggest API", method: "GET", path: "/api/labels/suggest?q=smoke" },
    ];

    for (const spec of staticGetChecks) {
      await runEndpointCheck(reportProgress, endpointReport, spec, async () => {
        await assertGetOk(spec.path);
      });
    }

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Actor set", method: "POST", path: "/actor/set" },
      async () => {
        const response = await fetch(appUrl("/actor/set"), {
          method: "POST",
          body: new URLSearchParams({ actor_id: `smoke-user-${randomDigits(4)}` }),
          redirect: "follow",
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "fetch",
            "Accept": "application/json",
          },
        });

        if (!response.ok) {
          const body = await response.text().catch(() => "");
          throw new Error(`Status ${response.status}; ${body.slice(0, 180)}`);
        }

        const payload = await response.json().catch(() => null);
        if (!payload || payload.ok !== true || !payload.current_actor) {
          throw new Error("Invalid actor payload");
        }
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Actor reset", method: "POST", path: "/actor/reset" },
      async () => {
        const response = await fetch(appUrl("/actor/reset"), {
          method: "POST",
          body: new URLSearchParams(),
          redirect: "follow",
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "fetch",
            "Accept": "application/json",
          },
        });

        if (!response.ok) {
          const body = await response.text().catch(() => "");
          throw new Error(`Status ${response.status}; ${body.slice(0, 180)}`);
        }

        const payload = await response.json().catch(() => null);
        if (!payload || payload.ok !== true || !payload.current_actor) {
          throw new Error("Invalid actor payload");
        }
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Calendar export", method: "POST", path: "/calendar/export" },
      async () => {
        const date = new Date();
        const yyyy = String(date.getUTCFullYear());
        const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
        const dd = String(date.getUTCDate()).padStart(2, "0");
        const response = await fetch(appUrl("/calendar/export"), {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
          },
          body: new URLSearchParams({
            title: `Smoke Calendar ${randomDigits(4)}`,
            event_date: `${yyyy}-${mm}-${dd}`,
            event_time: "",
            description: "Calendar export route smoke test.",
          }).toString(),
          redirect: "follow",
          credentials: "same-origin",
        });
        if (!response.ok) {
          const body = await response.text().catch(() => "");
          throw new Error(`Status ${response.status}; ${body.slice(0, 180)}`);
        }
        const contentType = (response.headers.get("content-type") || "").toLowerCase();
        if (!contentType.includes("text/calendar")) {
          throw new Error(`Unexpected content-type: ${contentType || "(missing)"}`);
        }
      },
    );
  }

  async function exerciseDynamicEndpointChecks(reportProgress, endpointReport, vendor) {
    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Vendor detail", method: "GET", path: `/vendor/${vendor.vendorUid}` },
      async () => {
        await assertGetOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}`);
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Vendor edit form", method: "GET", path: `/vendor/${vendor.vendorUid}/edit` },
      async () => {
        await assertGetOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}/edit`);
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Vendor edit submit", method: "POST", path: `/vendor/${vendor.vendorUid}/edit` },
      async () => {
        const payload = new URLSearchParams({
          vendor_name: vendor.vendor_name,
          vendor_account_number: `${randInt(1000, 9999)}-${randomDigits(6)}`,
          vendor_portal_url: randomPortalUrl(vendor.vendor_name, vendor.vendor_label),
          vendor_portal_username: randomPortalUsername(),
          vendor_phone_number: randomPhoneNumber(),
          vendor_address: randomStreetAddress(),
          vendor_notes: `Smoke edit check ${randomTicket()}`,
        });
        (vendor.seedLabelUids || []).forEach(uid => payload.append("label_uids", uid));
        await assertPostFormOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}/edit`, payload);
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Vendor entry form", method: "GET", path: `/vendor/${vendor.vendorUid}/entries/new` },
      async () => {
        await assertGetOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}/entries/new`);
      },
    );

    await createAttachmentEntry(vendor);
    const vendorDetailResponse = await assertGetOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}`);
    const vendorDetailHtml = await vendorDetailResponse.text();
    const extractedUids = extractDynamicUidsFromVendorHtml(vendorDetailHtml);
    const entryUid = extractedUids.entryUids[0];
    const attachmentUid = extractedUids.attachmentUids[0];

    if (!entryUid) {
      throw new Error("Could not discover any entry UID from vendor detail HTML");
    }

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Entry edit form", method: "GET", path: `/entry/${entryUid}/edit` },
      async () => {
        await assertGetOk(`/entry/${encodeURIComponent(entryUid)}/edit`);
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Entry edit submit", method: "POST", path: `/entry/${entryUid}/edit` },
      async () => {
        const payload = new URLSearchParams({
          entry_title: `Edited ${randomTicket()}`,
          entry_interaction_at: randomPastUtcIso(),
          entry_rep_name: `${pick(FIRST_NAMES)} ${String.fromCharCode(randInt(65, 90))}.`,
          entry_body_text: `Edited by smoke check ${new Date().toISOString()}`,
          next: appUrl(`/vendor/${encodeURIComponent(vendor.vendorUid)}`),
        });
        await assertPostFormOk(`/entry/${encodeURIComponent(entryUid)}/edit`, payload);
      },
    );

    if (attachmentUid) {
      await runEndpointCheck(
        reportProgress,
        endpointReport,
        { name: "Attachment download", method: "GET", path: `/attachments/${attachmentUid}` },
        async () => {
          await assertGetOk(`/attachments/${encodeURIComponent(attachmentUid)}`);
        },
      );
    }

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Entry delete", method: "POST", path: `/entry/${entryUid}/delete` },
      async () => {
        const payload = new URLSearchParams({
          next: appUrl(`/vendor/${encodeURIComponent(vendor.vendorUid)}`),
        });
        await assertPostFormOk(`/entry/${encodeURIComponent(entryUid)}/delete`, payload);
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Vendor archive", method: "POST", path: `/vendor/${vendor.vendorUid}/archive` },
      async () => {
        await assertPostFormOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}/archive`, new URLSearchParams());
      },
    );

    await runEndpointCheck(
      reportProgress,
      endpointReport,
      { name: "Vendor unarchive", method: "POST", path: `/vendor/${vendor.vendorUid}/unarchive` },
      async () => {
        await assertPostFormOk(`/vendor/${encodeURIComponent(vendor.vendorUid)}/unarchive`, new URLSearchParams());
      },
    );
  }

  function extractVendorUid(finalUrl) {
    const match = finalUrl.match(/\/vendor\/([^/?#]+)/i);
    if (!match) throw new Error(`Could not extract vendor UID from URL: ${finalUrl}`);
    return decodeURIComponent(match[1]);
  }

  async function createVendor(vendorDef, index) {
    const vendorLabel = await ensureLabel(vendorDef.vendor_label, randomLabelColor());
    const generatedLabelUids = await generateLabelUids(vendorDef.vendor_name, 1, 2);
    const labelUids = new Set(generatedLabelUids);
    if (vendorLabel && vendorLabel.label_uid) {
      labelUids.add(vendorLabel.label_uid);
    }

    const payload = buildVendorPayload(
      vendorDef.vendor_name,
      vendorDef.vendor_label,
      index,
      Array.from(labelUids),
    );
    const response = await postForm(appUrl("/vendors/new"), payload);
    const vendorUid = extractVendorUid(response.url);
    return { ...vendorDef, vendorUid, seedLabelUids: Array.from(labelUids) };
  }

  async function createEntry(vendor, entryIndex) {
    const entryLabelUids = new Set();
    if (Array.isArray(vendor.seedLabelUids)) {
      vendor.seedLabelUids.forEach(labelUid => {
        if (Math.random() < 0.35) {
          entryLabelUids.add(labelUid);
        }
      });
    }

    if (Math.random() < 0.45) {
      const generated = await generateLabelUids(vendor.vendor_name, 1, 1);
      generated.forEach(labelUid => entryLabelUids.add(labelUid));
    }

    const payload = buildEntryPayload(
      vendor.vendor_name,
      vendor.vendor_label,
      entryIndex,
      Array.from(entryLabelUids),
    );
    await postForm(appUrl(`/vendor/${encodeURIComponent(vendor.vendorUid)}/entries`), payload);
    return Array.from(entryLabelUids);
  }

  async function archiveVendor(vendor) {
    await postForm(appUrl(`/vendor/${encodeURIComponent(vendor.vendorUid)}/archive`), new URLSearchParams());
  }

  function buildSettingsPayload() {
    const cityStateZip = randomStreetAddress().split(", ").slice(1).join(", ");
    const locationName = `Smoke Test Home ${randomDigits(4)}`;
    const locationAddress = `${randInt(100, 9999)} ${pick(["Elm", "Juniper", "Canyon", "Maple", "Ridge"])} ${pick(["St", "Ave", "Ln", "Rd", "Dr"])}${cityStateZip ? `, ${cityStateZip}` : ""}`;
    const locationDescription = [
      `Smoke test update for ${locationName}.`,
      `Used to verify the server-rendered settings form and home page header.`,
      `Reference ${randomTicket()}.`,
    ].join(" ");

    return {
      location_name: locationName,
      location_address: locationAddress,
      location_description: locationDescription,
    };
  }

  async function exerciseSettingsRoutes(reportProgress) {
    logProgress(reportProgress, "Settings check: loading /settings form...");
    await getPage(appUrl("/settings"));

    const payload = buildSettingsPayload();
    logProgress(reportProgress, `Settings check: saving location \"${payload.location_name}\"...`);
    await postForm(appUrl("/settings"), new URLSearchParams(payload));
    logProgress(reportProgress, "Settings check: loading / to confirm updated home render...");
    await getPage(appUrl("/"));

    logProgress(reportProgress, `Settings check complete: ${payload.location_name}`);

    return payload;
  }

  async function exerciseLabelManagementRoutes(reportProgress) {
    logProgress(reportProgress, "Label route check: loading /labels...");
    await getPage(appUrl("/labels"));

    const baseName = `Smoke Label ${randomDigits(6)}`;
    const renamedName = `${baseName} Renamed`;
    logProgress(reportProgress, `Label route check: creating \"${baseName}\"...`);
    const created = await createLabel(baseName, "#1d4ed8");

    logProgress(reportProgress, `Label route check: renaming to \"${renamedName}\"...`);
    const renamePayload = await postJson(appUrl(`/labels/${encodeURIComponent(created.label_uid)}/rename`), {
      name: renamedName,
    });
    if (!renamePayload.ok || toNameKey(renamePayload.name) !== toNameKey(renamedName)) {
      throw new Error(`Label rename verification failed for ${created.label_uid}`);
    }

    logProgress(reportProgress, `Label route check: updating color for ${created.label_uid}...`);
    const colorPayload = await postJson(appUrl(`/labels/${encodeURIComponent(created.label_uid)}/color`), {
      color: "#0f766e",
    });
    if (!colorPayload.ok || String(colorPayload.color || "").toLowerCase() !== "#0f766e") {
      throw new Error(`Label color verification failed for ${created.label_uid}`);
    }

    logProgress(reportProgress, `Label route check: verifying suggest results for \"${renamedName}\"...`);
    const suggested = await findLabelByExactName(renamedName);
    if (!suggested || suggested.label_uid !== created.label_uid) {
      throw new Error(`Label suggest verification failed for ${renamedName}`);
    }

    logProgress(reportProgress, `Label route check: deleting ${created.label_uid}...`);
    const deletePayload = await postJson(appUrl(`/labels/${encodeURIComponent(created.label_uid)}/delete`), {});
    if (!deletePayload.ok) {
      throw new Error(`Label delete verification failed for ${created.label_uid}`);
    }

    logProgress(reportProgress, `Label route check: verifying deletion for \"${renamedName}\"...`);
    const afterDelete = await findLabelByExactName(renamedName);
    if (afterDelete && afterDelete.label_uid === created.label_uid) {
      throw new Error(`Deleted label still appears in suggest results for ${renamedName}`);
    }

    logProgress(reportProgress, `Label route check complete: ${baseName} -> ${renamedName}`);

    return {
      createdLabelUid: created.label_uid,
      createdName: baseName,
      renamedName,
    };
  }

  async function run(options = {}) {
    const cfg = { ...DEFAULTS, ...options };
    const reportProgress = typeof cfg.onProgress === "function" ? cfg.onProgress : () => {};
    const pauseMsBetweenVendors = Math.max(MIN_ACTION_PAUSE_MS, Number(cfg.pauseMsBetweenVendors) || 0);
    const pauseMsBetweenEntries = Math.max(MIN_ACTION_PAUSE_MS, Number(cfg.pauseMsBetweenEntries) || 0);
    const vendorPool = buildVendorPool();
    const totalEntriesTarget = cfg.vendors * cfg.entriesPerVendor;
    const endpointReport = createEndpointReport();

    if (cfg.vendors > vendorPool.length) {
      throw new Error(`Requested ${cfg.vendors} vendors, but only ${vendorPool.length} vendor definitions are available.`);
    }

    if (cfg.archiveCount > cfg.vendors) {
      throw new Error("archiveCount cannot be greater than vendors");
    }

    if (cfg.dryRun) {
      return cfg;
    }

    logProgress(reportProgress, `Starting seed: 0/${cfg.vendors} vendors, 0/${totalEntriesTarget} entries...`);

    if (cfg.endpointTests) {
      logProgress(reportProgress, "Running endpoint smoke checks for HTML and app routes...");
      await exerciseCommonEndpointChecks(reportProgress, endpointReport);
    }

    const settingsResult = await exerciseSettingsRoutes(reportProgress);

    const labelRouteResult = await exerciseLabelManagementRoutes(reportProgress);

    const createdVendors = [];
    const seenLabelUids = new Set();
    let entriesCreated = 0;

    for (let i = 0; i < cfg.vendors; i += 1) {
      const vendorDef = vendorPool[i];
      logProgress(reportProgress, `Creating vendor ${i + 1}/${cfg.vendors}: ${vendorDef.vendor_name} (${vendorDef.vendor_label})`);
      const vendor = await createVendor(vendorDef, i);
      createdVendors.push(vendor);
      (vendor.seedLabelUids || []).forEach(labelUid => seenLabelUids.add(labelUid));
      logProgress(
        reportProgress,
        `Created vendor ${i + 1}/${cfg.vendors}: ${vendor.vendor_name} (${vendor.vendorUid}) with ${(vendor.seedLabelUids || []).length} seed labels.`,
      );
      await sleep(pauseMsBetweenVendors);

      for (let j = 0; j < cfg.entriesPerVendor; j += 1) {
        logProgress(
          reportProgress,
          `Creating entry ${j + 1}/${cfg.entriesPerVendor} for ${vendor.vendor_name} (${entriesCreated + 1}/${totalEntriesTarget} total)...`,
        );
        const entryLabelUids = await createEntry(vendor, j);
        entriesCreated += 1;
        entryLabelUids.forEach(labelUid => seenLabelUids.add(labelUid));
        logProgress(
          reportProgress,
          `Created entry ${j + 1}/${cfg.entriesPerVendor} for ${vendor.vendor_name}; attached ${entryLabelUids.length} labels. Total entries: ${entriesCreated}/${totalEntriesTarget}.`,
        );
        await sleep(pauseMsBetweenEntries);
      }

      logProgress(
        reportProgress,
        `Vendor complete: ${vendor.vendor_name}. Progress: ${createdVendors.length}/${cfg.vendors} vendors, ${entriesCreated}/${totalEntriesTarget} entries, ${seenLabelUids.size} labels seen.`,
      );

      if (cfg.endpointTests && i === 0) {
        logProgress(reportProgress, `Running dynamic endpoint checks using vendor ${vendor.vendor_name}...`);
        await exerciseDynamicEndpointChecks(reportProgress, endpointReport, vendor);
      }
    }

    const toArchive = createdVendors.slice(-cfg.archiveCount);
    for (let i = 0; i < toArchive.length; i += 1) {
      const vendor = toArchive[i];
      logProgress(reportProgress, `Archiving vendor ${i + 1}/${toArchive.length}: ${vendor.vendor_name} (${vendor.vendorUid})`);
      await archiveVendor(vendor);
      logProgress(reportProgress, `Archived vendor ${i + 1}/${toArchive.length}: ${vendor.vendor_name}`);
      if (i < toArchive.length - 1) {
        await sleep(pauseMsBetweenVendors);
      }
    }

    const summary = {
      settingsUpdated: settingsResult,
      labelRouteTest: labelRouteResult,
      endpointReport: finalizeEndpointReport(endpointReport),
      vendorsCreated: createdVendors.length,
      entriesCreated,
      labelsGenerated: seenLabelUids.size,
      archivedVendors: toArchive.length,
      archivedVendorUids: toArchive.map(v => v.vendorUid),
      createdVendorNames: createdVendors.map(v => v.vendor_name),
    };

    if (cfg.endpointTests) {
      printEndpointReport(summary.endpointReport, cfg.logPrefix);
    }

    reportProgress(
      `Seed complete. ${cfg.endpointTests ? `${endpointSummaryText(summary.endpointReport)} ` : ""}Settings: ${settingsResult.location_name}. Label routes: ${labelRouteResult.renamedName}. Vendors: ${createdVendors.length}. Entries: ${entriesCreated}. Labels: ${seenLabelUids.size}. Archived: ${toArchive.length}.`,
    );

    return {
      settingsUpdated: settingsResult,
      labelRouteTest: labelRouteResult,
      endpointReport: summary.endpointReport,
      vendorsCreated: createdVendors,
      entriesCreated,
      labelsGenerated: seenLabelUids.size,
      archivedVendorUids: toArchive.map(v => v.vendorUid),
    };
  }

  window.HSLDevSeed = {
    run,
    buildVendorPool,
    defaults: { ...DEFAULTS },
  };

  function bindRunButton() {
    const runButton = document.getElementById("run-seed-file");
    if (!runButton) return;

    const statusEl = document.getElementById("seed-status");
    const setStatus = (message) => {
      if (statusEl) statusEl.textContent = message;
    };

    runButton.addEventListener("click", async () => {
      runButton.disabled = true;
      setStatus("Seeding in progress. Please wait...");
      try {
        const result = await run({ onProgress: setStatus });
        const endpointSummary = result.endpointReport
          ? `${result.endpointReport.passed}/${result.endpointReport.checks.length} endpoint checks passed`
          : "endpoint checks skipped";
        setStatus(`Seed complete. ${endpointSummary}. Vendors: ${result.vendorsCreated.length}, Entries: ${result.entriesCreated}, Labels: ${result.labelsGenerated}`);
      } catch (error) {
        setStatus(`Seed run failed: ${error instanceof Error ? error.message : "Unexpected error."}`);
      } finally {
        runButton.disabled = false;
      }
    });
  }

  bindRunButton();
})();
