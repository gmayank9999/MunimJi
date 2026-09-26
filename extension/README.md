# MunimJi Lens

A Manifest V3 browser extension that shows MunimJi's verdict on a client right inside
Gmail, and a popup to approve/reject parked actions without opening the dashboard.

Plain HTML/JS, no build step - load it unpacked as-is.

## Load it

1. `chrome://extensions` -> enable **Developer mode** (top right) -> **Load unpacked**
   -> select this `extension/` folder.
2. Click the extension's icon -> **Settings** (or right-click the icon -> Options).
3. Set:
   - **Backend URL**: `http://localhost:8000` (wherever `uvicorn app.main:app` is running)
   - **Extension key**: the exact value of `EXTENSION_KEY` in `backend/.env`
4. Save.

## Try it

- **Popup**: click the extension icon any time - lists whatever's sitting in
  `pending_approval` with the real written subject/body, Approve/Reject buttons call
  the same code path the dashboard's Approvals page and the Slack poller use.
- **Gmail badge**: open a Gmail thread with one of the seeded client addresses
  (`mayankguptawp+<name>@gmail.com`) as sender or recipient - a small 🪔 card should
  appear under the subject line with their open invoice, decision, and days overdue.
  Click **Why?** for one more line of detail.

## If the Gmail badge doesn't show up

Content scripts never talk to the backend or block Gmail on failure - a scan that
doesn't find a match, or fails outright, just does nothing silently. To debug: open
Gmail's DevTools console on a thread page and check for `content.js` errors, and
inspect the subject line (`h2.hP` is the primary selector `content.js` looks for -
Gmail's markup does shift over time, so if that class is gone, add whatever it's been
renamed to at the top of `SUBJECT_SELECTORS` in `content.js`).

## Architecture

- `content.js` - runs inside the Gmail page, only reads the DOM and asks the service
  worker for data; never fetches the backend directly and never stores credentials.
- `background.js` - the only place holding the extension key; relays messages from
  the content script and popup to `backend/app/main.py`'s `/api/ext/*` routes.
- `popup.js` / `options.js` - the toolbar popup and settings page, same messaging
  pattern as the content script.
