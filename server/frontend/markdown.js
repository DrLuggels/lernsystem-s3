"use strict";

/**
 * Kleiner Markdown-Renderer für Aufgabentexte und Musterlösungen.
 * Baut ausschließlich DOM-Knoten (kein innerHTML), Links werden nicht klickbar,
 * Bilder kommen nur aus den Dateien des Blatts.
 */
const Markdown = (() => {
  const INLINE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*)|(!\[[^\]]*\]\([^)\s]+\))/g;

  function inline(text, bildBasis) {
    const teile = [];
    let ende = 0;
    for (const treffer of text.matchAll(INLINE)) {
      if (treffer.index > ende) teile.push(text.slice(ende, treffer.index));
      const t = treffer[0];
      if (t.startsWith("`")) teile.push(el("code", { text: t.slice(1, -1) }));
      else if (t.startsWith("**")) teile.push(el("strong", {}, ...inline(t.slice(2, -2), bildBasis)));
      else if (t.startsWith("*")) teile.push(el("em", {}, ...inline(t.slice(1, -1), bildBasis)));
      else {
        const [, alt, ziel] = t.match(/^!\[([^\]]*)\]\(([^)\s]+)\)$/);
        const name = ziel.split("/").pop();
        teile.push(bildBasis && /^[\w.-]+$/.test(name)
          ? el("img", { src: `${bildBasis}/${name}`, alt, loading: "lazy" })
          : el("em", { text: `[Bild: ${alt || name}]` }));
      }
      ende = treffer.index + t.length;
    }
    if (ende < text.length) teile.push(text.slice(ende));
    return teile;
  }

  function tabelle(zeilen, bildBasis) {
    const zellen = (zeile) => zeile.trim().replace(/^\||\|$/g, "").split("|").map((z) => z.trim());
    const kopf = zellen(zeilen[0]);
    const rumpf = zeilen.slice(2).map(zellen);
    return el("div", { class: "md-tabelle" }, el("table", {},
      el("thead", {}, el("tr", {}, ...kopf.map((z) => el("th", {}, ...inline(z, bildBasis))))),
      el("tbody", {}, ...rumpf.map((zeile) =>
        el("tr", {}, ...zeile.map((z) => el("td", {}, ...inline(z, bildBasis))))))));
  }

  function rendern(quelle, bildBasis) {
    const wurzel = el("div", { class: "md" });
    const zeilen = String(quelle || "").replace(/\r/g, "").split("\n");
    let i = 0;
    while (i < zeilen.length) {
      const zeile = zeilen[i];
      if (!zeile.trim()) { i++; continue; }

      if (zeile.trim().startsWith("```")) {
        const code = [];
        i++;
        while (i < zeilen.length && !zeilen[i].trim().startsWith("```")) code.push(zeilen[i++]);
        i++;
        wurzel.append(el("pre", {}, el("code", { text: code.join("\n") })));
        continue;
      }

      const ueberschrift = zeile.match(/^(#{1,6})\s+(.*)$/);
      if (ueberschrift) {
        const stufe = Math.min(ueberschrift[1].length + 2, 6);
        wurzel.append(el(`h${stufe}`, {}, ...inline(ueberschrift[2], bildBasis)));
        i++;
        continue;
      }

      if (zeile.includes("|") && /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(zeilen[i + 1] || "")) {
        const block = [];
        while (i < zeilen.length && zeilen[i].includes("|")) block.push(zeilen[i++]);
        wurzel.append(tabelle(block, bildBasis));
        continue;
      }

      const punkt = /^\s*(?:[-*]|(\d+)[.)])\s+(.*)$/;
      if (punkt.test(zeile)) {
        const geordnet = Boolean(zeile.match(punkt)[1]);
        const liste = el(geordnet ? "ol" : "ul");
        while (i < zeilen.length && punkt.test(zeilen[i])) {
          let text = zeilen[i].match(punkt)[2];
          i++;
          // eingerückte Folgezeilen gehören zum Listenpunkt
          while (i < zeilen.length && /^\s{2,}\S/.test(zeilen[i]) && !punkt.test(zeilen[i])) text += " " + zeilen[i++].trim();
          liste.append(el("li", {}, ...inline(text, bildBasis)));
        }
        wurzel.append(liste);
        continue;
      }

      if (zeile.startsWith(">")) {
        const zitat = [];
        while (i < zeilen.length && zeilen[i].startsWith(">")) zitat.push(zeilen[i++].replace(/^>\s?/, ""));
        wurzel.append(el("blockquote", {}, ...inline(zitat.join(" "), bildBasis)));
        continue;
      }

      const absatz = [];
      while (i < zeilen.length && zeilen[i].trim() && !/^(#{1,6}\s|```|>|\s*(?:[-*]|\d+[.)])\s)/.test(zeilen[i])) {
        absatz.push(zeilen[i++]);
      }
      if (!absatz.length) absatz.push(zeilen[i++]);
      wurzel.append(el("p", {}, ...inline(absatz.join(" "), bildBasis)));
    }
    return wurzel;
  }

  return { rendern };
})();
