"""The single page served by the local web interface.

Everything shown in the results comes from the API response at runtime.
Report text is inserted with textContent only, never as HTML, because room
messages are written by strangers.
"""

PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="referrer" content="no-referrer">
<title>Contribution Mapper</title>
<style nonce="__NONCE__">
:root{
  --navy-950:#040d1e; --navy-900:#071730; --navy-800:#0c2346; --navy-700:#143262; --navy-600:#1d4380;
  --silver-50:#f7f8fb; --silver-100:#eef1f6; --silver-200:#dfe4ec; --silver-300:#c5ccd8; --silver-400:#a3adbd; --silver-600:#59647a;
  --ink:#0b1730; --white:#fff; --steel:#8fb2e3;
  --ok-bg:#e6f2ea; --ok-fg:#14502c; --warn-bg:#fff3d9; --warn-fg:#6d4300;
  --bad-bg:#fbe9e9; --bad-fg:#7a1c1c; --neutral-bg:#eceff5; --neutral-fg:#34415a;
  --radius:18px; --shadow:0 1px 0 rgba(255,255,255,.6) inset, 0 18px 40px -18px rgba(2,10,28,.65);
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --sans:"Inter",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;background:var(--navy-950)}
body{margin:0;min-height:100vh;font-family:var(--sans);color:var(--silver-100);line-height:1.55;
  background:radial-gradient(1200px 520px at 78% -8%,rgba(143,178,227,.18),transparent 60%),
             radial-gradient(900px 480px at -10% 8%,rgba(197,204,216,.10),transparent 55%),
             linear-gradient(180deg,var(--navy-900),var(--navy-950) 70%);
  background-repeat:no-repeat}
