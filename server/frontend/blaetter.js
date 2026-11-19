"use strict";

/* Blatt-Liste, Blatt-Ansicht (bearbeiten) und Korrektur-Ansicht. */

const STATUS_TEXT = { offen: "offen", abgegeben: "wartet auf Korrektur", korrigiert: "korrigiert" };
const FORMAT_TEXT = { text: "Text", tabelle: "Tabelle", code: "Code", pdf: "Handschriftlich (PDF)" };

function datum(wert) {
  if (!wert) return "";
  const d = new Date(wert.replace(" ", "T") + "Z");
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

async function zeigeBlaetter() {
  const blaetter = await api("GET", "/api/blaetter");
  const liste = $("blatt-liste");
  if (!blaetter.length) {
    liste.replaceChildren(el("p", { class: "leer",
      text: "Noch keine Blätter. Ein Blatt entsteht lokal mit dem Befehl „lernen“." }));
    return;
  }
  liste.replaceChildren(...blaetter.map((b, index) => {
    const punkte = b.status === "korrigiert"
      ? `${b.erreichte_punkte ?? 0} / ${b.punkte} P.`
      : `${b.aufgaben} Aufgaben · ${b.punkte} P.`;
    const zeile = el("a", { class: `blattzeile blattzeile--${b.status}`, href: `#/blatt/${b.id}` },
      el("span", { class: "blattzeile__titel", text: b.titel }),
      el("span", { class: `marke marke--status-${b.status}`, text: STATUS_TEXT[b.status] }),
      el("span", { class: "eintrag__meta" },
        el("span", { text: b.fach || "" }),
        el("span", { text: datum(b.erstellt_am) }),
        el("span", { text: punkte }),
        b.pdf_aufgaben ? el("span", { text: "mit PDF-Teil" }) : null));
    zeile.style.setProperty("--i", index);
    return zeile;
  }));
}

/* ---------- Eingabefelder je Format ---------- */

function tabellenWert(aufgabe) {
  const spalten = aufgabe.vorgabe?.spalten || ["Antwort"];
  const koepfe = aufgabe.vorgabe?.zeilenkoepfe || [];
  const anzahl = koepfe.length || aufgabe.vorgabe?.zeilen || 4;
  let zellen = [];
  try { zellen = JSON.parse(aufgabe.antwort || "[]"); } catch { zellen = []; }
  return { spalten, koepfe, anzahl, zellen: Array.isArray(zellen) ? zellen : [] };
}

function tabellenEingabe(aufgabe, gesperrt, beiAenderung) {
  const { spalten, koepfe, anzahl, zellen } = tabellenWert(aufgabe);
  const rumpf = el("tbody");
  const lesen = () => [...rumpf.rows].map((zeile) =>
    [...zeile.querySelectorAll("input")].map((feld) => feld.value));
  for (let z = 0; z < anzahl; z++) {
    rumpf.append(el("tr", {},
      koepfe.length ? el("th", { scope: "row", text: koepfe[z] }) : null,
      ...spalten.map((spalte, s) => el("input", {
        type: "text", value: zellen[z]?.[s] ?? "", disabled: gesperrt,
        "aria-label": `${koepfe[z] || `Zeile ${z + 1}`}, ${spalte}`,
        oninput: () => beiAenderung(JSON.stringify(lesen())),
      })).map((feld) => el("td", {}, feld))));
  }
  return el("div", { class: "md-tabelle" }, el("table", { class: "eingabetabelle" },
    el("thead", {}, el("tr", {},
      koepfe.length ? el("th") : null, ...spalten.map((s) => el("th", { scope: "col", text: s })))),
    rumpf));
}

function eingabe(aufgabe, gesperrt, beiAenderung) {
  if (aufgabe.format === "pdf") {
    return el("p", { class: "hinweis",
      text: "Diese Aufgabe wird handschriftlich im PDF gelöst (Xournal++ oder reMarkable). Hier nur die Sicherheit angeben." });
  }
  if (aufgabe.format === "tabelle") return tabellenEingabe(aufgabe, gesperrt, beiAenderung);
  const feld = el("textarea", {
    class: aufgabe.format === "code" ? "antwort antwort--code" : "antwort",
    rows: aufgabe.format === "code" ? 8 : 5,
    spellcheck: aufgabe.format === "code" ? "false" : "true",
    placeholder: gesperrt ? "" : (aufgabe.format === "code" ? "Code oder Befehle …" : "Antwort …"),
    disabled: gesperrt,
    "aria-label": `Antwort zu Aufgabe ${aufgabe.nummer}`,
    oninput: () => { wachsen(feld); beiAenderung(feld.value); },
  });
  feld.value = aufgabe.antwort || "";
  if (aufgabe.format === "code") {
    feld.addEventListener("keydown", (ereignis) => {
      if (ereignis.key !== "Tab" || ereignis.shiftKey) return;
      ereignis.preventDefault();
      feld.setRangeText("  ", feld.selectionStart, feld.selectionEnd, "end");
      beiAenderung(feld.value);
    });
  }
  requestAnimationFrame(() => wachsen(feld));
  return feld;
}

function wachsen(feld) {
  feld.style.height = "auto";
  feld.style.height = `${feld.scrollHeight + 2}px`;
}

function sicherheit(aufgabe, gesperrt, beiAenderung) {
  const anzeige = el("output", { class: "sicherheit__wert",
    text: aufgabe.user_wert == null ? "–" : `${aufgabe.user_wert} %` });
  const regler = el("input", {
    type: "range", min: "0", max: "100", step: "5", disabled: gesperrt,
    "aria-label": `Wie sicher bist du bei Aufgabe ${aufgabe.nummer}?`,
    oninput: () => { anzeige.textContent = `${regler.value} %`; regler.classList.remove("unberuehrt"); beiAenderung(Number(regler.value)); },
  });
  regler.value = aufgabe.user_wert ?? 50;
  if (aufgabe.user_wert == null) regler.classList.add("unberuehrt");
  return el("label", { class: "sicherheit" },
    el("span", { text: "Wie sicher bist du?" }), regler, anzeige);
}

/* ---------- Blatt-Ansicht ---------- */

function speicherer(blattId, aufgabe, anzeige) {
  let offen = {};
  let timer = null;
  let kette = Promise.resolve();
  const senden = () => {
    const daten = offen;
    offen = {};
    timer = null;
    kette = kette.then(async () => {
      try {
        await api("PUT", `/api/blaetter/${blattId}/aufgaben/${aufgabe.id}`, daten);
        anzeige.textContent = "gespeichert";
        anzeige.classList.remove("fehler");
      } catch (fehler) {
        anzeige.textContent = `nicht gespeichert: ${fehler.message}`;
        anzeige.classList.add("fehler");
      }
    });
    return kette;
  };
  return {
    merken(feld, wert) {
      offen[feld] = wert;
      aufgabe[feld] = wert;
      anzeige.textContent = "…";
      clearTimeout(timer);
      timer = setTimeout(senden, 700);
    },
    /** Sofort schicken, was noch aussteht (vor der Abgabe). */
    async fertig() {
      if (timer) { clearTimeout(timer); senden(); }
      await kette;
    },
  };
}

function korrekturBlock(aufgabe, bildBasis) {
  if (aufgabe.claude_wert == null) return null;
  return el("div", { class: "korrektur" },
    el("p", { class: "korrektur__zahlen" },
      el("b", { text: `${aufgabe.erreichte_punkte} / ${aufgabe.punkte} P.` }),
      el("span", { text: `Claude ${aufgabe.claude_wert} %` }),
      el("span", { text: `Ich ${aufgabe.user_wert} %` })),
    aufgabe.feedback ? el("div", {}, el("h4", { text: "Rückmeldung" }), Markdown.rendern(aufgabe.feedback, bildBasis)) : null,
    aufgabe.musterloesung ? el("div", {}, el("h4", { text: "Musterlösung" }), Markdown.rendern(aufgabe.musterloesung, bildBasis)) : null,
    aufgabe.quellverweis ? el("p", { class: "quelle", text: `Quelle: ${aufgabe.quellverweis}` }) : null);
}

function levelAenderungen(bewertungen) {
  if (!bewertungen.length) return null;
  return el("section", { class: "auswertung" },
    el("h3", { text: "Level nach diesem Blatt" }),
    el("ul", { class: "eintraege" }, ...bewertungen.map((b) => {
      const gestiegen = b.level_nachher > b.level_vorher;
      return el("li", { class: "eintrag" },
        el("i", { class: "pips", "data-level": String(b.level_nachher) }),
        el("span", { class: "eintrag__titel", text: b.titel }),
        el("span", { class: `stand${gestiegen ? " stand--hoch" : ""}`,
          text: gestiegen ? `Level ${b.level_vorher} → ${b.level_nachher}` : `bleibt Level ${b.level_nachher}` }),
        el("span", { class: "eintrag__meta" },
          el("span", { text: `Claude ${b.claude_wert} %` }), el("span", { text: `Ich ${b.user_wert} %` })));
    })));
}

async function zeigeBlatt(blattId) {
  const blatt = await api("GET", `/api/blaetter/${blattId}`);
  const bildBasis = `/api/blaetter/${blattId}/dateien`;
  const gesperrt = blatt.status !== "offen";
  const speicher = [];
  const meldung = el("p", { class: "fehler", role: "alert" });

  const aufgaben = blatt.aufgaben.map((aufgabe) => {
    const anzeige = el("span", { class: "speicherstand", "aria-live": "polite" });
    const s = speicherer(blattId, aufgabe, anzeige);
    speicher.push(s);
    return el("article", { class: "aufgabe" },
      el("header", { class: "aufgabe__kopf" },
        el("span", { class: "aufgabe__nummer", text: String(aufgabe.nummer) }),
        el("span", { class: "eintrag__meta" },
          el("span", { class: "marke", text: FORMAT_TEXT[aufgabe.format] }),
          el("span", { text: `${aufgabe.punkte} P.` }),
          anzeige)),
      Markdown.rendern(aufgabe.text, bildBasis),
      eingabe(aufgabe, gesperrt, (wert) => s.merken("antwort", wert)),
      sicherheit(aufgabe, gesperrt, (wert) => s.merken("user_wert", wert)),
      korrekturBlock(aufgabe, bildBasis));
  });

  const summe = blatt.aufgaben.reduce((n, a) => n + a.punkte, 0);
  const erreicht = blatt.aufgaben.reduce((n, a) => n + (a.erreichte_punkte || 0), 0);
  const kopf = el("header", { class: "blattkopf" },
    el("a", { class: "leise", href: "#/blaetter", text: "← alle Blätter" }),
    el("h2", { text: blatt.titel }),
    el("p", { class: "eintrag__meta" },
      el("span", { class: `marke marke--status-${blatt.status}`, text: STATUS_TEXT[blatt.status] }),
      el("span", { text: datum(blatt.erstellt_am) }),
      el("span", { text: blatt.status === "korrigiert" ? `${erreicht} / ${summe} P.` : `${summe} P.` })),
    blatt.dateien.includes("blatt.pdf")
      ? el("a", { class: "knopf knopf--hell", href: `${bildBasis}/blatt.pdf`, target: "_blank", rel: "noopener",
          text: "PDF-Teil öffnen" })
      : null);

  let fuss;
  if (blatt.status === "offen") {
    const knopf = el("button", { type: "button", text: "Blatt abgeben" });
    knopf.addEventListener("click", async () => {
      knopf.disabled = true;
      meldung.textContent = "";
      try {
        await Promise.all(speicher.map((s) => s.fertig()));
        await api("POST", `/api/blaetter/${blattId}/abgeben`);
        await zeigeBlatt(blattId);
        window.scrollTo({ top: 0 });
      } catch (fehler) {
        meldung.textContent = fehler.message;
        knopf.disabled = false;
      }
    });
    fuss = el("footer", { class: "blattfuss" },
      el("p", { class: "hinweis", text: "Nach der Abgabe ist das Blatt gesperrt. Antworten werden laufend gespeichert." }),
      knopf, meldung);
  } else if (blatt.status === "abgegeben") {
    fuss = el("footer", { class: "blattfuss" },
      el("p", { class: "hinweis", text: "Abgegeben. Die Korrektur startest du lokal mit „lernen korrigieren“." }));
  }

  const teile = [kopf, blatt.status === "korrigiert" ? levelAenderungen(blatt.bewertungen) : null, ...aufgaben, fuss];
  $("blatt-inhalt").replaceChildren(...teile.filter(Boolean));
}

/* ---------- Quell-Updates ---------- */

const UPDATE_TEXT = { laeuft: "läuft", fertig: "eingearbeitet", fehler: "fehlgeschlagen" };

async function zeigeUpdates() {
  const updates = await api("GET", "/api/updates");
  const liste = $("update-liste");
  if (!updates.length) {
    liste.replaceChildren(el("p", { class: "leer",
      text: "Bisher gab es kein Quell-Update. Beim Start von „lernen“ wird das Quell-Repo geprüft." }));
    return;
  }
  liste.replaceChildren(...updates.map((u) => el("details", { class: `update update--${u.status}` },
    el("summary", {},
      el("span", { class: "blattzeile__titel", text: u.zusammenfassung || "Update ohne Zusammenfassung" }),
      el("span", { class: "eintrag__meta" },
        el("span", { class: `marke marke--update-${u.status}`, text: UPDATE_TEXT[u.status] }),
        el("span", { text: datum(u.am) }),
        el("span", { text: `${(u.commit_von || "").slice(0, 7)} → ${u.commit_bis.slice(0, 7)}` }))),
    el("pre", { class: "protokoll", text: u.protokoll || "Kein Protokoll." }))));
}
