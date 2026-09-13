(function () {
  if (!API.requireAuth()) return;

  const list = document.getElementById("list");
  const empty = document.getElementById("empty");

  function renderQuota(q) {
    document.getElementById("quota").hidden = false;
    document.getElementById("quota-plan").textContent = `${q.plan_name} plan`;
    const fill = document.getElementById("quota-fill");
    let text;
    if (q.limit === null) {
      text = `Unlimited invitations · ${q.used} created this month`;
      fill.style.width = "100%";
    } else {
      text = `${q.used} of ${q.limit} invitation${q.limit === 1 ? "" : "s"} used this month`;
      fill.style.width = `${Math.min(100, (q.used / q.limit) * 100)}%`;
    }
    if (q.expires_at) text += ` · renews/expires ${new Date(q.expires_at).toLocaleDateString()}`;
    document.getElementById("quota-text").textContent = text;
    document.getElementById("upgrade-btn").hidden = q.plan === "pro";
  }

  function card(inv) {
    const el = document.createElement("article");
    el.className = "card inv-card";
    const title = inv.title || inv.template_name;
    el.innerHTML = `
      <div class="row-between">
        <span class="badge ${inv.is_deployed ? "badge-live" : ""}">${inv.is_deployed ? "● Live" : "Draft"}</span>
        <span class="muted small">${escapeHtml(inv.template_name)}</span>
      </div>
      <h3>${escapeHtml(title)}</h3>
      <p class="muted small">Updated ${new Date(inv.updated_at).toLocaleString()}</p>
      ${inv.live_url ? `<a class="live-link" href="${escapeHtml(inv.live_url)}" target="_blank" rel="noopener">${escapeHtml(inv.live_url)}</a>` : ""}
      <div class="inv-actions">
        <a class="btn btn-sm" href="/editor/${inv.id}/">Edit</a>
        ${inv.live_url ? `
          <a class="btn btn-sm btn-whatsapp" href="${escapeHtml(inv.whatsapp_url)}" target="_blank" rel="noopener">📲 WhatsApp</a>
          <button type="button" class="btn btn-sm btn-ghost" data-copy>Copy link</button>` : ""}
        <button type="button" class="btn btn-sm btn-danger" data-delete>Delete</button>
      </div>`;
    el.querySelector("[data-copy]")?.addEventListener("click", () => copyText(inv.live_url));
    el.querySelector("[data-delete]").addEventListener("click", async (e) => {
      const warning = inv.is_deployed
        ? "Delete this invitation? The live link will stop working. Your monthly quota is not refunded."
        : "Delete this draft? Your monthly quota is not refunded.";
      if (!confirm(warning)) return;
      e.target.disabled = true;
      try {
        await API.request(`/invitations/${inv.id}/`, { method: "DELETE" });
        toast("Invitation deleted.", "success");
        load();
      } catch (err) {
        toast(err.message, "error");
        e.target.disabled = false;
      }
    });
    return el;
  }

  async function load() {
    try {
      const [me, data] = await Promise.all([
        API.request("/auth/me/"),
        API.request("/invitations/"),
      ]);
      document.getElementById("me-email").textContent = me.email;
      renderQuota(data.quota);
      list.replaceChildren(...data.invitations.map(card));
      empty.hidden = data.invitations.length > 0;
    } catch (err) {
      toast(err.message, "error");
    }
  }

  load();
})();
