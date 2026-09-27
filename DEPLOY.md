# Running and deploying Instant Solver

## 1. Local, on Windows (through WSL)

The judge sandbox uses Linux process controls, so the engine runs inside WSL
Ubuntu, not in native Windows. The browser on Windows reaches it at localhost.

It runs from a copy in the Ubuntu home folder (`~/instant-solver`), not from
the D: drive: npm and Python cannot set Linux file permissions on `/mnt/d` and
are much slower there. You edit the files on D: and sync them across.

One-time setup, in an **Ubuntu** terminal:

```bash
bash "/mnt/d/C Drive Download/instant-solver/instant-solver/scripts/sync-to-wsl.sh"
cd ~/instant-solver && sudo bash scripts/setup-wsl.sh
```

Then, each time, in two Ubuntu terminals:

```bash
cd ~/instant-solver && make api    # engine on http://localhost:8000
cd ~/instant-solver && make web    # UI on http://localhost:3000
```

Open <http://localhost:3000> in your Windows browser. `make test` runs the engine
test suite. After editing files on D:, run `sync-to-wsl.sh` again. The dev servers
pick up the changes on their own.

Optional: to use the same sandbox as production (nsjail) locally, build it with
the commands in the "nsjail" step of `deploy/setup-vps.sh`. Without nsjail, the
engine uses the basic development sandbox.

## 2. Hostinger

### Which plan

You need a **VPS** plan (KVM 2 or higher is comfortable; KVM 1 works for light
use). Shared, Web and Cloud hosting will not work: they serve PHP sites, and this
app needs a long-running Python server, a C++ compiler and a sandbox for running
submitted code.

### Steps

1. **Create the VPS.** In hPanel, go to **VPS → OS & Panel → Operating System**.
   Choose plain **Ubuntu 24.04**, without a control panel. Set a root password or
   add your SSH key, and note the server's **IP address**.
2. **Point your domain at it.** In hPanel, go to **Domains → your domain → DNS / Nameservers**.
   Set the `A` record for `@` to the VPS IP. If you use `www`, add an `A` record
   for it as well. It can take a few minutes to an hour for the change to take effect.
3. **Package the code** on Windows (PowerShell). This leaves out build output
   and your local `.env`:

   ```powershell
   tar -czf "$env:USERPROFILE\Desktop\instant-solver.tgz" --exclude=node_modules --exclude=.next --exclude=.venv --exclude=__pycache__ --exclude=.env --exclude=screenshots -C "D:\C Drive Download\instant-solver" instant-solver
   ```

4. **Upload it** and log in (replace `SERVER_IP`):

   ```powershell
   scp "$env:USERPROFILE\Desktop\instant-solver.tgz" root@SERVER_IP:/root/
   ssh root@SERVER_IP
   ```

5. **Install**, on the server (replace the domain and email):

   ```bash
   tar -xzf /root/instant-solver.tgz -C /opt
   bash /opt/instant-solver/deploy/setup-vps.sh yourdomain.com you@example.com
   ```

   The script installs everything, builds the site, starts it as two services
   behind nginx, turns on the firewall and gets a free HTTPS certificate from
   Let's Encrypt. Running it means agreeing to Let's Encrypt's terms of service.
   When it finishes, the site is live at `https://yourdomain.com`.

### Optional: solving any problem, not just the built-in examples

Without an API key, the solver only handles its built-in example problems. To
solve any problem, add a key on the server:

```bash
nano /opt/instant-solver/.env          # set ANTHROPIC_API_KEY=...
systemctl restart instant-solver-api
```

Every solve on the public site is then billed to that key. nginx limits each
visitor to 6 solves a minute, and the engine runs at most 2 solves at a time
(`CPSOLVE_MAX_SOLVES` in `.env`). Keep a spending limit on the key as well.

### Updating the site

Package and upload again (steps 3 and 4), then on the server:

```bash
tar -xzf /root/instant-solver.tgz -C /opt
bash /opt/instant-solver/deploy/setup-vps.sh yourdomain.com you@example.com
```

Your `.env` on the server is kept.

### Troubleshooting

```bash
systemctl status instant-solver-api instant-solver-web
journalctl -u instant-solver-api -f      # engine logs
journalctl -u instant-solver-web -f      # web logs
curl http://127.0.0.1:8000/api/health    # "sandbox" should say "nsjail"
```

If Hostinger's own VPS firewall is enabled in hPanel, allow ports 22, 80 and 443.
