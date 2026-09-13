(function () {
  const grid = document.getElementById("grid");
  const chips = document.getElementById("chips");
  let templates = [];
  let active = "All";

  async function useTemplate(template, button) {
    if (!API.isLoggedIn()) {
      location.href = "/login/?mode=signup&next=" + encodeURIComponent("/templates/");
      return;
    }
    button.disabled = true;
    button.textContent = "Creating…";
    try {
      const data = await API.request("/invitations/", { method: "POST", json: { template_id: template.id } });
      location.href = `/editor/${data.invitation_id}/`;
    } catch (err) {
      button.disabled = false;
      button.textContent = "Use this template";
      if (err.data && err.data.code === "quota_exceeded") {
        if (confirm("You've used this month's free invitation. See subscription plans?")) {
          location.href = "/pricing/";
        }
        return;
      }
      toast(err.message, "error");
    }
  }

  function renderChips() {
    const categories = ["All", ...new Set(templates.map((t) => t.category).filter(Boolean))];
    chips.replaceChildren(...categories.map((cat) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip" + (cat === active ? " is-active" : "");
      chip.textContent = cat;
      chip.addEventListener("click", () => { active = cat; renderChips(); renderGrid(); });
      return chip;
    }));
  }

  function renderGrid() {
    const shown = templates.filter((t) => active === "All" || t.category === active);
    grid.replaceChildren(...shown.map((t) => {
      const card = document.createElement("article");
      card.className = "card tpl-card";
      card.innerHTML = `
        <div class="tpl-thumb">
          <iframe src="/api/templates/${t.id}/sample/" loading="lazy" tabindex="-1" title="${escapeHtml(t.name)} preview"></iframe>
        </div>
        <div class="tpl-body">
          <span class="badge">${escapeHtml(t.category)}</span>
          <h3>${escapeHtml(t.name)}</h3>
          <p>${escapeHtml(t.description)}</p>
          <div class="row-between">
            <a class="small" href="/api/templates/${t.id}/sample/" target="_blank" rel="noopener">Full preview ↗</a>
          </div>
          <button type="button" class="btn">Use this template</button>
        </div>`;
      const button = card.querySelector("button");
      button.addEventListener("click", () => useTemplate(t, button));
      return card;
    }));
  }

  API.request("/templates/")
    .then((data) => { templates = data; renderChips(); renderGrid(); })
    .catch((err) => toast(err.message, "error"));
})();
