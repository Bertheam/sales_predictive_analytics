import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "/Users/bertham/Documents/projects/django/sales_predictive_analytics/outputs";
const PREVIEW = "/Users/bertham/Documents/projects/django/sales_predictive_analytics/.tmp_presentation/rendered";
const ASSETS = "/Users/bertham/Documents/projects/django/sales_predictive_analytics/.tmp_presentation/assets";

const C = {
  ink: "#0B211A",
  forest: "#092A20",
  deep: "#051B15",
  emerald: "#0A8565",
  mint: "#58D6AB",
  paleMint: "#DDF7EE",
  cream: "#F5F7F3",
  paper: "#FFFFFF",
  stone: "#6B7D76",
  line: "#D8E3DE",
  amber: "#F4B94F",
  softAmber: "#FFF1CE",
  red: "#D85D55",
  softRed: "#FCE7E5",
  violet: "#7C62D7",
  softViolet: "#EEE9FF",
};

const W = 1280;
const H = 720;
const M = 64;
const FONT = "Aptos";
const FONT_DISPLAY = "Aptos Display";

async function bytes(path) {
  const b = await fs.readFile(path);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength);
}

function addText(slide, text, x, y, w, h, size, color = C.ink, opts = {}) {
  const s = slide.shapes.add({
    geometry: "textbox",
    name: opts.name,
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  s.text = text;
  s.text.style = {
    fontFamily: opts.fontFamily || FONT,
    fontSize: size,
    color,
    bold: Boolean(opts.bold),
    italic: Boolean(opts.italic),
    alignment: opts.align || "left",
  };
  return s;
}

function addBox(slide, x, y, w, h, fill, opts = {}) {
  const config = {
    geometry: opts.geometry || "roundRect",
    name: opts.name,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: opts.line || fill, width: opts.lineWidth ?? 0 },
    shadow: opts.shadow,
  };
  if ((opts.geometry || "roundRect") !== "rect") {
    config.borderRadius = opts.radius || "rounded-xl";
  }
  return slide.shapes.add(config);
}

function addRule(slide, x, y, w, color = C.line, height = 1) {
  return addBox(slide, x, y, w, height, color, { geometry: "rect", radius: "none" });
}

function addEyebrow(slide, text, x = M, y = 52, color = C.emerald) {
  return addText(slide, text.toUpperCase(), x, y, 420, 24, 13, color, { bold: true });
}

function addTitle(slide, text, x = M, y = 88, w = 1000, color = C.ink, size = 40) {
  return addText(slide, text, x, y, w, 92, size, color, { bold: true, fontFamily: FONT_DISPLAY });
}

function addFooter(slide, n, dark = false) {
  const color = dark ? "#9EC4B7" : "#87958F";
  addText(slide, "NexaStock  •  Présentation du projet", M, 685, 350, 18, 11, color);
  addText(slide, String(n).padStart(2, "0"), 1180, 685, 36, 18, 11, color, { align: "right", bold: true });
}

function addNote(slide, lines = []) {
  if (!lines.length) return;
  slide.speakerNotes.textFrame.setText(`[Sources]\n${lines.map((l) => `- ${l}`).join("\n")}\n[/Sources]`);
}

function addStep(slide, n, label, sub, x, y, color = C.emerald) {
  addBox(slide, x, y, 54, 54, color, { radius: "rounded-full" });
  addText(slide, String(n), x, y + 11, 54, 28, 20, C.paper, { bold: true, align: "center" });
  addText(slide, label, x + 76, y - 2, 210, 30, 22, C.ink, { bold: true });
  addText(slide, sub, x + 76, y + 31, 235, 42, 15, C.stone);
}

function addMetric(slide, value, label, x, y, w, accent = C.emerald) {
  addRule(slide, x, y, w, C.line, 1);
  addText(slide, value, x, y + 22, w, 54, 42, accent, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, label, x, y + 78, w, 42, 15, C.stone);
}

const deck = Presentation.create({ slideSize: { width: W, height: H } });

// 1 — Cover
{
  const slide = deck.slides.add();
  slide.background.fill = C.deep;
  slide.images.add({
    blob: await bytes(`${ASSETS}/nexastock-warehouse-hero.png`),
    contentType: "image/png",
    alt: "Gestionnaire dans un dépôt de boissons moderne",
    fit: "cover",
    position: { left: 0, top: 0, width: W, height: H },
  });
  addBox(slide, 0, 0, 650, H, C.deep, { geometry: "rect", radius: "none" });
  addBox(slide, 68, 66, 46, 46, C.paper, { radius: "rounded-lg" });
  addText(slide, "N", 68, 75, 46, 26, 20, C.emerald, { bold: true, align: "center" });
  addText(slide, "NexaStock", 130, 72, 300, 34, 23, C.paper, { bold: true });
  addText(slide, "LE COPILOTE DE VOTRE DÉPÔT", 70, 177, 390, 24, 13, C.mint, { bold: true });
  addText(slide, "Piloter aujourd’hui.\nAnticiper demain.", 66, 220, 540, 150, 50, C.paper, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "Gestion des ventes, maîtrise du stock et prévisions réunies dans une expérience simple pour les dépôts de boissons.", 70, 397, 490, 92, 20, "#D7E6E0");
  addRule(slide, 70, 534, 420, "#2B5F4E", 1);
  addText(slide, "Présentation du projet  •  Août 2026", 70, 556, 390, 28, 14, "#B4CEC5", { bold: true });
  addFooter(slide, 1, true);
}

// 2 — Problem
{
  const slide = deck.slides.add();
  slide.background.fill = C.cream;
  addEyebrow(slide, "Le constat");
  addTitle(slide, "Dans un dépôt, une mauvaise décision se paie immédiatement.");
  addText(slide, "Le défi n’est pas de produire plus de chiffres. C’est de savoir quoi vendre, quoi commander et quand agir.", M, 194, 900, 58, 20, C.stone);

  const cols = [
    { x: 64, num: "01", title: "Rupture", body: "Une demande réelle existe, mais le produit n’est plus disponible.", color: C.red, fill: C.softRed },
    { x: 453, num: "02", title: "Surstock", body: "La trésorerie reste immobilisée dans des références qui tournent peu.", color: C.amber, fill: C.softAmber },
    { x: 842, num: "03", title: "Décision tardive", body: "Les ventes, le stock et les alertes restent dispersés ou difficiles à lire.", color: C.violet, fill: C.softViolet },
  ];
  for (const c of cols) {
    addBox(slide, c.x, 286, 342, 268, C.paper, { line: C.line, lineWidth: 1, shadow: "shadow-sm" });
    addBox(slide, c.x + 28, 316, 58, 34, c.fill, { radius: "rounded-full" });
    addText(slide, c.num, c.x + 28, 323, 58, 19, 13, c.color, { bold: true, align: "center" });
    addText(slide, c.title, c.x + 28, 384, 280, 42, 29, C.ink, { bold: true, fontFamily: FONT_DISPLAY });
    addText(slide, c.body, c.x + 28, 444, 278, 76, 17, C.stone);
  }
  addText(slide, "NexaStock transforme ces trois risques en actions concrètes.", M, 610, 900, 34, 20, C.emerald, { bold: true });
  addFooter(slide, 2);
  addNote(slide, ["README.md — description fonctionnelle du projet, consulté le 06/08/2026"]);
}

// 3 — Positioning
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  addEyebrow(slide, "Le positionnement");
  addTitle(slide, "Une seule plateforme, deux niveaux d’usage.");
  addText(slide, "Le propriétaire obtient une décision claire. L’analyste conserve la profondeur nécessaire pour contrôler les modèles.", M, 164, 1000, 54, 19, C.stone);

  addBox(slide, 64, 262, 530, 312, C.forest, { shadow: "shadow-md" });
  addText(slide, "PRODUIT MÉTIER", 96, 296, 230, 22, 13, C.mint, { bold: true });
  addText(slide, "Django", 96, 337, 300, 46, 35, C.paper, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "Une interface accessible pour vendre, suivre le stock, gérer l’équipe et décider du réapprovisionnement.", 96, 399, 430, 86, 18, "#D6E7E1");
  addText(slide, "Simple • Responsive • Orientée action", 96, 520, 380, 24, 14, C.mint, { bold: true });

  addBox(slide, 630, 262, 586, 312, C.cream, { line: C.line, lineWidth: 1 });
  addText(slide, "LABORATOIRE EXPERT", 664, 296, 250, 22, 13, C.emerald, { bold: true });
  addText(slide, "Streamlit", 664, 337, 300, 46, 35, C.ink, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "Un espace séparé pour comparer les modèles, lire les métriques, analyser les erreurs et surveiller la dérive.", 664, 399, 470, 86, 18, C.stone);
  addText(slide, "Technique • Traçable • Contrôlable", 664, 520, 380, 24, 14, C.emerald, { bold: true });
  addFooter(slide, 3);
  addNote(slide, ["archi.md — architecture produit Django + laboratoire Streamlit, consulté le 06/08/2026"]);
}

