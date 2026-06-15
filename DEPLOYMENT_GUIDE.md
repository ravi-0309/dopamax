# Putting Dopamax online — a beginner's walkthrough

You'll use three free services. Think of them like this:

- **Supabase** = the filing cabinet where all the data lives (so nothing is ever lost).
- **GitHub** = a locker that holds a copy of your code.
- **Render** = the actual computer on the internet that runs your app and gives you a web link.

You'll do this once. Total time ~15–20 minutes. You do **not** need to type any code — I've already prepared everything (a `render.yaml` so Render configures itself, a secret key it generates for you, and a `.gitignore` so only the right files get uploaded).

⚠️ **One safety note:** during this you'll get a "connection string" that contains a password. You paste it **only** into Render's website. Never send it to anyone (including me).

---

## PART 1 — Create the database (Supabase)

1. Go to **https://supabase.com** and click **Start your project**. Sign in with Google or GitHub (quickest).
2. Click **New project**.
3. Fill in:
   - **Name:** `dopamax`
   - **Database Password:** click *Generate a password*, then **copy it and paste it into a notes file** — you'll need it in a moment.
   - **Region:** pick the one closest to where you live.
4. Click **Create new project** and wait ~2 minutes while it sets up.
5. At the top, click the green **Connect** button.
6. Find **Connection string**, and choose the **Session pooler** tab (this is the one that works on Render's free plan). Copy the line that starts with `postgresql://`. It looks like:
   ```
   postgresql://postgres.abcd1234:[YOUR-PASSWORD]@aws-0-region.pooler.supabase.com:5432/postgres
   ```
7. Replace `[YOUR-PASSWORD]` with the password you saved in step 3. Save this whole finished line in your notes — this is your **DATABASE_URL**.

✅ Part 1 done.

---

## PART 2 — Put the code on GitHub (easiest with GitHub Desktop)

1. Download **GitHub Desktop** from **https://desktop.github.com** and install it.
2. Open it and **sign in** (create a free GitHub account if you don't have one — just an email and password).
3. Click **File → Add local repository**.
4. Click **Choose…** and select your folder: `D:\Book Store\dopamax`.
5. It will say "this directory does not appear to be a Git repository" — click **create a repository** (the blue link), then click **Create repository**.
6. Click **Publish repository** (top right). You can leave **Keep this code private** ticked. Click **Publish**.

(GitHub Desktop automatically skips the big `venv` folder and your local database, because of the `.gitignore` I set up.)

✅ Part 2 done — your code is now safely on GitHub.

---

## PART 3 — Run it on Render

1. Go to **https://render.com** and **Sign up with GitHub** (one click, uses the account you just made).
2. If asked, **authorize Render** to access your repositories.
3. Click **New +** (top right) → **Blueprint**.
4. Find and select your **dopamax** repository, then click **Connect**.
5. Render reads my `render.yaml` and shows a service called **dopamax** with the settings already filled in. It will ask you for one value: **DATABASE_URL** — paste the connection string from Part 1, step 7.
6. Click **Apply** (or **Create**). Render now builds and starts your app — this takes 2–4 minutes. You'll see logs scrolling; when it says **Live**, it's ready.
7. At the top you'll see your link, like `https://dopamax.onrender.com`. Click it — you should see the Dopamax login page. Click **Register** to make your account.

✅ You're live!

> If Render shows a database connection error in the logs: go back to Supabase → Connect, and make sure you used the **Session pooler** string (port 5432). Update the `DATABASE_URL` in Render under your service's **Environment** tab, then click **Manual Deploy → Deploy latest commit**.

---

## PART 4 — Use it on your iPhone

1. Open your Render link in **Safari** on your iPhone.
2. Tap the **Share** button → **Add to Home Screen** → **Add**.
3. It now opens full-screen like a real app. Log in and your data is always there.

## Share with friends
Just send them your Render link. Each person clicks **Register** to get their own private account. Everyone's data is separate and private — one person can't see another's books, streaks, or anything else.

---

## PART 5 — Put it on your own web address (a subdomain)

Right now your app lives at something like `https://dopamax.onrender.com`. This part gives it a nicer address that *you* own, like `https://app.yourname.com`.

**10-second vocabulary (so the rest makes sense):**
- A **domain** is the web address you buy once a year, like `yourname.com`.
- A **subdomain** is a word with a dot in front of it, like `app.yourname.com`. Once you own the domain, you can make as many subdomains as you want, for free.
- **DNS** is just the phone book of the internet. You'll add one line that says: "when someone types `app.yourname.com`, send them to my Render app."

### Step 1 — Buy a domain
Go to a domain seller and buy your domain (usually about $10–12/year). Beginner-friendly options:
- **Cloudflare** (cloudflare.com) — cheapest, and it also manages the DNS phone book in the same place. **Recommended.**
- **Namecheap** or **Porkbun** also work fine.

Pick a name, pay, done. You now own `yourname.com`.

### Step 2 — Tell Render about your new address
1. In Render, open your **dopamax** service.
2. In the left menu click **Settings**, then scroll down to **Custom Domains**.
3. Click **Add Custom Domain**, type `app.yourname.com` (use your real domain), and click **Save**.
4. Render will now show a small instruction containing a **CNAME target** — a value that looks like `dopamax.onrender.com`. Leave this tab open; you'll copy that value in the next step.

### Step 3 — Add one line in your domain's DNS
Go to wherever you bought the domain (Cloudflare / Namecheap / etc.) and open its **DNS settings**. Add a **new record**:
- **Type:** `CNAME`
- **Name** (sometimes called *Host*): `app`  ← just the word, **not** the whole address
- **Target** (sometimes called *Value* or *Points to*): the value Render gave you (e.g. `dopamax.onrender.com`)
- **TTL:** leave it on Auto / Automatic

Click **Save**.

> 💡 If you're on **Cloudflare** and you see an **orange cloud** icon next to the record, click it once so it turns **grey** ("DNS only"). This lets Render set up the security padlock (HTTPS) without any hiccups.

### Step 4 — Wait a few minutes
Go back to the Render tab. Within a few minutes (occasionally up to an hour) it will change to **Verified** and automatically set up the HTTPS padlock for you. Then open `https://app.yourname.com` — your app is now live on your own address. 🎉

You can put **this** address on your iPhone home screen (Part 4) instead of the long Render one.

---

## Later: your portfolio on a second subdomain

When you're ready to put your portfolio online, it's the exact same DNS trick with a different word — they never interfere with each other:
- `app.yourname.com` → your Dopamax app (done above)
- `portfolio.yourname.com` → wherever you host the portfolio (Vercel or Netlify are great and free; they'll give you a target to point the CNAME at)
- `yourname.com` (the plain one) → you can point this at your portfolio as your main "front door"

Each one is just one more line in the DNS phone book. We'll walk through the portfolio together when you get there.

---

## A few things worth knowing
- **The app "sleeps" on the free plan.** After ~15 minutes of nobody using it, the first visit takes ~40 seconds to wake up. Your data is never affected. (A few dollars a month on Render removes this, only if you ever want to.)
- **Your data is safe** in Supabase even when you update the app. To make updates later: change files locally, open GitHub Desktop, click **Commit** then **Push** — Render redeploys automatically.
- **Backups:** Supabase → your project → Database → Backups. You can also view all your data anytime in Supabase's **Table Editor**.
