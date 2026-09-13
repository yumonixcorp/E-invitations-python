(function () {
  const params = new URLSearchParams(location.search);
  const next = params.get("next");
  const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard/";
  if (API.isLoggedIn()) { location.href = safeNext; return; }

  let mode = params.get("mode") === "signup" ? "signup" : "login";
  let email = "";
  let cooldownTimer;

  const emailForm = document.getElementById("email-form");
  const otpForm = document.getElementById("otp-form");
  const resendBtn = document.getElementById("resend");
  const copy = {
    login: ["Welcome back", "We'll email you a 6-digit code."],
    signup: ["Create your account", "Verify your email to start building invitations."],
  };

  function setMode(newMode) {
    mode = newMode;
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("is-active", t.dataset.mode === mode));
    document.getElementById("auth-title").textContent = copy[mode][0];
    document.getElementById("auth-sub").textContent = copy[mode][1];
    showEmailStep();
  }

  function showEmailStep() {
    otpForm.hidden = true;
    emailForm.hidden = false;
  }

  function startCooldown(seconds) {
    clearInterval(cooldownTimer);
    let left = seconds;
    resendBtn.disabled = true;
    const tick = () => {
      resendBtn.textContent = left > 0 ? `Resend in ${left}s` : "Resend code";
      if (left <= 0) { resendBtn.disabled = false; clearInterval(cooldownTimer); }
      left -= 1;
    };
    tick();
    cooldownTimer = setInterval(tick, 1000);
  }

  async function requestOtp(button) {
    button.disabled = true;
    try {
      await API.request(`/auth/${mode}/request-otp/`, { method: "POST", json: { email } });
      emailForm.hidden = true;
      otpForm.hidden = false;
      document.getElementById("otp-email").textContent = email;
      otpForm.otp.value = "";
      otpForm.otp.focus();
      startCooldown(60);
      toast("OTP sent to your email.", "success");
    } catch (err) {
      toast(err.message, "error");
      if (err.status === 404 && mode === "login") setMode("signup");
      if (err.status === 400 && mode === "signup" && /registered/i.test(err.message)) setMode("login");
    } finally {
      button.disabled = false;
    }
  }

  document.querySelectorAll(".tab").forEach((tab) =>
    tab.addEventListener("click", () => setMode(tab.dataset.mode)));

  emailForm.addEventListener("submit", (e) => {
    e.preventDefault();
    email = emailForm.email.value.trim().toLowerCase();
    if (!emailForm.email.checkValidity() || !email) {
      toast("Enter a valid email address.", "error");
      return;
    }
    requestOtp(emailForm.querySelector("button[type=submit]"));
  });

  otpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const otp = otpForm.otp.value.trim();
    if (!/^\d{6}$/.test(otp)) { toast("Enter the 6-digit code.", "error"); return; }
    const button = otpForm.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      const tokens = await API.request(`/auth/${mode}/verify-otp/`, { method: "POST", json: { email, otp } });
      API.setTokens(tokens);
      location.href = safeNext;
    } catch (err) {
      toast(err.message, "error");
      button.disabled = false;
    }
  });

  resendBtn.addEventListener("click", () => requestOtp(resendBtn));
  document.getElementById("change-email").addEventListener("click", showEmailStep);
  setMode(mode);
})();
