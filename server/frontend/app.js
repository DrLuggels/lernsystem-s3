"use strict";

const $ = (id) => document.getElementById(id);
const ART = { aufgabe: "Aufgabe", klausurfrage: "Klausur", lernpunkt: "Lernpunkt" };

/** Baut ein Element. Texte gehen immer über textContent, nie über innerHTML. */
function el(tag, attribute = {}, ...kinder) {
  const knoten = document.createElement(tag);
  for (const [name, wert] of Object.entries(attribute)) {
    if (name === "class") knoten.className = wert;
    else if (name === "text") knoten.textContent = wert;
    else if (name.startsWith("on")) knoten.addEventListener(name.slice(2), wert);
    else if (wert !== false && wert != null) knoten.setAttribute(name, wert === true ? "" : wert);
  }
  knoten.append(...kinder.filter(Boolean));
  return knoten;
}

async function api(methode, pfad, daten) {
  const antwort = await fetch(pfad, {
    method: methode,
    headers: daten ? { "Content-Type": "application/json" } : {},
    body: daten ? JSON.stringify(daten) : undefined,
  });
  if (antwort.status === 401 && pfad !== "/api/login") {
    zeigeAnmeldung();
    throw new Error("Nicht angemeldet");
  }
  const inhalt = await antwort.json().catch(() => ({}));
  if (!antwort.ok) throw new Error(inhalt.detail || `Fehler ${antwort.status}`);
  return inhalt;
}

/* Welche Bereiche aufgeklappt sind, merkt sich der Browser. */
const offen = {
  lesen() {
    try { return new Set(JSON.parse(localStorage.getItem("offen") || "[]")); } catch { return new Set(); }
  },
  setzen(schluessel, istOffen) {
    const menge = this.lesen();
    istOffen ? menge.add(schluessel) : menge.delete(schluessel);
    try { localStorage.setItem("offen", JSON.stringify([...menge])); } catch { /* ohne Speicher geht es auch */ }
  },
};

function aufklappbar(schluessel, klasse, kopf, inhalt) {
  const details = el("details", { class: klasse, open: offen.lesen().has(schluessel) }, kopf, inhalt);
  details.addEventListener("toggle", () => offen.setzen(schluessel, details.open));
  return details;
}

function stand(knoten) {
  return el("span", { class: "stand" },
    el("b", { text: String(knoten.beherrscht) }), ` / ${knoten.gesamt}`);
}

function balken(knoten) {
  const b = el("span", { class: "balken", role: "img",
    "aria-label": `${Math.round(knoten.fortschritt * 100)} Prozent Fortschritt` }, el("i"));
  b.firstChild.style.setProperty("--w", `${Math.round(knoten.fortschritt * 100)}%`);
  return b;
}

function schalter(aktiv, name, beiAenderung) {
  return el("input", {
    type: "checkbox", class: "schalter", checked: aktiv, role: "switch",
    title: aktiv ? "klausurrelevant – klicken zum Deaktivieren" : "deaktiviert – klicken zum Aktivieren",
    "aria-label": `${name} aktiv`,
    onclick: (ereignis) => ereignis.stopPropagation(),
    onchange: (ereignis) => beiAenderung(ereignis.target.checked),
  });
}

async function umschalten(pfad, aktiv) {
  try {
    await api("PATCH", pfad, { aktiv });
  } catch (fehler) {
    $("meldung").textContent = fehler.message;
  }
  await laden();
}

function eintrag(e) {
  const meta = el("span", { class: "eintrag__meta" },
    el("span", { class: `marke marke--${e.art}`, text: ART[e.art] || e.art }),
    el("span", { text: `Level ${e.level}` }),
    e.claude_wert != null && el("span", { text: `Claude ${e.claude_wert} %` }),
    e.user_wert != null && el("span", { text: `Ich ${e.user_wert} %` }),
    e.punkte != null && el("span", { text: `${e.punkte} P.` }),
    e.status === "geaendert" && el("span", { class: "marke marke--geaendert", text: "Quelle geändert" }));
  return el("li", { class: `eintrag${e.aktiv ? "" : " aus"}` },
    el("i", { class: "pips", "data-level": String(e.level), title: `Level ${e.level} von 5` }),
    el("span", { class: "eintrag__titel", text: e.titel, title: e.kurztext || null }),
    schalter(e.aktiv, e.titel, (aktiv) => umschalten(`/api/eintraege/${e.id}`, aktiv)),
    meta);
}

function thema(t) {
  const kopf = el("summary", {},
    el("span", { class: "thema__titel", text: t.titel }),
    stand(t),
    schalter(t.aktiv, t.titel, (aktiv) => umschalten(`/api/themen/${t.id}`, aktiv)),
    balken(t));
  const inhalt = el("div", {},
    ...t.themen.map(thema),
    t.eintraege.length ? el("ul", { class: "eintraege" }, ...t.eintraege.map(eintrag)) : null);
  return aufklappbar(`thema-${t.id}`, `thema${t.aktiv ? "" : " aus"}`, kopf, inhalt);
}

function fach(f, index) {
  const kopf = el("summary", {},
    el("span", { class: "fach__name", text: f.name }), stand(f), balken(f));
  const inhalt = el("div", { class: "fach__inhalt" },
    ...(f.themen.length
      ? f.themen.map(thema)
      : [el("p", { class: "leer", text: "Noch kein Stoff im Quell-Repo." })]));
  const karte = aufklappbar(`fach-${f.id}`, "fach", kopf, inhalt);
  karte.style.setProperty("--i", index);
  return karte;
}

async function laden() {
  const faecher = await api("GET", "/api/uebersicht");
  $("anmeldung").hidden = true;
  $("app").hidden = false;
  $("gesamt-beherrscht").textContent = faecher.reduce((summe, f) => summe + f.beherrscht, 0);
  $("gesamt-anzahl").textContent = faecher.reduce((summe, f) => summe + f.gesamt, 0);
  $("faecher").replaceChildren(...faecher.map(fach));
}

function zeigeAnmeldung() {
  $("app").hidden = true;
  $("anmeldung").hidden = false;
  $("passwort").focus();
}

$("login-form").addEventListener("submit", async (ereignis) => {
  ereignis.preventDefault();
  $("login-fehler").textContent = "";
  try {
    await api("POST", "/api/login", { passwort: $("passwort").value });
    $("passwort").value = "";
    await laden();
  } catch (fehler) {
    $("login-fehler").textContent = fehler.message;
  }
});

$("abmelden").addEventListener("click", async () => {
  await api("POST", "/api/logout");
  zeigeAnmeldung();
});

laden().catch(() => {});
