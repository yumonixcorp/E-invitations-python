/*
 * Shared behaviour for invitation templates (home, home2, home3, home4, ...).
 * Every feature is opt-in through markup, so a template only gets what it uses:
 *   .site-header / .menu-toggle / .main-nav   sticky header + mobile menu
 *   [data-countdown="2026-12-14T06:30:00"]    countdown ([data-unit], [data-countdown-done])
 *   .reveal                                    fade-up on scroll
 *   .js-gallery a[data-lightbox]              photo lightbox
 *   [data-video-embed] / [data-video-file]    video popup
 *   a[data-map-embed]                          map popup ("See Location")
 *   form[data-whatsapp]                        RSVP sent as a WhatsApp message
 *   .js-slider .slide                          fading hero slider
 *   .back-to-top                               scroll-to-top button
 */
(function () {
  "use strict";

  const root = document.documentElement;
  root.classList.add("js");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (sel, scope) => (scope || document).querySelector(sel);
  const $$ = (sel, scope) => Array.from((scope || document).querySelectorAll(sel));
  const header = $(".site-header");

  /* ---------- in-page links ---------- */
  // Handled manually: the editor preview uses <base href>, which would turn "#story" into a page load.
  function scrollToId(id) {
    const target = id ? document.getElementById(id) : null;
    if (id && !target) return false;
    const offset = header ? header.offsetHeight : 0;
    const top = target ? target.getBoundingClientRect().top + window.scrollY - offset + 1 : 0;
    window.scrollTo({ top, behavior: reduceMotion ? "auto" : "smooth" });
    return true;
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest('a[href^="#"]');
    if (!link || link.hasAttribute("data-map-embed")) return;
    if (scrollToId(link.getAttribute("href").slice(1))) event.preventDefault();
  });

  /* ---------- header ---------- */
  if (header) {
    const onScroll = () => header.classList.toggle("is-sticky", window.scrollY > 60);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    const toggle = $(".menu-toggle", header);
    if (toggle) {
      toggle.addEventListener("click", () => {
        const open = header.classList.toggle("menu-open");
        toggle.setAttribute("aria-expanded", String(open));
      });
      $$(".main-nav a", header).forEach((a) => a.addEventListener("click", () => {
        header.classList.remove("menu-open");
        toggle.setAttribute("aria-expanded", "false");
      }));
    }

    const links = $$('.main-nav a[href^="#"]', header);
    const sections = links.map((a) => document.getElementById(a.getAttribute("href").slice(1))).filter(Boolean);
    if ("IntersectionObserver" in window && sections.length) {
      const spy = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          links.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === "#" + entry.target.id));
        });
      }, { rootMargin: "-45% 0px -50% 0px" });
      sections.forEach((s) => spy.observe(s));
    }
  }

  /* ---------- countdown ---------- */
  $$("[data-countdown]").forEach((el) => {
    const target = new Date(el.dataset.countdown);
    if (isNaN(target.getTime())) return;
    const units = {};
    $$("[data-unit]", el).forEach((u) => { units[u.dataset.unit] = u; });
    const done = $("[data-countdown-done]", el);
    const pad = (n) => String(n).padStart(2, "0");
    let timer = null;
    const tick = () => {
      const diff = target.getTime() - Date.now();
      if (diff <= 0) {
        el.classList.add("is-done");
        Object.values(units).forEach((u) => { u.textContent = "00"; });
        if (done) done.hidden = false;
        if (timer) clearInterval(timer);
        return;
      }
      if (units.days) units.days.textContent = pad(Math.floor(diff / 86400000));
      if (units.hours) units.hours.textContent = pad(Math.floor(diff / 3600000) % 24);
      if (units.minutes) units.minutes.textContent = pad(Math.floor(diff / 60000) % 60);
      if (units.seconds) units.seconds.textContent = pad(Math.floor(diff / 1000) % 60);
    };
    tick();
    timer = setInterval(tick, 1000);
  });

  /* ---------- reveal on scroll ---------- */
  const revealables = $$(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    revealables.forEach((el) => observer.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add("is-visible"));
  }

  /* ---------- modal (video, map, lightbox) ---------- */
  let modal = null;
  let gallery = null; // { items: [...urls], index }

  function ensureModal() {
    if (modal) return modal;
    modal = document.createElement("div");
    modal.className = "ui-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.innerHTML =
      '<div class="ui-modal__backdrop" data-close></div>' +
      '<div class="ui-modal__box">' +
      '<button type="button" class="ui-modal__close" aria-label="Close" data-close>&times;</button>' +
      '<button type="button" class="ui-modal__nav ui-modal__prev" aria-label="Previous photo">&#8249;</button>' +
      '<div class="ui-modal__body"></div>' +
      '<button type="button" class="ui-modal__nav ui-modal__next" aria-label="Next photo">&#8250;</button>' +
      "</div>";
    document.body.appendChild(modal);
    modal.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closeModal(); });
    $(".ui-modal__prev", modal).addEventListener("click", () => stepGallery(-1));
    $(".ui-modal__next", modal).addEventListener("click", () => stepGallery(1));
    document.addEventListener("keydown", (e) => {
      if (!modal.classList.contains("is-open")) return;
      if (e.key === "Escape") closeModal();
      if (e.key === "ArrowLeft") stepGallery(-1);
      if (e.key === "ArrowRight") stepGallery(1);
    });
    return modal;
  }

  function openModal(content, variant) {
    ensureModal();
    modal.className = "ui-modal is-open" + (variant ? " ui-modal--" + variant : "");
    $(".ui-modal__body", modal).replaceChildren(content);
    document.body.classList.add("modal-open");
    $(".ui-modal__close", modal).focus({ preventScroll: true });
  }

  function closeModal() {
    if (!modal) return;
    modal.classList.remove("is-open");
    $(".ui-modal__body", modal).replaceChildren();
    document.body.classList.remove("modal-open");
    gallery = null;
  }

  function frame(src, title) {
    const iframe = document.createElement("iframe");
    iframe.src = src;
    iframe.title = title;
    iframe.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = "no-referrer-when-downgrade";
    return iframe;
  }

  function showGalleryItem() {
    const img = document.createElement("img");
    img.src = gallery.items[gallery.index];
    img.alt = `Photo ${gallery.index + 1} of ${gallery.items.length}`;
    $(".ui-modal__body", modal).replaceChildren(img);
  }

  function stepGallery(delta) {
    if (!gallery) return;
    gallery.index = (gallery.index + delta + gallery.items.length) % gallery.items.length;
    showGalleryItem();
  }

  $$(".js-gallery").forEach((wrap) => {
    const links = $$("a[data-lightbox]", wrap);
    links.forEach((link, index) => link.addEventListener("click", (e) => {
      e.preventDefault();
      openModal(document.createTextNode(""), links.length > 1 ? "gallery" : "photo");
      gallery = { items: links.map((a) => a.getAttribute("href")), index };
      showGalleryItem();
    }));
  });

  $$("[data-video-embed], [data-video-file]").forEach((btn) => btn.addEventListener("click", (e) => {
    e.preventDefault();
    const embed = btn.getAttribute("data-video-embed");
    if (embed) {
      openModal(frame(embed + (embed.includes("?") ? "&" : "?") + "autoplay=1", "Video"), "video");
    } else {
      const video = document.createElement("video");
      video.src = btn.getAttribute("data-video-file");
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      openModal(video, "video");
    }
  }));

  $$("a[data-map-embed]").forEach((link) => link.addEventListener("click", (e) => {
    const embed = link.getAttribute("data-map-embed");
    if (!embed) return;
    e.preventDefault();
    const wrap = document.createElement("div");
    wrap.className = "ui-map";
    wrap.appendChild(frame(embed, "Venue map"));
    const href = link.getAttribute("href");
    if (href && href.startsWith("http")) {
      const open = document.createElement("a");
      open.href = href;
      open.target = "_blank";
      open.rel = "noopener";
      open.className = "ui-map__open";
      open.textContent = "Open in Google Maps ↗";
      wrap.appendChild(open);
    }
    openModal(wrap, "map");
  }));

  /* ---------- RSVP via WhatsApp ---------- */
  $$("form[data-whatsapp]").forEach((form) => {
    const eventSelect = form.querySelector('select[name="event"]');
    if (eventSelect) {
      $$("[data-event-title]").forEach((el) => {
        const title = el.textContent.trim();
        if (title) eventSelect.add(new Option(title, title));
      });
      if (eventSelect.options.length > 1) eventSelect.add(new Option("All events", "All events"));
    }
    const status = form.querySelector("[data-rsvp-status]");
    const toggleDetails = () => {
      const declined = form.querySelector('input[name="attending"]:checked')?.value === "no";
      form.classList.toggle("is-declined", declined);
    };
    form.addEventListener("change", toggleDetails);
    toggleDetails();

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const name = String(data.get("name") || "").trim();
      if (!name) {
        form.querySelector('[name="name"]')?.focus();
        if (status) status.textContent = "Please enter your name.";
        return;
      }
      let phone = String(form.dataset.whatsapp || "").replace(/\D/g, "");
      if (phone.length === 10) phone = "91" + phone; // local Indian number without country code
      const declined = data.get("attending") === "no";
      const lines = [`RSVP from ${name}`, declined ? "Sorry, I can't come." : "Yes, I will be there!"];
      if (!declined) {
        if (data.get("guests")) lines.push(`Guests: ${data.get("guests")}`);
        if (data.get("event")) lines.push(`Attending: ${data.get("event")}`);
        if (data.get("meal")) lines.push(`Meal: ${data.get("meal")}`);
      }
      const message = String(data.get("message") || "").trim();
      if (message) lines.push(`Message: ${message}`);
      window.open(`https://wa.me/${phone}?text=${encodeURIComponent(lines.join("\n"))}`, "_blank", "noopener");
      if (status) status.textContent = "Opening WhatsApp… just press send. Thank you!";
    });
  });

  /* ---------- hero slider ---------- */
  $$(".js-slider").forEach((slider) => {
    const slides = $$(".slide", slider);
    if (slides.length) slides[0].classList.add("is-active");
    if (slides.length < 2) {
      slider.classList.add("is-single");
      return;
    }
    let index = 0;
    let timer = null;
    const go = (n) => {
      slides[index].classList.remove("is-active");
      index = (n + slides.length) % slides.length;
      slides[index].classList.add("is-active");
    };
    const play = () => {
      clearInterval(timer);
      if (!reduceMotion) timer = setInterval(() => go(index + 1), 6000);
    };
    $(".slider-prev", slider)?.addEventListener("click", () => { go(index - 1); play(); });
    $(".slider-next", slider)?.addEventListener("click", () => { go(index + 1); play(); });
    let startX = null;
    slider.addEventListener("touchstart", (e) => { startX = e.touches[0].clientX; }, { passive: true });
    slider.addEventListener("touchend", (e) => {
      if (startX === null) return;
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 50) { go(index + (dx < 0 ? 1 : -1)); play(); }
      startX = null;
    });
    play();
  });

  /* ---------- back to top ---------- */
  const backToTop = $(".back-to-top");
  if (backToTop) {
    const onScroll = () => backToTop.classList.toggle("is-visible", window.scrollY > 600);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    backToTop.addEventListener("click", () => scrollToId(""));
  }
})();
