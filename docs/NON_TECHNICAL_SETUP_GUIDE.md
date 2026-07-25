# Non-Technical Setup Guide — Run Sentinel From Scratch

> For someone with **no coding background**. Follow these steps top to bottom.
> You'll copy-paste commands; you don't need to understand them. Where a step
> needs a real developer decision, it says so. Total time: ~1–2 hours (mostly
> waiting on downloads/builds).

## What you're setting up

Two things run on your **computer**, and one app runs on your **Android phone**:
- A **"brain"** (the backend) — thinks and stores data.
- A **local AI** (Ollama) — reads and writes the replies, all on your computer.
- The **phone app** — where you see and approve support messages.

The phone talks to your computer over your home Wi-Fi, so **both must be on the
same Wi-Fi**, and your computer must be **on and running** for the app to work.

---

## Part 0 — Install the tools (one time)

Install these (accept the defaults in each installer):

1. **Python** — https://www.python.org/downloads/ (tick "Add Python to PATH"
   during install).
2. **Node.js** (LTS) — https://nodejs.org
3. **Ollama** (the local AI) — https://ollama.com/download
4. **Git** — https://git-scm.com/downloads

After installing, open **PowerShell** (search "PowerShell" in the Start menu).
You'll type commands there.

> 💡 In PowerShell, paste with **right-click** or **Ctrl+V**, then press **Enter**.

---

## Part 1 — Get the project onto your computer

In PowerShell, paste:
```powershell
cd "$HOME\Desktop"
git clone <YOUR-REPO-URL> sentinel
cd sentinel
```
*(Replace `<YOUR-REPO-URL>` with the repository link. If you already have the
folder, just `cd` into it.)*

---

## Part 2 — Turn on the local AI (Ollama)

Paste these one at a time (each downloads a model — a few minutes each):
```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```
Ollama runs automatically in the background after install. That's it for the AI.

---

## Part 3 — Set up the "brain" (backend)

Paste this block (it prepares the backend):
```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

### The secrets file
The backend needs a settings file called `.env` with some keys/passwords in it.
```powershell
copy .env.example backend\.env
notepad backend\.env
```
A text editor opens. You need to fill in a few values. **This is the one part
that needs real accounts** (Google, Discord, Firebase). A developer can create
these, or follow the dedicated guides:
- Google sign-in + Gmail → `docs/GOOGLE_OAUTH_AND_GMAIL_API.md`
- Discord → `docs/DISCORD_INTEGRATION.md`
- Notifications (Firebase) → `docs/PUSH_NOTIFICATIONS_FCM.md`

For the random secret keys (JWT secret, encryption key, API key), you can generate
strong values by pasting this and copying the output into the matching lines:
```powershell
python -c "import secrets;print('JWT:',secrets.token_urlsafe(32))"
python -c "from cryptography.fernet import Fernet;print('FERNET:',Fernet.generate_key().decode())"
```
Save the file (Ctrl+S) and close Notepad.

> If you just want to *see it run* without connecting real Discord/Gmail yet, you
> can leave the provider values blank — the backend will still start; you just
> can't sign in until they're filled.

---

## Part 4 — Get the phone app

The app is **not** on the Play Store — you install a special build file (an
`.apk`). A developer builds it once with a tool called **EAS**; you just need the
**install link** they share (it looks like an `expo.dev/...` page).

1. On your **Android phone**, open the install link the developer gives you.
2. Tap **Install** (allow "install from this source" if Android asks).
3. Open the app once it's installed.

> Rebuilding is only needed when the app's core changes — for everyday use you
> keep the same installed app.

---

## Part 5 — Start everything

Back in PowerShell, from the project folder, paste:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo-start-lan.ps1
```
This starts the brain, the message listeners, and the phone-app server all at
once. When it finishes it prints a box that says **"SENTINEL … IS UP"** with an
address like `http://192.168.0.102:8000`. Leave this window open.

To **stop** everything later:
```powershell
.\scripts\demo-stop.ps1
```

---

## Part 6 — Use it

1. Make sure your **phone is on the same Wi-Fi** as the computer.
2. Open the **Sentinel** app → tap **Connect** and sign in with **Discord** or
   **Google** (this both signs you in and links that channel).
3. Add your business info so the AI answers correctly:
   **Settings → Knowledge Base → Upload document** (a PDF/Word/text file of your
   policies) or **Add website** (paste your business website). Watch the green bar
   fill as it learns.
4. Send a test message:
   - **Discord:** post in the server your bot is in.
   - **Gmail:** email the connected mailbox.
5. If the message is **urgent/critical**, it pops up on the app's **Desk** (and
   your phone buzzes) — tap it, review the AI's suggested reply, and hit
   **Approve & Send**. If it's routine, the AI answers automatically.

---

## Everyday routine (after first-time setup)

1. Turn the computer on, make sure it's on Wi-Fi.
2. Open PowerShell → `cd` to the project → run the start command from Part 5.
3. Use the app on your phone.
4. Run the stop command when done.

---

## If something doesn't work

- **App shows errors / can't connect:** phone and computer on the **same Wi-Fi**?
  Re-run the start command (Part 5) — it fixes the address automatically.
- **Nothing happens on a test message:** make sure the start window still shows
  "IS UP" and the computer is awake.
- **More fixes:** `docs/TROUBLESHOOTING.md` (a developer can help interpret it).

Unfamiliar words? See `docs/GLOSSARY.md` for plain-English definitions.