// 4 — Operations
{
  const slide = deck.slides.add();
  slide.background.fill = C.cream;
  addEyebrow(slide, "Le quotidien");
  addTitle(slide, "La donnée prédictive naît d’une gestion opérationnelle solide.");
  addText(slide, "Chaque action enregistrée améliore la visibilité du dépôt — et alimente une prévision plus pertinente.", M, 194, 1000, 52, 19, C.stone);

  const steps = [
    [1, "Vendre", "Transactions, clients et paiements"],
    [2, "Réception", "Arrivages fournisseurs contrôlés"],
    [3, "Mouvement", "Entrées, sorties, pertes et retours"],
    [4, "Suivre", "Stock théorique, seuils et historique"],
  ];
  const xs = [70, 370, 670, 970];
  for (let i = 0; i < steps.length; i++) {
    const [n, label, sub] = steps[i];
    addBox(slide, xs[i], 297, 214, 210, C.paper, { line: C.line, lineWidth: 1, shadow: "shadow-sm" });
    addBox(slide, xs[i] + 28, 327, 48, 48, i === 3 ? C.forest : C.emerald, { radius: "rounded-full" });
    addText(slide, String(n), xs[i] + 28, 337, 48, 26, 18, C.paper, { bold: true, align: "center" });
    addText(slide, label, xs[i] + 28, 402, 160, 32, 24, C.ink, { bold: true });
    addText(slide, sub, xs[i] + 28, 449, 158, 52, 15, C.stone);
    if (i < 3) addText(slide, "→", xs[i] + 232, 381, 40, 38, 27, C.emerald, { bold: true, align: "center" });
  }
  addBox(slide, 70, 557, 1114, 62, C.paleMint, { radius: "rounded-lg" });
  addText(slide, "Catalogue, clients, fournisseurs, ventes, stocks, mouvements et imports Excel réunis dans le même flux.", 96, 576, 1062, 28, 17, C.forest, { bold: true, align: "center" });
  addFooter(slide, 4);
  addNote(slide, ["README.md — fonctionnalités opérationnelles, consulté le 06/08/2026"]);
}

