(() => {
  "use strict";

  const MIN_ACTION_PAUSE_MS = 150;

  // Dev-only route exerciser / sample data loader.
  // Uses the app's real form POST endpoints so it exercises request parsing,
  // normalization, DB writes, redirects, and archive behavior.
  //
  // Usage examples in browser console:
  //   await window.HSLDevSeed.run();
  //   await window.HSLDevSeed.run({ vendors: 15, entriesPerVendor: 22, archiveCount: 5 });
  //   await window.HSLDevSeed.run({ vendors: 18, entriesPerVendor: 25, archiveCount: 6, dryRun: false });

  const DEFAULTS = {
    vendors: 15,
    entriesPerVendor: 22,
    archiveCount: 5,
    pauseMsBetweenVendors: 250,
    pauseMsBetweenEntries: 200,
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

  function log(...args) {
    console.log(DEFAULTS.logPrefix, ...args);
  }

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
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

  function buildVendorPayload(vendorName, vendorLabel, index) {
    return new URLSearchParams({
      vendor_name: vendorName,
      vendor_label: vendorLabel,
      vendor_account_number: `${randInt(1000, 9999)}-${randomDigits(6)}`,
      vendor_portal_url: randomPortalUrl(vendorName, vendorLabel),
      vendor_portal_username: randomPortalUsername(),
      vendor_phone_number: randomPhoneNumber(),
      vendor_address: randomStreetAddress(),
      vendor_notes: `Seeded vendor ${index + 1}. Primary label: ${vendorLabel}. Added for UI testing and route exercise.`,
    });
  }

  function buildEntryPayload(vendorName, vendorLabel, entryIndex) {
    const titleBase = pick(TITLE_PARTS);
    const includeTicket = Math.random() < 0.55;
    const title = includeTicket
      ? `${titleBase} - ${randomTicket()}`
      : `${titleBase} - ${vendorName}`;

    const rep = `${pick(FIRST_NAMES)} ${String.fromCharCode(randInt(65, 90))}.`;
    const body = [
      `${pick(NOTE_OPENERS)} ${pick(NOTE_SUBJECTS)} for ${vendorName}.`,
      `Vendor label context: ${vendorLabel}.`,
      `Rep: ${rep}.`,
      maybe(`Reference discussed: ${randomTicket()}.`, 0.45),
      pick(NOTE_CLOSERS),
    ].filter(Boolean).join(" ");

    return new URLSearchParams({
      entry_title: title,
      entry_interaction_at: randomPastUtcIso(),
      entry_rep_name: rep,
      entry_body_text: body,
    });
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

  function extractVendorUid(finalUrl) {
    const match = finalUrl.match(/\/vendor\/([^/?#]+)/i);
    if (!match) throw new Error(`Could not extract vendor UID from URL: ${finalUrl}`);
    return decodeURIComponent(match[1]);
  }

  async function createVendor(vendorDef, index) {
    const payload = buildVendorPayload(vendorDef.vendor_name, vendorDef.vendor_label, index);
    const response = await postForm("/vendors/new", payload);
    const vendorUid = extractVendorUid(response.url);
    return { ...vendorDef, vendorUid };
  }

  async function createEntry(vendor, entryIndex) {
    const payload = buildEntryPayload(vendor.vendor_name, vendor.vendor_label, entryIndex);
    await postForm(`/vendor/${encodeURIComponent(vendor.vendorUid)}/entries`, payload);
  }

  async function archiveVendor(vendor) {
    await postForm(`/vendor/${encodeURIComponent(vendor.vendorUid)}/archive`, new URLSearchParams());
  }

  async function run(options = {}) {
    const cfg = { ...DEFAULTS, ...options };
    const pauseMsBetweenVendors = Math.max(MIN_ACTION_PAUSE_MS, Number(cfg.pauseMsBetweenVendors) || 0);
    const pauseMsBetweenEntries = Math.max(MIN_ACTION_PAUSE_MS, Number(cfg.pauseMsBetweenEntries) || 0);
    const vendorPool = buildVendorPool();

    if (cfg.vendors > vendorPool.length) {
      throw new Error(`Requested ${cfg.vendors} vendors, but only ${vendorPool.length} vendor definitions are available.`);
    }

    if (cfg.archiveCount > cfg.vendors) {
      throw new Error("archiveCount cannot be greater than vendors");
    }

    if (cfg.dryRun) {
      log("Dry run only.", cfg);
      return cfg;
    }

    log(`Creating ${cfg.vendors} vendors and ${cfg.entriesPerVendor} entries per vendor...`);

    const createdVendors = [];

    for (let i = 0; i < cfg.vendors; i += 1) {
      const vendorDef = vendorPool[i];
      log(`Creating vendor ${i + 1}/${cfg.vendors}: ${vendorDef.vendor_name}`);
      const vendor = await createVendor(vendorDef, i);
      createdVendors.push(vendor);
      await sleep(pauseMsBetweenVendors);

      for (let j = 0; j < cfg.entriesPerVendor; j += 1) {
        if ((j + 1) % 5 === 0 || j === 0) {
          log(`  entries ${j + 1}/${cfg.entriesPerVendor} for ${vendor.vendor_name}`);
        }
        await createEntry(vendor, j);
        await sleep(pauseMsBetweenEntries);
      }
    }

    const toArchive = createdVendors.slice(-cfg.archiveCount);
    for (let i = 0; i < toArchive.length; i += 1) {
      const vendor = toArchive[i];
      log(`Archiving vendor: ${vendor.vendor_name}`);
      await archiveVendor(vendor);
      if (i < toArchive.length - 1) {
        await sleep(pauseMsBetweenVendors);
      }
    }

    log("Done.", {
      vendorsCreated: createdVendors.length,
      entriesCreated: createdVendors.length * cfg.entriesPerVendor,
      archivedVendors: toArchive.length,
    });

    return {
      vendorsCreated: createdVendors,
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
        const result = await run();
        setStatus(`Seed complete: ${result.vendorsCreated.length} vendors created.`);
      } catch (error) {
        console.error("[HSL Dev Seed] Run failed", error);
        setStatus("Seed run failed. Check browser console for details.");
      } finally {
        runButton.disabled = false;
      }
    });
  }

  bindRunButton();

  console.log("[HSL Dev Seed] Ready. Run `await window.HSLDevSeed.run()` in the console.");
})();
