/* Live analysis progress, shared by the quick-analyze overlay and the map page.
 *
 * Renders a status payload from analysis_status.status_payload():
 *   {state, step, steps:[{key,label}], label, next, elapsed_s, timeout_s,
 *    error:{title, where, message, fix, detail}}
 * into a step checklist + "Now / Next" line + elapsed timer + error panel.
 * All text goes through textContent (error details come from the CLI).
 */
(function () {
  const SLOW_AFTER_S = 120;

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function fmt(s) {
    if (s == null) return "";
    const m = Math.floor(s / 60), r = s % 60;
    return m ? `${m} min ${String(r).padStart(2, "0")} s` : `${r} s`;
  }

  function renderSteps(root, p) {
    const keys = p.steps.map(s => s.key);
    let idx = keys.indexOf(p.step);
    if (idx < 0) idx = 0;
    const ul = el("ul", "steps");
    p.steps.forEach((s, i) => {
      const li = el("li");
      li.dataset.step = s.key;
      li.appendChild(el("span", "dot"));
      li.appendChild(document.createTextNode(" " + s.label));
      if (p.state === "done" || i < idx) li.classList.add("done");
      else if (i === idx && p.state === "running") li.classList.add("active");
      else if (i === idx && p.state === "error") li.classList.add("failed");
      ul.appendChild(li);
    });
    root.appendChild(ul);
  }

  function renderError(root, e) {
    const box = el("div", "err-panel");
    box.setAttribute("role", "alert");
    box.appendChild(el("div", "err-title", e.title || "Analysis failed"));
    if (e.where) {
      const w = el("div", "err-where");
      w.appendChild(el("strong", null, "Where: "));
      w.appendChild(document.createTextNode(e.where));
      box.appendChild(w);
    }
    if (e.message) box.appendChild(el("p", "err-msg", e.message));
    if (e.fix) {
      const f = el("div", "err-fix");
      f.appendChild(el("strong", null, "What to do: "));
      f.appendChild(document.createTextNode(e.fix));
      box.appendChild(f);
    }
    if (e.detail) {
      const d = el("details", "err-detail");
      d.appendChild(el("summary", null, "Technical details"));
      d.appendChild(el("pre", null, e.detail));
      box.appendChild(d);
    }
    root.appendChild(box);
  }

  // Re-render `root` from payload `p`; keeps a 1 s elapsed ticker while running.
  function render(root, p) {
    clearInterval(root._tick);
    root.replaceChildren();
    renderSteps(root, p);

    if (p.state === "running") {
      const now = el("div", "prog-now");
      now.appendChild(el("strong", null, "Now: "));
      now.appendChild(document.createTextNode(p.label || "Working…"));
      const clock = el("span", "prog-clock");
      now.appendChild(clock);
      root.appendChild(now);
      if (p.next) {
        const nx = el("div", "prog-next");
        nx.appendChild(el("strong", null, "Next: "));
        nx.appendChild(document.createTextNode(p.next));
        root.appendChild(nx);
      }
      const slow = el("div", "prog-slow");
      slow.style.display = "none";
      root.appendChild(slow);

      const base = p.elapsed_s || 0, t0 = Date.now();
      const tick = () => {
        const s = base + Math.floor((Date.now() - t0) / 1000);
        clock.textContent = " · " + fmt(s) + " elapsed";
        if (s >= SLOW_AFTER_S) {
          slow.style.display = "block";
          slow.textContent = "Still working — detailed maps can take a few minutes." +
            (p.timeout_s ? ` If the AI doesn't answer, this step stops automatically after ${Math.round(p.timeout_s / 60)} min and tells you what to do.` : "");
        }
      };
      tick();
      root._tick = setInterval(tick, 1000);
    } else if (p.state === "error") {
      renderError(root, p.error || {});
    } else if (p.state === "done" && p.elapsed_s != null) {
      root.appendChild(el("div", "prog-next", "Finished in " + fmt(p.elapsed_s) + "."));
    }
  }

  // Poll `url` every 2 s, re-rendering into `root`, until done or error.
  function poll(url, root, { onDone, onError, interval = 2000 } = {}) {
    let misses = 0;
    async function once() {
      let p;
      try {
        const r = await fetch(url, { headers: { Accept: "application/json" } });
        if (r.status === 401 || !(r.headers.get("content-type") || "").includes("json")) {
          p = connectionError("Your sign-in has expired", "Sign in again, then reopen this page.");
        } else {
          p = await r.json();
          if (!r.ok) p = connectionError(p.error || `The app answered ${r.status}`,
                                         "Refresh the page. If it keeps happening, check the terminal running the app.");
        }
      } catch (err) {
        if (++misses < 3) return setTimeout(once, interval);  // brief blips are fine
        p = connectionError("Lost connection to the app",
                            "The analysis may still be running. Check the app is still running in its terminal, then refresh this page.");
      }
      misses = 0;
      if (p.steps) render(root, p);
      if (p.state === "done") return onDone && onDone(p);
      if (p.state === "error") {
        if (!p.steps) {  // connection problem: keep the last checklist, add the panel
          clearInterval(root._tick);
          root.querySelectorAll(".err-panel").forEach(n => n.remove());
          renderError(root, p.error);
        }
        return onError && onError(p);
      }
      setTimeout(once, interval);
    }
    once();
  }

  function connectionError(title, fix) {
    return { state: "error", error: { title, where: "Checking progress", fix } };
  }

  window.AnalysisProgress = { render, poll, renderError };
})();
