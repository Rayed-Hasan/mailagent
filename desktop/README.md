# Mail Agent desktop wrapper

The supported demonstrable desktop target for Days 9–11 is **Windows 10/11**.
The wrapper starts the existing FastAPI dashboard on loopback, injects an
ephemeral bearer token, loads the existing frontend, and terminates the backend
when the window exits. The token is not written to disk or browser storage by
the wrapper.

## Development

From the repository root:

```powershell
cd desktop
npm install
npm start
```

Use `MAILAGENT_PYTHON` when Python is not on PATH. `npm run build` creates a
portable Windows executable through electron-builder when the Windows account
has the approved symlink capability required by its `winCodeSign` helper.
If that capability is unavailable, `npm run build:portable` creates a
no-symlink portable archive and stages the backend package and frontend assets
inside the application resources. The packaged app still requires Python and
the installed `requirements.txt` dependencies on the target machine.
macOS/Linux packaging is not claimed yet; the frontend and API remain usable
with the documented Python launch commands.

The desktop process forces `127.0.0.1`, SQLite, and the local queue. Email
synchronization and any configured cloud AI provider still use their external
network destinations.
