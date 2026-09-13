# 💍 E-Invite: E-Invitation Website Builder

A Django platform where users verify their email with an OTP, pick a wedding invitation template,
fill in names, dates, their story, photos, video, events and maps, preview live, and **deploy to Netlify**
in one click. The live link can then be shared on WhatsApp.

- **Storage:** SQLite only. Uploaded files live in `media/` and SQLite stores their paths (Option A).
- **Free tier:** 1 invitation per email per month. Paid plans (Razorpay) raise the limit.
- **Locked design:** only fields declared in each template's `config.json` are editable. Colors,
  fonts, animations and layout stay in the template's CSS/JS.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # then fill in the values you have
python manage.py migrate        # also loads the 10 templates from templates_library/
python manage.py createsuperuser  # optional, for /admin/
python manage.py runserver
```

Open http://127.0.0.1:8000.

With no `EMAIL_HOST_USER` set, OTP emails are **printed to the runserver console**, so you can
test signup without Gmail. Without `NETLIFY_TOKEN` everything works except the Deploy button,
which returns a clear "not configured" error. Without Razorpay keys the pricing page shows plans
with the buttons disabled.

## Configuration (`.env`)

| Key | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Standard Django settings |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Gmail address + [App Password](https://myaccount.google.com/apppasswords) for OTP mail |
| `NETLIFY_TOKEN` | Netlify personal access token (User settings → Applications) |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay API keys (test keys work) |

Plans, prices and monthly limits are in `PLANS` in [config/settings.py](config/settings.py).

## Project layout

```
config/              settings, root urls
accounts/            custom User, OTP model, signup/login OTP APIs (JWT)
billing/             Subscription + Payment models, quota logic, Razorpay order/verify
invitations/         Template + Invitation models, editor/media/preview/deploy APIs
  fields.py          config.json field validation, YouTube/Vimeo + Google Maps parsing
  renderer.py        {{placeholder}} engine (HTML-escaped) for preview and deploy
  netlify.py         builds the static site folder, zips it, deploys via Netlify API
  media.py           image/video upload validation → MEDIA_ROOT
frontend/            page shells + vanilla JS (login, dashboard, gallery, editor, pricing)
templates_library/   home, home2, home3, home4 (index.html, style.css, config.json)
  _common/           CSS, JS and floral SVGs shared by the templates (copied into every deploy)
```

## User flow

1. **Sign up / log in** at `/login/`: email → 6-digit OTP → JWT stored in the browser.
2. **Templates** at `/templates/`: live thumbnails rendered with sample data. "Use this template"
   checks the monthly quota and creates the invitation.
3. **Editor** at `/editor/<id>/`: a form generated from `config.json`, autosave, uploads, and a live
   iframe preview (mobile/desktop).
4. **Deploy**: required fields are checked, the site is built and uploaded to Netlify, and the
   `https://….netlify.app` link is saved. Deploying again updates the **same** site and link.
5. **Share**: WhatsApp button (`wa.me`), copy link. Deployed pages include Open Graph tags, so
   WhatsApp shows the title and couple photo in the link preview.

## API reference

All endpoints except auth, template list/sample and billing plans need
`Authorization: Bearer <access>`.

| Method | Path | Notes |
|---|---|---|
| POST | `/api/auth/signup/request-otp/` | `{email}`. 60 s resend cooldown, IP throttle |
| POST | `/api/auth/signup/verify-otp/` | `{email, otp, password?}` → `{access, refresh}` |
| POST | `/api/auth/login/request-otp/` | `{email}` |
| POST | `/api/auth/login/verify-otp/` | `{email, otp}` → `{access, refresh}` |
| POST | `/api/auth/token/refresh/` | `{refresh}` |
| GET | `/api/auth/me/` | email + quota summary |
| GET | `/api/templates/` | active templates with editable fields |
| GET | `/api/templates/<id>/sample/` | HTML preview with sample values |
| GET/POST | `/api/invitations/` | list (+quota) / create `{template_id, content_data?}` (403 `quota_exceeded`) |
| GET/PATCH/DELETE | `/api/invitations/<id>/` | PATCH `{content_data?, map_link?, video_url?}` |
| POST | `/api/invitations/<id>/media/` | multipart `hero_image`, `gallery_images` (multiple), `video_file` |
| DELETE | `/api/invitations/<id>/media/hero_image/` · `video_file/` · `gallery/<index>/` | remove media |
| POST | `/api/invitations/<id>/preview/` | returns HTML. Body may carry unsaved values |
| POST | `/api/invitations/<id>/deploy/` | → `{live_url, whatsapp_url}` |
| GET | `/api/billing/plans/` | plans + whether payments are enabled |
| POST | `/api/billing/order/` | `{plan}` → Razorpay order for Checkout |
| POST | `/api/billing/verify/` | Checkout response; signature verified, plan activated for 30 days |

## Templates

| Folder | Name | Look |
|---|---|---|
| `home` | Save The Date | Grey hero, oval portrait, heart couple photo, oval story timeline, dark footer |
| `home2` | Blossom Watercolor | Watercolor hero with countdown blooms, soft-edged photos, oval RSVP card, "Thank You" footer |
| `home3` | Rose Frame | Line frames with coral roses, arched portrait, ring countdown, story circles |
| `home4` | Grand Slider | Full-screen fading photo slider with names and countdown, then the `home` sections |