// 5 — Predictive engine
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  addEyebrow(slide, "Le moteur prédictif");
  addTitle(slide, "La prévision est une chaîne contrôlée, pas une boîte noire.");
  addText(slide, "NexaStock prépare les données, teste plusieurs approches et ne retient que le modèle le plus fiable pour chaque produit.", M, 194, 1030, 55, 19, C.stone);

  const items = [
    ["01", "Historique", "Ventes, stock, calendrier"],
    ["02", "Variables", "Retards, moyennes, saisonnalité"],
    ["03", "Tester", "Baselines + modèles ML"],
    ["04", "Champion", "Meilleur modèle par produit"],
    ["05", "J+1 → J+7", "Prévision itérative"],
    ["06", "Décision", "Stock et risque de rupture"],
  ];
  let x = 64;
  for (let i = 0; i < items.length; i++) {
    const [num, title, sub] = items[i];
    addBox(slide, x, 292, 174, 236, i === 3 ? C.forest : C.cream, { line: i === 3 ? C.forest : C.line, lineWidth: 1 });
    addText(slide, num, x + 22, 315, 52, 24, 13, i === 3 ? C.mint : C.emerald, { bold: true });
    addText(slide, title, x + 22, 369, 134, 54, 22, i === 3 ? C.paper : C.ink, { bold: true });
    addText(slide, sub, x + 22, 442, 132, 58, 14, i === 3 ? "#CFE4DC" : C.stone);
    if (i < items.length - 1) addText(slide, "›", x + 176, 382, 30, 38, 30, C.emerald, { bold: true, align: "center" });
    x += 190;
  }
  addText(slide, "Le niveau de détail reste dans le laboratoire ; l’application métier affiche l’action recommandée.", M, 586, 1060, 34, 18, C.emerald, { bold: true });
  addFooter(slide, 5);
  addNote(slide, ["README.md — chaîne prédictive J+1 à J+7, consulté le 06/08/2026"]);
}

