(function () {
  if (!API.requireAuth()) return;

  const id = document.getElementById("editor").dataset.invitationId;
  const form = document.getElementById("fields");
  const frame = document.getElementById("preview");
  const statusEl = document.getElementById("save-status");
  const deployBtn = document.getElementById("deploy-btn");
  const TEXT_TYPES = ["text", "textarea", "date", "time", "location", "url"];
  const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp,image/gif";
  const DEFAULT_GROUPS = { details: "Details", photos: "Photos", video: "Video", location: "Location" };

  let invitation = null;
  let dirty = false;
  let saveTimer, previewTimer, previewSeq = 0;

  const setStatus = (text) => { statusEl.textContent = text; };
  const fields = () => invitation.template.editable_fields;

  /* ---------- form building ---------- */
  function fieldWrap(key, spec, control, hint) {
    const label = document.createElement("label");
    label.className = "field";
    label.dataset.key = key;
    label.innerHTML = `<span>${escapeHtml(spec.label || key)}${spec.required ? ' <b class="req">*</b>' : ""}</span>`;
    label.appendChild(control);
    const help = spec.hint || hint;
    if (help) label.insertAdjacentHTML("beforeend", `<div class="hint">${escapeHtml(help)}</div>`);
    return label;
  }

  function textControl(key, spec, value) {
    const input = document.createElement(spec.type === "textarea" ? "textarea" : "input");
    if (spec.type !== "textarea") input.type = spec.type === "location" ? "text" : spec.type;
    input.name = key;
    input.value = value || "";
    if (spec.sample && !["date", "time"].includes(spec.type)) input.placeholder = "e.g. " + spec.sample;
    if (spec.max_length) input.maxLength = spec.max_length;
    input.dataset.kind = "content";
    return input;
  }

  function uploadButton(label, name, accept, multiple) {
    const wrap = document.createElement("label");
    wrap.className = "upload btn btn-ghost btn-sm";
    wrap.innerHTML = `${label}<input type="file" name="${escapeHtml(name)}" accept="${accept}" ${multiple ? "multiple" : ""}>`;
    wrap.querySelector("input").addEventListener("change", (e) => upload(name, e.target));
    return wrap;
  }

  function mediaBox(button, thumbsId) {
    const box = document.createElement("div");
    box.append(button);
    box.insertAdjacentHTML("beforeend", `<div class="thumbs" id="${thumbsId}"></div>`);
    return box;
  }

  function defaultGroup(spec) {
    if (TEXT_TYPES.includes(spec.type)) return "details";
    if (spec.type === "image" || spec.type === "image_multiple") return "photos";
    if (spec.type === "video") return "video";
    return "location";
  }

  function buildForm() {
    const titles = invitation.template.groups || {};
    const sections = new Map();
    const sectionFor = (groupId) => {
      if (!sections.has(groupId)) {
        const s = document.createElement("section");
        s.innerHTML = `<h2>${escapeHtml(titles[groupId] || DEFAULT_GROUPS[groupId] || groupId)}</h2>`;
        sections.set(groupId, s);
      }
      return sections.get(groupId);
    };
    Object.keys(titles).forEach(sectionFor); // keep the order declared in config.json

    Object.entries(fields()).forEach(([key, spec]) => {
      const section = sectionFor(spec.group || defaultGroup(spec));
      if (TEXT_TYPES.includes(spec.type)) {
        section.appendChild(fieldWrap(key, spec, textControl(key, spec, invitation.content_data[key])));
      } else if (spec.type === "image") {
        const box = mediaBox(uploadButton("Upload photo", key, IMAGE_ACCEPT), `thumbs-${key}`);
        section.appendChild(fieldWrap(key, spec, box, "JPG, PNG or WEBP, up to 5 MB."));
      } else if (spec.type === "image_multiple") {
        const box = mediaBox(uploadButton("Add photos", "gallery_images", IMAGE_ACCEPT, true), "gallery-thumbs");
        section.appendChild(fieldWrap(key, spec, box, `Up to ${spec.max || 6} photos.`));
      } else if (spec.type === "video") {
        const input = document.createElement("input");
        input.type = "url";
        input.name = "video_url";
        input.value = invitation.video_url || "";
        input.placeholder = "https://youtu.be/…";
        section.appendChild(fieldWrap("video_url", spec, input, "Paste a YouTube or Vimeo link…"));
        const box = mediaBox(uploadButton("…or upload MP4 / WEBM", "video_file", "video/mp4,video/webm"), "video-thumbs");
        section.appendChild(fieldWrap("video_file", { label: "Video file" }, box, "Up to 25 MB. Keep it short for fast loading."));
      } else if (spec.type === "map") {
        const input = document.createElement("input");
        input.type = "text";
        input.name = key;
        input.placeholder = "https://maps.app.goo.gl/…";
        if (key === "map_link") {
          input.value = invitation.map_link || "";
        } else {
          input.value = invitation.content_data[key] || "";
          input.dataset.kind = "content";
        }
        section.appendChild(fieldWrap(key, spec, input,
          "Optional. Google Maps → Share → Copy link (or Embed a map → Copy HTML). Empty = map from the address."));
      }
    });

    form.replaceChildren(...[...sections.values()].filter((s) => s.children.length > 1));
    renderMedia();
  }

  function thumb(html, onRemove) {
    const el = document.createElement("div");
    el.className = "thumb";
    el.innerHTML = html + '<button type="button" aria-label="Remove">×</button>';
    el.querySelector("button").addEventListener("click", onRemove);
    return el;
  }

  function renderMedia() {
    Object.entries(fields()).forEach(([key, spec]) => {
      if (spec.type !== "image") return;
      const box = document.getElementById(`thumbs-${key}`);
      const url = key === "hero_image" ? invitation.hero_image : (invitation.images || {})[key];
      if (box) box.replaceChildren(...(url ? [thumb(`<img src="${escapeHtml(url)}" alt="">`, () => removeMedia(key))] : []));
    });
    const gallery = document.getElementById("gallery-thumbs");
    if (gallery) gallery.replaceChildren(...invitation.gallery_images.map((url, i) =>
      thumb(`<img src="${escapeHtml(url)}" alt="">`, () => removeMedia(`gallery/${i}`))));
    const video = document.getElementById("video-thumbs");
    if (video) video.replaceChildren(...(invitation.video_file
      ? [thumb(`<video src="${escapeHtml(invitation.video_file)}" muted></video>`, () => removeMedia("video_file"))] : []));
  }

  /* ---------- data ---------- */
  function collect() {
    const payload = { content_data: {} };
    form.querySelectorAll('[data-kind="content"]').forEach((el) => { payload.content_data[el.name] = el.value; });
    if (form.elements.map_link) payload.map_link = form.elements.map_link.value;
    if (form.elements.video_url) payload.video_url = form.elements.video_url.value;
    return payload;
  }

  function showErrors(errors = {}) {
    form.querySelectorAll(".field").forEach((f) => {
      f.classList.remove("has-error");
      f.querySelector(".error")?.remove();
    });
    let first = null;
    Object.entries(errors).forEach(([key, message]) => {
      const f = form.querySelector(`.field[data-key="${CSS.escape(key)}"]`);
      if (!f) return;
      f.classList.add("has-error");
      f.insertAdjacentHTML("beforeend", `<div class="error">${escapeHtml(message)}</div>`);
      first = first || f;
    });
    first?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function merge(updated) {
    invitation = { ...updated, template: updated.template || invitation.template };
  }

  async function save() {
    clearTimeout(saveTimer);
    if (!dirty) return true;
    setStatus("Saving…");
    try {
      merge(await API.request(`/invitations/${id}/`, { method: "PATCH", json: collect() }));
      dirty = false;
      showErrors();
      renderMedia();
      setStatus("All changes saved ✓");
      return true;
    } catch (err) {
      showErrors(err.data && err.data.fields);
      setStatus("Not saved");
      toast(err.message, "error");
      return false;
    }
  }

  async function refreshPreview() {
    const seq = ++previewSeq;
    try {
      const res = await API.request(`/invitations/${id}/preview/`, { method: "POST", json: collect(), raw: true });
      const html = await res.text();
      if (seq !== previewSeq) return;
      let scrollY = 0;
      try { scrollY = frame.contentWindow.scrollY; } catch (_) { /* ignore */ }
      frame.onload = () => { try { frame.contentWindow.scrollTo(0, scrollY); } catch (_) { /* ignore */ } };
      frame.srcdoc = html;
    } catch (err) {
      if (seq === previewSeq) toast(err.message, "error");
    }
  }

  function onEdit() {
    dirty = true;
    setStatus("Unsaved changes");
    clearTimeout(previewTimer);
    previewTimer = setTimeout(refreshPreview, 450);
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 1500);
  }

  async function upload(name, input) {
    if (!input.files.length) return;
    const data = new FormData();
    [...input.files].forEach((file) => data.append(name, file));
    setStatus("Uploading…");
    const button = input.closest(".upload");
    button.style.opacity = ".6";
    try {
      await save();
      merge(await API.request(`/invitations/${id}/media/`, { method: "POST", form: data }));
      if (name === "video_file" && form.elements.video_url) form.elements.video_url.value = "";
      renderMedia();
      refreshPreview();
      setStatus("All changes saved ✓");
    } catch (err) {
      toast(err.message, "error");
      setStatus("Upload failed");
    } finally {
      input.value = "";
      button.style.opacity = "";
    }
  }

  async function removeMedia(path) {
    try {
      merge(await API.request(`/invitations/${id}/media/${path}/`, { method: "DELETE" }));
      renderMedia();
      refreshPreview();
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function showDeployed(inv) {
    if (!inv.live_url) return;
    document.getElementById("deploy-result").hidden = false;
    const link = document.getElementById("live-link");
    link.href = link.textContent = inv.live_url;
    document.getElementById("open-link").href = inv.live_url;
    document.getElementById("wa-link").href = inv.whatsapp_url;
  }

  async function deploy() {
    dirty = true;
    if (!(await save())) return;
    const original = deployBtn.innerHTML;
    deployBtn.disabled = true;
    deployBtn.innerHTML = '<span class="spinner"></span> Deploying…';
    try {
      const result = await API.request(`/invitations/${id}/deploy/`, { method: "POST" });
      merge(result.invitation);
      showDeployed(result.invitation);
      toast(result.message, "success");
    } catch (err) {
      if (err.data && err.data.missing) {
        showErrors(Object.fromEntries(Object.entries(fields())
          .filter(([, spec]) => err.data.missing.includes(spec.label))
          .map(([key]) => [key, "Required before deploying."])));
      }
      toast(err.message, "error");
    } finally {
      deployBtn.disabled = false;
      deployBtn.innerHTML = original;
    }
  }

  /* ---------- wiring ---------- */
  form.addEventListener("input", (e) => { if (e.target.type !== "file") onEdit(); });
  document.getElementById("save-btn").addEventListener("click", () => { dirty = true; save(); });
  deployBtn.addEventListener("click", deploy);
  document.getElementById("copy-link").addEventListener("click", () => copyText(invitation.live_url));
  document.querySelectorAll("[data-device]").forEach((chip) => chip.addEventListener("click", () => {
    document.querySelectorAll("[data-device]").forEach((c) => c.classList.toggle("is-active", c === chip));
    document.getElementById("stage").classList.toggle("is-mobile", chip.dataset.device === "mobile");
  }));
  window.addEventListener("beforeunload", (e) => { if (dirty) { save(); e.preventDefault(); } });

  API.request(`/invitations/${id}/`)
    .then((data) => {
      invitation = data;
      document.getElementById("editor-title").textContent = data.template.name;
      document.title = `Editing ${data.template.name} · E-Invite`;
      buildForm();
      showDeployed(data);
      setStatus("All changes saved ✓");
      refreshPreview();
    })
    .catch((err) => {
      toast(err.message, "error");
      if (err.status === 404) setTimeout(() => { location.href = "/dashboard/"; }, 1500);
    });
})();