.skip{position:absolute;left:-999px;top:8px;background:var(--white);color:var(--ink);padding:10px 14px;border-radius:10px;z-index:10}
.skip:focus{left:12px}
:focus-visible{outline:2px solid var(--steel);outline-offset:3px;border-radius:8px}
.wrap{max-width:1120px;margin:0 auto;padding:0 20px}
header.top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 12px;padding:22px 0 8px}
.brand{display:flex;align-items:center;gap:12px;font-weight:650;letter-spacing:.01em;color:var(--white)}
.brand svg{flex:none}
.pill{font-size:.78rem;color:var(--silver-300);border:1px solid rgba(197,204,216,.28);padding:6px 12px;border-radius:999px;background:rgba(255,255,255,.04)}
.hero{padding:34px 0 26px;max-width:720px}
.hero h1{margin:0 0 12px;font-size:clamp(1.9rem,4.6vw,3rem);line-height:1.1;letter-spacing:-.02em;color:var(--white);font-weight:680}
.hero h1 span{background:linear-gradient(90deg,var(--silver-50),var(--silver-400));-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{margin:0;color:var(--silver-300);font-size:1.05rem;max-width:62ch}
.layout{display:grid;gap:22px;grid-template-columns:minmax(0,1fr);padding-bottom:56px;align-items:start}
@media(min-width:960px){.layout{grid-template-columns:400px minmax(0,1fr)} .form{position:sticky;top:20px}}
.card{background:var(--white);color:var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);border:1px solid var(--silver-200)}
.form{padding:24px}
.form h2{margin:0 0 4px;font-size:1.1rem;color:var(--navy-800)}
.form .lead{margin:0 0 18px;color:var(--silver-600);font-size:.92rem}
.field{margin:0 0 16px}
label,.legend{display:block;font-weight:600;font-size:.88rem;color:var(--navy-800);margin:0 0 6px}
.opt{font-weight:500;color:var(--silver-600)}
input[type=text],textarea{width:100%;font:inherit;font-size:16px;color:var(--ink);background:var(--silver-50);border:1px solid var(--silver-300);border-radius:12px;padding:12px 14px;min-height:46px;transition:border-color .15s,box-shadow .15s,background .15s}
input[type=text]:hover,textarea:hover{border-color:var(--silver-400)}
input[type=text]:focus,textarea:focus{outline:none;background:var(--white);border-color:var(--navy-600);box-shadow:0 0 0 4px rgba(29,67,128,.14)}
input[aria-invalid=true],textarea[aria-invalid=true]{border-color:#b13a3a;background:#fff8f8}
textarea{resize:vertical;min-height:110px;font-family:var(--mono);font-size:13px;line-height:1.45}
.hint{margin:6px 0 0;color:var(--silver-600);font-size:.82rem}
.err{margin:6px 0 0;color:var(--bad-fg);font-size:.84rem;font-weight:550}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:6px;background:var(--silver-100);padding:5px;border-radius:14px;border:1px solid var(--silver-200)}
.seg input{position:absolute;opacity:0;pointer-events:none}
.seg label{margin:0;text-align:center;padding:10px 8px;border-radius:10px;cursor:pointer;color:var(--silver-600);font-weight:600;font-size:.88rem;transition:background .15s,color .15s,box-shadow .15s}
.seg input:checked+label{background:var(--white);color:var(--navy-800);box-shadow:0 1px 3px rgba(7,23,48,.18),0 0 0 1px var(--silver-300)}
.seg input:focus-visible+label{outline:2px solid var(--navy-600);outline-offset:2px}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px}
.btn{font:inherit;font-weight:600;font-size:.92rem;border-radius:12px;padding:10px 16px;min-height:44px;cursor:pointer;border:1px solid var(--silver-300);background:var(--white);color:var(--navy-800);transition:background .15s,border-color .15s,transform .05s}
.btn:hover{background:var(--silver-50);border-color:var(--silver-400)}
.btn:active{transform:translateY(1px)}
.btn.primary{width:100%;color:var(--white);border:1px solid #35588f;background:linear-gradient(180deg,#183c73,var(--navy-800));box-shadow:0 10px 22px -12px rgba(12,35,70,.9),0 1px 0 rgba(255,255,255,.18) inset;font-size:1rem;min-height:50px;display:flex;align-items:center;justify-content:center;gap:10px}
.btn.primary:hover{background:linear-gradient(180deg,#1d4686,#0f2b57)}
.btn[disabled]{opacity:.65;cursor:progress}
details.adv{margin:0 0 18px;border-top:1px solid var(--silver-200);padding-top:12px}
details.adv summary{cursor:pointer;font-weight:600;color:var(--navy-700);font-size:.9rem;list-style:none}
details.adv summary::-webkit-details-marker{display:none}
details.adv summary::before{content:"+";display:inline-block;width:18px;color:var(--silver-600)}
details.adv[open] summary::before{content:"−"}
details.adv .field{margin-top:12px}
.privacy{margin:14px 0 0;color:var(--silver-600);font-size:.8rem;text-align:center}
.spin{width:18px;height:18px;border-radius:50%;border:2px solid rgba(255,255,255,.35);border-top-color:#fff;animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
.results{min-width:0}
.empty{border:1px dashed rgba(197,204,216,.38);border-radius:var(--radius);padding:28px;background:rgba(255,255,255,.035)}
.empty h2{margin:0 0 6px;color:var(--white);font-size:1.15rem}
.empty p{margin:0 0 16px;color:var(--silver-300)}
.checks{display:grid;gap:12px;margin:0;padding:0;list-style:none}
.checks li{display:flex;gap:12px;align-items:flex-start;color:var(--silver-300);font-size:.94rem}
.checks b{color:var(--white);display:block;font-weight:600}
.dot{flex:none;width:28px;height:28px;border-radius:9px;border:1px solid rgba(197,204,216,.35);display:grid;place-items:center;color:var(--silver-300);font-size:.8rem;background:rgba(255,255,255,.05)}
.banner{border-radius:14px;padding:14px 16px;margin:0 0 16px;font-weight:550}
.banner.error{background:var(--bad-bg);color:var(--bad-fg);border:1px solid #efc4c4}
.sheet{display:grid;gap:16px;animation:rise .35s ease both}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.head{padding:22px 24px;background:linear-gradient(180deg,var(--navy-800),var(--navy-900));color:var(--white);border-radius:var(--radius);border:1px solid rgba(197,204,216,.22);box-shadow:var(--shadow)}
.head small{color:var(--silver-400);letter-spacing:.08em;text-transform:uppercase;font-size:.72rem;font-weight:600}
.head h2{margin:4px 0 6px;font-size:1.35rem;word-break:break-word}
.head h2 a{color:var(--white);text-decoration:none;border-bottom:1px solid rgba(197,204,216,.5)}
.head h2 a:hover{border-bottom-color:var(--white)}
.head p{margin:0;color:var(--silver-300);font-size:.88rem}
.grid{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.tile{padding:18px 18px 16px}
.tile .k{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--silver-600);font-weight:650}
.tile h3{margin:8px 0 6px;font-size:1rem;line-height:1.35;color:var(--navy-800)}
.tile p{margin:0 0 8px;color:var(--silver-600);font-size:.88rem}
.kv{margin:10px 0 0;display:grid;gap:6px;font-size:.84rem}
.kv div{display:flex;justify-content:space-between;gap:12px;border-top:1px solid var(--silver-100);padding-top:6px}
.kv dt{color:var(--silver-600)}
.kv dd{margin:0;text-align:right;color:var(--ink);font-family:var(--mono);font-size:.8rem;word-break:break-all}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:650;padding:4px 10px;border-radius:999px;border:1px solid transparent}
.chip.ok{background:var(--ok-bg);color:var(--ok-fg);border-color:#bddcc8}
.chip.warn{background:var(--warn-bg);color:var(--warn-fg);border-color:#efd9a6}
.chip.bad{background:var(--bad-bg);color:var(--bad-fg);border-color:#efc4c4}
.chip.neutral{background:var(--neutral-bg);color:var(--neutral-fg);border-color:var(--silver-300)}
.panel{padding:20px 22px}
.panel h3{margin:0 0 10px;font-size:1rem;color:var(--navy-800)}
.panel ul{margin:0;padding-left:20px;color:var(--silver-600);font-size:.9rem;display:grid;gap:6px}
.panel p.note{margin:12px 0 0;color:var(--silver-600);font-size:.86rem}
.rec{border-top:1px solid var(--silver-200);padding:14px 0 0;margin-top:14px}
.rec:first-of-type{border-top:0;padding-top:0;margin-top:0}
.rec .claim{font-weight:600;color:var(--ink);word-break:break-word;margin:6px 0 4px}
.rec .detail{color:var(--silver-600);font-size:.86rem;word-break:break-word}
.rec .meta{display:flex;gap:10px;flex-wrap:wrap;align-items:center;color:var(--silver-600);font-size:.8rem}
table.cov{width:100%;border-collapse:collapse;font-size:.86rem}
table.cov th{text-align:left;color:var(--silver-600);font-weight:550;padding:8px 12px 8px 0;border-top:1px solid var(--silver-100);width:46%;vertical-align:top}
table.cov td{padding:8px 0;border-top:1px solid var(--silver-100);font-family:var(--mono);font-size:.8rem;word-break:break-all}
table.cov tr:first-child th,table.cov tr:first-child td{border-top:0}
details.raw summary{cursor:pointer;font-weight:600;color:var(--navy-700)}
details.raw pre{margin:12px 0 0;max-height:420px;overflow:auto;background:var(--navy-950);color:var(--silver-200);padding:16px;border-radius:12px;font-size:.78rem;line-height:1.5;font-family:var(--mono)}
footer{border-top:1px solid rgba(197,204,216,.16);padding:22px 0 40px;color:var(--silver-400);font-size:.82rem}
.plain{border:0;padding:0;margin:0 0 16px;min-width:0}
.plain legend{padding:0}
.lnk{margin:12px 0 0!important}
.ext{color:var(--navy-600);font-weight:600;font-size:.86rem;text-decoration:none;border-bottom:1px solid var(--silver-300)}
.ext:hover{color:var(--navy-800);border-bottom-color:var(--navy-600)}
.ns{padding:20px;color:#fff}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (prefers-reduced-motion:reduce){.sheet{animation:none}.spin{animation-duration:2s}*{transition:none!important}}
</style>
</head>
<body>
<a class="skip" href="#repo">Skip to the form</a>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f7f8fb"/><stop offset="1" stop-color="#a3adbd"/></linearGradient></defs><rect x="1" y="1" width="32" height="32" rx="9" fill="#0c2346" stroke="url(#g)" stroke-width="1.4"/><path d="M9 22l5-8 4 5 3-4 4 7" fill="none" stroke="url(#g)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="14" cy="14" r="1.8" fill="#f7f8fb"/><circle cx="25" cy="22" r="1.8" fill="#f7f8fb"/></svg>
      <span>Contribution Mapper</span>
    </div>
    <span class="pill">Runs on your machine · public data only</span>
  </header>

  <section class="hero">
    <h1>Map your work.<br><span>Without overclaiming.</span></h1>
    <p>Line up a public GitHub commit with public Technocore messages and a signed proof, then see exactly what was found and what remains unproven.</p>
  </section>

  <main class="layout">
    <form id="form" class="card form" novalidate autocomplete="off">
      <h2>Run a check</h2>
      <p class="lead">Only the repository is required.</p>

      <div class="field">
        <label for="repo">GitHub repository</label>
        <input id="repo" type="text" inputmode="url" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="owner/repository" aria-describedby="repo-hint repo-err" required>
        <p class="hint" id="repo-hint">You can also paste a github.com link.</p>
        <p class="err" id="repo-err" role="alert" hidden></p>
      </div>

      <div class="field">
        <label for="commit">Commit <span class="opt">(optional)</span></label>
        <input id="commit" type="text" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Full 40-character hash" aria-describedby="commit-hint commit-err">
        <p class="hint" id="commit-hint">Checked on GitHub and searched for in room messages.</p>
        <p class="err" id="commit-err" role="alert" hidden></p>
      </div>

      <div class="field">
        <label for="room">Technocore room</label>
        <input id="room" type="text" autocapitalize="off" autocorrect="off" spellcheck="false" value="technocore" aria-describedby="room-err">
        <p class="err" id="room-err" role="alert" hidden></p>
      </div>

      <fieldset class="field plain">
        <legend class="legend">Search scope</legend>
        <div class="seg" role="radiogroup">
          <input type="radio" name="source" id="src-export" value="export" checked><label for="src-export">Retained window</label>
          <input type="radio" name="source" id="src-recent" value="recent"><label for="src-recent">Latest batch</label>
        </div>
        <p class="hint">The room keeps only recent messages. The retained window is the widest view available; the latest batch is about 50 messages.</p>
      </fieldset>

      <div class="field">
        <label for="proof">Signed proof <span class="opt">(optional)</span></label>
        <textarea id="proof" spellcheck="false" placeholder="Paste the public proof JSON" aria-describedby="proof-err"></textarea>
        <div class="row">
          <button type="button" class="btn" id="load-proof">Load a file…</button>
          <input type="file" id="proof-file" accept=".json,application/json" hidden>
          <button type="button" class="btn" id="clear-proof" hidden>Clear</button>
        </div>
        <p class="err" id="proof-err" role="alert" hidden></p>
      </div>

      <details class="adv">
        <summary>Advanced</summary>
        <div class="field">
          <label for="artifact">Artifact URL <span class="opt">(optional)</span></label>
          <input id="artifact" type="text" inputmode="url" autocapitalize="off" spellcheck="false" placeholder="Defaults to the repository link" aria-describedby="artifact-err">
          <p class="err" id="artifact-err" role="alert" hidden></p>
        </div>
      </details>

      <button class="btn primary" id="run" type="submit"><span id="run-label">Run mapper</span></button>
      <p class="privacy">Never paste a private key. Only public proof files are ever needed.</p>
    </form>

    <section id="results" class="results" aria-live="polite" aria-busy="false" tabindex="-1">
      <div class="empty" id="empty">
        <h2>Your report will appear here</h2>
        <p>Each run reads live public sources and reports four things separately.</p>
        <ul class="checks">
          <li><span class="dot">1</span><span><b>Commit on GitHub</b>Whether GitHub serves the commit under the repository.</span></li>
          <li><span class="dot">2</span><span><b>Signed proof</b>Whether a supplied proof’s signature is valid for its stated DID.</span></li>
          <li><span class="dot">3</span><span><b>Message matches</b>Exact repository or commit references in room messages, always unverified.</span></li>
          <li><span class="dot">4</span><span><b>Search coverage</b>Exactly which messages were searched, so “no match” is never overstated.</span></li>
        </ul>
      </div>
    </section>
  </main>

  <footer>Everything here runs locally and calls only public GitHub and Technocore endpoints. A text match is a clue, not proof of authorship.</footer>
</div>
<noscript><p class="ns">This interface needs JavaScript. The command-line tool works without it.</p></noscript>

<script nonce="__NONCE__">
"use strict";
const TOKEN = "__TOKEN__";
const $ = (id) => document.getElementById(id);
const MAX_PROOF = 64 * 1024;

function el(tag, props, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const kid of kids) if (kid != null) node.append(kid);
  return node;
}

/* ---------- input parsing and validation ---------- */
function parseRepo(raw) {
  let s = raw.trim();
  if (!s) return { error: "Enter a repository such as owner/repository." };
  s = s.replace(/^git@github\.com:/i, "");
  const m = s.match(/^(?:https?:\/\/)?(?:www\.)?github\.com\/(.+)$/i);
  if (m) s = m[1];
  else if (/^[a-z][a-z0-9+.-]*:\/\//i.test(s) || /^[^/]+\.[a-z]{2,}\//i.test(s)) {
    return { error: "Only github.com repositories are supported." };
  }
  const parts = s.split("/");
  const owner = (parts[0] || "").trim();
  const repo = (parts[1] || "").replace(/\.git$/i, "").split(/[?#]/)[0].trim();
  const ok = /^[A-Za-z0-9_.-]{1,100}$/;
  if (!owner || !repo) return { error: "Use the form owner/repository." };
  if (!ok.test(owner) || !ok.test(repo) || owner === "." || owner === ".." || repo === "." || repo === "..") {
    return { error: "That owner or repository name has characters GitHub doesn’t allow." };
  }
  return { owner, repo };
}

function showError(id, input, message) {
  const p = $(id);
  p.hidden = !message;
  p.textContent = message || "";
  if (input) { if (message) input.setAttribute("aria-invalid", "true"); else input.removeAttribute("aria-invalid"); }
}

function validate() {
  let firstBad = null;
  const bad = (id, input, msg) => { showError(id, input, msg); if (msg && !firstBad) firstBad = input; return !msg; };

  const repoRes = parseRepo($("repo").value);
  bad("repo-err", $("repo"), repoRes.error || "");

  const commit = $("commit").value.trim();
  bad("commit-err", $("commit"), commit && !/^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$/.test(commit)
    ? "Use the full 40-character commit hash (a short hash can’t be checked reliably)." : "");

  const room = $("room").value.trim() || "technocore";
  bad("room-err", $("room"), !/^[a-z0-9][a-z0-9_-]{0,47}$/.test(room)
    ? "Room names use lowercase letters, numbers, hyphens and underscores." : "");

  const proof = $("proof").value.trim();
  let proofMsg = "";
  if (proof) {
    if (/PRIVATE KEY/i.test(proof)) proofMsg = "That looks like a private key. Never paste secrets; only the public proof file is needed.";
    else if (proof.length > MAX_PROOF) proofMsg = "That proof is too large.";
    else { try { const o = JSON.parse(proof); if (o === null || typeof o !== "object" || Array.isArray(o)) proofMsg = "A proof is a JSON object."; } catch { proofMsg = "That isn’t valid JSON."; } }
  }
  bad("proof-err", $("proof"), proofMsg);

  const artifact = $("artifact").value.trim();
  bad("artifact-err", $("artifact"), artifact && !/^https:\/\//i.test(artifact) ? "The artifact URL must start with https://." : "");
  if (artifact && $("artifact-err").hidden === false) $("artifact").closest("details").open = true;

  if (firstBad) { firstBad.focus(); return null; }
  return {
    owner: repoRes.owner, repository: repoRes.repo, room,
    source: document.querySelector("input[name=source]:checked").value,
    commit: commit || null, artifact_url: artifact || null, proof: proof || null,
  };
}

/* ---------- rendering (textContent only) ---------- */
const CHIP_ICON = { ok: "✓", warn: "!", bad: "✕", neutral: "–" };
function chip(kind, label) { return el("span", { class: "chip " + kind }, el("span", { "aria-hidden": "true", text: CHIP_ICON[kind] }), el("span", { text: label })); }
const short = (s, n) => (typeof s === "string" && s.length > n ? s.slice(0, n - 8) + "…" + s.slice(-6) : s);
const yesno = (v) => (v === true ? "Yes" : v === false ? "No" : "—");

function kvList(rows) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of rows) if (v !== undefined && v !== null && v !== "") dl.append(el("div", {}, el("dt", { text: k }), el("dd", { text: String(v) })));
  return dl;
}
function tile(label, kind, chipLabel, headline, body, rows) {
  const t = el("section", { class: "card tile" }, el("div", { class: "k", text: label }), el("h3", { text: headline }));
  t.insertBefore(chip(kind, chipLabel), t.children[1]);
  for (const line of body) if (line) t.append(el("p", { text: line }));
  if (rows && rows.length) t.append(kvList(rows));
  return t;
}

function commitTile(c) {
  c = c || {};
  switch (c.status) {
    case "found": {
      const t = tile("Commit on GitHub", "ok", "Found", "GitHub serves this commit under the repository.", ["This doesn’t show who wrote it or which branch holds it."], [["Commit", short(c.commit, 20)]]);
      if (typeof c.url === "string" && /^https:\/\/github\.com\//.test(c.url)) t.append(el("p", { class: "lnk" }, el("a", { class: "ext", href: c.url, target: "_blank", rel: "noopener noreferrer", text: "View commit on GitHub ↗" })));
      return t;
    }
    case "not_found": return tile("Commit on GitHub", "bad", "Not found", "GitHub doesn’t serve this commit here.", [c.reason], [["Commit", short(c.commit, 20)]]);
    case "unavailable": return tile("Commit on GitHub", "warn", "Couldn’t check", "The check didn’t run.", [c.reason, "This says nothing about the commit itself."], []);
    case "skipped": return tile("Commit on GitHub", "neutral", "Skipped", "Not a full commit hash.", [c.reason], []);
    default: return tile("Commit on GitHub", "neutral", "Not requested", "No commit was given.", ["Add a full commit hash to check it on GitHub."], []);
  }
}

function proofTile(p) {
  p = p || {};
  const rows = [["DID", short(p.did, 26)], ["Commit", short(p.commit, 20)], ["Matches your repository", p.artifact_url_matches_request === null || p.artifact_url_matches_request === undefined ? "" : yesno(p.artifact_url_matches_request)], ["Matches your commit", p.commit_matches_request === null || p.commit_matches_request === undefined ? "" : yesno(p.commit_matches_request)]];
  switch (p.status) {
    case "valid": {
      const off = p.artifact_url_matches_request === false || p.commit_matches_request === false;
      return tile("Signed proof", off ? "warn" : "ok", off ? "Valid, different target" : "Valid",
        off ? "Valid, but about something else." : "The signature matches the stated DID.",
        [off ? "This proof covers a different repository or commit than the one you entered." : p.proves], rows);
    }
    case "invalid": return tile("Signed proof", "bad", "Invalid", "The signature doesn’t match.", [p.reason], rows.slice(0, 2));
    case "malformed": return tile("Signed proof", "bad", "Malformed", "Not a usable proof file.", [p.reason], []);
    case "unavailable": return tile("Signed proof", "warn", "Couldn’t check", "Signature checking isn’t available.", [p.reason], []);
    default: return tile("Signed proof", "neutral", "Not supplied", "No proof was given.", ["Paste or load a public proof file to verify it."], []);
  }
}

function matchesTile(ev, cov) {
  const n = ev && ev.record_count ? ev.record_count : 0;
  const searched = cov && cov.messages_examined != null ? cov.messages_examined.toLocaleString() : "the";
  return n
    ? tile("Message matches", "warn", n + " unverified", n === 1 ? "One message references this work." : n + " messages reference this work.", ["A match is a clue, not proof of who wrote it or who sent it."], [["Messages searched", searched]])
    : tile("Message matches", "neutral", "None found", "No match in the messages searched.", ["That doesn’t show nothing was ever posted; older messages may be gone."], [["Messages searched", searched]]);
}

function coverageTile(cov) {
  cov = cov || {};
  const full = cov.retained_window_fully_examined === true;
  const range = cov.first_seq_examined != null ? cov.first_seq_examined + " – " + cov.last_seq_examined : "";
  return tile("Search coverage", full ? "neutral" : "warn", full ? "Retained window" : "Partial", (cov.messages_examined != null ? cov.messages_examined.toLocaleString() : "0") + " messages searched.",
    [cov.scope, "Full history was not searched."], [["Sequence", range]]);
}

function limitsPanel(report) {
  const items = [];
  for (const src of [report.commit_check, report.proof_verification]) {
    if (src && Array.isArray(src.does_not_prove) && (src.status === "found" || src.status === "valid")) {
      for (const t of src.does_not_prove) if (!items.includes(t)) items.push(t);
    }
  }
  const panel = el("section", { class: "card panel" }, el("h3", { text: "What this does not prove" }));
  if (items.length) { const ul = el("ul"); for (const t of items) ul.append(el("li", { text: t })); panel.append(ul); }
  const note = report.interpretation && report.interpretation.note;
  panel.append(el("p", { class: "note", text: note || "A text match is a clue, not proof of authorship." }));
  return panel;
}

function evidencePanel(ev) {
  const panel = el("section", { class: "card panel" }, el("h3", { text: "Matching messages" }));
  const records = (ev && ev.records) || [];
  if (!records.length) { panel.append(el("p", { class: "note", text: "No message in the searched range mentions this repository or commit." })); return panel; }
  for (const r of records) {
    panel.append(el("div", { class: "rec" },
      el("div", { class: "meta" }, chip("warn", String(r.status || "unverified")), el("span", { text: String(r.source_type || "") })),
      el("div", { class: "claim", text: String(r.claim || "") }),
      el("div", { class: "detail", text: String(r.details || "") })));
  }
  return panel;
}

function coveragePanel(cov) {
  const panel = el("section", { class: "card panel" }, el("h3", { text: "Coverage details" }));
  const rows = [["Method", cov.method], ["Messages examined", cov.messages_examined], ["First sequence", cov.first_seq_examined], ["Last sequence", cov.last_seq_examined],
    ["Earliest message", cov.earliest_ts_examined], ["Latest message", cov.latest_ts_examined], ["Truncated", yesno(cov.truncated)],
    ["Unreadable records skipped", cov.malformed_records_skipped], ["Whole retained window searched", yesno(cov.retained_window_fully_examined)], ["Complete history searched", yesno(cov.complete_history_searched)]];
  const table = el("table", { class: "cov" });
  for (const [k, v] of rows) if (v !== undefined && v !== null) table.append(el("tr", {}, el("th", { scope: "row", text: k }), el("td", { text: String(v) })));
  panel.append(table);
  if (cov.note) panel.append(el("p", { class: "note", text: cov.note }));
  return panel;
}

function rawPanel(report, input) {
  const json = JSON.stringify(report, null, 2);
  const status = el("span", { class: "hint", role: "status" });
  const copy = el("button", { class: "btn", type: "button", text: "Copy JSON" });
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(json); status.textContent = "Copied."; }
    catch { const ta = el("textarea"); ta.value = json; document.body.append(ta); ta.select(); try { document.execCommand("copy"); status.textContent = "Copied."; } catch { status.textContent = "Select the text and copy it manually."; } ta.remove(); }
  });
  const save = el("button", { class: "btn", type: "button", text: "Download JSON" });
  save.addEventListener("click", () => {
    const name = ("contribution-report-" + input.owner + "-" + input.repository).replace(/[^A-Za-z0-9_.-]/g, "_") + ".json";
    const url = URL.createObjectURL(new Blob([json + "\n"], { type: "application/json" }));
    const a = el("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  return el("section", { class: "card panel" },
    el("details", { class: "raw" }, el("summary", { text: "Full report (JSON)" }), el("div", { class: "row" }, copy, save, status), el("pre", { text: json })));
}

function renderReport(report, input, seconds) {
  const repo = report.repository || {};
  const title = el("h2");
  if (typeof repo.html_url === "string" && /^https:\/\/github\.com\//.test(repo.html_url)) title.append(el("a", { href: repo.html_url, target: "_blank", rel: "noopener noreferrer", text: repo.full_name || (input.owner + "/" + input.repository) }));
  else title.textContent = repo.full_name || (input.owner + "/" + input.repository);
  const bits = ["Report v" + report.report_version, report.generated_at ? "generated " + report.generated_at : "", "ran in " + seconds.toFixed(1) + " s"].filter(Boolean).join(" · ");
  const sheet = el("div", { class: "sheet" },
    el("div", { class: "head" }, el("small", { text: "Evidence report" }), title, el("p", { text: bits })),
    el("div", { class: "grid" }, commitTile(report.commit_check), proofTile(report.proof_verification), matchesTile(report.evidence, report.retrieval_coverage), coverageTile(report.retrieval_coverage)),
    limitsPanel(report), evidencePanel(report.evidence), coveragePanel(report.retrieval_coverage || {}), rawPanel(report, input));
  return sheet;
}

function setResults(node) {
  const box = $("results");
  box.replaceChildren(node);
  box.focus({ preventScroll: true });
  if (window.matchMedia("(max-width: 959px)").matches) box.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- running ---------- */
let running = false;
async function run(input) {
  const btn = $("run"), label = $("run-label"), box = $("results");
  running = true; btn.disabled = true; box.setAttribute("aria-busy", "true");
  label.textContent = "Running… this can take up to a minute";
  btn.insertBefore(el("span", { class: "spin", id: "spin", "aria-hidden": "true" }), label);
  const started = performance.now();
  const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 150000);
  try {
    const res = await fetch("/api/run", { method: "POST", signal: ctl.signal, headers: { "Content-Type": "application/json", "X-Mapper-Token": TOKEN }, body: JSON.stringify(input) });
    let data = null;
    try { data = await res.json(); } catch { /* handled below */ }
    if (!res.ok) throw new Error((data && data.error) || ("The request failed (" + res.status + ")."));
    setResults(renderReport(data, input, (performance.now() - started) / 1000));
  } catch (err) {
    const msg = err && err.name === "AbortError" ? "That took too long and was stopped. Try the latest batch, or run again." : (err && err.message) || "Something went wrong.";
    setResults(el("div", { class: "banner error", role: "alert", text: msg }));
  } finally {
    clearTimeout(timer); running = false; btn.disabled = false; box.setAttribute("aria-busy", "false");
    label.textContent = "Run mapper"; const sp = $("spin"); if (sp) sp.remove();
  }
}

$("form").addEventListener("submit", (e) => { e.preventDefault(); if (running) return; const input = validate(); if (input) run(input); });

/* proof file loader */
$("load-proof").addEventListener("click", () => $("proof-file").click());
$("proof-file").addEventListener("change", async (e) => {
  const f = e.target.files && e.target.files[0]; e.target.value = ""; if (!f) return;
  if (f.size > MAX_PROOF) { showError("proof-err", $("proof"), "That file is too large to be a proof."); return; }
  $("proof").value = await f.text(); showError("proof-err", $("proof"), ""); $("clear-proof").hidden = false;
});
$("proof").addEventListener("input", () => { $("clear-proof").hidden = !$("proof").value; showError("proof-err", $("proof"), ""); });
$("clear-proof").addEventListener("click", () => { $("proof").value = ""; $("clear-proof").hidden = true; showError("proof-err", $("proof"), ""); $("proof").focus(); });
for (const id of ["repo", "commit", "room", "artifact"]) $(id).addEventListener("input", () => showError(id + "-err", $(id), ""));
</script>
</body>
</html>
"""


def render_page(token: str, nonce: str) -> str:
    """Return the page with the per-launch token and CSP nonce filled in."""
    return PAGE_TEMPLATE.replace("__NONCE__", nonce).replace("__TOKEN__", token)
