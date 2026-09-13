(function () {
  const container = document.getElementById("plans");
  let quota = null;

  const features = {
    free: ["1 invitation per month", "All 10 templates", "Netlify hosting + share link"],
    basic: ["5 invitations per month", "All 10 templates", "Photo gallery, video & map"],
    pro: ["Unlimited invitations", "All 10 templates", "Best for event planners"],
  };

  async function subscribe(plan, button) {
    if (!API.isLoggedIn()) {
      location.href = "/login/?next=/pricing/";
      return;
    }
    if (typeof Razorpay === "undefined") {
      toast("Payment window could not load. Check your connection.", "error");
      return;
    }
    button.disabled = true;
    try {
      const order = await API.request("/billing/order/", { method: "POST", json: { plan: plan.id } });
      const checkout = new Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "E-Invite",
        description: `${order.plan_name} plan`,
        prefill: { email: order.email },
        theme: { color: "#4a1d3f" },
        handler: async (response) => {
          try {
            await API.request("/billing/verify/", { method: "POST", json: response });
            toast("Subscription activated! 🎉", "success");
            setTimeout(() => { location.href = "/dashboard/"; }, 1200);
          } catch (err) {
            toast(err.message, "error");
          }
        },
        modal: { ondismiss: () => { button.disabled = false; } },
      });
      checkout.open();
    } catch (err) {
      toast(err.message, "error");
      button.disabled = false;
    }
  }

  function render(data) {
    document.getElementById("payments-note").hidden = data.payments_enabled;
    container.replaceChildren(...data.plans.map((plan) => {
      const el = document.createElement("article");
      const isCurrent = quota && quota.plan === plan.id;
      el.className = "card plan" + (plan.id === "basic" ? " is-featured" : "");
      el.innerHTML = `
        <h3>${escapeHtml(plan.name)}</h3>
        <div class="price">₹${plan.price_inr}<small>${plan.price_inr ? ` / ${data.plan_days} days` : " forever"}</small></div>
        <ul>${(features[plan.id] || []).map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`;
      const button = document.createElement("button");
      button.type = "button";
      if (!plan.price_inr) {
        button.className = "btn btn-ghost";
        button.textContent = isCurrent ? "Current plan" : "Included";
        button.disabled = true;
      } else {
        button.className = plan.id === "basic" ? "btn btn-gold" : "btn";
        button.textContent = isCurrent ? "Extend 30 days" : `Choose ${plan.name}`;
        button.disabled = !data.payments_enabled;
        button.addEventListener("click", () => subscribe(plan, button));
      }
      el.appendChild(button);
      return el;
    }));
  }

  async function load() {
    try {
      if (API.isLoggedIn()) {
        quota = (await API.request("/auth/me/")).quota;
        document.getElementById("current-plan").textContent =
          `You're on ${quota.plan_name}` + (quota.expires_at ? ` until ${new Date(quota.expires_at).toLocaleDateString()}` : "");
      }
      render(await API.request("/billing/plans/"));
    } catch (err) {
      toast(err.message, "error");
    }
  }

  load();
})();
