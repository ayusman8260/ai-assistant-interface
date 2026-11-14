"use strict";
const $ = s => document.querySelector(s);
const esc = s => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } }
};
let chats = store.get("ai_chats", []);
let activeId = store.get("ai_active", null);
let busy = false;
const active = () => chats.find(c => c.id === activeId);
const save = () => { store.set("ai_chats", chats); store.set("ai_active", activeId); };

/* ---- tiny safe Markdown: escape first, then format ---- */
function inline(t) {
  return esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}
function markdown(src) {
  const parts = src.split(/```/);
  return parts.map((part, i) => {
    if (i % 2) {                                   // fenced code block
      const nl = part.indexOf("\n");
      const lang = part.slice(0, nl).trim(), code = part.slice(nl + 1).replace(/\n$/, "");
      return `<pre data-lang="${esc(lang)}"><button class="copy" type="button">Copy</button><code>${esc(code)}</code></pre>`;
    }
    return part.split(/\n{2,}/).map(block => {
      const lines = block.split("\n").filter(l => l.trim());
      if (!lines.length) return "";
      if (lines.every(l => /^\s*[-*]\s+/.test(l))) return "<ul>" + lines.map(l => `<li>${inline(l.replace(/^\s*[-*]\s+/, ""))}</li>`).join("") + "</ul>";
      if (lines.every(l => /^\s*\d+\.\s+/.test(l))) return "<ol>" + lines.map(l => `<li>${inline(l.replace(/^\s*\d+\.\s+/, ""))}</li>`).join("") + "</ol>";
      return "<p>" + lines.map(inline).join("<br>") + "</p>";
    }).join("");
  }).join("");
}

/* ---- rendering ---- */
function renderSide() {
  $("#chats").innerHTML = chats.map(c =>
    `<li><button data-id="${c.id}" aria-current="${c.id === activeId}">${esc(c.title)}</button></li>`).join("");
}
function bubble(m, i, isLast) {
  if (m.role === "user") return `<div class="msg user"><div class="bubble">${esc(m.content)}</div></div>`;
  const cls = m.error ? "msg bot error" : "msg bot";
  const tools = isLast && !m.error ? `<div class="tools"><button data-regen type="button">Regenerate</button></div>` : "";
  return `<div class="${cls}"><div class="bubble">${m.error ? esc(m.content) : markdown(m.content)}</div>${tools}</div>`;
}
function render() {
  const c = active();
  $("#title").textContent = c ? c.title : "New chat";
  $("#log").innerHTML = !c || !c.messages.length
    ? `<div class="empty"><p><strong>How can I help?</strong></p><p>Ask a question, try <code>2^10 + 5</code>, or type <code>help</code>.</p></div>`
    : c.messages.map((m, i) => bubble(m, i, i === c.messages.length - 1)).join("");
  $("#log").scrollTop = $("#log").scrollHeight;
  renderSide();
}
function newChat() {
  const c = { id: "c" + Date.now() + Math.random().toString(36).slice(2, 5), title: "New chat", messages: [] };
  chats.unshift(c); activeId = c.id; save(); render(); $("#input").focus();
}

/* ---- talking to the server ---- */
async function ask(c) {
  const history = c.messages.filter(m => !m.error).map(({ role, content }) => ({ role, content }));
  const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: history }) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Something went wrong. Please try again.");
  return data.reply;
}
async function respond(c) {
  busy = true; $("#send").disabled = true;
  $("#log").insertAdjacentHTML("beforeend", `<div class="msg bot" id="typing"><div class="bubble"><span class="dots"><span></span><span></span><span></span></span></div></div>`);
  $("#log").scrollTop = $("#log").scrollHeight;
  try { c.messages.push({ role: "assistant", content: await ask(c) }); }
  catch (e) { c.messages.push({ role: "assistant", content: e.message, error: true }); }
  busy = false; $("#send").disabled = false; save(); render(); $("#input").focus();
}
async function send() {
  const text = $("#input").value.trim();
  if (!text || busy) return;
  if (!active()) newChat();
  const c = active();
  c.messages.push({ role: "user", content: text });
  if (c.title === "New chat") c.title = text.length > 34 ? text.slice(0, 34) + "…" : text;
  $("#input").value = ""; $("#input").style.height = "auto";
  save(); render(); await respond(c);
}

/* ---- events ---- */
$("#form").onsubmit = e => { e.preventDefault(); send(); };
$("#input").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
$("#input").addEventListener("input", e => { e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px"; });
$("#new").onclick = () => { newChat(); $("#side").classList.remove("open"); };
$("#menu").onclick = () => $("#side").classList.toggle("open");
$("#chats").onclick = e => {
  const b = e.target.closest("[data-id]"); if (!b) return;
  activeId = b.dataset.id; save(); render(); $("#side").classList.remove("open");
};
$("#delete").onclick = () => {
  const c = active(); if (!c || !confirm(`Delete "${c.title}"?`)) return;
  chats = chats.filter(x => x.id !== c.id); activeId = chats[0]?.id ?? null; save(); render();
};
$("#export").onclick = () => {
  const c = active(); if (!c || !c.messages.length) return;
  const md = `# ${c.title}\n\n` + c.messages.map(m => `**${m.role === "user" ? "You" : "Assistant"}:**\n\n${m.content}`).join("\n\n---\n\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
  a.download = c.title.replace(/[^\w-]+/g, "_") + ".md"; a.click();
};
$("#log").onclick = async e => {
  if (e.target.matches(".copy")) {
    try { await navigator.clipboard.writeText(e.target.nextElementSibling.textContent); e.target.textContent = "Copied"; }
    catch { e.target.textContent = "Copy failed"; }
    setTimeout(() => (e.target.textContent = "Copy"), 1500);
  }
  if (e.target.matches("[data-regen]") && !busy) {
    const c = active(); c.messages.pop(); render(); await respond(c);
  }
};
fetch("/api/status").then(r => r.json()).then(s => {
  $("#mode").textContent = s.mode === "api" ? "Connected to the AI API." : "Offline mode: built-in assistant. Add an API key for full answers.";
}).catch(() => {});
render();