// 6 — Backtesting evidence
{
  const slide = deck.slides.add();
  slide.background.fill = C.cream;
  addEyebrow(slide, "La discipline modèle");
  addTitle(slide, "Le modèle le plus complexe n’est pas toujours le meilleur.");
  addText(slide, "Avant toute prévision future, les candidats sont comparés sur une période passée qu’ils n’ont pas vue.", M, 194, 980, 48, 19, C.stone);

  addBox(slide, 64, 270, 760, 324, C.paper, { line: C.line, lineWidth: 1, shadow: "shadow-sm" });
  addText(slide, "Exemple de backtest — Cola 50 cl", 96, 299, 430, 32, 20, C.ink, { bold: true });
  addText(slide, "Plus la barre est courte, plus l’erreur est faible.", 96, 335, 430, 24, 14, C.stone);
  const max = 14;
  const rows = [
    ["J-7", 9.58, 13.40, C.stone],
    ["Moyenne mobile 7 j", 8.62, 10.83, C.emerald],
  ];
  for (let i = 0; i < rows.length; i++) {
    const [name, mae, rmse, color] = rows[i];
    const y = 392 + i * 88;
    addText(slide, name, 96, y, 180, 25, 15, C.ink, { bold: true });
    addBox(slide, 282, y + 2, (mae / max) * 355, 22, color, { geometry: "rect", radius: "none" });
    addText(slide, `MAE ${mae.toFixed(2).replace(".", ",")}`, 650, y - 1, 130, 25, 14, color, { bold: true, align: "right" });
    addBox(slide, 282, y + 34, (rmse / max) * 355, 13, color === C.emerald ? C.mint : "#B6C0BC", { geometry: "rect", radius: "none" });
    addText(slide, `RMSE ${rmse.toFixed(2).replace(".", ",")}`, 650, y + 27, 130, 25, 13, C.stone, { align: "right" });
  }

  addBox(slide, 862, 270, 354, 324, C.forest);
  addText(slide, "SÉLECTION AUTOMATIQUE", 894, 304, 290, 22, 12, C.mint, { bold: true });
  addText(slide, "Le champion est choisi par produit.", 894, 354, 280, 78, 29, C.paper, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "Baselines, régression linéaire, Random Forest et XGBoost sont évalués avec les mêmes règles.", 894, 456, 274, 86, 16, "#D1E3DD");
  addFooter(slide, 6);
  addNote(slide, ["Résultats internes de backtesting communiqués dans l’historique projet — Cola 50 cl, fenêtre de 60 jours"]);
}