All four are written from scratch in the style of the Mawhub reference pages. They use none of the
Mawhub code, fonts or photos. Jost and Sail come from Google Fonts, and the flowers are original SVGs in
`_common/img/`. The HTML files in `templates/invitations/` are only saved copies of the demo site for reference.
The app doesn't use them, and they shouldn't be deployed.

Every page section hides itself when its fields are empty (a story item without a title, an RSVP
section without a WhatsApp number, and so on), so couples only fill in what they need.

RSVP needs no backend: a guest's reply opens WhatsApp with a ready-made message to the couple's number.
"See Location" opens a Google Map popup built from the venue address, or from a pasted Maps link.

## Adding or editing a template

1. Create `templates_library/<folder>/` with `index.html`, `style.css` and `config.json`. Link the
   shared files with `../_common/css/base.css`, `../_common/css/sections.css` and
   `../_common/js/common.js`. The same relative paths work in the editor preview and on Netlify.
   The fastest start is copying an existing template and changing the hero or section variants
   (`couple--heart|plain|frame`, `story--oval|soft|circles`, `rsvp--photo|oval|box`, `event--card|circle`).
2. In `config.json`, declare `name`, `category`, `order`, `description`, `share_title`,
   `share_description`, `groups` (editor sections, in order) and `editable_fields`. Each field takes
   `type`, `group`, `label`, and optionally `required`, `max_length`, `sample`, `hint`.
   Field types:
   - `text`, `textarea`, `date`, `time`: plain values. Add `"no_countdown": true` on event dates.
   - `url`: an https link (social profiles).
   - `location`: an address. It also provides `{{key_embed}}` and `{{key_directions}}` map URLs.
   - `map`: an optional Google Maps link. `"for": "<location key>"` makes it override that location's map.
     The key `map_link` is the invitation's main map.
   - `image`: any number of photo fields (`hero_image`, `couple_photo`, `story_1_photo`, …).
   - `image_multiple` (key `gallery_images`, with `max`) and `video` (key `video_url`, YouTube/Vimeo or upload).
3. Use placeholders in `index.html`:
   - `{{field}}`: HTML-escaped value. Textarea line breaks become `<br>`.
   - `{{#field}}…{{/field}}`: shown only if set. For lists it repeats, with `{{.}}` as the item and `{{index}}`.
   - `{{^field}}…{{/field}}`: shown only if empty (for example, a photo placeholder).
   - Computed values:
     - dates: `{{<date>_iso|_day|_month|_month_short|_year|_weekday|_short}}`
     - times and text: `{{<time>_24}}`, `{{<text>_initial}}`
     - countdown and sections: `{{countdown_target}}`, `{{has_<group>}}`
     - gallery: `{{gallery_images}}`, `{{gallery_preview}}` (first 3), `{{has_gallery}}`
     - video: `{{video_embed}}`, `{{video_file}}`, `{{has_video}}`
     - sharing: `{{share_title}}`, `{{share_description}}`, `{{og_image}}`, `{{year}}`
4. Optional: put sample photos in `<folder>/sample/` and set an image field's `"sample": "sample/x.jpg"`.
   The gallery preview then shows them. The `sample/` folder is never deployed.
5. Run `python manage.py sync_templates` (also runs automatically after `migrate`).

## Maintenance

- `python manage.py cleanup_invitations --days 30 [--dry-run]` deletes never-deployed invitations
  untouched for N days, their media, and old OTP rows. Schedule it with cron or Task Scheduler.
- Tests: `python manage.py test accounts billing invitations`. Netlify and Razorpay are mocked.

## Production notes

- Set `DEBUG=False`, a long random `SECRET_KEY`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
  Run `collectstatic` and serve `/static/` and `/media/` from the web server (nginx) or WhiteNoise.
  Django only serves media while `DEBUG=True`.
- The editor preview needs the uploaded images reachable at `/media/`. Deployed sites don't:
  their images are copied into the Netlify bundle.
- SQLite is fine for small to medium traffic. Move to PostgreSQL when concurrent writes grow.
  Watch the disk used by `media/`.
- Gmail SMTP allows about 500 emails/day. Switch to SendGrid or SES at scale.
- Each deploy is a synchronous request (typically 5–20 s). For heavy use, move it to a task queue.
- Netlify API rate limits and site counts apply per account. Check your Netlify plan.
- Deleting an invitation also deletes its Netlify site. Used monthly quota is not refunded.

## Changes from the original spec

- **OTP hardening:** codes come from `secrets`, only the latest code is valid, 5 wrong tries
  invalidate it, there is a 60 s resend cooldown, and DRF throttling limits requests per IP.
  DRF throttling replaces `django-ratelimit`, so that package isn't needed.
- **XSS-safe rendering:** user text is HTML-escaped and never re-parsed as placeholders.
  Video accepts only YouTube/Vimeo, and map links must be https Google Maps URLs.
- **Netlify:** the site is reused on redeploy (stable link), a random name suffix avoids name clashes,
  a temporary build folder is always cleaned up, and the deploy waits until the site is `ready`.
- **Maps:** users can paste a share link, an embed URL or the full `<iframe>` code. When there's no
  embeddable link, the map is embedded from the venue address instead.
- **Razorpay:** called over its REST API with `requests`, and payment signatures are verified with
  HMAC-SHA256. No SDK needed.
