(() => {
  "use strict";

  const ALL_SECTION_KEY = "all";

  const SECTIONS = Object.freeze([
    { key: "project", label: "О проекте" },
    { key: "architecture", label: "Архитектура" },
    { key: "development", label: "Разработка" },
    { key: "status", label: "Состояние" },
    { key: "api", label: "API" },
    { key: "ai", label: "Для ИИ" },
    { key: "root", label: "Главная" },
  ]);

  const SECTION_BY_KEY = new Map(
    SECTIONS.map((section) => [section.key, section])
  );

  let activeSection = readSectionFromUrl();

  function normalizeText(value) {
    return value.replace(/\s+/g, " ").trim();
  }

  function readSectionFromUrl() {
    const value = new URLSearchParams(window.location.search).get("section");

    if (value === ALL_SECTION_KEY || SECTION_BY_KEY.has(value)) {
      return value;
    }

    return ALL_SECTION_KEY;
  }

  function writeSectionToUrl(sectionKey) {
    const url = new URL(window.location.href);

    if (sectionKey === ALL_SECTION_KEY) {
      url.searchParams.delete("section");
    } else {
      url.searchParams.set("section", sectionKey);
    }

    window.history.replaceState({}, "", url);
  }

  function findSection(resultUrl) {
    const pathParts = resultUrl.pathname
      .split("/")
      .filter(Boolean)
      .map((part) => decodeURIComponent(part));

    for (const part of pathParts) {
      if (SECTION_BY_KEY.has(part) && part !== "root") {
        return SECTION_BY_KEY.get(part);
      }
    }

    return SECTION_BY_KEY.get("root");
  }

  function createSectionIndexUrl(resultUrl, sectionKey) {
    const url = new URL(resultUrl.href);

    if (sectionKey === "root") {
      const pathParts = url.pathname.split("/");
      pathParts[pathParts.length - 1] = "index.html";
      url.pathname = pathParts.join("/");
      url.hash = "";
      return url.href;
    }

    const pathParts = url.pathname.split("/");
    const sectionIndex = pathParts.findIndex(
      (part) => decodeURIComponent(part) === sectionKey
    );

    if (sectionIndex >= 0) {
      url.pathname = [
        ...pathParts.slice(0, sectionIndex + 1),
        "index.html",
      ].join("/");
    }

    url.hash = "";
    url.search = "";
    return url.href;
  }

  function createPageUrl(resultUrl) {
    return new URL(resultUrl.href).href;
  }

  function getTitleParts(link) {
    return normalizeText(link.textContent || "")
      .split(/\s*>\s*/)
      .map(normalizeText)
      .filter(Boolean);
  }

  function createLocationLink(kind, value, level, href) {
    const link = document.createElement("a");
    link.className = [
      "search-result-location__item",
      `search-result-location__item--${level}`,
    ].join(" ");
    link.href = href;
    link.setAttribute("aria-label", `${kind}: ${value}`);

    const kindElement = document.createElement("span");
    kindElement.className = "search-result-location__kind";
    kindElement.textContent = kind;

    const valueElement = document.createElement("span");
    valueElement.className = "search-result-location__value";
    valueElement.textContent = value;

    link.append(kindElement, valueElement);
    return link;
  }

  function enhanceResult(item) {
    if (item.dataset.locationEnhanced === "true") {
      return false;
    }

    const originalLink = item.querySelector(":scope > a");

    if (!originalLink) {
      return false;
    }

    const resultUrl = new URL(originalLink.href, window.location.href);
    const section = findSection(resultUrl);
    const titleParts = getTitleParts(originalLink);
    const location = document.createElement("nav");

    location.className = "search-result-location";
    location.setAttribute(
      "aria-label",
      `Расположение результата в документации`
    );

    location.append(
      createLocationLink(
        "Вкладка",
        section.label,
        "section",
        createSectionIndexUrl(resultUrl, section.key)
      )
    );

    const pageTitle = titleParts[0];

    if (
      pageTitle &&
      normalizeText(pageTitle).toLocaleLowerCase("ru-RU") !==
        normalizeText(section.label).toLocaleLowerCase("ru-RU")
    ) {
      location.append(
        createLocationLink(
          "Страница",
          pageTitle,
          "page",
          createPageUrl(resultUrl)
        )
      );
    }

    for (const headingTitle of titleParts.slice(1)) {
      location.append(
        createLocationLink(
          "Раздел",
          headingTitle,
          "heading",
          resultUrl.href
        )
      );
    }

    item.insertBefore(location, originalLink);
    originalLink.remove();

    item.dataset.searchSection = section.key;
    item.dataset.locationEnhanced = "true";
    item.classList.add("search-result--with-location");

    return true;
  }

  function createFilterButton(key, label) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-section-filter__button";
    button.dataset.sectionFilter = key;
    button.setAttribute("aria-pressed", "false");

    const labelElement = document.createElement("span");
    labelElement.className = "search-section-filter__label";
    labelElement.textContent = label;

    button.append(labelElement);

    button.addEventListener("click", () => {
      activeSection = key;
      writeSectionToUrl(key);
      applyFilter();
    });

    return button;
  }

  function ensureFilterPanel() {
    const resultsRoot = document.querySelector("#search-results");
    const resultsList = resultsRoot?.querySelector("ul.search");

    if (!resultsRoot || !resultsList) {
      return null;
    }

    let panel = resultsRoot.querySelector(".search-section-filter");

    if (panel) {
      return panel;
    }

    panel = document.createElement("section");
    panel.className = "search-section-filter";
    panel.setAttribute("aria-label", "Фильтр результатов по вкладкам");

    const title = document.createElement("div");
    title.className = "search-section-filter__title";
    title.textContent = "Показывать результаты из";

    const controls = document.createElement("div");
    controls.className = "search-section-filter__controls";

    controls.append(createFilterButton(ALL_SECTION_KEY, "Все"));

    for (const section of SECTIONS) {
      controls.append(createFilterButton(section.key, section.label));
    }

    const emptyMessage = document.createElement("p");
    emptyMessage.className = "search-section-filter__empty";
    emptyMessage.hidden = true;
    emptyMessage.textContent =
      "В выбранной вкладке совпадений не найдено.";

    panel.append(title, controls, emptyMessage);
    resultsRoot.insertBefore(panel, resultsList);

    return panel;
  }

  function applyFilter() {
    const panel = ensureFilterPanel();
    const resultsRoot = document.querySelector("#search-results");
    const items = [
      ...(resultsRoot?.querySelectorAll("ul.search > li") || []),
    ];

    if (!panel) {
      return;
    }

    for (const item of items) {
      const sectionKey = item.dataset.searchSection || "root";

      const visible =
        activeSection === ALL_SECTION_KEY ||
        sectionKey === activeSection;

      item.hidden = !visible;
    }

    const buttons = panel.querySelectorAll(
      "[data-section-filter]"
    );

    for (const button of buttons) {
      const sectionKey = button.dataset.sectionFilter;
      button.classList.toggle(
        "is-active",
        sectionKey === activeSection
      );
      button.setAttribute(
        "aria-pressed",
        String(sectionKey === activeSection)
      );

    }

    const visibleCount = items.filter((item) => !item.hidden).length;
    const emptyMessage = panel.querySelector(
      ".search-section-filter__empty"
    );

    if (emptyMessage) {
      emptyMessage.hidden = visibleCount !== 0;
    }
  }

  function enhanceSearchResults() {
    const items = document.querySelectorAll(
      "#search-results ul.search > li"
    );

    let changed = false;

    for (const item of items) {
      changed = enhanceResult(item) || changed;
    }

    ensureFilterPanel();

    if (changed || items.length > 0) {
      applyFilter();
    }
  }

  function startObserver() {
    enhanceSearchResults();

    const target =
      document.querySelector("#search-results") ||
      document.querySelector("main") ||
      document.body;

    const observer = new MutationObserver(enhanceSearchResults);
    observer.observe(target, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver, {
      once: true,
    });
  } else {
    startObserver();
  }
})();