// 7 — Decision output
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  addEyebrow(slide, "La valeur métier");
  addTitle(slide, "Une prévision utile se termine par une décision.");
  addText(slide, "L’utilisateur ne doit pas interpréter une métrique ML : il doit savoir combien commander et pourquoi.", M, 165, 1000, 52, 19, C.stone);

  addBox(slide, 64, 265, 700, 330, C.cream, { line: C.line, lineWidth: 1 });
  addText(slide, "COLA 50 CL  •  PROCHAINS 7 JOURS", 96, 295, 470, 22, 13, C.emerald, { bold: true });
  addText(slide, "Le stock actuel ne couvre pas le scénario prudent.", 96, 340, 590, 68, 28, C.ink, { bold: true, fontFamily: FONT_DISPLAY });
  addMetric(slide, "85", "cartons disponibles", 96, 448, 160, C.ink);
  addMetric(slide, "142", "besoin haut estimé", 286, 448, 170, C.emerald);
  addMetric(slide, "20", "stock de sécurité", 486, 448, 150, C.amber);

  addBox(slide, 800, 265, 416, 330, C.forest, { shadow: "shadow-md" });
  addText(slide, "ACTION RECOMMANDÉE", 834, 300, 310, 22, 13, C.mint, { bold: true });
  addText(slide, "+77", 832, 350, 320, 86, 67, C.paper, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "cartons à commander", 836, 430, 310, 34, 22, C.paper, { bold: true });
  addBox(slide, 834, 498, 174, 44, C.softAmber, { radius: "rounded-full" });
  addText(slide, "RISQUE ÉLEVÉ", 834, 510, 174, 22, 13, "#996000", { bold: true, align: "center" });
  addText(slide, "Le calcul combine le scénario haut et le stock de sécurité.", 834, 551, 320, 36, 12, "#CBE0D9");
  addFooter(slide, 7);
  addNote(slide, ["archi.md — exemple métier de recommandation de stock, consulté le 06/08/2026"]);
}

// 8 — Reliability
{
  const slide = deck.slides.add();
  slide.background.fill = C.cream;
  addEyebrow(slide, "La confiance");
  addTitle(slide, "La qualité prédictive est suivie après chaque échéance.");
  addText(slide, "Un modèle performant aujourd’hui peut dériver demain. NexaStock compare en continu le prévu au réel.", M, 194, 1040, 52, 19, C.stone);

  addBox(slide, 64, 270, 1120, 100, C.forest);
  addText(slide, "Prévision générée", 94, 307, 220, 28, 20, C.paper, { bold: true });
  addText(slide, "→", 326, 303, 44, 35, 25, C.mint, { bold: true, align: "center" });
  addText(slide, "Échéance atteinte", 386, 307, 220, 28, 20, C.paper, { bold: true });
  addText(slide, "→", 616, 303, 44, 35, 25, C.mint, { bold: true, align: "center" });
  addText(slide, "Réel disponible", 674, 307, 210, 28, 20, C.paper, { bold: true });
  addText(slide, "→", 886, 303, 44, 35, 25, C.mint, { bold: true, align: "center" });
  addText(slide, "Modèle réévalué", 944, 307, 210, 28, 20, C.paper, { bold: true });

  const items = [
    ["ACTIVE", "Prévision encore exploitable"],
    ["EXPIRÉE", "Échéance terminée"],
    ["ÉVALUÉE", "Erreur calculée et historisée"],
  ];
  const xs = [64, 442, 820];
  for (let i = 0; i < items.length; i++) {
    addBox(slide, xs[i], 412, 346, 150, C.paper, { line: C.line, lineWidth: 1 });
    addText(slide, items[i][0], xs[i] + 26, 440, 150, 24, 14, i === 0 ? C.emerald : i === 1 ? C.amber : C.violet, { bold: true });
    addText(slide, items[i][1], xs[i] + 26, 483, 270, 42, 18, C.ink, { bold: true });
  }
  addText(slide, "MAE • RMSE • MAPE • WAPE • biais • dérive temporelle", M, 605, 900, 28, 17, C.emerald, { bold: true });
  addFooter(slide, 8);
  addNote(slide, ["README.md — historique, évaluation et qualité prédictive, consulté le 06/08/2026"]);
}

// 9 — Multi-depot & security
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  addEyebrow(slide, "L’échelle et le contrôle");
  addTitle(slide, "Chaque dépôt reste isolé, chaque action reste traçable.");
  addText(slide, "L’architecture multi-entreprises permet de grandir sans mélanger les données, les équipes ni les responsabilités.", M, 194, 1050, 54, 19, C.stone);

  addBox(slide, 64, 282, 510, 298, C.forest);
  addText(slide, "MULTI-DÉPÔTS", 96, 315, 220, 22, 13, C.mint, { bold: true });
  addText(slide, "Un utilisateur autorisé change de dépôt sans changer d’application.", 96, 357, 420, 88, 27, C.paper, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "Les tableaux de bord, stocks, ventes et prévisions se recalculent dans le contexte actif.", 96, 477, 420, 70, 16, "#D2E4DE");

  addBox(slide, 612, 282, 604, 298, C.cream, { line: C.line, lineWidth: 1 });
  const security = [
    ["Rôles", "Propriétaire, administrateur, analyste, lecteur"],
    ["Audit", "Qui a fait quoi, quand et sur quel dépôt"],
    ["Suppression logique", "Historique préservé et actions réversibles"],
    ["RLS PostgreSQL", "Isolation renforcée au niveau des données"],
  ];
  for (let i = 0; i < security.length; i++) {
    const y = 307 + i * 62;
    addText(slide, String(i + 1).padStart(2, "0"), 642, y, 36, 22, 12, C.emerald, { bold: true });
    addText(slide, security[i][0], 690, y - 2, 180, 26, 18, C.ink, { bold: true });
    addText(slide, security[i][1], 854, y - 1, 322, 38, 14, C.stone);
    if (i < 3) addRule(slide, 642, y + 44, 530, C.line, 1);
  }
  addFooter(slide, 9);
  addNote(slide, ["docs/MULTI_TENANT_ARCHITECTURE.md — isolation, rôles et accès, consulté le 06/08/2026", "README.md — journal d’audit et suppression logique, consulté le 06/08/2026"]);
}

// 10 — UX
{
  const slide = deck.slides.add();
  slide.background.fill = C.cream;
  addEyebrow(slide, "L’expérience");
  addTitle(slide, "Premium ne veut pas dire compliqué.");
  addText(slide, "La partie web reste fluide et accessible ; le vocabulaire technique est réservé au laboratoire expert.", M, 165, 1000, 52, 19, C.stone);

  addBox(slide, 64, 258, 752, 356, C.paper, { line: C.line, lineWidth: 1, shadow: "shadow-md" });
  slide.images.add({
    blob: await bytes(`${ASSETS}/nexastock-login.png`),
    contentType: "image/png",
    alt: "Écran de connexion responsive NexaStock",
    fit: "cover",
    position: { left: 76, top: 270, width: 728, height: 332 },
    geometry: "roundRect",
    borderRadius: "rounded-lg",
  });

  addText(slide, "Une interface pensée pour l’action", 858, 276, 330, 66, 29, C.ink, { bold: true, fontFamily: FONT_DISPLAY });
  const bullets = [
    "Tailwind CSS et design responsive",
    "Navigation adaptée au mobile et à la tablette",
    "Toasts, loaders et confirmations explicites",
    "Filtres, pagination et tris cohérents",
    "Actions courtes, labels en français",
  ];
  for (let i = 0; i < bullets.length; i++) {
    addBox(slide, 858, 372 + i * 43, 11, 11, i === 0 ? C.emerald : C.mint, { radius: "rounded-full" });
    addText(slide, bullets[i], 882, 363 + i * 43, 310, 31, 15, C.stone, { bold: i < 2 });
  }
  addFooter(slide, 10);
  addNote(slide, ["Capture produit locale NexaStock — écran de connexion, 06/08/2026", "README.md — stack d’interface Django, consulté le 06/08/2026"]);
}

// 11 — Architecture
{
  const slide = deck.slides.add();
  slide.background.fill = C.paper;
  addEyebrow(slide, "L’architecture");
  addTitle(slide, "Une base robuste pour le web, le ML et les\ntraitements asynchrones.", M, 88, 1080, C.ink, 38);
  addText(slide, "Les composants sont séparés par responsabilité et partagent une seule source de vérité : PostgreSQL.", M, 194, 1030, 52, 19, C.stone);

  const nodes = [
    { x: 64, y: 290, w: 230, h: 116, fill: C.forest, title: "Django", sub: "Produit métier + API", dark: true },
    { x: 64, y: 448, w: 230, h: 116, fill: C.cream, title: "Streamlit", sub: "Laboratoire expert", dark: false },
    { x: 393, y: 290, w: 230, h: 116, fill: C.paleMint, title: "Services métier", sub: "Règles et orchestration", dark: false },
    { x: 393, y: 448, w: 230, h: 116, fill: C.softViolet, title: "Moteur ML", sub: "Features, modèles, qualité", dark: false },
    { x: 722, y: 290, w: 230, h: 116, fill: C.softAmber, title: "Celery + Redis", sub: "Prévisions et e-mails", dark: false },
    { x: 986, y: 369, w: 230, h: 116, fill: C.emerald, title: "PostgreSQL 17", sub: "Données + audit + RLS", dark: true },
  ];
  for (const n of nodes) {
    addBox(slide, n.x, n.y, n.w, n.h, n.fill, { line: n.dark ? n.fill : C.line, lineWidth: 1 });
    addText(slide, n.title, n.x + 24, n.y + 25, n.w - 48, 29, 21, n.dark ? C.paper : C.ink, { bold: true });
    addText(slide, n.sub, n.x + 24, n.y + 66, n.w - 48, 28, 14, n.dark ? "#CFE1DA" : C.stone);
  }
  addText(slide, "→", 318, 333, 50, 38, 26, C.emerald, { bold: true, align: "center" });
  addText(slide, "→", 318, 490, 50, 38, 26, C.emerald, { bold: true, align: "center" });
  addText(slide, "→", 648, 333, 50, 38, 26, C.emerald, { bold: true, align: "center" });
  addText(slide, "→", 648, 490, 50, 38, 26, C.emerald, { bold: true, align: "center" });
  addText(slide, "→", 951, 409, 34, 38, 26, C.emerald, { bold: true, align: "center" });
  addText(slide, "Docker Compose en local  •  Railway en production  •  migrations non destructives", M, 612, 930, 28, 16, C.emerald, { bold: true });
  addFooter(slide, 11);
  addNote(slide, ["README.md — architecture technique et déploiement, consulté le 06/08/2026"]);
}

// 12 — Maturity & roadmap
{
  const slide = deck.slides.add();
  slide.background.fill = C.cream;
  addEyebrow(slide, "L’état du projet");
  addTitle(slide, "Le cœur du produit est construit. La prochaine étape est l’industrialisation.");
  addText(slide, "NexaStock couvre déjà la chaîne complète, de la saisie métier à la recommandation de stock.", M, 194, 1000, 48, 19, C.stone);

  addBox(slide, 64, 263, 536, 340, C.forest);
  addText(slide, "DÉJÀ EN PLACE", 96, 296, 220, 22, 13, C.mint, { bold: true });
  const done = [
    "Gestion ventes, stocks et mouvements",
    "Prévisions J+1 à J+7 et backtesting",
    "Recommandations et risques de rupture",
    "Multi-dépôts, rôles et audit",
    "Docker, Celery, Redis et Railway",
    "Import Excel et e-mails transactionnels",
  ];
  for (let i = 0; i < done.length; i++) {
    addText(slide, "✓", 96, 340 + i * 40, 28, 28, 17, C.mint, { bold: true });
    addText(slide, done[i], 132, 338 + i * 40, 410, 30, 16, C.paper, { bold: i < 3 });
  }

  addText(slide, "PROCHAINS LEVIERS", 650, 285, 260, 22, 13, C.emerald, { bold: true });
  const road = [
    ["01", "Observabilité", "Logs, alertes techniques et suivi des tâches"],
    ["02", "Décision enrichie", "Simulations, couverture et explications simples"],
    ["03", "API & mobile", "DRF stabilisée puis application Flutter"],
    ["04", "Passage à l’échelle", "Onboarding, tarification et support multi-clients"],
  ];
  for (let i = 0; i < road.length; i++) {
    const y = 333 + i * 67;
    addText(slide, road[i][0], 650, y, 38, 24, 12, C.emerald, { bold: true });
    addText(slide, road[i][1], 704, y - 2, 180, 26, 18, C.ink, { bold: true });
    addText(slide, road[i][2], 884, y - 2, 300, 36, 14, C.stone);
    if (i < 3) addRule(slide, 650, y + 45, 534, C.line, 1);
  }
  addFooter(slide, 12);
  addNote(slide, ["README.md — périmètre fonctionnel et technique, consulté le 06/08/2026", "archi.md — trajectoire API et mobile, consulté le 06/08/2026"]);
}

// 13 — Close
{
  const slide = deck.slides.add();
  slide.background.fill = C.deep;
  slide.images.add({
    blob: await bytes(`${ASSETS}/nexastock-warehouse-hero.png`),
    contentType: "image/png",
    alt: "Dépôt de boissons moderne au lever du jour",
    fit: "cover",
    position: { left: 685, top: 0, width: 595, height: H },
  });
  addBox(slide, 0, 0, 760, H, C.deep, { geometry: "rect", radius: "none" });
  addText(slide, "NEXASTOCK", 70, 86, 280, 24, 13, C.mint, { bold: true });
  addText(slide, "Voir venir.\nDécider simplement.", 68, 166, 590, 135, 50, C.paper, { bold: true, fontFamily: FONT_DISPLAY });
  addText(slide, "NexaStock transforme les données du dépôt en décisions quotidiennes : vendre, prévoir, commander et grandir avec confiance.", 70, 340, 540, 94, 20, "#D1E4DD");
  addBox(slide, 70, 499, 300, 56, C.emerald, { radius: "rounded-full" });
  addText(slide, "PRÊT POUR LA DÉMONSTRATION", 70, 516, 300, 24, 13, C.paper, { bold: true, align: "center" });
  addFooter(slide, 13, true);
}

await fs.mkdir(OUT, { recursive: true });
await fs.mkdir(PREVIEW, { recursive: true });

for (const [index, slide] of deck.slides.items.entries()) {
  const stem = `slide-${String(index + 1).padStart(2, "0")}`;
  const png = await deck.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(`${PREVIEW}/${stem}.png`, new Uint8Array(await png.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(`${PREVIEW}/${stem}.layout.json`, await layout.text());
}

const montage = await deck.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(`${PREVIEW}/montage.webp`, new Uint8Array(await montage.arrayBuffer()));

const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(`${OUT}/NexaStock_presentation_projet.pptx`);

console.log(`Deck créé : ${OUT}/NexaStock_presentation_projet.pptx`);
